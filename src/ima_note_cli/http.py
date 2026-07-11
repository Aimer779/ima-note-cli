from __future__ import annotations

import json
import http.client
import time
from typing import Any, Callable
from urllib import error, request

from . import __version__
from .config import Credentials
from .errors import ApiBusinessError, ApiError, ApiProtocolError, ApiTransportError
from .security import redact_sensitive_text, validate_ima_base_url, validate_relative_endpoint


MESSAGE_KEYS = ("message", "msg", "errmsg", "error_message", "error_msg")
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_ERROR_BYTES = 16 * 1024
RETRYABLE_STATUS = frozenset({408, 429, 500, 502, 503, 504})


class ImaApiClient:
    def __init__(
        self,
        credentials: Credentials,
        *,
        base_url: str,
        timeout: int = 30,
        opener: Callable[..., Any] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._credentials = credentials
        self._base_url = validate_ima_base_url(base_url)
        self._timeout = timeout
        self._opener = opener
        self._sleep = sleep

    def post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.post_write_json(endpoint, payload)

    def post_read_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(endpoint, payload, max_attempts=3)

    def post_write_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._post_json(endpoint, payload, max_attempts=1)

    def _post_json(self, endpoint: str, payload: dict[str, Any], *, max_attempts: int) -> dict[str, Any]:
        endpoint = validate_relative_endpoint(endpoint)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self._base_url}/{endpoint}", data=body, method="POST",
            headers={
                "Content-Type": "application/json", "Accept": "application/json",
                "User-Agent": f"ima-note-cli/{__version__}",
                "ima-openapi-clientid": self._credentials.client_id,
                "ima-openapi-apikey": self._credentials.api_key,
            },
        )
        for attempt in range(1, max_attempts + 1):
            try:
                with (self._opener or request.urlopen)(req, timeout=self._timeout) as response:
                    raw_body = self._read_limited(response, MAX_JSON_BYTES, endpoint)
                return self._parse(raw_body, endpoint)
            except error.HTTPError as exc:
                retryable = exc.code in RETRYABLE_STATUS
                if retryable and attempt < max_attempts:
                    exc.close()
                    self._sleep(self._retry_delay(exc, attempt))
                    continue
                message = self._read_error_message(exc)
                exc.close()
                raise ApiTransportError(
                    f"IMA API request failed with HTTP {exc.code}." + (f" {message}" if message else ""),
                    endpoint=endpoint, retryable=retryable,
                    details={"http_status": exc.code, "attempts": attempt},
                ) from exc
            except TimeoutError as exc:
                if attempt < max_attempts:
                    self._sleep(0.25 * attempt)
                    continue
                raise ApiTransportError(
                    "The request to the IMA API timed out.", endpoint=endpoint,
                    details={"attempts": attempt},
                ) from exc
            except error.URLError as exc:
                if attempt < max_attempts:
                    self._sleep(0.25 * attempt)
                    continue
                raise ApiTransportError(
                    "Unable to reach the IMA API.", endpoint=endpoint,
                    details={"attempts": attempt},
                ) from exc
            except (OSError, http.client.HTTPException) as exc:
                if attempt < max_attempts:
                    self._sleep(0.25 * attempt)
                    continue
                raise ApiTransportError(
                    "The IMA API response was interrupted.", endpoint=endpoint,
                    details={"attempts": attempt},
                ) from exc
        raise AssertionError("unreachable")

    @staticmethod
    def _read_limited(response: Any, limit: int, endpoint: str) -> bytes:
        header = response.headers.get("Content-Length") if getattr(response, "headers", None) else None
        if header:
            try:
                if int(header) > limit:
                    raise ApiProtocolError(
                        f"IMA API endpoint {endpoint} returned a response larger than {limit} bytes.",
                        endpoint=endpoint, details={"max_bytes": limit, "field": "response"},
                    )
            except ValueError:
                pass
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ApiProtocolError(
                f"IMA API endpoint {endpoint} returned a response larger than {limit} bytes.",
                endpoint=endpoint, details={"max_bytes": limit, "field": "response"},
            )
        return body

    def _parse(self, raw_body: bytes, endpoint: str) -> dict[str, Any]:
        try:
            text = raw_body.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ApiProtocolError(f"IMA API endpoint {endpoint} returned invalid UTF-8 JSON.", endpoint=endpoint, details={"field": "response"}) from exc
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ApiProtocolError(f"IMA API endpoint {endpoint} returned invalid JSON.", endpoint=endpoint, details={"field": "response"}) from exc
        if not isinstance(parsed, dict):
            raise ApiProtocolError(f"IMA API endpoint {endpoint} returned a non-object response.", endpoint=endpoint, details={"field": "response"})
        if "code" not in parsed:
            raise ApiProtocolError(f"IMA API endpoint {endpoint} response is missing code.", endpoint=endpoint, details={"field": "code"})
        code = parsed["code"]
        success = not isinstance(code, bool) and ((isinstance(code, int) and code == 0) or code == "0")
        if not success:
            message = next((parsed[key] for key in MESSAGE_KEYS if isinstance(parsed.get(key), str)), "IMA API rejected the request.")
            raise ApiBusinessError(self._redact(message), endpoint=endpoint)
        if "data" not in parsed or not isinstance(parsed["data"], dict):
            raise ApiProtocolError(f"IMA API endpoint {endpoint} returned a non-object data payload.", endpoint=endpoint, details={"field": "data"})
        return parsed["data"]

    def _read_error_message(self, exc: error.HTTPError) -> str:
        try:
            raw = exc.read(MAX_ERROR_BYTES)
            parsed = json.loads(raw.decode("utf-8"))
            if isinstance(parsed, dict):
                value = next((parsed[key] for key in MESSAGE_KEYS if isinstance(parsed.get(key), str)), "")
                return self._redact(value)
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
        return ""

    def _redact(self, value: object) -> str:
        text = redact_sensitive_text(value)
        for secret in (self._credentials.client_id, self._credentials.api_key):
            if secret:
                text = text.replace(secret, "<redacted>")
        return text

    @staticmethod
    def _retry_delay(exc: error.HTTPError, attempt: int) -> float:
        value = exc.headers.get("Retry-After") if exc.headers else None
        if value and value.isdecimal():
            return min(int(value), 2)
        return 0.25 * attempt


def maybe_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    return value if isinstance(value, int) else None


__all__ = ["ApiError", "ApiBusinessError", "ApiProtocolError", "ApiTransportError", "ImaApiClient"]
