from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

from .config import Credentials
from .errors import ApiProtocolError, InputError
from .http import ImaApiClient
from .protocol import (
    optional_int, optional_object, optional_string, require_array, require_bool,
    require_identifier, require_int, require_non_empty_string, require_object,
    require_string_map,
)
from .security import safe_url_host, validate_media_source_url


BASE_URL = "https://ima.qq.com/openapi/wiki/v1"


@dataclass(frozen=True)
class KnowledgeBaseSummary:
    knowledge_base_id: str
    name: str
    cover_url: str


@dataclass(frozen=True)
class KnowledgeBaseResult:
    knowledge_base_id: str
    name: str
    cover_url: str
    description: str
    recommended_questions: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgePathNode:
    folder_id: str
    name: str


@dataclass(frozen=True)
class KnowledgeEntry:
    kind: str
    item_id: str
    title: str
    parent_folder_id: str
    highlight_content: str
    file_number: int | None
    folder_number: int | None
    is_top: bool | None

    @property
    def media_id(self) -> str:
        return self.item_id if self.kind == "file" else ""

    @property
    def folder_id(self) -> str:
        return self.item_id if self.kind == "folder" else ""


@dataclass(frozen=True)
class ImportUrlResult:
    url: str
    ret_code: int
    media_id: str


@dataclass(frozen=True)
class RepeatedNameResult:
    name: str
    is_repeated: bool


@dataclass(frozen=True)
class CosCredential:
    token: str = field(repr=False)
    secret_id: str = field(repr=False)
    secret_key: str = field(repr=False)
    start_time: int
    expired_time: int
    appid: str
    bucket_name: str
    region: str
    custom_domain: str
    cos_key: str


@dataclass(frozen=True)
class MediaAccessInfo:
    url: str = field(repr=False)
    headers: dict[str, str] = field(repr=False)
    safe_host: str
    header_names: tuple[str, ...]


@dataclass(frozen=True)
class MediaInfo:
    media_id: str
    media_type: int
    source_kind: str
    note_id: str | None = None
    access: MediaAccessInfo | None = field(default=None, repr=False)

    def to_safe_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "media_id": self.media_id, "media_type": self.media_type,
            "source_kind": self.source_kind, "available": self.source_kind != "unavailable",
        }
        if self.note_id:
            result["note_id"] = self.note_id
        if self.access:
            result["safe_host"] = self.access.safe_host
            result["header_names"] = list(self.access.header_names)
        return result


