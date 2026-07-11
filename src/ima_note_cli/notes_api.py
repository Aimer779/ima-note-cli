from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Credentials
from .errors import ApiProtocolError, InputError
from .http import ImaApiClient
from .notes_content import ensure_valid_utf8
from .protocol import optional_int, optional_object, optional_string, require_array, require_bool, require_identifier, require_int, require_string


BASE_URL = "https://ima.qq.com/openapi/note/v1"
VALID_SEARCH_TYPES = {0, 1}
VALID_SORT_TYPES = {0, 1, 2, 3}


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{field_name} cannot be empty.")
    return value.strip()


def _require_content(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError("content cannot be empty.")
    ensure_valid_utf8(value, "content")
    return value


def _require_limit(limit: int) -> None:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 20:
        raise InputError("limit must be between 1 and 20.")


@dataclass(frozen=True, init=False)
class SearchResult:
    note_id: str
    title: str
    summary: str
    folder_id: str
    folder_name: str
    create_time: int | None
    modify_time: int | None
    cover_image: str
    highlight_title: str
    status: int | None

    def __init__(
        self,
        note_id: str | None = None,
        title: str = "",
        summary: str = "",
        folder_id: str = "",
        folder_name: str = "",
        create_time: int | None = None,
        modify_time: int | None = None,
        cover_image: str = "",
        highlight_title: str = "",
        status: int | None = None,
        *,
        doc_id: str | None = None,
    ) -> None:
        if note_id is not None and doc_id is not None and note_id != doc_id:
            raise InputError("note_id and doc_id must match when both are provided.")
        resolved_id = note_id if note_id is not None else doc_id
        if resolved_id is None:
            raise TypeError("SearchResult requires note_id (or deprecated doc_id).")
        for name, value in (
            ("note_id", resolved_id), ("title", title), ("summary", summary),
            ("folder_id", folder_id), ("folder_name", folder_name),
            ("create_time", create_time), ("modify_time", modify_time),
            ("cover_image", cover_image), ("highlight_title", highlight_title),
            ("status", status),
        ):
            object.__setattr__(self, name, value)

    @property
    def doc_id(self) -> str:
        """Deprecated compatibility alias for note_id."""
        return self.note_id


@dataclass(frozen=True)
class FolderResult:
    folder_id: str
    name: str
    note_number: int | None
    create_time: int | None
    modify_time: int | None
    folder_type: int | None
    parent_folder_id: str
    status: int | None = None


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
        query = _require_text(query, "query")
        _require_limit(limit)
        if not isinstance(start, int) or isinstance(start, bool) or start < 0:
            raise InputError("start must be greater than or equal to 0.")
        if search_type not in VALID_SEARCH_TYPES:
            raise InputError("search_type must be 0 or 1.")
        if sort_type not in VALID_SORT_TYPES:
            raise InputError("sort_type must be between 0 and 3.")
        query_info = {"content": query} if search_type == 1 else {"title": query}
        data = self.post_read_json(
            "search_note",
            {
                "search_type": search_type,
                "sort_type": sort_type,
                "query_info": query_info,
                "start": start,
                "end": start + limit,
            },
        )
        infos = require_array(data, "search_note_infos", "search_note")
        return {
            "docs": [self._parse_search_note(item) for item in infos],
            "total_hit_num": require_int(data, "total_hit_num", "search_note"),
            "is_end": require_bool(data, "is_end", "search_note"),
            "start": start,
            "end": start + limit,
            "search_type": search_type,
            "sort_type": sort_type,
        }

    def get_doc_content(self, note_id: str) -> dict[str, Any]:
        note_id = _require_text(note_id, "note_id")
        data = self.post_read_json("get_doc_content", {"note_id": note_id, "target_content_format": 0})
        return {"note_id": note_id, "doc_id": note_id, "content": require_string(data, "content", "get_doc_content")}

    def list_folders(
        self,
        limit: int,
        *,
        cursor: str = "0",
        version: str | None = None,
    ) -> dict[str, Any]:
        _require_limit(limit)
        if not isinstance(cursor, str):
            raise InputError("cursor must be a string.")
        payload: dict[str, Any] = {"cursor": cursor, "limit": limit}
        if version is not None:
            payload["version"] = _require_text(version, "version")
        data = self.post_read_json("list_notebook", payload)
        folders = require_array(data, "note_folder_infos", "list_notebook")
        return {
            "folders": [self._parse_folder(item) for item in folders],
            "next_cursor": optional_string(data, "next_cursor", "list_notebook"),
            "is_end": require_bool(data, "is_end", "list_notebook"),
            "next_version": optional_string(data, "next_version", "list_notebook"),
            "need_update": require_bool(data, "need_update", "list_notebook"),
        }

    def list_notes(
        self,
        limit: int,
        *,
        folder_id: str = "",
        cursor: str = "",
        sort_type: int = 0,
    ) -> dict[str, Any]:
        _require_limit(limit)
        if not isinstance(folder_id, str):
            raise InputError("folder_id must be a string.")
        if folder_id == "0":
            raise InputError('folder_id cannot be "0"; use an empty string for all notes.')
        if not isinstance(cursor, str):
            raise InputError("cursor must be a string.")
        if sort_type not in VALID_SORT_TYPES:
            raise InputError("sort_type must be between 0 and 3.")
        data = self.post_read_json(
            "list_note",
            {"folder_id": folder_id, "sort_type": sort_type, "cursor": cursor, "limit": limit},
        )
        notes = require_array(data, "note_book_list", "list_note")
        return {
            "notes": [self._parse_note_info(item, endpoint="list_note") for item in notes],
            "next_cursor": optional_string(data, "next_cursor", "list_note"),
            "is_end": require_bool(data, "is_end", "list_note"),
            "folder_id": folder_id,
            "sort_type": sort_type,
        }

    def create_note(self, content: str, *, folder_id: str | None = None) -> dict[str, Any]:
        content = _require_content(content)
        payload: dict[str, Any] = {"content_format": 1, "content": content}
        if folder_id:
            payload["folder_id"] = folder_id
        data = self.post_write_json("import_doc", payload)
        note_id = self._response_note_id(data, "import_doc")
        return {"note_id": note_id, "doc_id": note_id, "folder_id": folder_id or ""}

    def append_note(self, note_id: str, content: str) -> dict[str, Any]:
        note_id = _require_text(note_id, "note_id")
        content = _require_content(content)
        data = self.post_write_json(
            "append_doc",
            {"note_id": note_id, "content_format": 1, "content": content},
        )
        returned_id = self._response_note_id(data, "append_doc")
        return {"note_id": returned_id, "doc_id": returned_id}

    @classmethod
    def _parse_search_note(cls, item: Any) -> SearchResult:
        if not isinstance(item, dict) or not isinstance(item.get("note_book_info"), dict):
            raise ApiProtocolError("search_note response is missing note_book_info.", endpoint="search_note", details={"field": "data.search_note_infos.note_book_info"})
        note = cls._parse_note_info(item["note_book_info"], endpoint="search_note")
        highlight = item.get("highlightInfo")
        highlight_title = optional_string(highlight, "doc_title", "search_note", "data.search_note_infos.highlightInfo") if isinstance(highlight, dict) else ""
        return SearchResult(
            note_id=note.note_id,
            title=note.title,
            summary=note.summary,
            folder_id=note.folder_id,
            folder_name=note.folder_name,
            create_time=note.create_time,
            modify_time=note.modify_time,
            cover_image=note.cover_image,
            highlight_title=highlight_title,
        )

    @staticmethod
    def _parse_note_info(item: Any, *, endpoint: str) -> SearchResult:
        if not isinstance(item, dict):
            raise ApiProtocolError(f"{endpoint} returned a non-object note entry.", endpoint=endpoint, details={"field": "data.note"})
        note_id = require_identifier(item, "note_id", endpoint, "data.note")
        ext = optional_object(item, "note_ext_info", endpoint, "data.note") or {}
        return SearchResult(
            note_id=note_id,
            title=optional_string(item, "title", endpoint, "data.note"),
            summary=optional_string(item, "summary", endpoint, "data.note"),
            folder_id=optional_string(ext, "folder_id", endpoint, "data.note.note_ext_info"),
            folder_name=optional_string(ext, "folder_name", endpoint, "data.note.note_ext_info"),
            create_time=optional_int(item, "create_time", endpoint, "data.note"),
            modify_time=optional_int(item, "modify_time", endpoint, "data.note"),
            cover_image=optional_string(item, "cover_image", endpoint, "data.note"),
            highlight_title="",
        )

    @staticmethod
    def _parse_folder(item: Any) -> FolderResult:
        if not isinstance(item, dict):
            raise ApiProtocolError("list_notebook returned a non-object folder entry.", endpoint="list_notebook", details={"field": "data.note_folder_infos"})
        folder_id = require_identifier(item, "folder_id", "list_notebook", "data.note_folder_infos")
        return FolderResult(
            folder_id=folder_id,
            name=optional_string(item, "name", "list_notebook", "data.note_folder_infos"),
            note_number=optional_int(item, "note_number", "list_notebook", "data.note_folder_infos"),
            create_time=optional_int(item, "create_time", "list_notebook", "data.note_folder_infos"),
            modify_time=optional_int(item, "modify_time", "list_notebook", "data.note_folder_infos"),
            folder_type=optional_int(item, "folder_type", "list_notebook", "data.note_folder_infos"),
            parent_folder_id=optional_string(item, "parent_folder_id", "list_notebook", "data.note_folder_infos"),
        )

    @staticmethod
    def _response_note_id(data: dict[str, Any], endpoint: str) -> str:
        return require_identifier(data, "note_id", endpoint)
