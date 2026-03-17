from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any
from urllib import error, request

from .config import Credentials


BASE_URL = "https://ima.qq.com/openapi/note/v1"
SUCCESS_CODE_VALUES = {0, "0", None}
CODE_KEYS = ("code", "retcode", "errcode", "error_code")
MESSAGE_KEYS = ("message", "msg", "errmsg", "error_message", "error_msg")
DATA_KEYS = ("data", "result")


class ApiError(RuntimeError):
    """Raised when the remote API returns an error."""


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


class ImaNoteApiClient:
    def __init__(self, credentials: Credentials, timeout: int = 30) -> None:
        self._credentials = credentials
        self._timeout = timeout

    def search_notes(
        self,
        query: str,
        limit: int,
        *,
        start: int = 0,
        search_type: int = 0,
        sort_type: int = 0,
    ) -> dict[str, Any]:
        query_info: dict[str, str]
        if search_type == 1:
            query_info = {"content": query}
        else:
            query_info = {"title": query}

        payload = {
            "search_type": search_type,
            "sort_type": sort_type,
            "query_info": query_info,
            "start": start,
            "end": start + limit,
        }
        data = self._post("search_note_book", payload)
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
        payload = {
            "doc_id": doc_id,
            "target_content_format": 0,
        }
        data = self._post("get_doc_content", payload)
        return {
            "doc_id": doc_id,
            "content": data.get("content", ""),
        }

    def list_folders(self, limit: int, *, cursor: str = "0") -> dict[str, Any]:
        payload = {
            "cursor": cursor,
            "limit": limit,
        }
        data = self._post("list_note_folder_by_cursor", payload)
        folders = data.get("note_book_folders", [])
        return {
            "folders": [self._parse_folder(item) for item in folders],
            "next_cursor": str(data.get("next_cursor", "")),
            "is_end": data.get("is_end"),
        }

    def list_notes(self, limit: int, *, folder_id: str = "", cursor: str = "") -> dict[str, Any]:
        payload = {
            "folder_id": folder_id,
            "cursor": cursor,
            "limit": limit,
        }
        data = self._post("list_note_by_folder_id", payload)
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
        data = self._post("import_doc", payload)
        return {
            "doc_id": str(data.get("doc_id", "")),
            "folder_id": folder_id or "",
        }

    def append_note(self, doc_id: str, content: str) -> dict[str, Any]:
        payload = {
            "doc_id": doc_id,
            "content_format": 1,
            "content": content,
        }
        data = self._post("append_doc", payload)
        return {
            "doc_id": str(data.get("doc_id", doc_id)),
        }

    def _post(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        url = f"{BASE_URL}/{endpoint}"
        req = request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "ima-openapi-clientid": self._credentials.client_id,
                "ima-openapi-apikey": self._credentials.api_key,
            },
        )

        try:
            with request.urlopen(req, timeout=self._timeout) as response:
                raw_text = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = self._read_error_body(exc)
            raise ApiError(f"HTTP {exc.code} from IMA API: {detail}") from exc
        except error.URLError as exc:
            reason = exc.reason if getattr(exc, "reason", None) else "request failed"
            raise ApiError(f"Unable to reach the IMA API: {reason}") from exc
        except TimeoutError as exc:
            raise ApiError("The request to the IMA API timed out.") from exc

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ApiError("IMA API returned invalid JSON.") from exc

        if not isinstance(parsed, dict):
            raise ApiError("IMA API returned an unexpected response shape.")

        return self._unwrap_payload(parsed)

    def _unwrap_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        code = self._first_value(payload, CODE_KEYS)
        if code not in SUCCESS_CODE_VALUES:
            message = self._first_value(payload, MESSAGE_KEYS) or "unknown API error"
            raise ApiError(f"IMA API error {code}: {message}")

        data = self._first_value(payload, DATA_KEYS)
        if data is None:
            return payload
        if not isinstance(data, dict):
            raise ApiError("IMA API returned a non-object data payload.")
        return data

    @staticmethod
    def _parse_search_doc(item: dict[str, Any]) -> SearchResult:
        basic_info = (
            item.get("doc", {}).get("basic_info", {})
            if isinstance(item, dict)
            else {}
        )
        highlight_info = item.get("highlight_info", {}) if isinstance(item, dict) else {}
        return SearchResult(
            doc_id=str(basic_info.get("docid", "")),
            title=str(basic_info.get("title", "")),
            summary=str(basic_info.get("summary", "")),
            folder_id=str(basic_info.get("folder_id", "")),
            folder_name=str(basic_info.get("folder_name", "")),
            create_time=_maybe_int(basic_info.get("create_time")),
            modify_time=_maybe_int(basic_info.get("modify_time")),
            status=_maybe_int(basic_info.get("status")),
            highlight_title=str(highlight_info.get("doc_title", "")),
        )

    @staticmethod
    def _parse_listed_note(item: dict[str, Any]) -> SearchResult:
        basic_info = (
            item.get("basic_info", {}).get("basic_info", {})
            if isinstance(item, dict)
            else {}
        )
        return SearchResult(
            doc_id=str(basic_info.get("docid", "")),
            title=str(basic_info.get("title", "")),
            summary=str(basic_info.get("summary", "")),
            folder_id=str(basic_info.get("folder_id", "")),
            folder_name=str(basic_info.get("folder_name", "")),
            create_time=_maybe_int(basic_info.get("create_time")),
            modify_time=_maybe_int(basic_info.get("modify_time")),
            status=_maybe_int(basic_info.get("status")),
            highlight_title="",
        )

    @staticmethod
    def _parse_folder(item: dict[str, Any]) -> FolderResult:
        basic_info = (
            item.get("folder", {}).get("basic_info", {})
            if isinstance(item, dict)
            else {}
        )
        return FolderResult(
            folder_id=str(basic_info.get("folder_id", "")),
            name=str(basic_info.get("name", "")),
            note_number=_maybe_int(basic_info.get("note_number")),
            create_time=_maybe_int(basic_info.get("create_time")),
            modify_time=_maybe_int(basic_info.get("modify_time")),
            folder_type=_maybe_int(basic_info.get("folder_type")),
            status=_maybe_int(basic_info.get("status")),
            parent_folder_id=str(basic_info.get("parent_folder_id", "")),
        )

    @staticmethod
    def _first_value(payload: dict[str, Any], keys: tuple[str, ...]) -> Any:
        for key in keys:
            if key in payload:
                return payload[key]
        return None

    @staticmethod
    def _read_error_body(exc: error.HTTPError) -> str:
        try:
            body = exc.read().decode("utf-8").strip()
        except Exception:
            body = ""
        return body or exc.reason


def _maybe_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