def _non_empty(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{name} cannot be empty.")
    return value.strip()


def _limit(value: int, low: int, high: int, name: str = "limit") -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise InputError(f"{name} must be between {low} and {high}.", details={"limit": high})
    return value


class KnowledgeBaseApiClient(ImaApiClient):
    def __init__(self, credentials: Credentials, timeout: int = 30, **kwargs: Any) -> None:
        super().__init__(credentials, base_url=BASE_URL, timeout=timeout, **kwargs)

    def search_knowledge_bases(self, query: str, limit: int, *, cursor: str = "") -> dict[str, Any]:
        endpoint = "search_knowledge_base"
        data = self.post_read_json(endpoint, {"query": query, "cursor": cursor, "limit": _limit(limit, 1, 20)})
        raw = require_array(data, "info_list", endpoint)
        return {"knowledge_bases": [self._parse_kb_summary(item, endpoint, f"data.info_list[{i}]") for i, item in enumerate(raw)],
                "next_cursor": optional_string(data, "next_cursor", endpoint), "is_end": require_bool(data, "is_end", endpoint), "query": query}

    def list_addable_knowledge_bases(self, limit: int, *, cursor: str = "") -> dict[str, Any]:
        endpoint = "get_addable_knowledge_base_list"
        data = self.post_read_json(endpoint, {"cursor": cursor, "limit": _limit(limit, 1, 50)})
        raw = require_array(data, "addable_knowledge_base_list", endpoint)
        items = [self._parse_kb_summary(item, endpoint, f"data.addable_knowledge_base_list[{i}]", cover_optional=True) for i, item in enumerate(raw)]
        return {"knowledge_bases": items, "next_cursor": optional_string(data, "next_cursor", endpoint), "is_end": require_bool(data, "is_end", endpoint)}

    def get_knowledge_bases(self, ids: list[str]) -> dict[str, KnowledgeBaseResult]:
        if not isinstance(ids, list) or not 1 <= len(ids) <= 20:
            raise InputError("ids must contain between 1 and 20 identifiers.")
        normalized = [_non_empty(value, "knowledge_base_id") for value in ids]
        if len(set(normalized)) != len(normalized):
            raise InputError("knowledge base identifiers must be unique.")
        endpoint = "get_knowledge_base"
        data = self.post_read_json(endpoint, {"ids": normalized})
        infos = require_object(data, "infos", endpoint)
        results: dict[str, KnowledgeBaseResult] = {}
        for index, (key, value) in enumerate(infos.items()):
            if not isinstance(key, str) or not isinstance(value, dict):
                raise ApiProtocolError("IMA API get_knowledge_base returned invalid infos entries.", endpoint=endpoint, details={"field": "data.infos"})
            item = self._parse_kb_detail(value, endpoint, f"data.infos[{index}]")
            results[item.knowledge_base_id] = item
        return results

    def get_knowledge_base(self, knowledge_base_id: str) -> KnowledgeBaseResult | None:
        kb_id = _non_empty(knowledge_base_id, "knowledge_base_id")
        return self.get_knowledge_bases([kb_id]).get(kb_id)

    def list_knowledge(self, knowledge_base_id: str, limit: int, *, cursor: str = "", folder_id: str | None = None) -> dict[str, Any]:
        kb_id = _non_empty(knowledge_base_id, "knowledge_base_id")
        payload: dict[str, Any] = {"knowledge_base_id": kb_id, "cursor": cursor, "limit": _limit(limit, 1, 50)}
        if folder_id:
            payload["folder_id"] = folder_id
        endpoint = "get_knowledge_list"
        data = self.post_read_json(endpoint, payload)
        entries = require_array(data, "knowledge_list", endpoint)
        path = require_array(data, "current_path", endpoint)
        return {"items": [self._parse_entry(v, endpoint, f"data.knowledge_list[{i}]") for i, v in enumerate(entries)],
                "next_cursor": optional_string(data, "next_cursor", endpoint), "is_end": require_bool(data, "is_end", endpoint),
                "current_path": [self._parse_path(v, endpoint, f"data.current_path[{i}]") for i, v in enumerate(path)],
                "knowledge_base_id": kb_id, "folder_id": folder_id or ""}

    def search_knowledge(self, query: str, knowledge_base_id: str, *, cursor: str = "") -> dict[str, Any]:
        endpoint = "search_knowledge"
        kb_id = _non_empty(knowledge_base_id, "knowledge_base_id")
        data = self.post_read_json(endpoint, {"query": query, "knowledge_base_id": kb_id, "cursor": cursor})
        entries = require_array(data, "info_list", endpoint)
        return {"items": [self._parse_entry(v, endpoint, f"data.info_list[{i}]") for i, v in enumerate(entries)],
                "next_cursor": optional_string(data, "next_cursor", endpoint), "is_end": require_bool(data, "is_end", endpoint),
                "query": query, "knowledge_base_id": kb_id}

    def add_note(self, knowledge_base_id: str, note_id: str, *, title: str, folder_id: str | None = None) -> dict[str, Any]:
        kb_id, note_id = _non_empty(knowledge_base_id, "knowledge_base_id"), _non_empty(note_id, "note_id")
        payload: dict[str, Any] = {"media_type": 11, "title": title, "knowledge_base_id": kb_id, "note_info": {"content_id": note_id}}
        if folder_id: payload["folder_id"] = folder_id
        endpoint = "add_knowledge"
        data = self.post_write_json(endpoint, payload)
        media_id = require_identifier(data, "media_id", endpoint)
        return {"media_id": media_id, "knowledge_base_id": kb_id, "folder_id": folder_id or "", "note_id": note_id, "doc_id": note_id, "title": title}

    def import_urls(self, knowledge_base_id: str, urls: list[str], *, folder_id: str | None = None) -> dict[str, Any]:
        kb_id = _non_empty(knowledge_base_id, "knowledge_base_id")
        if not isinstance(urls, list) or not 1 <= len(urls) <= 10:
            raise InputError("urls must contain between 1 and 10 values.")
        if any(not isinstance(url, str) or urlsplit(url).scheme not in {"http", "https"} or not urlsplit(url).netloc for url in urls):
            raise InputError("Each URL must be an absolute HTTP or HTTPS URL.")
        endpoint = "import_urls"
        data = self.post_write_json(endpoint, {"knowledge_base_id": kb_id, "folder_id": folder_id or kb_id, "urls": urls})
        raw = require_object(data, "results", endpoint)
        if not set(urls).issubset(raw):
            raise ApiProtocolError("IMA API import_urls result URLs did not match the request.", endpoint=endpoint, details={"field": "data.results"})
        results = []
        for index, url in enumerate(urls):
            info = raw[url]
            if not isinstance(url, str) or not isinstance(info, dict):
                raise ApiProtocolError("IMA API import_urls returned an invalid result.", endpoint=endpoint, details={"field": "data.results"})
            path = f"data.results[{index}]"
            code = require_int(info, "ret_code", endpoint, path)
            media_id = optional_string(info, "media_id", endpoint, path)
            if code == 0 and not media_id:
                raise ApiProtocolError("IMA API import_urls success result is missing media_id.", endpoint=endpoint, details={"field": "data.results.media_id"})
            results.append(ImportUrlResult(url, code, media_id))
        return {"results": results, "knowledge_base_id": kb_id, "folder_id": folder_id or ""}

    def check_repeated_names(self, knowledge_base_id: str, params: list[dict[str, Any]], *, folder_id: str | None = None) -> list[RepeatedNameResult]:
        if not isinstance(params, list) or not 1 <= len(params) <= 2000:
            raise InputError("params must contain between 1 and 2000 entries.")
        payload: dict[str, Any] = {"params": params, "knowledge_base_id": _non_empty(knowledge_base_id, "knowledge_base_id")}
        if folder_id: payload["folder_id"] = folder_id
        endpoint = "check_repeated_names"
        raw = require_array(self.post_write_json(endpoint, payload), "results", endpoint)
        results = []
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                raise ApiProtocolError("IMA API check_repeated_names returned an invalid result.", endpoint=endpoint, details={"field": f"data.results[{i}]"})
            results.append(RepeatedNameResult(require_non_empty_string(item, "name", endpoint, f"data.results[{i}]"), require_bool(item, "is_repeated", endpoint, f"data.results[{i}]")))
        requested_names = [item.get("name") for item in params]
        returned_names = [item.name for item in results]
        if len(set(returned_names)) != len(returned_names) or set(returned_names) != set(requested_names):
            raise ApiProtocolError("IMA API repeated-name results did not match the request.", endpoint=endpoint, details={"field": "data.results"})
        by_name = {item.name: item for item in results}
        results = [by_name[name] for name in requested_names]
        return results

    def create_media(self, knowledge_base_id: str, *, file_name: str, file_size: int, content_type: str, file_ext: str) -> dict[str, Any]:
        endpoint = "create_media"
        data = self.post_write_json(endpoint, {"file_name": file_name, "file_size": file_size, "content_type": content_type,
                                                    "knowledge_base_id": _non_empty(knowledge_base_id, "knowledge_base_id"), "file_ext": file_ext})
        return {"media_id": require_identifier(data, "media_id", endpoint),
                "cos_credential": self._parse_cos(require_object(data, "cos_credential", endpoint), endpoint)}

    def add_file(self, knowledge_base_id: str, *, media_type: int, media_id: str, title: str, file_info: dict[str, Any], folder_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"media_type": media_type, "media_id": _non_empty(media_id, "media_id"), "title": title,
                                   "knowledge_base_id": _non_empty(knowledge_base_id, "knowledge_base_id"), "file_info": file_info}
        if folder_id: payload["folder_id"] = folder_id
        endpoint = "add_knowledge"
        data = self.post_write_json(endpoint, payload)
        returned = require_identifier(data, "media_id", endpoint)
        return {"media_id": returned, "knowledge_base_id": knowledge_base_id, "folder_id": folder_id or "", "title": title}

    def get_media_info(self, media_id: str) -> MediaInfo:
        media_id = _non_empty(media_id, "media_id")
        endpoint = "get_media_info"
        data = self.post_read_json(endpoint, {"media_id": media_id})
        media_type = require_int(data, "media_type", endpoint)
        note_ext, url_info = optional_object(data, "notebook_ext_info", endpoint), optional_object(data, "url_info", endpoint)
        if media_type == 11:
            if url_info is not None or note_ext is None:
                field = "data.url_info" if url_info is not None else "data.notebook_ext_info"
                raise ApiProtocolError("IMA API get_media_info returned conflicting note media metadata.", endpoint=endpoint, details={"field": field})
            return MediaInfo(media_id, media_type, "note", require_identifier(note_ext, "notebook_id", endpoint, "data.notebook_ext_info"))
        if note_ext is not None:
            raise ApiProtocolError("IMA API get_media_info returned conflicting media metadata.", endpoint=endpoint, details={"field": "data.notebook_ext_info"})
        if url_info is None:
            return MediaInfo(media_id, media_type, "unavailable")
        url = require_non_empty_string(url_info, "url", endpoint, "data.url_info")
        try:
            validate_media_source_url(url)
        except InputError as exc:
            raise ApiProtocolError("IMA API get_media_info returned an unsafe media URL.", endpoint=endpoint, details={"field": "data.url_info.url"}) from exc
        headers = {} if url_info.get("headers") is None else require_string_map(url_info, "headers", endpoint, "data.url_info")
        access = MediaAccessInfo(url, headers, safe_url_host(url), tuple(sorted(headers, key=str.lower)))
        return MediaInfo(media_id, media_type, "url", access=access)

    @staticmethod
    def _dict(item: Any, endpoint: str, path: str) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise ApiProtocolError(f"IMA API endpoint {endpoint} returned invalid {path}.", endpoint=endpoint, details={"field": path})
        return item

    @classmethod
    def _parse_kb_summary(cls, value: Any, endpoint: str, path: str, cover_optional: bool = False) -> KnowledgeBaseSummary:
        item = cls._dict(value, endpoint, path)
        return KnowledgeBaseSummary(require_identifier(item, "id", endpoint, path), require_non_empty_string(item, "name", endpoint, path), optional_string(item, "cover_url", endpoint, path) if cover_optional else require_non_empty_string(item, "cover_url", endpoint, path))

    @classmethod
    def _parse_kb_detail(cls, value: Any, endpoint: str, path: str) -> KnowledgeBaseResult:
        item = cls._dict(value, endpoint, path)
        questions = require_array(item, "recommended_questions", endpoint, path)
        if not all(isinstance(v, str) for v in questions):
            raise ApiProtocolError("IMA API returned invalid recommended questions.", endpoint=endpoint, details={"field": f"{path}.recommended_questions"})
        return KnowledgeBaseResult(require_identifier(item, "id", endpoint, path), require_non_empty_string(item, "name", endpoint, path), optional_string(item, "cover_url", endpoint, path), optional_string(item, "description", endpoint, path), tuple(questions))

    @classmethod
    def _parse_path(cls, value: Any, endpoint: str, path: str) -> KnowledgePathNode:
        item = cls._dict(value, endpoint, path)
        return KnowledgePathNode(require_identifier(item, "folder_id", endpoint, path), require_non_empty_string(item, "name", endpoint, path))

    @classmethod
    def _parse_entry(cls, value: Any, endpoint: str, path: str) -> KnowledgeEntry:
        item = cls._dict(value, endpoint, path)
        is_folder = "folder_id" in item
        if is_folder:
            return KnowledgeEntry("folder", require_identifier(item, "folder_id", endpoint, path), require_non_empty_string(item, "name", endpoint, path), optional_string(item, "parent_folder_id", endpoint, path), optional_string(item, "highlight_content", endpoint, path), optional_int(item, "file_number", endpoint, path), optional_int(item, "folder_number", endpoint, path), require_bool(item, "is_top", endpoint, path) if "is_top" in item else None)
        return KnowledgeEntry("file", require_identifier(item, "media_id", endpoint, path), require_non_empty_string(item, "title", endpoint, path), optional_string(item, "parent_folder_id", endpoint, path), optional_string(item, "highlight_content", endpoint, path), None, None, None)

    @staticmethod
    def _parse_cos(item: dict[str, Any], endpoint: str) -> CosCredential:
        path = "data.cos_credential"
        return CosCredential(require_non_empty_string(item, "token", endpoint, path), require_non_empty_string(item, "secret_id", endpoint, path), require_non_empty_string(item, "secret_key", endpoint, path), require_int(item, "start_time", endpoint, path), require_int(item, "expired_time", endpoint, path), require_non_empty_string(item, "appid", endpoint, path), require_non_empty_string(item, "bucket_name", endpoint, path), require_non_empty_string(item, "region", endpoint, path), optional_string(item, "custom_domain", endpoint, path), require_non_empty_string(item, "cos_key", endpoint, path))
