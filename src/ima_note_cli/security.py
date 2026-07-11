from __future__ import annotations

from collections.abc import Mapping
import ipaddress
import re
from urllib.parse import urlsplit

from .errors import InputError


_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)
_TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SENSITIVE = re.compile(
    r"(?i)(authorization|cookie|ima-openapi-(?:clientid|apikey)|secret(?:_key|_id)?|security-token|"
    r"(?:sign|signature|token|key|credential)=)[^\s,;&]+"
)
_BLOCKED_HEADERS = {"host", "content-length", "transfer-encoding", "connection"}


def _valid_host(host: str) -> bool:
    return bool(host) and all(_DNS_LABEL.fullmatch(label) for label in host.split("."))


def validate_ima_base_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise InputError("IMA API base URL must be an official HTTPS service URL.", code="unsafe_ima_base_url") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname != "ima.qq.com"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") not in {"/openapi/note/v1", "/openapi/wiki/v1"}
    ):
        raise InputError("IMA API base URL must be an official HTTPS service URL.", code="unsafe_ima_base_url")
    return value.rstrip("/")


def validate_relative_endpoint(endpoint: str) -> str:
    if not isinstance(endpoint, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", endpoint):
        raise InputError("IMA API endpoint must be a simple relative endpoint name.", code="unsafe_endpoint")
    return endpoint


def build_and_validate_cos_origin(bucket_name: str, region: str) -> str:
    if not _DNS_LABEL.fullmatch(bucket_name or "") or not _DNS_LABEL.fullmatch(region or ""):
        raise InputError("COS bucket and region must be valid DNS labels.", code="unsafe_cos_origin")
    host = f"{bucket_name}.cos.{region}.myqcloud.com".lower()
    if not _valid_host(host) or not host.endswith(".myqcloud.com"):
        raise InputError("COS target must be an official HTTPS myqcloud.com host.", code="unsafe_cos_origin")
    return f"https://{host}"


def validate_media_source_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as exc:
        raise InputError("Media source URL is invalid.", code="unsafe_media_url") from exc
    host = (parsed.hostname or "").lower()
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise InputError("Media source URL cannot use an IP address.", code="unsafe_media_url")
    allowed = host == "ima.qq.com" or host.endswith(".myqcloud.com")
    if (
        parsed.scheme != "https"
        or not allowed
        or not _valid_host(host)
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or host == "localhost"
        or _CONTROL.search(value)
    ):
        raise InputError("Media source URL is outside the allowed HTTPS hosts.", code="unsafe_media_url")
    return value


def sanitize_header_map(headers: Mapping[object, object]) -> dict[str, str]:
    result: dict[str, str] = {}
    for name, value in headers.items():
        if not isinstance(name, str) or not isinstance(value, str):
            raise ValueError("Header names and values must be strings.")
        normalized = name.strip()
        if not _TOKEN.fullmatch(normalized) or normalized.lower() in _BLOCKED_HEADERS:
            raise ValueError("Header name is not allowed.")
        if _CONTROL.search(value):
            raise ValueError("Header value contains control characters.")
        result[normalized] = value
    return result


def safe_url_host(value: str) -> str:
    return (urlsplit(value).hostname or "").lower()


def redact_sensitive_text(value: object) -> str:
    text = _CONTROL.sub(" ", str(value))
    text = _SENSITIVE.sub(lambda match: f"{match.group(1)}<redacted>", text)
    text = re.sub(r"https://[^\s]+", "<redacted-url>", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()[:512]
