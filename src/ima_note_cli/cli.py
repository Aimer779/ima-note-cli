from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from typing import Sequence

from .config import CredentialStatus, Credentials, inspect_credentials, load_credentials
from .errors import ConfigError, ImaCliError, InputError
from .knowledge_api import KnowledgeBaseApiClient
from .knowledge_cli import add_kb_subcommands
from .media_service import MediaContentService
from .notes_api import NotesApiClient
from .notes_cli import add_note_subcommands
from .output import emit_command_result, emit_human_error, emit_json_error
from .source_http import SourceHttpClient
from .command_result import CommandResult
from .commands.notes import execute as execute_note
from .commands.knowledge import execute as execute_knowledge
from .upload_service import UploadService
from .url_ingest import UrlIngestService
from .validation import validate_max_pages, validate_timeout


class CliArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise InputError(message, code="usage_error")


def build_parser(*, prog: str = "ima") -> argparse.ArgumentParser:
    parser = CliArgumentParser(
        prog=prog,
        description="Manage IMA notes and knowledge bases from the command line.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_parser = subparsers.add_parser("auth", help="Check whether IMA credentials are configured.")
    auth_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")

    note_parser = subparsers.add_parser("note", help="Manage IMA notes.")
    add_note_subcommands(note_parser.add_subparsers(dest="note_action", required=True))

    kb_parser = subparsers.add_parser("kb", help="Manage IMA knowledge bases.")
    add_kb_subcommands(kb_parser.add_subparsers(dest="kb_action", required=True))

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    argv_list = list(argv) if argv is not None else list(sys.argv[1:])
    as_json = "--json" in argv_list
    command_name = _command_name(argv_list)
    parser = build_parser()
    try:
        args = parser.parse_args(argv_list)
        if hasattr(args, "max_pages"):
            validate_max_pages(args.max_pages)
        if hasattr(args, "download_timeout"):
            validate_timeout(args.download_timeout, "--download-timeout")
        if hasattr(args, "upload_timeout"):
            validate_timeout(args.upload_timeout, "--upload-timeout")
        command_name = _command_name_from_args(args)
        status = inspect_credentials(Path.cwd())
        if args.command == "auth":
            if not status.is_configured:
                if not as_json:
                    result = auth_result(status)
                    emit_command_result(command_name, result, as_json=False)
                    return 3
                raise ConfigError("IMA credentials are not fully configured.")
            return emit_command_result(command_name, auth_result(status), as_json=as_json)

        if not status.is_configured:
            raise ConfigError("IMA credentials are not fully configured.")
        credentials = Credentials(
            status.client_id, status.api_key,
            status.client_id_source or "unknown", status.api_key_source or "unknown",
        )
        if args.command == "note":
            return emit_command_result(command_name, execute_note(args, NotesApiClient(credentials)), as_json=as_json)
        if args.command == "kb":
            knowledge = KnowledgeBaseApiClient(credentials)
            media_service = None
            if args.kb_action in {"media-info", "read", "export"}:
                media_service = MediaContentService(knowledge, NotesApiClient(credentials), SourceHttpClient())
            upload = UploadService(knowledge)
            url_service = UrlIngestService(knowledge, upload)
            result = execute_knowledge(args, knowledge, media_service=media_service, upload_service=upload, url_service=url_service)
            return emit_command_result(command_name, result, as_json=as_json)
        raise InputError("Unknown command.")
    except KeyboardInterrupt:
        error = ImaCliError("Interrupted.", code="interrupted", exit_code=130)
    except ImaCliError as exc:
        error = exc
    except Exception:
        error = ImaCliError("An unexpected internal error occurred.", code="internal_error", exit_code=70)
    if as_json:
        emit_json_error(command_name, error)
    else:
        emit_human_error(error)
    return error.exit_code


def _command_name(argv: Sequence[str]) -> str:
    values = [value for value in argv if not value.startswith("-")]
    if not values:
        return "cli"
    if values[0] in {"note", "kb"} and len(values) > 1:
        return f"{values[0]}.{values[1]}"
    return values[0] if values[0] in {"auth"} else "cli"


def _command_name_from_args(args: argparse.Namespace) -> str:
    if args.command == "note":
        return f"note.{args.note_action}"
    if args.command == "kb":
        return f"kb.{args.kb_action}"
    return args.command


def run_note_legacy(argv: Sequence[str] | None = None) -> int:
    argv_list = list(argv) if argv is not None else list(sys.argv[1:])
    if argv_list and argv_list[0] == "auth":
        return run(argv_list)
    return run(["note", *argv_list])


def auth_result(status: CredentialStatus) -> CommandResult:
    environment_check = inspect_runtime_environment()
    payload = {
        "configured": status.is_configured,
        "credentials": {
            "IMA_OPENAPI_CLIENTID": {
                "set": bool(status.client_id),
                "source": status.client_id_source,
            },
            "IMA_OPENAPI_APIKEY": {
                "set": bool(status.api_key),
                "source": status.api_key_source,
            },
        },
        "environment_check": environment_check,
    }

    lines = [f"Status: {'configured' if status.is_configured else 'missing credentials'}"]
    lines.append(
        "IMA_OPENAPI_CLIENTID: "
        f"{'set' if status.client_id else 'missing'}"
        f"{format_source_suffix(status.client_id_source)}"
    )
    lines.append(
        "IMA_OPENAPI_APIKEY: "
        f"{'set' if status.api_key else 'missing'}"
        f"{format_source_suffix(status.api_key_source)}"
    )
    if environment_check["platform"] == "windows" and not environment_check["ok"]:
        lines.extend(environment_check_lines(environment_check))
    warnings = () if status.is_configured else ("Configure the missing values in the environment, project .env, or ~/.config/ima files.",)
    return CommandResult(payload, tuple(lines), warnings)


def format_source_suffix(source: str | None) -> str:
    if not source:
        return ""
    return f" ({source})"


def inspect_runtime_environment() -> dict[str, object]:
    platform_name = "windows" if sys.platform.startswith("win") else sys.platform
    if platform_name != "windows":
        return {
            "platform": platform_name,
            "shell": "unknown",
            "ok": True,
            "missing": [],
        }

    missing: list[str] = []
    if os.environ.get("PYTHONUTF8") != "1":
        missing.append("PYTHONUTF8")

    pythonioencoding = os.environ.get("PYTHONIOENCODING", "")
    if pythonioencoding.lower() != "utf-8":
        missing.append("PYTHONIOENCODING")

    return {
        "platform": "windows",
        "shell": detect_windows_shell(),
        "ok": not missing,
        "missing": missing,
    }


def detect_windows_shell() -> str:
    if os.environ.get("PSModulePath"):
        return "powershell"

    comspec_name = Path(os.environ.get("ComSpec", "")).name.lower()
    if comspec_name == "cmd.exe":
        return "cmd"
    return "unknown"


def environment_check_lines(environment_check: dict[str, object]) -> list[str]:
    lines = ["", "Environment: warning", "Windows terminal encoding may cause garbled output."]
    if environment_check["shell"] == "powershell":
        lines.append('Set PowerShell session variables: `$env:PYTHONUTF8="1"` and `$env:PYTHONIOENCODING="utf-8"`')
    elif environment_check["shell"] == "cmd":
        lines.append("Or in CMD: `set PYTHONUTF8=1` and `set PYTHONIOENCODING=utf-8`")
    else:
        lines.extend(['Set PowerShell session variables: `$env:PYTHONUTF8="1"` and `$env:PYTHONIOENCODING="utf-8"`', "Or in CMD: `set PYTHONUTF8=1` and `set PYTHONIOENCODING=utf-8`"])
    return lines


def handle_auth(status: CredentialStatus, as_json: bool) -> int:
    """Compatibility façade for callers that used the pre-batch-C handler."""
    return emit_command_result("auth", auth_result(status), as_json=as_json)
