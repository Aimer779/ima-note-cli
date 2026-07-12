from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
import unittest
from unittest.mock import patch

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.cli import run
from ima_note_cli.config import CredentialStatus
from ima_note_cli.errors import ApiProtocolError
from ima_note_cli.knowledge_api import MediaInfo
from ima_note_cli.knowledge_cli import validate_urls
from ima_note_cli.errors import InputError
from pathlib import Path
from tempfile import TemporaryDirectory


class FakeKnowledge:
    def __init__(self, *_args, **_kwargs): pass
    def get_media_info(self, media_id): return MediaInfo(media_id, 9, "unavailable")

class FakeNoteKnowledge(FakeKnowledge):
    def get_media_info(self, media_id): return MediaInfo(media_id, 11, "note", "note_test")

class FakeNotes:
    def __init__(self, *_args, **_kwargs): pass
    def get_doc_content(self, note_id): return {"note_id": note_id, "content": "# CLI body"}


class CliBatchBTests(unittest.TestCase):
    @staticmethod
    def configured() -> CredentialStatus:
        return CredentialStatus("client", "key", "environment", "environment")

    def invoke(self, argv):
        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = run(argv)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_json_parser_error_is_structured_and_stderr_empty(self) -> None:
        code, stdout, stderr = self.invoke(["kb", "media-info", "--json"])
        payload = json.loads(stdout)
        self.assertEqual(code, 2); self.assertFalse(payload["ok"]); self.assertEqual(stderr, "")
        self.assertEqual(payload["command"], "kb.media-info")

    def test_media_info_json_is_safe_envelope(self) -> None:
        with patch("ima_note_cli.cli.inspect_credentials", return_value=self.configured()), patch("ima_note_cli.cli.KnowledgeBaseApiClient", FakeKnowledge):
            code, stdout, stderr = self.invoke(["kb", "media-info", "--media-id", "media_test", "--json"])
        payload = json.loads(stdout)
        self.assertEqual(code, 0); self.assertEqual(stderr, "")
        self.assertEqual((payload["ok"], payload["command"], payload["source_kind"]), (True, "kb.media-info", "unavailable"))

    def test_classified_json_error_uses_exit_code_and_no_stderr(self) -> None:
        class FailingKnowledge(FakeKnowledge):
            def get_media_info(self, media_id): raise ApiProtocolError("bad response", endpoint="get_media_info")
        with patch("ima_note_cli.cli.inspect_credentials", return_value=self.configured()), patch("ima_note_cli.cli.KnowledgeBaseApiClient", FailingKnowledge):
            code, stdout, stderr = self.invoke(["kb", "media-info", "--media-id", "media_test", "--json"])
        payload = json.loads(stdout)
        self.assertEqual(code, 6); self.assertEqual(stderr, ""); self.assertFalse(payload["ok"])

    def test_read_and_export_note_media(self) -> None:
        patches = (patch("ima_note_cli.cli.inspect_credentials", return_value=self.configured()),
                   patch("ima_note_cli.cli.KnowledgeBaseApiClient", FakeNoteKnowledge),
                   patch("ima_note_cli.cli.NotesApiClient", FakeNotes))
        with patches[0], patches[1], patches[2]:
            code, stdout, stderr = self.invoke(["kb", "read", "--media-id", "media_test", "--json"])
        payload = json.loads(stdout)
        self.assertEqual((code, stderr, payload["content"], payload["source_kind"]), (0, "", "# CLI body", "note"))
        with TemporaryDirectory() as tmp:
            output = Path(tmp) / "note.md"
            patches = (patch("ima_note_cli.cli.inspect_credentials", return_value=self.configured()),
                       patch("ima_note_cli.cli.KnowledgeBaseApiClient", FakeNoteKnowledge),
                       patch("ima_note_cli.cli.NotesApiClient", FakeNotes))
            with patches[0], patches[1], patches[2]:
                code, stdout, stderr = self.invoke(["kb", "export", "--media-id", "media_test", "--output", str(output), "--json"])
            payload = json.loads(stdout)
            self.assertEqual((code, stderr, output.read_text(encoding="utf-8")), (0, "", "# CLI body"))
            self.assertEqual(payload["bytes"], len("# CLI body".encode()))

    def test_add_url_validation_never_echoes_signed_url(self) -> None:
        signed = "file:///TOP_SECRET"
        with self.assertRaises(InputError) as caught:
            validate_urls([signed])
        self.assertNotIn(signed, str(caught.exception)); self.assertNotIn("TOP_SECRET", str(caught.exception))

    def test_internal_error_and_interrupt_are_sanitized(self) -> None:
        for raised, expected_code, machine_code in [(RuntimeError("SECRET_DETAIL"), 70, "internal_error"), (KeyboardInterrupt(), 130, "interrupted")]:
            class FailingKnowledge(FakeKnowledge):
                def get_media_info(self, media_id): raise raised
            with patch("ima_note_cli.cli.inspect_credentials", return_value=self.configured()), patch("ima_note_cli.cli.KnowledgeBaseApiClient", FailingKnowledge):
                code, stdout, stderr = self.invoke(["kb", "media-info", "--media-id", "media_test", "--json"])
            payload = json.loads(stdout)
            self.assertEqual((code, stderr, payload["error"]["code"]), (expected_code, "", machine_code))
            self.assertNotIn("SECRET_DETAIL", stdout)
