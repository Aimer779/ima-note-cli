from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


class ConfigError(RuntimeError):
    """Raised when required CLI configuration is missing."""


@dataclass(frozen=True)
class Credentials:
    client_id: str
    api_key: str


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


def load_credentials(cwd: Path | None = None) -> Credentials:
    root = cwd or Path.cwd()
    dotenv_values = parse_dotenv(root / ".env")

    client_id = os.environ.get("IMA_OPENAPI_CLIENTID", dotenv_values.get("IMA_OPENAPI_CLIENTID", "")).strip()
    api_key = os.environ.get("IMA_OPENAPI_APIKEY", dotenv_values.get("IMA_OPENAPI_APIKEY", "")).strip()

    if client_id and api_key:
        return Credentials(client_id=client_id, api_key=api_key)

    missing: list[str] = []
    if not client_id:
        missing.append("IMA_OPENAPI_CLIENTID")
    if not api_key:
        missing.append("IMA_OPENAPI_APIKEY")

    missing_text = ", ".join(missing)
    raise ConfigError(
        "Missing IMA credentials: "
        f"{missing_text}. Set them in the environment or a project-root .env file."
    )
