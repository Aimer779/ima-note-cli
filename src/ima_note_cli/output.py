from __future__ import annotations

import json
import sys
from collections.abc import Iterable, Mapping
from typing import Any, TextIO

from .errors import ImaCliError


_RESERVED = frozenset({"schema_version", "ok", "command", "error"})


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

