from __future__ import annotations

from dataclasses import dataclass
from email.message import Message
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import unquote, urlsplit

from .command_result import CommandResult
from .errors import ImaCliError, InputError, RemoteFetchError
from .knowledge_upload import CONTENT_TYPE_ALIASES, DEFAULT_SIZE_LIMIT, EXTENSION_MAP, SIZE_LIMITS
from .remote_http import RemoteHttpClient, RemoteResponseInfo
from .security import safe_url

_HTML = {"text/html", "application/xhtml+xml"}
_UNSUPPORTED_HOSTS = {"youtube.com", "www.youtube.com", "youtu.be", "bilibili.com", "www.bilibili.com", "b23.tv"}
_INVALID_FILENAME = re.compile(r'[\x00-\x1f\x7f<>:"/\\|?*]+')
_WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


@dataclass(frozen=True)
class UrlClassification:
    route: str
    safe_url: str
    file_name: str | None = None
    content_type: str = ""
    warnings: tuple[str, ...] = ()


def classify_response(info: RemoteResponseInfo) -> UrlClassification:
    parsed = urlsplit(info.final_url)
    host = (parsed.hostname or "").lower()
    if host in _UNSUPPORTED_HOSTS or any(host.endswith("." + item) for item in _UNSUPPORTED_HOSTS):
        return UrlClassification("unsupported", safe_url(info.final_url))
    if host == "mp.weixin.qq.com":
        return UrlClassification("web", safe_url(info.final_url), content_type=info.content_type)
    content_type = info.content_type
    if content_type in _HTML:
        return UrlClassification("web", safe_url(info.final_url), content_type=content_type)
    raw_name = _disposition_filename(info.headers.get("content-disposition", "")) or unquote(Path(parsed.path).name)
    file_name = sanitize_filename(raw_name) if raw_name else None
    ext = Path(file_name or "").suffix[1:].lower()
    supported_mimes = {mime for _, mime in EXTENSION_MAP.values()} | set(CONTENT_TYPE_ALIASES)
    mime_file = content_type in supported_mimes
    if content_type == "application/octet-stream":
        mime_file = ext in EXTENSION_MAP
    if mime_file or (not content_type and ext in EXTENSION_MAP):
        if not file_name:
            raise InputError("Remote file has no usable filename.", code="remote_filename_missing")
        warnings: tuple[str, ...] = ()
        mapped = EXTENSION_MAP.get(ext)
        if mapped and content_type and content_type not in {mapped[1], "application/octet-stream"}:
            warnings = ("Remote Content-Type conflicts with the filename extension.",)
        return UrlClassification("file", safe_url(info.final_url), file_name, content_type, warnings)
    return UrlClassification("unsupported", safe_url(info.final_url), file_name, content_type)


def sanitize_filename(value: str) -> str:
    name = _INVALID_FILENAME.sub("_", Path(value).name).strip(" .")
    if not name:
        raise InputError("Remote filename is unsafe.", code="unsafe_remote_filename")
    stem = Path(name).stem.upper()
    if stem in _WINDOWS_RESERVED:
        name = "_" + name
    if len(name) > 1024:
        suffix = Path(name).suffix
        name = name[: 1024 - len(suffix)] + suffix
    return name


def _disposition_filename(value: str) -> str:
    if not value:
        return ""
    message = Message()
    message["content-disposition"] = value
    filename = message.get_filename() or ""
    return filename


