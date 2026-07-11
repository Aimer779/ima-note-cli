from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Any

from .errors import InputError, LocalIOError, MediaUnavailableError
from .knowledge_api import MediaInfo
from .source_http import SourceHttpClient


@dataclass(frozen=True)
class MediaReadResult:
    media_id: str
    media_type: int
    source_kind: str
    content: str
    content_type: str


@dataclass(frozen=True)
class MediaExportResult:
    media_id: str
    media_type: int
    source_kind: str
    output: str
    bytes_count: int
    sha256: str
    content_type: str


class _HashingWriter:
    def __init__(self, target: Any) -> None:
        self.target = target
        self.digest = hashlib.sha256()

    def write(self, value: bytes) -> int:
        self.digest.update(value)
        return self.target.write(value)


class MediaContentService:
    def __init__(self, knowledge_client: Any, notes_client: Any, source_client: SourceHttpClient) -> None:
        self.knowledge = knowledge_client
        self.notes = notes_client
        self.source = source_client

    def inspect_media(self, media_id: str) -> MediaInfo:
        return self.knowledge.get_media_info(media_id)

    def read_media(self, media_id: str) -> MediaReadResult:
        info = self.inspect_media(media_id)
        if info.source_kind == "unavailable":
            raise MediaUnavailableError("The original content is not available through the API.", endpoint="get_media_info")
        if info.source_kind == "note":
            if not info.note_id:
                raise MediaUnavailableError("Note media metadata is incomplete.")
            content = self._note_content(info.note_id)
            return MediaReadResult(info.media_id, info.media_type, "note", content, "text/markdown; charset=utf-8")
        if not info.access:
            raise MediaUnavailableError("URL media metadata is incomplete.")
        result = self.source.read_text(info.access)
        return MediaReadResult(info.media_id, info.media_type, "url", result.content, result.content_type)

    def export_media(self, media_id: str, output: str | Path, *, force: bool = False) -> MediaExportResult:
        info = self.inspect_media(media_id)
        if info.source_kind == "unavailable":
            raise MediaUnavailableError("The original content is not available through the API.", endpoint="get_media_info")
        target = Path(output).expanduser()
        if target.is_symlink() or target.is_dir():
            raise InputError("The export target must be a regular file path.")
        if target.exists() and not force:
            raise InputError("The export target already exists; use --force to replace it.", code="output_exists")
        if not target.parent.is_dir():
            raise InputError("The export target parent directory does not exist.")
        temp_path: Path | None = None
        try:
            fd, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
            temp_path = Path(name)
            with os.fdopen(fd, "wb") as raw:
                writer = _HashingWriter(raw)
                if info.source_kind == "note":
                    if not info.note_id:
                        raise MediaUnavailableError("Note media metadata is incomplete.")
                    encoded = self._note_content(info.note_id).encode("utf-8", errors="strict")
                    writer.write(encoded)
                    count, content_type = len(encoded), "text/markdown; charset=utf-8"
                else:
                    if not info.access:
                        raise MediaUnavailableError("URL media metadata is incomplete.")
                    streamed = self.source.stream_to(info.access, writer)
                    count, content_type = streamed.bytes_count, streamed.content_type
                raw.flush()
                os.fsync(raw.fileno())
            if force:
                os.replace(temp_path, target)
                temp_path = None
            else:
                try:
                    os.link(temp_path, target)
                except FileExistsError as exc:
                    raise InputError("The export target already exists; use --force to replace it.", code="output_exists") from exc
                temp_path.unlink()
                temp_path = None
            return MediaExportResult(info.media_id, info.media_type, info.source_kind, str(target), count, writer.digest.hexdigest(), content_type)
        except (InputError, MediaUnavailableError, LocalIOError):
            raise
        except (OSError, UnicodeError) as exc:
            raise LocalIOError("The media export could not be written.", code="media_export_failed") from exc
        finally:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except OSError:
                    pass

    def _note_content(self, note_id: str) -> str:
        result = self.notes.get_doc_content(note_id)
        if isinstance(result, dict):
            content = result.get("content")
        else:
            content = result
        if not isinstance(content, str):
            raise MediaUnavailableError("Note content response is invalid.", code="note_content_invalid")
        return content
