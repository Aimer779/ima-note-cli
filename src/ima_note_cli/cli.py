from __future__ import annotations

import argparse
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from .config import CredentialStatus, Credentials, inspect_credentials, load_credentials
from .errors import ConfigError, ImaCliError, InputError
from .knowledge_api import KnowledgeBaseApiClient
from .knowledge_cli import add_kb_subcommands, handle_kb_command
from .media_service import MediaContentService
from .notes_api import NotesApiClient
from .notes_cli import add_note_subcommands, handle_note_command
from .output import emit_human_error, emit_json_error, emit_json_success
from .source_http import SourceHttpClient


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
        command_name = _command_name_from_args(args)
        status = inspect_credentials(Path.cwd())
        if args.command == "auth":
            if not status.is_configured:
                if not as_json:
                    return handle_auth(status, False)
                raise ConfigError("IMA credentials are not fully configured.")
            return _run_handler(lambda: handle_auth(status, args.as_json), command_name, as_json)

        if not status.is_configured:
            raise ConfigError("IMA credentials are not fully configured.")
        credentials = Credentials(
            status.client_id, status.api_key,
            status.client_id_source or "unknown", status.api_key_source or "unknown",
        )
        if args.command == "note":
            return _run_handler(lambda: handle_note_command(args, NotesApiClient(credentials)), command_name, as_json)
        if args.command == "kb":
            knowledge = KnowledgeBaseApiClient(credentials)
            media_service = None
            if args.kb_action in {"media-info", "read", "export"}:
                media_service = MediaContentService(knowledge, NotesApiClient(credentials), SourceHttpClient())
            return _run_handler(lambda: handle_kb_command(args, knowledge, media_service), command_name, as_json)
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


def _run_handler(callback: object, command: str, as_json: bool) -> int:
    if not as_json:
        return callback()  # type: ignore[operator]
    stdout, stderr = StringIO(), StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = callback()  # type: ignore[operator]
    if exit_code:
        raise ImaCliError("The command failed without a classified error.", code="internal_error", exit_code=70)
    raw = stdout.getvalue().strip()
    try:
        payload = json.loads(raw) if raw else {}
    except json.JSONDecodeError as exc:
        raise ImaCliError("The command produced invalid internal JSON.", code="internal_error", exit_code=70) from exc
    if not isinstance(payload, dict):
        raise ImaCliError("The command produced invalid internal JSON.", code="internal_error", exit_code=70)
    emit_json_success(command, payload)
    return 0


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


def handle_auth(status: CredentialStatus, as_json: bool) -> int:
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

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"Status: {'configured' if status.is_configured else 'missing credentials'}")
    print(
        "IMA_OPENAPI_CLIENTID: "
        f"{'set' if status.client_id else 'missing'}"
        f"{format_source_suffix(status.client_id_source)}"
    )
    print(
        "IMA_OPENAPI_APIKEY: "
        f"{'set' if status.api_key else 'missing'}"
        f"{format_source_suffix(status.api_key_source)}"
    )
    print_environment_check(environment_check)

    if status.is_configured:
        return 0

    print()
    print("Configure the missing values in the environment, project .env, or ~/.config/ima files.", file=sys.stderr)
    return 3


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


def print_environment_check(environment_check: dict[str, object]) -> None:
    if environment_check["platform"] != "windows" or environment_check["ok"]:
        return

    print()
    print("Environment: warning")
    print("Windows terminal encoding may cause garbled output.")

    shell_name = environment_check["shell"]
    if shell_name == "powershell":
        print('Set PowerShell session variables: `$env:PYTHONUTF8="1"` and `$env:PYTHONIOENCODING="utf-8"`')
        return
    if shell_name == "cmd":
        print("Or in CMD: `set PYTHONUTF8=1` and `set PYTHONIOENCODING=utf-8`")
        return

    print('Set PowerShell session variables: `$env:PYTHONUTF8="1"` and `$env:PYTHONIOENCODING="utf-8"`')
    print("Or in CMD: `set PYTHONUTF8=1` and `set PYTHONIOENCODING=utf-8`")