class UrlIngestService:
    def __init__(self, knowledge: Any, upload_service: Any, remote: RemoteHttpClient | None = None) -> None:
        self.knowledge = knowledge
        self.upload_service = upload_service
        self.remote = remote or RemoteHttpClient()

    def ingest(
        self, knowledge_base_id: str, urls: list[str], *, folder_id: str | None = None,
        on_conflict: str = "error", download_timeout: int = 300, upload_timeout: int = 300,
    ) -> CommandResult:
        if not 1 <= len(urls) <= 10:
            raise InputError("--url must be provided between 1 and 10 times.")
        classified: list[tuple[int, str, UrlClassification]] = []
        warnings: list[str] = []
        results: list[dict[str, Any] | None] = [None] * len(urls)
        for index, url in enumerate(urls):
            host = (urlsplit(url).hostname or "").lower()
            if host in _UNSUPPORTED_HOSTS or any(host.endswith("." + item) for item in _UNSUPPORTED_HOSTS):
                error = InputError("URL content type is not supported.", code="unsupported_url_type")
                results[index] = _failed(index, "unsupported", safe_url(url), "probe", error)
                continue
            try:
                classification = classify_response(self.remote.probe(url, timeout=download_timeout))
                if classification.route == "unsupported":
                    raise InputError("URL content type is not supported.", code="unsupported_url_type")
                classified.append((index, url, classification))
                warnings.extend(classification.warnings)
            except ImaCliError as exc:
                results[index] = _failed(index, "unsupported", safe_url(url), "probe", exc)
        web_items = [(i, url, c) for i, url, c in classified if c.route == "web"]
        if web_items:
            try:
                imported = self.knowledge.import_urls(knowledge_base_id, [url for _, url, _ in web_items], folder_id=folder_id)
                values = imported["results"]
                if len(values) != len(web_items):
                    raise InputError("URL import result count did not match the request.", code="url_result_mismatch")
                for (index, _, classification), item in zip(web_items, values):
                    ok = item.ret_code == 0
                    results[index] = {
                        "input_index": index, "route": "web", "url": classification.safe_url,
                        "status": "success" if ok else "failed", "stage": "complete" if ok else "import_urls",
                        "ret_code": item.ret_code, "media_id": item.media_id,
                    }
                    if not ok:
                        results[index]["error"] = {"code": "url_import_failed", "retryable": False}
            except ImaCliError as exc:
                for index, _, classification in web_items:
                    results[index] = _failed(index, "web", classification.safe_url, "import_urls", exc)
        for index, url, classification in classified:
            if classification.route != "file":
                continue
            try:
                with TemporaryDirectory(prefix="ima-download-") as directory:
                    path = Path(directory) / (classification.file_name or "download")
                    self.remote.download(url, path, max_bytes=_classification_limit(classification), timeout=download_timeout)
                    uploaded = self.upload_service.upload_one(
                        knowledge_base_id, str(path), folder_id=folder_id, content_type=classification.content_type or None,
                        on_conflict=on_conflict, timeout=upload_timeout
                    )
                    results[index] = {"input_index": index, "route": "file", "url": classification.safe_url, **uploaded}
                    if classification.warnings:
                        results[index]["warnings"] = list(classification.warnings)
            except ImaCliError as exc:
                results[index] = _failed(index, "file", classification.safe_url, "download", exc)
        final = [item for item in results if item is not None]
        lines = tuple(
            f"{item['input_index'] + 1}. {item['route']} {item['status']} ({item['stage']}): {item['url']}"
            for item in final
        )
        return CommandResult.batch(final, payload={"knowledge_base_id": knowledge_base_id}, human_lines=lines, warnings=tuple(warnings))


def _failed(index: int, route: str, url: str, stage: str, error: ImaCliError) -> dict[str, Any]:
    return {
        "input_index": index, "route": route, "url": url, "status": "failed", "stage": stage,
        "ret_code": None, "media_id": "", "error": {"code": error.code, "retryable": error.retryable},
    }


def _classification_limit(classification: UrlClassification) -> int:
    extension = Path(classification.file_name or "").suffix[1:].lower()
    mapping = EXTENSION_MAP.get(extension)
    if classification.content_type:
        for media_type, content_type in EXTENSION_MAP.values():
            if content_type == classification.content_type:
                return SIZE_LIMITS.get(media_type, DEFAULT_SIZE_LIMIT)
    return SIZE_LIMITS.get(mapping[0], DEFAULT_SIZE_LIMIT) if mapping else DEFAULT_SIZE_LIMIT
