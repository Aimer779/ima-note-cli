from __future__ import annotations

from argparse import Namespace
from io import StringIO
import json
import unittest

from ima_note_cli.commands.knowledge import execute
from ima_note_cli.output import emit_command_result


class Upload:
    def __init__(self, results): self.results = results
    def upload_many(self, *args, **kwargs): return self.results


class CliBatchCTests(unittest.TestCase):
    def args(self) -> Namespace:
        return Namespace(kb_action="add-file", kb_id="kb", files=["a.txt"], folder_id=None, content_type=None, on_conflict="error", upload_timeout=300)

    def test_single_file_keeps_top_level_compatibility_fields(self) -> None:
        result = execute(self.args(), object(), upload_service=Upload([{"file_name": "a.txt", "media_id": "m", "status": "success", "stage": "complete"}]))
        stream = StringIO(); emit_command_result("kb.add-file", result, as_json=True, stdout=stream)
        payload = json.loads(stream.getvalue())
        self.assertEqual((payload["title"], payload["media_id"], payload["status"]), ("a.txt", "m", "success"))

    def test_partial_human_output_preserves_items(self) -> None:
        args = self.args(); args.files = ["a.txt", "b.txt"]
        result = execute(args, object(), upload_service=Upload([
            {"file_name": "a.txt", "media_id": "m", "status": "success", "stage": "complete"},
            {"file_name": "b.txt", "media_id": "", "status": "failed", "stage": "cos_upload", "error": {"code": "x"}},
        ]))
        out, err = StringIO(), StringIO(); code = emit_command_result("kb.add-file", result, as_json=False, stdout=out, stderr=err)
        self.assertEqual(code, 9); self.assertIn("a.txt success", out.getvalue()); self.assertIn("b.txt failed", out.getvalue())
