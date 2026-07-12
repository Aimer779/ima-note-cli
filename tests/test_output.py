from __future__ import annotations

from io import BytesIO, StringIO, TextIOWrapper
import json
import unittest

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.errors import InputError
from ima_note_cli.output import emit_json_error, emit_json_success


class OutputTests(unittest.TestCase):
    def test_success_and_error_are_single_envelopes(self) -> None:
        stream = StringIO()
        emit_json_success("note.search", {"docs": [], "warnings": ["a"]}, ["a", "b"], stream=stream)
        result = json.loads(stream.getvalue())
        self.assertEqual((result["schema_version"], result["ok"], result["command"]), (1, True, "note.search"))
        self.assertEqual(result["warnings"], ["a", "b"])
        stream = StringIO()
        emit_json_error("cli", InputError("bad"), stream=stream)
        result = json.loads(stream.getvalue())
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["exit_code"], 2)

    def test_json_is_safe_on_ascii_only_windows_streams(self) -> None:
        raw = BytesIO()
        stream = TextIOWrapper(raw, encoding="ascii")
        emit_json_success("kb.read", {"content": "正文 😀"}, [], stream=stream)
        stream.flush()
        result = json.loads(raw.getvalue().decode("ascii"))
        self.assertEqual(result["content"], "正文 😀")
