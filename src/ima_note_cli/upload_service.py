from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
import os
from pathlib import Path
from typing import Any, Callable

from .cos_http import CosHttpClient, build_cos_target
from .errors import ApiProtocolError, ImaCliError, InputError, KnowledgeUploadError
from .knowledge_api import CosCredential
from .knowledge_upload import UploadFileInfo, build_cos_authorization, build_file_info_payload, inspect_upload_file
from .validation import validate_timeout


@dataclass(frozen=True)
class FileSnapshot:
    device: int
    inode: int
    size: int
    mtime_ns: int

    @classmethod
    def from_stat(cls, stat: os.stat_result) -> "FileSnapshot":
        return cls(stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


class UploadService:
    def __init__(self, knowledge: Any, cos: CosHttpClient | None = None, *, clock: Callable[[], datetime] | None = None) -> None:
        self.knowledge = knowledge
        self.cos = cos or CosHttpClient()
        self.clock = clock or datetime.now

    def upload_many(
        self, knowledge_base_id: str, files: list[str], *, folder_id: str | None = None,
        content_type: str | None = None, on_conflict: str = "error", timeout: int = 300,
    ) -> list[dict[str, Any]]:
        if not 1 <= len(files) <= 2000:
            raise InputError("--file must be provided between 1 and 2000 times.")
        if len(files) > 1 and content_type:
            raise InputError("--content-type can only be used with one --file.")
        validate_timeout(timeout, "--upload-timeout")
        infos = [inspect_upload_file(path, content_type=content_type) for path in files]
        if len({info.file_name.casefold() for info in infos}) != len(infos):
            if on_conflict == "error":
                raise InputError("Input files contain duplicate names.", code="duplicate_input_name")
        repeated = self._repeated(knowledge_base_id, infos, folder_id)
        if on_conflict == "error" and any(repeated.values()):
            return [
                {
                    "file_name": info.file_name,
                    "status": "failed" if repeated[info.file_name] else "not_attempted",
                    "stage": "conflict_check",
                    "media_id": "",
                    **({"error": {"code": "repeated_file_name", "retryable": False}} if repeated[info.file_name] else {}),
                }
                for info in infos
            ]
        final_infos = self._resolve_conflicts(knowledge_base_id, infos, repeated, folder_id, on_conflict)
        results: list[dict[str, Any]] = []
        for position, info in enumerate(final_infos):
            try:
                results.append(self._upload_prechecked(knowledge_base_id, info, folder_id=folder_id, timeout=timeout))
            except KeyboardInterrupt:
                results.append({"file_name": info.file_name, "status": "failed", "stage": "interrupted", "media_id": "", "error": {"code": "interrupted", "retryable": False}})
                results.extend({"file_name": pending.file_name, "status": "not_attempted", "stage": "interrupted", "media_id": ""} for pending in final_infos[position + 1:])
                break
            except ImaCliError as exc:
                orphan = getattr(exc, "orphaned_media_id", "")
                results.append({
                    "file_name": info.file_name, "status": "failed",
                    "stage": getattr(exc, "failure_stage", "upload"), "media_id": orphan,
                    "orphaned_media": bool(orphan),
                    "error": {"code": exc.code, "retryable": exc.retryable},
                })
        return results

    def upload_one(self, knowledge_base_id: str, file_path: str, **kwargs: Any) -> dict[str, Any]:
        return self.upload_many(knowledge_base_id, [file_path], **kwargs)[0]

    def _repeated(self, kb_id: str, infos: list[UploadFileInfo], folder_id: str | None) -> dict[str, bool]:
        response = self.knowledge.check_repeated_names(
            kb_id, [{"name": item.file_name, "media_type": item.media_type} for item in infos], folder_id=folder_id
        )
        mapping = {item.name: item.is_repeated for item in response}
        expected = {item.file_name for item in infos}
        if set(mapping) != expected:
            raise ApiProtocolError("Repeated-name response did not match the request.", code="repeated_name_mismatch")
        return mapping

    def _resolve_conflicts(self, kb_id: str, infos: list[UploadFileInfo], repeated: dict[str, bool], folder_id: str | None, policy: str) -> list[UploadFileInfo]:
        if policy not in {"error", "rename"}:
            raise InputError("--on-conflict must be error or rename.")
        used: set[str] = set()
        output: list[UploadFileInfo] = []
        stamp = self.clock().strftime("%Y%m%d_%H%M%S")
        for info in infos:
            if not repeated[info.file_name] and info.file_name.casefold() not in used:
                output.append(info)
                used.add(info.file_name.casefold())
                continue
            for sequence in range(1, 101):
                suffix = f"_{stamp}" + (f"_{sequence}" if sequence > 1 else "")
                candidate = f"{Path(info.file_name).stem}{suffix}{Path(info.file_name).suffix}"
                if candidate.casefold() in used:
                    continue
                check = self.knowledge.check_repeated_names(kb_id, [{"name": candidate, "media_type": info.media_type}], folder_id=folder_id)
                if len(check) != 1 or check[0].name != candidate:
                    raise ApiProtocolError("Renamed repeated-name response did not match the request.")
                if not check[0].is_repeated:
                    output.append(replace(info, file_name=candidate))
                    used.add(candidate.casefold())
                    break
            else:
                raise InputError("Could not find an available renamed filename.", code="rename_exhausted")
        return output

    def _upload_prechecked(self, kb_id: str, info: UploadFileInfo, *, folder_id: str | None, timeout: int) -> dict[str, Any]:
        before = FileSnapshot.from_stat(info.file_path.stat())
        expected = FileSnapshot(info.device, info.inode, info.file_size, info.mtime_ns)
        if before != expected:
            raise KnowledgeUploadError("Local file changed before upload.", code="file_changed")
        with info.file_path.open("rb") as stream:
            opened = FileSnapshot.from_stat(os.fstat(stream.fileno()))
            if opened != before:
                raise KnowledgeUploadError("Local file changed before upload.", code="file_changed")
            created = self.knowledge.create_media(
                kb_id, file_name=info.file_name, file_size=info.file_size,
                content_type=info.content_type, file_ext=info.file_ext,
            )
            media_id = created["media_id"]
            credential: CosCredential = created["cos_credential"]
            target = build_cos_target(credential)
            authorization = build_cos_authorization(
                secret_id=credential.secret_id, secret_key=credential.secret_key, method="PUT",
                pathname=target.pathname, headers={"content-length": str(info.file_size), "host": target.host},
                start_time=credential.start_time, expired_time=credential.expired_time,
            )
            try:
                self.cos.put(stream, size=info.file_size, content_type=info.content_type, credential=credential,
                             authorization=authorization, timeout=timeout, target=target)
                after = FileSnapshot.from_stat(os.fstat(stream.fileno()))
                path_after = FileSnapshot.from_stat(info.file_path.stat())
                if after != before or path_after != before:
                    raise KnowledgeUploadError("Local file changed during upload.", code="file_changed")
                try:
                    self.knowledge.add_file(
                        kb_id, media_type=info.media_type, media_id=media_id, title=info.file_name,
                        file_info=build_file_info_payload(info, credential), folder_id=folder_id,
                    )
                except ImaCliError as exc:
                    exc.failure_stage = "add_knowledge"
                    raise
            except ImaCliError as exc:
                result = KnowledgeUploadError(exc.message, code=exc.code, retryable=exc.retryable)
                result.orphaned_media_id = media_id
                result.failure_stage = getattr(exc, "failure_stage", "cos_upload")
                raise result from exc
        return {"file_name": info.file_name, "status": "success", "stage": "complete", "media_id": media_id}
