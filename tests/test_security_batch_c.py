from __future__ import annotations

import socket
import unittest

from ima_note_cli.errors import InputError
from ima_note_cli.security import safe_url, validate_cos_key, validate_public_url, validate_cos_credential_times


def resolver_for(*addresses: str):
    return lambda *args: [(socket.AF_INET6 if ":" in value else socket.AF_INET, socket.SOCK_STREAM, 6, "", (value, args[1])) for value in addresses]


class SecurityBatchCTests(unittest.TestCase):
    def test_public_url_is_resolved_and_query_is_redacted(self) -> None:
        target = validate_public_url("https://public.test/a?token=secret#x", resolver=resolver_for("8.8.8.8"))
        self.assertEqual(target.addresses, ("8.8.8.8",))
        self.assertEqual(target.safe_url, "https://public.test/a")
        self.assertEqual(safe_url("https://user:pass@public.test/a?q=x"), "https://public.test/a")

    def test_ssrf_shapes_are_rejected(self) -> None:
        cases = ["file:///tmp/x", "https://u:p@public.test/a", "https://127.0.0.1/a", "https://localhost/a", "https://public.test:444/a"]
        for value in cases:
            with self.subTest(value=value), self.assertRaises(InputError):
                validate_public_url(value, resolver=resolver_for("8.8.8.8"))
        with self.assertRaises(InputError):
            validate_public_url("https://public.test/a", resolver=resolver_for("8.8.8.8", "10.0.0.1"))

    def test_cos_key_rejects_unsafe_paths(self) -> None:
        self.assertEqual(validate_cos_key("folder/file.txt"), "folder/file.txt")
        for value in ("", "/x", "a//b", "a/../b", "https://x/y", "a\\b", "a?x"):
            with self.subTest(value=value), self.assertRaises(InputError): validate_cos_key(value)

    def test_expired_cos_time_is_never_a_signing_vector_bypass(self) -> None:
        with self.assertRaises(InputError):
            validate_cos_credential_times(1, 2, now=100)
