from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from collections.abc import Mapping
import os

from .errors import ConfigError


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


@dataclass(frozen=True)
class CredentialResolution:
    status: CredentialStatus

    def require_credentials(self) -> Credentials:
        status = self.status
        if status.is_configured:
            return Credentials(
                client_id=status.client_id,
                api_key=status.api_key,
                client_id_source=status.client_id_source or "unknown",
                api_key_source=status.api_key_source or "unknown",
            )
        missing = []
        if not status.client_id:
            missing.append("IMA_OPENAPI_CLIENTID")
        if not status.api_key:
            missing.append("IMA_OPENAPI_APIKEY")
        raise ConfigError(
            "Missing IMA credentials: " + ", ".join(missing) + ". Configure environment, .env, or ~/.config/ima files."
        )


def _read_text(path: Path, *, optional: bool) -> str:
    try:
        if optional and not path.exists():
            return ""
        if not path.is_file():
            raise ConfigError("A credential configuration path is not a regular file.")
        return path.read_text(encoding="utf-8")
    except ConfigError:
        raise
    except (OSError, UnicodeError) as exc:
        raise ConfigError("A credential configuration file could not be read as UTF-8.") from exc


def parse_dotenv(dotenv_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    text = _read_text(dotenv_path, optional=True)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip()
        if not key:
            continue
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        values[key] = value
    return values


def resolve_credentials(
    cwd: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    config_dir: Path | None = None,
) -> CredentialResolution:
    root = cwd or Path.cwd()
    environment = os.environ if env is None else env
    if config_dir is not None:
        user_dir: Path | None = config_dir
    else:
        try:
            user_dir = Path.home() / ".config" / "ima"
        except RuntimeError:
            user_dir = None
    dotenv = parse_dotenv(root / ".env")
    user_client_id = _read_text(user_dir / "client_id", optional=True).strip() if user_dir else ""
    user_api_key = _read_text(user_dir / "api_key", optional=True).strip() if user_dir else ""

    env_client_id = environment.get("IMA_OPENAPI_CLIENTID", "").strip()
    env_api_key = environment.get("IMA_OPENAPI_APIKEY", "").strip()
    dot_client_id = dotenv.get("IMA_OPENAPI_CLIENTID", "").strip()
    dot_api_key = dotenv.get("IMA_OPENAPI_APIKEY", "").strip()

    client_id, client_source = _select(env_client_id, dot_client_id, user_client_id)
    api_key, api_source = _select(env_api_key, dot_api_key, user_api_key)
    return CredentialResolution(CredentialStatus(client_id, api_key, client_source, api_source))


def inspect_credentials(
    cwd: Path | None = None, *, env: Mapping[str, str] | None = None, config_dir: Path | None = None,
) -> CredentialStatus:
    return resolve_credentials(cwd, env=env, config_dir=config_dir).status


def load_credentials(
    cwd: Path | None = None, *, resolution: CredentialResolution | None = None,
    env: Mapping[str, str] | None = None, config_dir: Path | None = None,
) -> Credentials:
    return (resolution or resolve_credentials(cwd, env=env, config_dir=config_dir)).require_credentials()


def _select(env_value: str, dotenv_value: str, user_value: str) -> tuple[str, str | None]:
    if env_value:
        return env_value, "environment"
    if dotenv_value:
        return dotenv_value, "project_dotenv"
    if user_value:
        return user_value, "user_config"
    return "", None


__all__ = [
    "ConfigError", "CredentialResolution", "CredentialStatus", "Credentials", "inspect_credentials",
    "load_credentials", "parse_dotenv", "resolve_credentials",
]
