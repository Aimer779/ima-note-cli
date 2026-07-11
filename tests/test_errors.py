from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.errors import (
    ApiBusinessError, ApiProtocolError, ApiTransportError, ConfigError, InputError,
    KnowledgeUploadError, LocalIOError,
)


class ErrorTests(unittest.TestCase):
    def test_exit_codes_and_safe_dict(self) -> None:
        cases = [(InputError, 2), (ConfigError, 3), (ApiTransportError, 4), (ApiBusinessError, 5),
                 (ApiProtocolError, 6), (LocalIOError, 7), (KnowledgeUploadError, 8)]
        for error_type, exit_code in cases:
            with self.subTest(error_type=error_type):
                error = error_type("safe\nmessage", endpoint="endpoint", details={"attempts": 2, "secret": "no"})
                payload = error.to_error_dict()
                self.assertEqual(payload["exit_code"], exit_code)
                self.assertEqual(payload["message"], "safe message")
                self.assertNotIn("secret", payload.get("details", {}))

