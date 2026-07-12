from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import http.client
from pathlib import Path
import socket
import ssl
from typing import BinaryIO, Callable, Mapping
from urllib.parse import urljoin

from .errors import InputError, LocalIOError, RemoteFetchError
from .security import PublicUrlTarget, safe_url, validate_public_url
from .validation import validate_timeout

CHUNK_SIZE = 64 * 1024
MAX_REDIRECTS = 5
MAX_ERROR_BODY = 16 * 1024
_REDIRECTS = {301, 302, 303, 307, 308}


@dataclass(frozen=True)
class RemoteResponseInfo:
    original_url: str
    final_url: str = field(repr=False)
    status: int
    headers: Mapping[str, str] = field(repr=False)
    method: str

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";", 1)[0].strip().lower()


@dataclass(frozen=True)
class DownloadResult:
    path: Path = field(repr=False)
    safe_url: str
    size: int
    sha256: str
    headers: Mapping[str, str] = field(repr=False)


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, port: int, timeout: float, context: ssl.SSLContext) -> None:
        super().__init__(host, port, timeout=timeout, context=context)
        self._address = address

    def connect(self) -> None:
        raw = socket.create_connection((self._address, self.port), self.timeout, self.source_address)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


ConnectionFactory = Callable[[PublicUrlTarget, str, float], http.client.HTTPConnection]


def _connection(target: PublicUrlTarget, address: str, timeout: float) -> http.client.HTTPConnection:
    if target.scheme == "https":
        return _PinnedHTTPSConnection(target.host, address, target.port, timeout, ssl.create_default_context())
    return http.client.HTTPConnection(address, target.port, timeout=timeout)


class RemoteHttpClient:
    def __init__(self, *, resolver: Callable[..., object] | None = None, connection_factory: ConnectionFactory = _connection) -> None:
        self._resolver = resolver
        self._connection_factory = connection_factory

    def _target(self, url: str) -> PublicUrlTarget:
        return validate_public_url(url) if self._resolver is None else validate_public_url(url, resolver=self._resolver)  # type: ignore[arg-type]

    def probe(self, url: str, *, timeout: int = 300) -> RemoteResponseInfo:
        validate_timeout(timeout, "--download-timeout")
        head = self._request(url, "HEAD", timeout=timeout, allowed_statuses={405, 501})
        if head.status in {405, 501} or not (head.content_type or head.headers.get("content-disposition")):
            return self._request(url, "GET", timeout=timeout, headers={"Range": "bytes=0-0"})
        return head

    def download(self, url: str, destination: Path, *, max_bytes: int, timeout: int = 300) -> DownloadResult:
        validate_timeout(timeout, "--download-timeout")
        if max_bytes <= 0:
            raise InputError("Download size limit must be positive.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        last_error: RemoteFetchError | None = None
        for attempt in range(3):
            try:
                return self._download_once(url, destination, max_bytes=max_bytes, timeout=timeout)
            except RemoteFetchError as exc:
                last_error = exc
                if not exc.retryable or attempt == 2:
                    raise
        raise last_error or AssertionError("unreachable")

    def _download_once(self, url: str, destination: Path, *, max_bytes: int, timeout: int) -> DownloadResult:
        part = destination.with_name(destination.name + ".part")
        part.unlink(missing_ok=True)
        try:
            response, info, connection = self._open(url, "GET", timeout, {})
            try:
                length = _content_length(info.headers)
                if length is not None and length > max_bytes:
                    raise InputError("Remote file exceeds the allowed size.", code="remote_file_too_large", details={"max_bytes": max_bytes})
                digest = sha256()
                total = 0
                try:
                    output = part.open("xb")
                except OSError as exc:
                    raise LocalIOError("Could not create the temporary download file.", code="download_write_failed") from exc
                with output:
                    while True:
                        try:
                            chunk = response.read(CHUNK_SIZE)
                        except (OSError, http.client.HTTPException) as exc:
                            raise RemoteFetchError("Remote response body was interrupted.", retryable=True) from exc
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            raise InputError("Remote file exceeds the allowed size.", code="remote_file_too_large", details={"max_bytes": max_bytes})
                        try:
                            output.write(chunk)
                        except OSError as exc:
                            raise LocalIOError("Could not write the temporary download file.", code="download_write_failed") from exc
                        digest.update(chunk)
                if length is not None and total != length:
                    raise RemoteFetchError("Remote response length did not match Content-Length.", code="remote_length_mismatch", retryable=True)
                try:
                    part.replace(destination)
                except OSError as exc:
                    raise LocalIOError("Could not finalize the temporary download file.", code="download_write_failed") from exc
                return DownloadResult(destination, safe_url(info.final_url), total, digest.hexdigest(), info.headers)
            finally:
                response.close()
                connection.close()
        except (InputError, LocalIOError, RemoteFetchError):
            raise
        except http.client.HTTPException as exc:
            raise RemoteFetchError("Remote file download failed.", retryable=True) from exc
        finally:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass

    def _request(self, url: str, method: str, *, timeout: int, headers: Mapping[str, str] | None = None, allowed_statuses: set[int] | None = None) -> RemoteResponseInfo:
        response, info, connection = self._open(url, method, timeout, headers or {}, allowed_statuses=allowed_statuses)
        response.close()
        connection.close()
        return info

    def _open(self, url: str, method: str, timeout: int, extra_headers: Mapping[str, str], *, allowed_statuses: set[int] | None = None):
        current = url
        for redirect_count in range(MAX_REDIRECTS + 1):
            target = self._target(current)
            headers = {
                "Host": target.host,
                "User-Agent": "ima-note-cli/0.1",
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                **extra_headers,
            }
            connection = self._connection_factory(target, target.addresses[0], float(timeout))
            try:
                connection.request(method, target.path_and_query, headers=headers)
                response = connection.getresponse()
            except (OSError, http.client.HTTPException) as exc:
                connection.close()
                raise RemoteFetchError("Remote URL request failed.", retryable=True) from exc
            normalized_headers = {name.lower(): value for name, value in response.getheaders()}
            if response.status in _REDIRECTS:
                location = normalized_headers.get("location")
                response.close()
                connection.close()
                if not location:
                    raise RemoteFetchError("Remote redirect omitted Location.", code="invalid_remote_redirect")
                if redirect_count == MAX_REDIRECTS:
                    raise RemoteFetchError("Remote URL exceeded the redirect limit.", code="remote_redirect_limit")
                current = urljoin(target.url, location)
                continue
            if (response.status < 200 or response.status >= 300) and response.status not in (allowed_statuses or set()):
                response.read(MAX_ERROR_BODY)
                status = response.status
                response.close()
                connection.close()
                raise RemoteFetchError(f"Remote URL returned HTTP {status}.", details={"http_status": status})
            info = RemoteResponseInfo(safe_url(url), target.url, response.status, normalized_headers, method)
            return response, info, connection
        raise AssertionError("unreachable")


def _content_length(headers: Mapping[str, str]) -> int | None:
    value = headers.get("content-length")
    if value is None:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise RemoteFetchError("Remote Content-Length is invalid.", code="invalid_content_length") from exc
    if parsed < 0:
        raise RemoteFetchError("Remote Content-Length is invalid.", code="invalid_content_length")
    return parsed
