from __future__ import annotations

import unittest

from ima_note_cli.command_result import CommandResult, CommandStatus
from ima_note_cli.errors import ExitCode


class CommandResultTests(unittest.TestCase):
    def test_batch_statuses_and_summary(self) -> None:
        success = CommandResult.batch([{"status": "success"}])
        self.assertEqual((success.status, success.exit_code), (CommandStatus.SUCCESS, 0))
        partial = CommandResult.batch([{"status": "success"}, {"status": "failed"}])
        self.assertEqual((partial.status, partial.exit_code), (CommandStatus.PARTIAL, ExitCode.PARTIAL))
        self.assertEqual(partial.payload["summary"]["failed"], 1)

    def test_invalid_status_exit_pair_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            CommandResult(status=CommandStatus.PARTIAL)
