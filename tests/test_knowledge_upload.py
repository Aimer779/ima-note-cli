from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from _bootstrap import ROOT  # noqa: F401
from ima_note_cli.knowledge_upload import build_cos_authorization, inspect_upload_file


class KnowledgeUploadTests(unittest.TestCase):
    def test_inspect_upload_file_detects_markdown(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "note.md"
            path.write_text("# title", encoding="utf-8")
            info = inspect_upload_file(str(path))

        self.assertEqual(info.media_type, 7)
        self.assertEqual(info.content_type, "text/markdown")
        self.assertEqual(info.file_name, "note.md")

    def test_inspect_upload_file_rejects_video(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "clip.mp4"
            path.write_bytes(b"00")
            with self.assertRaises(ValueError):
                inspect_upload_file(str(path))

    def test_build_cos_authorization_is_stable(self) -> None:
        authorization = build_cos_authorization(
            secret_id="sid",
            secret_key="skey",
            method="PUT",
            pathname="/path/to/file.txt",
            headers={
                "content-length": "10",
                "host": "bucket.cos.ap-shanghai.myqcloud.com",
            },
            start_time=100,
            expired_time=200,
        )

        self.assertIn("q-sign-algorithm=sha1", authorization)
        self.assertIn("q-ak=sid", authorization)
        self.assertIn("q-sign-time=100;200", authorization)
