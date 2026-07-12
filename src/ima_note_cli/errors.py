from __future__ import annotations

from collections.abc import Mapping
from enum import IntEnum
import re
from typing import Any


class ExitCode(IntEnum):
    INPUT = 2
    CONFIG = 3
    TRANSPORT = 4
    BUSINESS = 5
    PROTOCOL = 6
    LOCAL_IO = 7
    UPLOAD = 8
    PARTIAL = 9
    INTERNAL = 70
    INTERRUPTED = 130


_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]+")
_SPACE_RE = re.compile(r"\s+")
_DETAIL_KEYS = frozenset({"attempts", "http_status", "limit", "field", "max_bytes"})


def safe_message(value: object, *, fallback: str = "The operation failed.") -> str:
    text = _SPACE_RE.sub(" ", _CONTROL_RE.sub(" ", str(value))).strip()
    return (text or fallback)[:512]


class ImaCliError(Exception):
    default_code = "ima_cli_error"
    default_exit_code = ExitCode.INTERNAL
    default_retryable = False

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        exit_code: int | None = None,
        retryable: bool | None = None,
        endpoint: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.code = code or self.default_code
        self.message = safe_message(message)
        self.exit_code = int(exit_code if exit_code is not None else self.default_exit_code)
        self.retryable = self.default_retryable if retryable is None else bool(retryable)
        self.endpoint = safe_message(endpoint, fallback="") if endpoint else None
        self.details = {key: value for key, value in (details or {}).items() if key in _DETAIL_KEYS}
        super().__init__(self.message)

    def to_error_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "exit_code": self.exit_code,
            "retryable": self.retryable,
        }
        if self.endpoint:
            payload["endpoint"] = self.endpoint
        if self.details:
            payload["details"] = dict(self.details)
        return payload


class InputError(ImaCliError, ValueError):
    default_code = "invalid_input"
    default_exit_code = ExitCode.INPUT


class ConfigError(ImaCliError):
    default_code = "configuration_error"
    default_exit_code = ExitCode.CONFIG


class ApiError(ImaCliError):
    """Compatibility error: direct construction means an IMA business failure."""

    default_code = "api_error"
    default_exit_code = ExitCode.BUSINESS


class ApiTransportError(ApiError):
    default_code = "api_transport_error"
    default_exit_code = ExitCode.TRANSPORT
    default_retryable = True


class ApiBusinessError(ApiError):
    default_code = "api_business_error"
    default_exit_code = ExitCode.BUSINESS


class ApiProtocolError(ApiError):
    default_code = "api_protocol_error"
    default_exit_code = ExitCode.PROTOCOL


class MediaUnavailableError(ImaCliError):
    default_code = "media_unavailable"
    default_exit_code = ExitCode.LOCAL_IO


class LocalIOError(ImaCliError):
    default_code = "local_io_error"
    default_exit_code = ExitCode.LOCAL_IO


class KnowledgeUploadError(ImaCliError):
    default_code = "knowledge_upload_error"
    default_exit_code = ExitCode.UPLOAD


class RemoteFetchError(ImaCliError):
    default_code = "remote_fetch_error"
    default_exit_code = ExitCode.TRANSPORT
