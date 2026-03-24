from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import hmac
from pathlib import Path
from time import time
from typing import Any
from urllib import error, parse, request

from .http import ApiError
from .knowledge_api import CosCredential


SAFE_URI_CHARS = "-_.!~*'()"
MB = 1024 * 1024
DEFAULT_SIZE_LIMIT = 200 * MB
SIZE_LIMITS = {
    5: 10 * MB,
    7: 10 * MB,
    9: 30 * MB,
    13: 10 * MB,
    14: 10 * MB,
}
EXTENSION_MAP: dict[str, tuple[int, str]] = {
    "pdf": (1, "application/pdf"),
    "doc": (3, "application/msword"),
    "docx": (3, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    "ppt": (4, "application/vnd.ms-powerpoint"),
    "pptx": (4, "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    "xls": (5, "application/vnd.ms-excel"),
    "xlsx": (5, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    "csv": (5, "text/csv"),
    "md": (7, "text/markdown"),
    "markdown": (7, "text/markdown"),
    "png": (9, "image/png"),
    "jpg": (9, "image/jpeg"),
    "jpeg": (9, "image/jpeg"),
    "webp": (9, "image/webp"),
    "txt": (13, "text/plain"),
    "xmind": (14, "application/x-xmind"),
    "mp3": (15, "audio/mpeg"),
    "m4a": (15, "audio/x-m4a"),
    "wav": (15, "audio/wav"),
    "aac": (15, "audio/aac"),
}
CONTENT_TYPE_ALIASES = {
    "text/x-markdown": (7, "text/x-markdown"),
    "application/md": (7, "application/md"),
    "application/markdown": (7, "application/markdown"),
    "application/vnd.xmind.workbook": (14, "application/vnd.xmind.workbook"),
    "application/zip": (14, "application/zip"),
}
UNSUPPORTED_VIDEO_EXT = {"mp4", "avi", "mov", "mkv", "wmv", "flv", "webm", "m4v", "rmvb", "rm", "3gp"}
UNSUPPORTED_VIDEO_CT = {
    "video/mp4",
    "video/x-msvideo",
    "video/quicktime",
    "video/x-matroska",
    "video/x-ms-wmv",
    "video/x-flv",
    "video/webm",
}


class KnowledgeUploadError(RuntimeError):
    """Raised when the COS upload flow fails."""


@dataclass(frozen=True)
class UploadFileInfo:
    file_path: Path
    file_name: str
    file_ext: str
    file_size: int
    media_type: int
    content_type: str
    last_modify_time: int


def inspect_upload_file(file_path: str, *, content_type: str | None = None) -> UploadFileInfo:
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"File not found: {file_path}")

    ext = path.suffix[1:].lower() if path.suffix else ""
    provided_content_type = (content_type or "").strip().lower()
    if ext in UNSUPPORTED_VIDEO_EXT or provided_content_type in UNSUPPORTED_VIDEO_CT:
        raise ValueError("Video files are not supported. Only supported in the IMA desktop app.")

    resolved_media_type: int | None = None
    resolved_content_type: str | None = None
    if provided_content_type:
        if provided_content_type in CONTENT_TYPE_ALIASES:
            resolved_media_type, resolved_content_type = CONTENT_TYPE_ALIASES[provided_content_type]
        else:
            for mapped_media_type, mapped_content_type in EXTENSION_MAP.values():
                if mapped_content_type == provided_content_type:
                    resolved_media_type = mapped_media_type
                    resolved_content_type = provided_content_type
                    break

    if resolved_media_type is None:
        if not ext:
            raise ValueError("File has no extension and no supported --content-type was provided.")
        mapping = EXTENSION_MAP.get(ext)
        if mapping is None:
            raise ValueError(f"Unrecognized file extension .{ext}. This file type is not supported.")
        resolved_media_type, resolved_content_type = mapping

    stat = path.stat()
    size_limit = SIZE_LIMITS.get(resolved_media_type, DEFAULT_SIZE_LIMIT)
    if stat.st_size > size_limit:
        raise ValueError(
            f"File size {format_size(stat.st_size)} exceeds the {format_size(size_limit)} limit for this file type."
        )

    return UploadFileInfo(
        file_path=path,
        file_name=path.name,
        file_ext=ext,
        file_size=stat.st_size,
        media_type=resolved_media_type,
        content_type=resolved_content_type or provided_content_type,
        last_modify_time=int(stat.st_mtime),
    )


def upload_to_cos(file_info: UploadFileInfo, credential: CosCredential, *, timeout: int = 120) -> None:
    file_content = file_info.file_path.read_bytes()
    hostname = f"{credential.bucket_name}.cos.{credential.region}.myqcloud.com"
    pathname = f"/{credential.cos_key}"
    authorization = build_cos_authorization(
        secret_id=credential.secret_id,
        secret_key=credential.secret_key,
        method="PUT",
        pathname=pathname,
        headers={
            "content-length": str(len(file_content)),
            "host": hostname,
        },
        start_time=credential.start_time or int(time()),
        expired_time=credential.expired_time or int(time()) + 3600,
    )
    req = request.Request(
        f"https://{hostname}{pathname}",
        data=file_content,
        method="PUT",
        headers={
            "Content-Type": file_info.content_type,
            "Content-Length": str(len(file_content)),
            "Authorization": authorization,
            "x-cos-security-token": credential.token,
        },
    )
    try:
        with request.urlopen(req, timeout=timeout) as response:
            status_code = getattr(response, "status", response.getcode())
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        raise KnowledgeUploadError(f"COS upload failed (HTTP {exc.code}): {detail or exc.reason}") from exc
    except error.URLError as exc:
        raise KnowledgeUploadError(f"COS upload error: {exc.reason}") from exc

    if not 200 <= status_code < 300:
        raise ApiError(f"COS upload failed with unexpected status {status_code}.")


def build_file_info_payload(file_info: UploadFileInfo, credential: CosCredential) -> dict[str, Any]:
    return {
        "cos_key": credential.cos_key,
        "file_size": file_info.file_size,
        "last_modify_time": file_info.last_modify_time,
        "file_name": file_info.file_name,
    }


def build_cos_authorization(
    *,
    secret_id: str,
    secret_key: str,
    method: str,
    pathname: str,
    headers: dict[str, str],
    start_time: int,
    expired_time: int,
) -> str:
    key_time = f"{start_time};{expired_time}"
    sign_key = hmac_sha1(secret_key, key_time)
    header_keys = sorted(headers.keys())
    http_headers = "&".join(f"{key.lower()}={encode_uri_component(headers[key])}" for key in header_keys)
    http_string = f"{method.lower()}\n{pathname}\n\n{http_headers}\n"
    string_to_sign = f"sha1\n{key_time}\n{sha1_hex(http_string)}\n"
    signature = hmac_sha1(sign_key, string_to_sign)
    header_list = ";".join(key.lower() for key in header_keys)
    return "&".join(
        [
            "q-sign-algorithm=sha1",
            f"q-ak={secret_id}",
            f"q-sign-time={key_time}",
            f"q-key-time={key_time}",
            f"q-header-list={header_list}",
            "q-url-param-list=",
            f"q-signature={signature}",
        ]
    )


def encode_uri_component(value: str) -> str:
    return parse.quote(value, safe=SAFE_URI_CHARS)


def hmac_sha1(key: str, data: str) -> str:
    return hmac.new(key.encode("utf-8"), data.encode("utf-8"), sha1).hexdigest()


def sha1_hex(data: str) -> str:
    return sha1(data.encode("utf-8")).hexdigest()


def format_size(bytes_count: int) -> str:
    if bytes_count < MB:
        return f"{bytes_count / 1024:.1f} KB"
    return f"{bytes_count / MB:.1f} MB"
