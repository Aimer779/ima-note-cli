from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Credentials
from .http import ImaApiClient, maybe_int


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
    ret_code: int | None
    media_id: str


@dataclass(frozen=True)
class RepeatedNameResult:
    name: str
    is_repeated: bool


@dataclass(frozen=True)
class CosCredential:
    token: str
    secret_id: str
    secret_key: str
    start_time: int
    expired_time: int
    appid: str
    bucket_name: str
    region: str
    custom_domain: str
    cos_key: str


class KnowledgeBaseApiClient(ImaApiClient):
    def __init__(self, credentials: Credentials, timeout: int = 30) -> None:
        super().__init__(credentials, base_url=BASE_URL, timeout=timeout)

    def search_knowledge_bases(self, query: str, limit: int, *, cursor: str = "") -> dict[str, Any]:
        data = self.post_json(
            "search_knowledge_base",
            {
                "query": query,
                "cursor": cursor,
                "limit": limit,
            },
        )
        return {
            "knowledge_bases": [self._parse_kb_summary(item) for item in data.get("info_list", [])],
            "next_cursor": str(data.get("next_cursor", "")),
            "is_end": data.get("is_end"),
            "query": query,
        }

    def list_addable_knowledge_bases(self, limit: int, *, cursor: str = "") -> dict[str, Any]:
        data = self.post_json(
            "get_addable_knowledge_base_list",
            {
                "cursor": cursor,
                "limit": limit,
            },
        )
        raw_items = data.get("addable_knowledge_base_list", [])
        return {
            "knowledge_bases": [
                KnowledgeBaseSummary(
                    knowledge_base_id=str(item.get("id", "")),
                    name=str(item.get("name", "")),
                    cover_url="",
                )
                for item in raw_items
                if isinstance(item, dict)
            ],
            "next_cursor": str(data.get("next_cursor", "")),
            "is_end": data.get("is_end"),
        }

    def get_knowledge_bases(self, ids: list[str]) -> dict[str, KnowledgeBaseResult]:
        data = self.post_json("get_knowledge_base", {"ids": ids})
        infos = data.get("infos", {})
        if not isinstance(infos, dict):
            return {}
        results: dict[str, KnowledgeBaseResult] = {}
        for kb_id in ids:
            raw = infos.get(kb_id, {})
            if isinstance(raw, dict):
                parsed = self._parse_kb_detail(raw)
                results[parsed.knowledge_base_id or kb_id] = parsed
        return results

    def get_knowledge_base(self, knowledge_base_id: str) -> KnowledgeBaseResult | None:
        results = self.get_knowledge_bases([knowledge_base_id])
        return results.get(knowledge_base_id) or next(iter(results.values()), None)

    def list_knowledge(
        self,
        knowledge_base_id: str,
        limit: int,
        *,
        cursor: str = "",
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "knowledge_base_id": knowledge_base_id,
            "cursor": cursor,
            "limit": limit,
        }
        if folder_id:
            payload["folder_id"] = folder_id
        data = self.post_json("get_knowledge_list", payload)
        return {
            "items": [self._parse_entry(item) for item in data.get("knowledge_list", [])],
            "next_cursor": str(data.get("next_cursor", "")),
            "is_end": data.get("is_end"),
            "current_path": [self._parse_path_node(item) for item in data.get("current_path", [])],
            "knowledge_base_id": knowledge_base_id,
            "folder_id": folder_id or "",
        }

    def search_knowledge(self, query: str, knowledge_base_id: str, *, cursor: str = "") -> dict[str, Any]:
        data = self.post_json(
            "search_knowledge",
            {
                "query": query,
                "knowledge_base_id": knowledge_base_id,
                "cursor": cursor,
            },
        )
        return {
            "items": [self._parse_entry(item) for item in data.get("info_list", [])],
            "next_cursor": str(data.get("next_cursor", "")),
            "is_end": data.get("is_end"),
            "query": query,
            "knowledge_base_id": knowledge_base_id,
        }

    def add_note(self, knowledge_base_id: str, doc_id: str, *, title: str, folder_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "media_type": 11,
            "title": title,
            "knowledge_base_id": knowledge_base_id,
            "note_info": {"content_id": doc_id},
        }
        if folder_id:
            payload["folder_id"] = folder_id
        data = self.post_json("add_knowledge", payload)
        return {
            "media_id": str(data.get("media_id", "")),
            "knowledge_base_id": knowledge_base_id,
            "folder_id": folder_id or "",
            "doc_id": doc_id,
            "title": title,
        }

    def import_urls(self, knowledge_base_id: str, urls: list[str], *, folder_id: str | None = None) -> dict[str, Any]:
        data = self.post_json(
            "import_urls",
            {
                "knowledge_base_id": knowledge_base_id,
                "folder_id": folder_id or knowledge_base_id,
                "urls": urls,
            },
        )
        raw_results = data.get("results", {})
        results: list[ImportUrlResult] = []
        if isinstance(raw_results, dict):
            for url, info in raw_results.items():
                result_info = info if isinstance(info, dict) else {}
                results.append(
                    ImportUrlResult(
                        url=str(url),
                        ret_code=maybe_int(result_info.get("ret_code")),
                        media_id=str(result_info.get("media_id", "")),
                    )
                )
        return {
            "results": results,
            "knowledge_base_id": knowledge_base_id,
            "folder_id": folder_id or "",
        }

    def check_repeated_names(
        self,
        knowledge_base_id: str,
        params: list[dict[str, Any]],
        *,
        folder_id: str | None = None,
    ) -> list[RepeatedNameResult]:
        payload: dict[str, Any] = {
            "params": params,
            "knowledge_base_id": knowledge_base_id,
        }
        if folder_id:
            payload["folder_id"] = folder_id
        data = self.post_json("check_repeated_names", payload)
        return [
            RepeatedNameResult(
                name=str(item.get("name", "")),
                is_repeated=bool(item.get("is_repeated")),
            )
            for item in data.get("results", [])
            if isinstance(item, dict)
        ]

    def create_media(
        self,
        knowledge_base_id: str,
        *,
        file_name: str,
        file_size: int,
        content_type: str,
        file_ext: str,
    ) -> dict[str, Any]:
        data = self.post_json(
            "create_media",
            {
                "file_name": file_name,
                "file_size": file_size,
                "content_type": content_type,
                "knowledge_base_id": knowledge_base_id,
                "file_ext": file_ext,
            },
        )
        credential = data.get("cos_credential", {})
        if not isinstance(credential, dict):
            credential = {}
        return {
            "media_id": str(data.get("media_id", "")),
            "cos_credential": self._parse_cos_credential(credential),
        }

    def add_file(
        self,
        knowledge_base_id: str,
        *,
        media_type: int,
        media_id: str,
        title: str,
        file_info: dict[str, Any],
        folder_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "media_type": media_type,
            "media_id": media_id,
            "title": title,
            "knowledge_base_id": knowledge_base_id,
            "file_info": file_info,
        }
        if folder_id:
            payload["folder_id"] = folder_id
        data = self.post_json("add_knowledge", payload)
        return {
            "media_id": str(data.get("media_id", media_id)),
            "knowledge_base_id": knowledge_base_id,
            "folder_id": folder_id or "",
            "title": title,
        }

    @staticmethod
    def _parse_kb_summary(item: dict[str, Any]) -> KnowledgeBaseSummary:
        return KnowledgeBaseSummary(
            knowledge_base_id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            cover_url=str(item.get("cover_url", "")),
        )

    @staticmethod
    def _parse_kb_detail(item: dict[str, Any]) -> KnowledgeBaseResult:
        questions = item.get("recommended_questions", [])
        if not isinstance(questions, list):
            questions = []
        return KnowledgeBaseResult(
            knowledge_base_id=str(item.get("id", "")),
            name=str(item.get("name", "")),
            cover_url=str(item.get("cover_url", "")),
            description=str(item.get("description", "")),
            recommended_questions=tuple(str(q) for q in questions),
        )

    @staticmethod
    def _parse_path_node(item: dict[str, Any]) -> KnowledgePathNode:
        return KnowledgePathNode(
            folder_id=str(item.get("folder_id", "")),
            name=str(item.get("name", "")),
        )

    @staticmethod
    def _parse_entry(item: dict[str, Any]) -> KnowledgeEntry:
        if not isinstance(item, dict):
            return KnowledgeEntry("file", "", "", "", "", None, None, None)
        is_folder = "folder_id" in item or ("name" in item and "media_id" not in item and "title" not in item)
        if is_folder:
            return KnowledgeEntry(
                kind="folder",
                item_id=str(item.get("folder_id", "")),
                title=str(item.get("name", "")),
                parent_folder_id=str(item.get("parent_folder_id", "")),
                highlight_content=str(item.get("highlight_content", "")),
                file_number=maybe_int(item.get("file_number")),
                folder_number=maybe_int(item.get("folder_number")),
                is_top=bool(item["is_top"]) if "is_top" in item else None,
            )
        return KnowledgeEntry(
            kind="file",
            item_id=str(item.get("media_id", "")),
            title=str(item.get("title", "")),
            parent_folder_id=str(item.get("parent_folder_id", "")),
            highlight_content=str(item.get("highlight_content", "")),
            file_number=None,
            folder_number=None,
            is_top=None,
        )

    @staticmethod
    def _parse_cos_credential(item: dict[str, Any]) -> CosCredential:
        return CosCredential(
            token=str(item.get("token", "")),
            secret_id=str(item.get("secret_id", "")),
            secret_key=str(item.get("secret_key", "")),
            start_time=maybe_int(item.get("start_time")) or 0,
            expired_time=maybe_int(item.get("expired_time")) or 0,
            appid=str(item.get("appid", "")),
            bucket_name=str(item.get("bucket_name", "")),
            region=str(item.get("region", "")),
            custom_domain=str(item.get("custom_domain", "")),
            cos_key=str(item.get("cos_key", "")),
        )
