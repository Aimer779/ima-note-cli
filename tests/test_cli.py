from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from _bootstrap import ROOT  # noqa: F401
from ima_note_cli.api import (
    ApiError,
    FolderResult,
    KnowledgeBaseResult,
    KnowledgeBaseSummary,
    KnowledgeEntry,
    SearchResult,
)
from ima_note_cli.cli import run
from ima_note_cli.config import CredentialStatus, Credentials


class FakeNotesClient:
    def __init__(
        self,
        search_result=None,
        get_result=None,
        folders_result=None,
        notes_result=None,
        create_result=None,
        append_result=None,
        error: Exception | None = None,
    ) -> None:
        self._search_result = search_result or {"docs": [], "total_hit_num": 0, "is_end": True}
        self._get_result = get_result or {"doc_id": "doc-1", "content": ""}
        self._folders_result = folders_result or {"folders": [], "next_cursor": "", "is_end": True}
        self._notes_result = notes_result or {"notes": [], "next_cursor": "", "is_end": True, "folder_id": ""}
        self._create_result = create_result or {"doc_id": "doc-created", "folder_id": ""}
        self._append_result = append_result or {"doc_id": "doc-appended"}
        self._error = error
        self.last_search_call = None
        self.last_list_notes_call = None
        self.last_create_call = None
        self.last_append_call = None

    def search_notes(self, query: str, limit: int, **kwargs):
        if self._error:
            raise self._error
        self.last_search_call = {"query": query, "limit": limit, **kwargs}
        return self._search_result

    def get_doc_content(self, doc_id: str):
        if self._error:
            raise self._error
        return self._get_result

    def list_folders(self, limit: int, *, cursor: str = "0"):
        if self._error:
            raise self._error
        return self._folders_result

    def list_notes(self, limit: int, *, folder_id: str = "", cursor: str = ""):
        if self._error:
            raise self._error
        self.last_list_notes_call = {"limit": limit, "folder_id": folder_id, "cursor": cursor}
        return self._notes_result

    def create_note(self, content: str, *, folder_id: str | None = None):
        if self._error:
            raise self._error
        self.last_create_call = {"content": content, "folder_id": folder_id}
        return self._create_result

    def append_note(self, doc_id: str, content: str):
        if self._error:
            raise self._error
        self.last_append_call = {"doc_id": doc_id, "content": content}
        return self._append_result


class FakeKnowledgeClient:
    def __init__(
        self,
        search_bases_result=None,
        detail_result=None,
        browse_result=None,
        search_result=None,
        addable_result=None,
        add_note_result=None,
        import_urls_result=None,
        error: Exception | None = None,
    ) -> None:
        self._search_bases_result = search_bases_result or {"knowledge_bases": [], "next_cursor": "", "is_end": True}
        self._detail_result = detail_result
        self._browse_result = browse_result or {"items": [], "next_cursor": "", "is_end": True, "current_path": []}
        self._search_result = search_result or {"items": [], "next_cursor": "", "is_end": True}
        self._addable_result = addable_result or {"knowledge_bases": [], "next_cursor": "", "is_end": True}
        self._add_note_result = add_note_result or {"media_id": "media-1", "knowledge_base_id": "kb-1", "doc_id": "doc-1", "title": "doc-1", "folder_id": ""}
        self._import_urls_result = import_urls_result or {"results": [], "knowledge_base_id": "kb-1", "folder_id": ""}
        self._error = error
        self.last_import_urls_call = None

    def search_knowledge_bases(self, query: str, limit: int, *, cursor: str = ""):
        if self._error:
            raise self._error
        return self._search_bases_result

    def get_knowledge_base(self, knowledge_base_id: str):
        if self._error:
            raise self._error
        return self._detail_result

    def list_knowledge(self, knowledge_base_id: str, limit: int, *, cursor: str = "", folder_id: str | None = None):
        if self._error:
            raise self._error
        return self._browse_result

    def search_knowledge(self, query: str, knowledge_base_id: str, *, cursor: str = ""):
        if self._error:
            raise self._error
        return self._search_result

    def list_addable_knowledge_bases(self, limit: int, *, cursor: str = ""):
        if self._error:
            raise self._error
        return self._addable_result

    def add_note(self, knowledge_base_id: str, doc_id: str, *, title: str, folder_id: str | None = None):
        if self._error:
            raise self._error
        return self._add_note_result

    def import_urls(self, knowledge_base_id: str, urls: list[str], *, folder_id: str | None = None):
        if self._error:
            raise self._error
        self.last_import_urls_call = {
            "knowledge_base_id": knowledge_base_id,
            "urls": urls,
            "folder_id": folder_id,
        }
        return self._import_urls_result


