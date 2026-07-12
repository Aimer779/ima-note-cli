from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Generic, TypeVar

from .errors import ApiProtocolError
from .validation import validate_max_pages

T = TypeVar("T")


@dataclass(frozen=True)
class PageCollection(Generic[T]):
    items: tuple[T, ...]
    pages_fetched: int
    complete: bool
    next_cursor: str
    reason: str | None = None


def collect_cursor_pages(
    fetch: Callable[[str], dict[str, Any]], item_key: str, *, initial_cursor: str = "", max_pages: int = 100
) -> PageCollection[Any]:
    validate_max_pages(max_pages)
    cursor = initial_cursor
    seen: set[str] = set()
    items: list[Any] = []
    for page_number in range(1, max_pages + 1):
        if cursor in seen:
            raise ApiProtocolError("Pagination cursor repeated.", code="pagination_cursor_loop")
        seen.add(cursor)
        page = fetch(cursor)
        values = page.get(item_key)
        if not isinstance(values, list):
            raise ApiProtocolError(f"Pagination field {item_key} must be an array.")
        items.extend(values)
        is_end = page.get("is_end")
        next_cursor = page.get("next_cursor")
        if not isinstance(is_end, bool) or not isinstance(next_cursor, str):
            raise ApiProtocolError("Pagination metadata is malformed.")
        if is_end:
            return PageCollection(tuple(items), page_number, True, next_cursor)
        if not next_cursor:
            raise ApiProtocolError("Pagination did not provide a next cursor.", code="pagination_no_progress")
        cursor = next_cursor
    return PageCollection(tuple(items), max_pages, False, cursor, "max_pages")


def collect_offset_pages(
    fetch: Callable[[int], dict[str, Any]], item_key: str, *, initial_offset: int = 0, max_pages: int = 100
) -> PageCollection[Any]:
    validate_max_pages(max_pages)
    offset = initial_offset
    items: list[Any] = []
    for page_number in range(1, max_pages + 1):
        page = fetch(offset)
        values = page.get(item_key)
        if not isinstance(values, list):
            raise ApiProtocolError(f"Pagination field {item_key} must be an array.")
        items.extend(values)
        if page.get("is_end") is True:
            return PageCollection(tuple(items), page_number, True, "")
        if not values:
            raise ApiProtocolError("Offset pagination made no progress.", code="pagination_no_progress")
        offset += len(values)
    return PageCollection(tuple(items), max_pages, False, str(offset), "max_pages")
