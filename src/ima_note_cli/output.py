from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from typing import Any, TextIO

from .errors import ImaCliError
from .command_result import CommandResult


_RESERVED = frozenset({"schema_version", "ok", "status", "command", "error"})


def _warnings(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(str(value) for value in values if str(value)))


def emit_json_success(
    command: str,
    payload: Mapping[str, Any] | None = None,
    warnings: Iterable[str] = (),
    *,
    stream: TextIO | None = None,
) -> None:
    result = dict(payload or {})
    conflict = _RESERVED.intersection(result)
    if conflict:
        raise ValueError(f"JSON payload uses reserved fields: {', '.join(sorted(conflict))}")
    payload_warnings = result.pop("warnings", ())
    result = {
        "schema_version": 1,
        "ok": True,
        "command": command,
        "warnings": _warnings([*warnings, *payload_warnings]),
        **result,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), file=stream or sys.stdout)


def emit_json_error(command: str, error: ImaCliError, *, stream: TextIO | None = None) -> None:
    result = {
        "schema_version": 1,
        "ok": False,
        "command": command,
        "warnings": [],
        "error": error.to_error_dict(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2), file=stream or sys.stdout)


def emit_human_error(error: ImaCliError, *, stream: TextIO | None = None) -> None:
    print(f"Error: {error.message}", file=stream or sys.stderr)


def emit_command_result(
    command: str, result: CommandResult, *, as_json: bool,
    stdout: TextIO | None = None, stderr: TextIO | None = None,
) -> int:
    out, err = stdout or sys.stdout, stderr or sys.stderr
    if as_json:
        payload = dict(result.payload)
        conflict = _RESERVED.intersection(payload)
        if conflict:
            raise ValueError(f"JSON payload uses reserved fields: {', '.join(sorted(conflict))}")
        document = {
            "schema_version": 1,
            "ok": result.status.value in {"success", "empty"},
            "status": result.status.value,
            "command": command,
            "warnings": _warnings(result.warnings),
            **payload,
        }
        if result.error is not None:
            document["error"] = result.error.to_error_dict()
        print(json.dumps(document, ensure_ascii=False, indent=2), file=out)
    else:
        for line in result.human_lines:
            print(line, file=out)
        for warning in result.warnings:
            print(f"Warning: {warning}", file=err)
        if result.error is not None:
            emit_human_error(result.error, stream=err)
    return result.exit_code
