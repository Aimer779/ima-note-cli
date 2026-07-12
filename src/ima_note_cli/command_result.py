from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import ExitCode, ImaCliError


class CommandStatus(str, Enum):
    SUCCESS = "success"
    EMPTY = "empty"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True)
class CommandResult:
    payload: dict[str, Any] = field(default_factory=dict)
    human_lines: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    status: CommandStatus = CommandStatus.SUCCESS
    exit_code: int = 0
    error: ImaCliError | None = None

    def __post_init__(self) -> None:
        if self.status in {CommandStatus.SUCCESS, CommandStatus.EMPTY}:
            if self.exit_code != 0 or self.error is not None:
                raise ValueError("Successful command results cannot contain an error or non-zero exit code.")
        elif self.exit_code == 0:
            raise ValueError("Partial and failed command results require a non-zero exit code.")

    @classmethod
    def batch(
        cls,
        results: list[dict[str, Any]],
        *,
        payload: dict[str, Any] | None = None,
        human_lines: tuple[str, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> "CommandResult":
        succeeded = sum(item.get("status") == "success" for item in results)
        failed = sum(item.get("status") == "failed" for item in results)
        not_attempted = sum(item.get("status") == "not_attempted" for item in results)
        summary = {"total": len(results), "succeeded": succeeded, "failed": failed, "not_attempted": not_attempted}
        merged = {**(payload or {}), "summary": summary, "results": results}
        if not failed and not not_attempted:
            status = CommandStatus.SUCCESS if succeeded else CommandStatus.EMPTY
            return cls(merged, human_lines, warnings, status)
        status = CommandStatus.PARTIAL if succeeded else CommandStatus.FAILED
        error = ImaCliError(
            f"{failed + not_attempted} of {len(results)} items failed or were not attempted.",
            code="partial_failure",
            exit_code=ExitCode.PARTIAL,
        )
        return cls(merged, human_lines, warnings, status, int(ExitCode.PARTIAL), error)
