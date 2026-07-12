from __future__ import annotations

from dataclasses import dataclass
import http.client
from pathlib import Path
from time import time
from typing import BinaryIO, Callable
from urllib.parse import quote, urlsplit

from .errors import KnowledgeUploadError
from .knowledge_api import CosCredential
from .security import build_and_validate_cos_origin, validate_cos_credential_times, validate_cos_key
from .validation import validate_timeout

CHUNK_SIZE = 64 * 1024
MAX_ERROR_BODY = 16 * 1024


@dataclass(frozen=True)
class CosUploadTarget:
    origin: str
    host: str
    pathname: str


def build_cos_target(credential: CosCredential, *, now: int | None = None) -> CosUploadTarget:
    validate_cos_credential_times(credential.start_time, credential.expired_time, now=now)
    key = validate_cos_key(credential.cos_key)
    origin = build_and_validate_cos_origin(credential.bucket_name, credential.region)
    host = urlsplit(origin).hostname or ""
    pathname = "/" + quote(key, safe="/-_.!~*'()")
    return CosUploadTarget(origin, host, pathname)


class CosHttpClient:
    def __init__(self, connection_factory: Callable[[str, int], http.client.HTTPConnection] | None = None) -> None:
        self._factory = connection_factory or (lambda host, timeout: http.client.HTTPSConnection(host, 443, timeout=timeout))

    def put(
        self, stream: BinaryIO, *, size: int, content_type: str, credential: CosCredential,
        authorization: str, timeout: int = 300, target: CosUploadTarget | None = None,
    ) -> None:
        validate_timeout(timeout, "--upload-timeout")
        validate_cos_credential_times(
            credential.start_time, credential.expired_time, minimum_remaining=timeout + 60
        )
        upload_target = target or build_cos_target(credential)
        connection = self._factory(upload_target.host, timeout)
        try:
            connection.putrequest("PUT", upload_target.pathname, skip_host=True, skip_accept_encoding=True)
            headers = {
                "Host": upload_target.host,
                "Content-Type": content_type,
                "Content-Length": str(size),
                "Authorization": authorization,
                "x-cos-security-token": credential.token,
            }
            for name, value in headers.items():
                connection.putheader(name, value)
            connection.endheaders()
            sent = 0
            while sent < size:
                chunk = stream.read(min(CHUNK_SIZE, size - sent))
                if not chunk:
                    raise KnowledgeUploadError("Local file ended before the declared upload size.", code="file_changed")
                connection.send(chunk)
                sent += len(chunk)
            if stream.read(1):
                raise KnowledgeUploadError("Local file grew during upload.", code="file_changed")
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                response.read(MAX_ERROR_BODY)
                raise KnowledgeUploadError(
                    f"COS upload failed with HTTP {response.status}.", details={"http_status": response.status}
                )
            response.read(MAX_ERROR_BODY)
        except KnowledgeUploadError:
            raise
        except (OSError, http.client.HTTPException) as exc:
            raise KnowledgeUploadError("COS upload could not reach the target host.", retryable=True) from exc
        finally:
            connection.close()
