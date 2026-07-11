from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .errors import ApiProtocolError
from .security import sanitize_header_map


_MISSING = object()


def _failure(endpoint: str, path: str, expected: str) -> ApiProtocolError:
    return ApiProtocolError(
        f"IMA API endpoint {endpoint} returned an invalid {path}; expected {expected}.",
        endpoint=endpoint,
        details={"field": path},
    )


def _value(obj: Mapping[str, Any], key: str, endpoint: str, path: str) -> Any:
    value = obj.get(key, _MISSING)
    if value is _MISSING:
        raise _failure(endpoint, f"{path}.{key}", "a required field")
    return value


def require_object(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> dict[str, Any]:
    value = _value(obj, key, endpoint, path)
    if not isinstance(value, dict):
        raise _failure(endpoint, f"{path}.{key}", "an object")
    return value


def optional_object(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> dict[str, Any] | None:
    value = obj.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise _failure(endpoint, f"{path}.{key}", "an object or null")
    return value


def require_array(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> list[Any]:
    value = _value(obj, key, endpoint, path)
    if not isinstance(value, list):
        raise _failure(endpoint, f"{path}.{key}", "an array")
    return value


def optional_array(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> list[Any] | None:
    value = obj.get(key)
    if value is None:
        return None
    if not isinstance(value, list):
        raise _failure(endpoint, f"{path}.{key}", "an array or null")
    return value


def require_string(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> str:
    value = _value(obj, key, endpoint, path)
    if not isinstance(value, str):
        raise _failure(endpoint, f"{path}.{key}", "a string")
    return value


def optional_string(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data", default: str = "") -> str:
    value = obj.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise _failure(endpoint, f"{path}.{key}", "a string or null")
    return value


def require_non_empty_string(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> str:
    value = require_string(obj, key, endpoint, path).strip()
    if not value:
        raise _failure(endpoint, f"{path}.{key}", "a non-empty string")
    return value


require_identifier = require_non_empty_string


def require_int(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> int:
    value = _value(obj, key, endpoint, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise _failure(endpoint, f"{path}.{key}", "an integer")
    return value


def optional_int(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> int | None:
    value = obj.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _failure(endpoint, f"{path}.{key}", "an integer or null")
    return value


def require_bool(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> bool:
    value = _value(obj, key, endpoint, path)
    if not isinstance(value, bool):
        raise _failure(endpoint, f"{path}.{key}", "a boolean")
    return value


def require_string_map(obj: Mapping[str, Any], key: str, endpoint: str, path: str = "data") -> dict[str, str]:
    value = _value(obj, key, endpoint, path)
    if not isinstance(value, dict):
        raise _failure(endpoint, f"{path}.{key}", "an object with string values")
    try:
        return sanitize_header_map(value)
    except ValueError as exc:
        raise _failure(endpoint, f"{path}.{key}", "safe HTTP string headers") from exc