class CliTests(unittest.TestCase):
    @staticmethod
    def _configured_status() -> CredentialStatus:
        return CredentialStatus("client", "key", "environment", "environment")

    @staticmethod
    def _configured_credentials() -> Credentials:
        return Credentials("client", "key", "environment", "environment")

    def test_auth_reports_configured_sources(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        configured = CredentialStatus(
            client_id="client",
            api_key="key",
            client_id_source=".env",
            api_key_source="environment",
        )

        with patch("ima_note_cli.cli.inspect_credentials", return_value=configured):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = run(["auth"])

        output = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("Status: configured", output)
        self.assertIn("IMA_OPENAPI_CLIENTID: set (.env)", output)
        self.assertIn("IMA_OPENAPI_APIKEY: set (environment)", output)
        self.assertEqual(stderr.getvalue(), "")

    def test_auth_json_output(self) -> None:
        stdout = io.StringIO()
        configured = CredentialStatus(
            client_id="client",
            api_key="key",
            client_id_source=".env",
            api_key_source=".env",
        )

        with patch("ima_note_cli.cli.inspect_credentials", return_value=configured):
            with redirect_stdout(stdout):
                code = run(["auth", "--json"])

        parsed = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertTrue(parsed["configured"])
        self.assertTrue(parsed["credentials"]["IMA_OPENAPI_CLIENTID"]["set"])

    def test_note_search_prints_human_readable_output(self) -> None:
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

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.NotesApiClient", return_value=FakeNotesClient(search_result=fake_result)):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = run(["note", "search", "会议"])

        output = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("Search query: 会议", output)
        self.assertIn("doc-123", output)
        self.assertIn("会议纪要", output)
        self.assertEqual(stderr.getvalue(), "")

    def test_note_search_json_output(self) -> None:
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
        fake_client = FakeNotesClient(search_result=fake_result)

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.NotesApiClient", return_value=fake_client):
                with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                    with redirect_stdout(stdout):
                        code = run(["note", "search", "会议", "--json"])

        parsed = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(parsed["query"], "会议")
        self.assertEqual(parsed["docs"][0]["doc_id"], "doc-123")
        self.assertEqual(fake_client.last_search_call["search_type"], 0)
        self.assertEqual(fake_client.last_search_call["sort_type"], 0)

    def test_note_search_supports_content_search_type_and_sort(self) -> None:
        fake_client = FakeNotesClient()

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.NotesApiClient", return_value=fake_client):
                    code = run(["note", "search", "项目排期", "--search-type", "content", "--sort", "title", "--start", "5"])

        self.assertEqual(code, 0)
        self.assertEqual(fake_client.last_search_call["search_type"], 1)
        self.assertEqual(fake_client.last_search_call["sort_type"], 2)
        self.assertEqual(fake_client.last_search_call["start"], 5)

    def test_note_folders_prints_human_readable_output(self) -> None:
        folders_result = {
            "folders": [
                FolderResult(
                    folder_id="folder-1",
                    name="工作",
                    note_number=12,
                    create_time=1710000000000,
                    modify_time=1710000000000,
                    folder_type=0,
                    status=0,
                    parent_folder_id="",
                )
            ],
            "next_cursor": "next-1",
            "is_end": False,
        }
        stdout = io.StringIO()

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.NotesApiClient", return_value=FakeNotesClient(folders_result=folders_result)):
                    with redirect_stdout(stdout):
                        code = run(["note", "folders"])

        output = stdout.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("工作", output)
        self.assertIn("folder-1", output)
        self.assertIn("Next cursor: next-1", output)

    def test_note_list_json_output(self) -> None:
        notes_result = {
            "notes": [
                SearchResult(
                    doc_id="doc-200",
                    title="周报",
                    summary="本周完成事项",
                    folder_id="folder-1",
                    folder_name="工作",
                    create_time=1710000000000,
                    modify_time=1710000000000,
                    status=0,
                    highlight_title="",
                )
            ],
            "next_cursor": "next-note",
            "is_end": False,
            "folder_id": "folder-1",
        }
        stdout = io.StringIO()
        fake_client = FakeNotesClient(notes_result=notes_result)

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.NotesApiClient", return_value=fake_client):
                    with redirect_stdout(stdout):
                        code = run(["note", "list", "--folder-id", "folder-1", "--json"])

        parsed = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(parsed["notes"][0]["doc_id"], "doc-200")
        self.assertEqual(fake_client.last_list_notes_call["folder_id"], "folder-1")

    def test_note_create_with_title_wraps_markdown(self) -> None:
        fake_client = FakeNotesClient(create_result={"doc_id": "doc-new", "folder_id": "folder-1"})

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.NotesApiClient", return_value=fake_client):
                    code = run(["note", "create", "--title", "测试标题", "--content", "正文内容", "--folder-id", "folder-1"])

        self.assertEqual(code, 0)
        self.assertEqual(fake_client.last_create_call["folder_id"], "folder-1")
        self.assertEqual(fake_client.last_create_call["content"], "# 测试标题\n\n正文内容")

    def test_note_create_can_read_markdown_from_file(self) -> None:
        fake_client = FakeNotesClient(create_result={"doc_id": "doc-new", "folder_id": ""})
        with TemporaryDirectory() as tmp_dir:
            note_path = Path(tmp_dir) / "note.md"
            note_path.write_text("# 文件标题\n\n文件正文", encoding="utf-8")

            with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
                with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                    with patch("ima_note_cli.cli.NotesApiClient", return_value=fake_client):
                        code = run(["note", "create", "--file", str(note_path), "--json"])

        self.assertEqual(code, 0)
        self.assertEqual(fake_client.last_create_call["content"], "# 文件标题\n\n文件正文")

    def test_note_append_with_content(self) -> None:
        fake_client = FakeNotesClient(append_result={"doc_id": "doc-9"})

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.NotesApiClient", return_value=fake_client):
                    code = run(["note", "append", "doc-9", "--content", "\n## 补充\n\n追加内容"])

        self.assertEqual(code, 0)
        self.assertEqual(fake_client.last_append_call["doc_id"], "doc-9")
        self.assertIn("追加内容", fake_client.last_append_call["content"])

    def test_note_get_prints_content(self) -> None:
        stdout = io.StringIO()

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch(
                    "ima_note_cli.cli.NotesApiClient",
                    return_value=FakeNotesClient(get_result={"doc_id": "doc-1", "content": "正文内容"}),
                ):
                    with redirect_stdout(stdout):
                        code = run(["note", "get", "doc-1"])

        self.assertEqual(code, 0)
        self.assertIn("Doc ID: doc-1", stdout.getvalue())
        self.assertIn("正文内容", stdout.getvalue())

    def test_kb_search_base_json_output(self) -> None:
        stdout = io.StringIO()
        fake_client = FakeKnowledgeClient(
            search_bases_result={
                "knowledge_bases": [KnowledgeBaseSummary("kb-1", "产品文档库", "https://example.com/cover.png")],
                "next_cursor": "",
                "is_end": True,
            }
        )

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.KnowledgeBaseApiClient", return_value=fake_client):
                    with redirect_stdout(stdout):
                        code = run(["kb", "search-base", "产品", "--json"])

        parsed = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(parsed["knowledge_bases"][0]["knowledge_base_id"], "kb-1")

    def test_kb_show_base_prints_details(self) -> None:
        stdout = io.StringIO()
        fake_client = FakeKnowledgeClient(
            detail_result=KnowledgeBaseResult(
                knowledge_base_id="kb-1",
                name="产品文档库",
                cover_url="",
                description="产品资料",
                recommended_questions=("最新版本是什么？",),
            )
        )

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.KnowledgeBaseApiClient", return_value=fake_client):
                    with redirect_stdout(stdout):
                        code = run(["kb", "show-base", "--kb-id", "kb-1"])

        self.assertEqual(code, 0)
        output = stdout.getvalue()
        self.assertIn("产品文档库", output)
        self.assertIn("产品资料", output)

    def test_kb_browse_json_output(self) -> None:
        stdout = io.StringIO()
        fake_client = FakeKnowledgeClient(
            browse_result={
                "items": [KnowledgeEntry("file", "media-1", "需求文档.pdf", "folder-1", "", None, None, None)],
                "next_cursor": "next-1",
                "is_end": False,
                "current_path": [],
            }
        )

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.KnowledgeBaseApiClient", return_value=fake_client):
                    with redirect_stdout(stdout):
                        code = run(["kb", "browse", "--kb-id", "kb-1", "--json"])

        parsed = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(parsed["items"][0]["item_id"], "media-1")

    def test_kb_add_url_passes_urls_to_client(self) -> None:
        stdout = io.StringIO()
        fake_client = FakeKnowledgeClient(import_urls_result={"results": [], "knowledge_base_id": "kb-1", "folder_id": ""})

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.KnowledgeBaseApiClient", return_value=fake_client):
                    with redirect_stdout(stdout):
                        code = run(["kb", "add-url", "--kb-id", "kb-1", "--url", "https://example.com/article"])

        self.assertEqual(code, 0)
        self.assertEqual(fake_client.last_import_urls_call["urls"], ["https://example.com/article"])

    def test_api_errors_return_non_zero_exit_code(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch("ima_note_cli.cli.inspect_credentials", return_value=self._configured_status()):
            with patch("ima_note_cli.cli.load_credentials", return_value=self._configured_credentials()):
                with patch("ima_note_cli.cli.NotesApiClient", return_value=FakeNotesClient(error=ApiError("boom"))):
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = run(["note", "search", "会议"])

        self.assertEqual(code, 1)
        self.assertIn("Error: boom", stderr.getvalue())
