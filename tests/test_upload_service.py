from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ima_note_cli.errors import InputError
from ima_note_cli.knowledge_api import RepeatedNameResult
from ima_note_cli.knowledge_api import CosCredential
from ima_note_cli.upload_service import UploadService


class FakeKnowledge:
    def __init__(self, repeated: bool = False) -> None:
        self.repeated = repeated
        self.calls: list[str] = []

    def check_repeated_names(self, kb, params, folder_id=None):
        self.calls.append("check")
        value = self.repeated
        self.repeated = False
        return [RepeatedNameResult(item["name"], value) for item in params]


class UploadServiceTests(unittest.TestCase):
    def test_conflict_is_checked_before_create_and_rename_is_stable(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "a.txt"; path.write_text("x", encoding="utf-8")
            knowledge = FakeKnowledge(False)
            service = UploadService(knowledge, clock=lambda: datetime(2026, 1, 2, 3, 4, 5))
            info = service._resolve_conflicts("kb", [__import__("ima_note_cli.knowledge_upload", fromlist=["inspect_upload_file"]).inspect_upload_file(str(path))], {"a.txt": True}, None, "rename")
            self.assertEqual(info[0].file_name, "a_20260102_030405.txt")
            self.assertEqual(knowledge.calls, ["check"])

    def test_multiple_files_reject_global_content_type_before_network(self) -> None:
        service = UploadService(FakeKnowledge())
        with self.assertRaises(InputError):
            service.upload_many("kb", ["a", "b"], content_type="text/plain")

    def test_conflict_error_returns_itemized_gate_results(self) -> None:
        with TemporaryDirectory() as directory:
            first = Path(directory) / "a.txt"; first.write_text("a", encoding="utf-8")
            second = Path(directory) / "b.txt"; second.write_text("b", encoding="utf-8")
            results = UploadService(FakeKnowledge(True)).upload_many("kb", [str(first), str(second)])
        self.assertEqual([item["status"] for item in results], ["failed", "failed"])
        self.assertTrue(all(item["stage"] == "conflict_check" for item in results))

    def test_gate_order_reaches_add_only_after_cos(self) -> None:
        from time import time
        calls: list[str] = []
        class Knowledge(FakeKnowledge):
            def create_media(self, *args, **kwargs):
                calls.append("create")
                now = int(time())
                return {"media_id": "m", "cos_credential": CosCredential("t", "sid", "key", now - 1, now + 1000, "app", "bucket", "ap-test", "ignored", "folder/a.txt")}
            def add_file(self, *args, **kwargs): calls.append("add"); return {"media_id": "m"}
        class Cos:
            def put(self, *args, **kwargs): calls.append("cos"); args[0].read()
        with TemporaryDirectory() as directory:
            path = Path(directory) / "a.txt"; path.write_text("body", encoding="utf-8")
            result = UploadService(Knowledge(), Cos()).upload_many("kb", [str(path)])
        self.assertEqual(calls, ["create", "cos", "add"])
        self.assertEqual(result[0]["status"], "success")
