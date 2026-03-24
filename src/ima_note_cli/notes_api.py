from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Credentials
from .http import ImaApiClient, maybe_int


BASE_URL = "https://ima.qq.com/openapi/note/v1"


@dataclass(frozen=True)
class SearchResult:
    doc_id: str
    title: str
    summary: str
    folder_id: str
    folder_name: str
    create_time: int | None
    modify_time: int | None
    status: int | None
    highlight_title: str


@dataclass(frozen=True)
class FolderResult:
    folder_id: str
    name: str
    note_number: int | None
    create_time: int | None
    modify_time: int | None
    folder_type: int | None
    status: int | None
    parent_folder_id: str


class NotesApiClient(ImaApiClient):
    def __init__(self, credentials: Credentials, timeout: int = 30) -> None:
        super().__init__(credentials, base_url=BASE_URL, timeout=timeout)

    def search_notes(
        self,
        query: str,
        limit: int,
        *,
        start: int = 0,
        search_type: int = 0,
        sort_type: int = 0,
    ) -> dict[str, Any]:
        query_info = {"content": query} if search_type == 1 else {"title": query}
        data = self.post_json(
            "search_note_book",
            {
                "search_type": search_type,
                "sort_type": sort_type,
                "query_info": query_info,
                "start": start,
                "end": start + limit,
            },
        )
        docs = data.get("docs", [])
        return {
            "docs": [self._parse_search_doc(item) for item in docs],
            "total_hit_num": data.get("total_hit_num", len(docs)),
            "is_end": data.get("is_end"),
            "start": start,
            "end": start + limit,
            "search_type": search_type,
            "sort_type": sort_type,
        }

    def get_doc_content(self, doc_id: str) -> dict[str, Any]:
        data = self.post_json(
            "get_doc_content",
            {
                "doc_id": doc_id,
                "target_content_format": 0,
            },
        )
        return {
            "doc_id": doc_id,
            "content": data.get("content", ""),
        }

    def list_folders(self, limit: int, *, cursor: str = "0") -> dict[str, Any]:
        data = self.post_json(
            "list_note_folder_by_cursor",
            {
                "cursor": cursor,
                "limit": limit,
            },
        )
        folders = data.get("note_book_folders", [])
        return {
            "folders": [self._parse_folder(item) for item in folders],
            "next_cursor": str(data.get("next_cursor", "")),
            "is_end": data.get("is_end"),
        }

    def list_notes(self, limit: int, *, folder_id: str = "", cursor: str = "") -> dict[str, Any]:
        data = self.post_json(
            "list_note_by_folder_id",
            {
                "folder_id": folder_id,
                "cursor": cursor,
                "limit": limit,
            },
        )
        notes = data.get("note_book_list", [])
        return {
            "notes": [self._parse_listed_note(item) for item in notes],
            "next_cursor": str(data.get("next_cursor", "")),
            "is_end": data.get("is_end"),
            "folder_id": folder_id,
        }

    def create_note(self, content: str, *, folder_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "content_format": 1,
            "content": content,
        }
        if folder_id:
            payload["folder_id"] = folder_id
        data = self.post_json("import_doc", payload)
        return {
            "doc_id": str(data.get("doc_id", "")),
            "folder_id": folder_id or "",
        }

    def append_note(self, doc_id: str, content: str) -> dict[str, Any]:
        data = self.post_json(
            "append_doc",
            {
                "doc_id": doc_id,
                "content_format": 1,
                "content": content,
            },
        )
        return {
            "doc_id": str(data.get("doc_id", doc_id)),
        }

    @staticmethod
    def _parse_search_doc(item: dict[str, Any]) -> SearchResult:
        basic_info = item.get("doc", {}).get("basic_info", {}) if isinstance(item, dict) else {}
        highlight_info = item.get("highlight_info", {}) if isinstance(item, dict) else {}
        return SearchResult(
            doc_id=str(basic_info.get("docid", "")),
            title=str(basic_info.get("title", "")),
            summary=str(basic_info.get("summary", "")),
            folder_id=str(basic_info.get("folder_id", "")),
            folder_name=str(basic_info.get("folder_name", "")),
            create_time=maybe_int(basic_info.get("create_time")),
            modify_time=maybe_int(basic_info.get("modify_time")),
            status=maybe_int(basic_info.get("status")),
            highlight_title=str(highlight_info.get("doc_title", "")),
        )

    @staticmethod
    def _parse_listed_note(item: dict[str, Any]) -> SearchResult:
        basic_info = item.get("basic_info", {}).get("basic_info", {}) if isinstance(item, dict) else {}
        return SearchResult(
            doc_id=str(basic_info.get("docid", "")),
            title=str(basic_info.get("title", "")),
            summary=str(basic_info.get("summary", "")),
            folder_id=str(basic_info.get("folder_id", "")),
            folder_name=str(basic_info.get("folder_name", "")),
            create_time=maybe_int(basic_info.get("create_time")),
            modify_time=maybe_int(basic_info.get("modify_time")),
            status=maybe_int(basic_info.get("status")),
            highlight_title="",
        )

    @staticmethod
    def _parse_folder(item: dict[str, Any]) -> FolderResult:
        basic_info = item.get("folder", {}).get("basic_info", {}) if isinstance(item, dict) else {}
        return FolderResult(
            folder_id=str(basic_info.get("folder_id", "")),
            name=str(basic_info.get("name", "")),
            note_number=maybe_int(basic_info.get("note_number")),
            create_time=maybe_int(basic_info.get("create_time")),
            modify_time=maybe_int(basic_info.get("modify_time")),
            folder_type=maybe_int(basic_info.get("folder_type")),
            status=maybe_int(basic_info.get("status")),
            parent_folder_id=str(basic_info.get("parent_folder_id", "")),
        )
