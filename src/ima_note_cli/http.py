from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from .config import Credentials


SUCCESS_CODE_VALUES = {0, "0", None}
CODE_KEYS = ("code", "retcode", "errcode", "error_code")
MESSAGE_KEYS = ("message", "msg", "errmsg", "error_message", "error_msg")
DATA_KEYS = ("data", "result")


class ApiError(RuntimeError):
    """Raised when the remote API returns an error."""


class ImaApiClient:
    def __init__(self, credentials: Credentials, *, base_url: str, timeout: int = 30) -> None:
        self._credentials = credentials
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def post_json(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        url = f"{self._base_url}/{endpoint}"
        req = request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "ima-openapi-clientid": self._credentials.client_id,
                "ima-openapi-apikey": self._credentials.api_key,
            },
        )

        try:
            with request.urlopen(req, timeout=self._timeout) as response:
                raw_text = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = self._read_error_body(exc)
            raise ApiError(f"HTTP {exc.code} from IMA API: {detail}") from exc
        except error.URLError as exc:
            reason = exc.reason if getattr(exc, "reason", None) else "request failed"
            raise ApiError(f"Unable to reach the IMA API: {reason}") from exc
        except TimeoutError as exc:
            raise ApiError("The request to the IMA API timed out.") from exc

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ApiError("IMA API returned invalid JSON.") from exc

        if not isinstance(parsed, dict):
            raise ApiError("IMA API returned an unexpected response shape.")

        return self._unwrap_payload(parsed)

    def _unwrap_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        code = self._first_value(payload, CODE_KEYS)
        if code not in SUCCESS_CODE_VALUES:
            message = self._first_value(payload, MESSAGE_KEYS) or "unknown API error"
            raise ApiError(f"IMA API error {code}: {message}")

        data = self._first_value(payload, DATA_KEYS)
        if data is None:
            return payload
        if not isinstance(data, dict):
            raise ApiError("IMA API returned a non-object data payload.")
        return data

    @staticmethod
    def _first_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if key in payload:
                return payload[key]
        return None

    @staticmethod
    def _read_error_body(exc: error.HTTPError) -> str:
        try:
            body = exc.read().decode("utf-8").strip()
        except Exception:
            body = ""
        return body or exc.reason


def maybe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
