from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
import http.client
from typing import Any, BinaryIO, Callable
from urllib import error, request

from .errors import InputError, LocalIOError, MediaUnavailableError
from .knowledge_api import MediaAccessInfo
from .security import safe_url_host, validate_media_source_url


MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_EXPORT_BYTES = 200 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
TEXT_TYPES = {"application/json", "application/xml", "application/xhtml+xml"}


@dataclass(frozen=True)
class SourceReadResult:
    content: str
    content_type: str
    bytes_count: int


@dataclass(frozen=True)
class SourceStreamResult:
    content_type: str
    bytes_count: int


class _SafeRedirectHandler(request.HTTPRedirectHandler):
    def redirect_request(self, req: request.Request, fp: Any, code: int, msg: str, headers: Message, newurl: str) -> request.Request | None:
        try:
            validate_media_source_url(newurl)
        except InputError as exc:
            raise MediaUnavailableError("A media redirect left the trusted HTTPS boundary.", code="unsafe_media_redirect") from exc
        if safe_url_host(req.full_url) != safe_url_host(newurl) and req.headers:
            raise MediaUnavailableError("A media redirect crossed the trusted origin.", code="unsafe_media_redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SourceHttpClient:
    def __init__(self, *, timeout: int = 30, opener: Callable[..., Any] | None = None) -> None:
        self._timeout = timeout
        self._opener = opener or request.build_opener(_SafeRedirectHandler()).open

    def read_text(self, access: MediaAccessInfo) -> SourceReadResult:
        try:
            with self._open(access) as response:
                content_type, charset = self._content_type(response)
                if not self._is_text(content_type):
                    raise MediaUnavailableError("This media is binary; use `ima kb export`.", code="media_binary_requires_export")
                raw = self._read_limited(response, MAX_TEXT_BYTES)
        except (OSError, http.client.HTTPException) as exc:
            raise MediaUnavailableError("The media source response was interrupted.", code="media_transport_error", retryable=True) from exc
        try:
            return SourceReadResult(raw.decode(charset or "utf-8", errors="strict"), content_type, len(raw))
        except (LookupError, UnicodeDecodeError) as exc:
            raise LocalIOError("The media text encoding is invalid.", code="media_text_encoding_error") from exc

    def stream_to(self, access: MediaAccessInfo, destination: BinaryIO) -> SourceStreamResult:
        try:
            with self._open(access) as response:
                content_type, _ = self._content_type(response)
                expected = self._content_length(response)
                if expected is not None and expected > MAX_EXPORT_BYTES:
                    raise LocalIOError("The media exceeds the 200 MiB export limit.", code="media_too_large", details={"max_bytes": MAX_EXPORT_BYTES})
                total = 0
                while True:
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_EXPORT_BYTES:
                        raise LocalIOError("The media exceeds the 200 MiB export limit.", code="media_too_large", details={"max_bytes": MAX_EXPORT_BYTES})
                    try:
                        destination.write(chunk)
                    except OSError as exc:
                        raise LocalIOError("The media export could not be written.", code="media_export_failed") from exc
                if expected is not None and total != expected:
                    raise LocalIOError("The media response length did not match Content-Length.", code="media_length_mismatch")
        except (OSError, http.client.HTTPException) as exc:
            raise LocalIOError("The media export response was interrupted.", code="media_transport_error", retryable=True) from exc
        return SourceStreamResult(content_type, total)

    def _open(self, access: MediaAccessInfo) -> Any:
        validate_media_source_url(access.url)
        req = request.Request(access.url, method="GET", headers=dict(access.headers))
        try:
            return self._opener(req, timeout=self._timeout)
        except MediaUnavailableError:
            raise
        except error.HTTPError as exc:
            raise MediaUnavailableError("The media source returned an HTTP error.", code="media_http_error", details={"http_status": exc.code}) from exc
        except (error.URLError, TimeoutError) as exc:
            raise MediaUnavailableError("The media source could not be reached.", code="media_transport_error", retryable=True) from exc

    @staticmethod
    def _content_type(response: Any) -> tuple[str, str | None]:
        headers = response.headers
        if not headers.get("Content-Type"):
            return "application/octet-stream", None
        content_type = (headers.get_content_type() if hasattr(headers, "get_content_type") else "") or "application/octet-stream"
        charset = headers.get_content_charset() if hasattr(headers, "get_content_charset") else None
        return content_type.lower(), charset

    @staticmethod
    def _content_length(response: Any) -> int | None:
        value = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
        if value is None:
            return None
        try:
            length = int(value)
        except ValueError:
            return None
        return length if length >= 0 else None

    @classmethod
    def _read_limited(cls, response: Any, limit: int) -> bytes:
        expected = cls._content_length(response)
        if expected is not None and expected > limit:
            raise LocalIOError("The media text exceeds the 4 MiB read limit; use export.", code="media_too_large", details={"max_bytes": limit})
        raw = response.read(limit + 1)
        if len(raw) > limit:
            raise LocalIOError("The media text exceeds the 4 MiB read limit; use export.", code="media_too_large", details={"max_bytes": limit})
        if expected is not None and len(raw) != expected:
            raise LocalIOError("The media response length did not match Content-Length.", code="media_length_mismatch")
        return raw

    @staticmethod
    def _is_text(content_type: str) -> bool:
        return content_type.startswith("text/") or content_type in TEXT_TYPES or content_type.endswith("+json") or content_type.endswith("+xml")
