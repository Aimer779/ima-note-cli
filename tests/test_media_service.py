from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import hashlib
import unittest

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.errors import InputError, LocalIOError, MediaUnavailableError
from ima_note_cli.knowledge_api import MediaAccessInfo, MediaInfo
from ima_note_cli.media_service import MediaContentService
from ima_note_cli.source_http import SourceReadResult, SourceStreamResult


class FakeKnowledge:
    def __init__(self, info): self.info, self.calls = info, 0
    def get_media_info(self, media_id): self.calls += 1; return self.info

class FakeNotes:
    def __init__(self): self.calls = []
    def get_doc_content(self, note_id): self.calls.append(note_id); return {"note_id": note_id, "content": "# 正文"}

class FakeSource:
    def __init__(self): self.read_calls = 0; self.stream_calls = 0
    def read_text(self, access): self.read_calls += 1; return SourceReadResult("url text", "text/plain", 8)
    def stream_to(self, access, output): self.stream_calls += 1; output.write(b"\x00\xff"); return SourceStreamResult("application/octet-stream", 2)


class MediaServiceTests(unittest.TestCase):
    def test_note_and_url_routing_are_exclusive(self) -> None:
        notes, source = FakeNotes(), FakeSource()
        result = MediaContentService(FakeKnowledge(MediaInfo("m", 11, "note", "n")), notes, source).read_media("m")
        self.assertEqual(result.content, "# 正文")
        self.assertEqual(notes.calls, ["n"]); self.assertEqual(source.read_calls, 0)
        access = MediaAccessInfo("https://ima.qq.com/x", {}, "ima.qq.com", ())
        notes, source = FakeNotes(), FakeSource()
        result = MediaContentService(FakeKnowledge(MediaInfo("m", 1, "url", access=access)), notes, source).read_media("m")
        self.assertEqual(result.content, "url text"); self.assertEqual(notes.calls, []); self.assertEqual(source.read_calls, 1)

    def test_unavailable_stops_without_secondary_call(self) -> None:
        notes, source = FakeNotes(), FakeSource()
        with self.assertRaises(MediaUnavailableError):
            MediaContentService(FakeKnowledge(MediaInfo("m", 9, "unavailable")), notes, source).read_media("m")
        self.assertEqual(notes.calls, []); self.assertEqual(source.read_calls, 0)

    def test_note_and_binary_export_are_atomic_and_hashed(self) -> None:
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.bin"
            service = MediaContentService(FakeKnowledge(MediaInfo("m", 11, "note", "n")), FakeNotes(), FakeSource())
            result = service.export_media("m", target)
            expected = "# 正文".encode()
            self.assertEqual(target.read_bytes(), expected)
            self.assertEqual(result.sha256, hashlib.sha256(expected).hexdigest())
            with self.assertRaises(InputError): service.export_media("m", target)
            result = service.export_media("m", target, force=True)
            self.assertEqual(result.bytes_count, len(expected))
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_url_export_preserves_bytes_and_failure_preserves_target(self) -> None:
        access = MediaAccessInfo("https://ima.qq.com/x", {}, "ima.qq.com", ())
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.bin"
            source = FakeSource()
            service = MediaContentService(FakeKnowledge(MediaInfo("m", 1, "url", access=access)), FakeNotes(), source)
            result = service.export_media("m", target)
            self.assertEqual(target.read_bytes(), b"\x00\xff")
            self.assertEqual(result.sha256, hashlib.sha256(b"\x00\xff").hexdigest())
            class FailingSource(FakeSource):
                def stream_to(self, access, output):
                    output.write(b"partial")
                    raise LocalIOError("failed")
            target.write_bytes(b"original")
            service = MediaContentService(FakeKnowledge(MediaInfo("m", 1, "url", access=access)), FakeNotes(), FailingSource())
            with self.assertRaises(LocalIOError): service.export_media("m", target, force=True)
            self.assertEqual(target.read_bytes(), b"original")
            self.assertFalse(any(path.suffix == ".tmp" for path in Path(tmp).iterdir()))
