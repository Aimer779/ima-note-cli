from __future__ import annotations

from .errors import InputError


def require_range(value: int, low: int, high: int, option: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InputError(f"{option} must be between {low} and {high}.", details={"field": option, "limit": high})
    return value


def validate_timeout(value: int, option: str = "--timeout") -> int:
    return require_range(value, 1, 3600, option)


def validate_max_pages(value: int) -> int:
    return require_range(value, 1, 1000, "--max-pages")
