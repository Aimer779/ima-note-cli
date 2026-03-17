from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import unittest
from unittest.mock import patch

from ima_note_cli.api import ApiError, SearchResult
from ima_note_cli.cli import run
from ima_note_cli.config import Credentials


class FakeClient:
    def __init__(self, search_result=None, get_result=None, error: Exception | None = None) -> None:
        self._search_result = search_result or {"docs": [], "total_hit_num": 0, "is_end": True}
        self._get_result = get_result or {"doc_id": "doc-1", "content": ""}
        self._error = error

    def search_notes(self, query: str, limit: int):
        if self._error:
            raise self._error
        return self._search_result

    def get_doc_content(self, doc_id: str):
        if self._error:
            raise self._error
        return self._get_result


class CliTests(unittest.TestCase):
    def test_search_prints_human_readable_output(self) -> None:
        fake_result = {
            "docs": [
                SearchResult(
                    doc_id="doc-123",
                    title="会议纪要",
                    summary="本周项目进展",
                    folder_id="folder-1",
                    folder_name="工作",
                    create_time=1710000000000,
                    modify_time=1710000000000,
                    status=0,
                    highlight_title="<em>会议</em>纪要",
                )
            ],
            "total_hit_num": 1,
            "is_end": True,
        }
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("ima_note_cli.cli.load_credentials", return_value=Credentials("client", "key")):
            with patch("ima_note_cli.cli.ImaNoteApiClient", return_value=FakeClient(search_result=fake_result)):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = run(["search", "会议"])

        output = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("Search query: 会议", output)
        self.assertIn("doc-123", output)
        self.assertIn("会议纪要", output)
        self.assertEqual(stderr.getvalue(), "")

    def test_search_json_output(self) -> None:
        fake_result = {
            "docs": [
                SearchResult(
                    doc_id="doc-123",
                    title="会议纪要",
                    summary="摘要",
                    folder_id="folder-1",
                    folder_name="工作",
                    create_time=1710000000000,
                    modify_time=1710000000000,
                    status=0,
                    highlight_title="",
                )
            ],
            "total_hit_num": 1,
            "is_end": True,
        }
        stdout = io.StringIO()

        with patch("ima_note_cli.cli.load_credentials", return_value=Credentials("client", "key")):
            with patch("ima_note_cli.cli.ImaNoteApiClient", return_value=FakeClient(search_result=fake_result)):
                with redirect_stdout(stdout):
                    code = run(["search", "会议", "--json"])

        parsed = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(parsed["query"], "会议")
        self.assertEqual(parsed["docs"][0]["doc_id"], "doc-123")

    def test_get_prints_content(self) -> None:
        stdout = io.StringIO()

        with patch("ima_note_cli.cli.load_credentials", return_value=Credentials("client", "key")):
            with patch(
                "ima_note_cli.cli.ImaNoteApiClient",
                return_value=FakeClient(get_result={"doc_id": "doc-1", "content": "正文内容"}),
            ):
                with redirect_stdout(stdout):
                    code = run(["get", "doc-1"])

        self.assertEqual(code, 0)
        self.assertIn("Doc ID: doc-1", stdout.getvalue())
        self.assertIn("正文内容", stdout.getvalue())

    def test_api_errors_return_non_zero_exit_code(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("ima_note_cli.cli.load_credentials", return_value=Credentials("client", "key")):
            with patch(
                "ima_note_cli.cli.ImaNoteApiClient",
                return_value=FakeClient(error=ApiError("boom")),
            ):
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = run(["search", "会议"])

        self.assertEqual(code, 1)
        self.assertIn("Error: boom", stderr.getvalue())
