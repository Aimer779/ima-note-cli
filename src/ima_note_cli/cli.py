from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence

from .config import ConfigError, CredentialStatus, inspect_credentials, load_credentials
from .http import ApiError
from .knowledge_api import KnowledgeBaseApiClient
from .knowledge_cli import add_kb_subcommands, handle_kb_command
from .knowledge_upload import KnowledgeUploadError
from .notes_api import NotesApiClient
from .notes_cli import add_note_subcommands, handle_note_command


def build_parser(*, prog: str = "ima") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
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
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        status = inspect_credentials(Path.cwd())
        if args.command == "auth":
            return handle_auth(status, args.as_json)

        credentials = load_credentials(Path.cwd())
        if args.command == "note":
            return handle_note_command(args, NotesApiClient(credentials))
        if args.command == "kb":
            return handle_kb_command(args, KnowledgeBaseApiClient(credentials))
    except (ConfigError, ApiError, KnowledgeUploadError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.error("Unknown command")
    return 2


def run_note_legacy(argv: Sequence[str] | None = None) -> int:
    argv_list = list(argv) if argv is not None else list(sys.argv[1:])
    if argv_list and argv_list[0] == "auth":
        return run(argv_list)
    return run(["note", *argv_list])


def handle_auth(status: CredentialStatus, as_json: bool) -> int:
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
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if status.is_configured else 1

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

    if status.is_configured:
        return 0

    print()
    print("Configure the missing values in the environment or a project-root .env file.", file=sys.stderr)
    return 1


def format_source_suffix(source: str | None) -> str:
    if not source:
        return ""
    return f" ({source})"
