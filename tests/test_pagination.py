from __future__ import annotations

import unittest

from ima_note_cli.errors import ApiProtocolError
from ima_note_cli.pagination import collect_cursor_pages, collect_offset_pages


class PaginationTests(unittest.TestCase):
    def test_cursor_collects_and_stops(self) -> None:
        pages = {"": {"items": [1], "next_cursor": "a", "is_end": False}, "a": {"items": [2], "next_cursor": "", "is_end": True}}
        result = collect_cursor_pages(lambda cursor: pages[cursor], "items")
        self.assertEqual((result.items, result.pages_fetched, result.complete), ((1, 2), 2, True))

    def test_cursor_loop_and_missing_progress_fail(self) -> None:
        with self.assertRaises(ApiProtocolError):
            collect_cursor_pages(lambda cursor: {"items": [], "next_cursor": cursor, "is_end": False}, "items")
        with self.assertRaises(ApiProtocolError):
            collect_cursor_pages(lambda cursor: {"items": [], "next_cursor": "", "is_end": False}, "items")

    def test_offset_no_progress_and_cap(self) -> None:
        with self.assertRaises(ApiProtocolError):
            collect_offset_pages(lambda offset: {"docs": [], "is_end": False}, "docs")
        result = collect_offset_pages(lambda offset: {"docs": [offset], "is_end": False}, "docs", max_pages=2)
        self.assertFalse(result.complete)
