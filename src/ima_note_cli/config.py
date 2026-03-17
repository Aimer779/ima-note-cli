from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


class ConfigError(RuntimeError):
    """Raised when required CLI configuration is missing."""


@dataclass(frozen=True)
class CredentialStatus:
    client_id: str
    api_key: str
    client_id_source: str | None
    api_key_source: str | None

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.api_key)


@dataclass(frozen=True)
class Credentials:
    client_id: str
    api_key: str
    client_id_source: str
    api_key_source: str


def parse_dotenv(dotenv_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not dotenv_path.is_file():
        return values

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value

    return values


def inspect_credentials(cwd: Path | None = None) -> CredentialStatus:
    root = cwd or Path.cwd()
    dotenv_values = parse_dotenv(root / ".env")

    env_client_id = os.environ.get("IMA_OPENAPI_CLIENTID", "").strip()
    env_api_key = os.environ.get("IMA_OPENAPI_APIKEY", "").strip()
    dotenv_client_id = dotenv_values.get("IMA_OPENAPI_CLIENTID", "").strip()
    dotenv_api_key = dotenv_values.get("IMA_OPENAPI_APIKEY", "").strip()

    client_id = env_client_id or dotenv_client_id
    api_key = env_api_key or dotenv_api_key

    client_id_source = _detect_source(env_client_id, dotenv_client_id)
    api_key_source = _detect_source(env_api_key, dotenv_api_key)

    return CredentialStatus(
        client_id=client_id,
        api_key=api_key,
        client_id_source=client_id_source,
        api_key_source=api_key_source,
    )


def load_credentials(cwd: Path | None = None) -> Credentials:
    status = inspect_credentials(cwd)

    if status.is_configured:
        return Credentials(
            client_id=status.client_id,
            api_key=status.api_key,
            client_id_source=status.client_id_source or "unknown",
            api_key_source=status.api_key_source or "unknown",
        )

    missing: list[str] = []
    if not status.client_id:
        missing.append("IMA_OPENAPI_CLIENTID")
    if not status.api_key:
        missing.append("IMA_OPENAPI_APIKEY")

    missing_text = ", ".join(missing)
    raise ConfigError(
        "Missing IMA credentials: "
        f"{missing_text}. Set them in the environment or a project-root .env file."
    )


def _detect_source(env_value: str, dotenv_value: str) -> str | None:
    if env_value:
        return "environment"
    if dotenv_value:
        return ".env"
    return None
