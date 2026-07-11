from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.errors import ApiProtocolError
from ima_note_cli.protocol import require_array, require_bool, require_int, require_non_empty_string, require_string_map


class ProtocolTests(unittest.TestCase):
    def test_strict_scalar_and_collection_types(self) -> None:
        self.assertEqual(require_non_empty_string({"id": " x "}, "id", "ep"), "x")
        self.assertEqual(require_int({"n": 2}, "n", "ep"), 2)
        self.assertTrue(require_bool({"flag": True}, "flag", "ep"))
        self.assertEqual(require_array({"items": []}, "items", "ep"), [])
        for payload, fn, key in [({"n": True}, require_int, "n"), ({"flag": "false"}, require_bool, "flag"), ({"items": None}, require_array, "items")]:
            with self.subTest(payload=payload), self.assertRaises(ApiProtocolError):
                fn(payload, key, "ep")

    def test_headers_reject_non_strings_and_crlf_without_echo(self) -> None:
        for value in [{"Authorization": False}, {"X-Test": "secret\r\nInjected: yes"}]:
            with self.assertRaises(ApiProtocolError) as caught:
                require_string_map({"headers": value}, "headers", "ep")
            self.assertNotIn("secret", str(caught.exception))

