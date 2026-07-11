from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.knowledge_api import KnowledgeBaseApiClient


class RecordingKnowledgeClient(KnowledgeBaseApiClient):
    def __init__(self) -> None:
        self.calls = []

    def post_json(self, endpoint: str, payload: dict):
        self.calls.append((endpoint, payload))
        return {"media_id": "media_test_001"}


class KnowledgeAddNoteTests(unittest.TestCase):
    def test_add_note_uses_note_id_and_compatible_output(self):
        client = RecordingKnowledgeClient()
        result = client.add_note("kb_test", "note_test", title="标题")
        self.assertEqual(client.calls, [("add_knowledge", {"media_type": 11, "title": "标题", "knowledge_base_id": "kb_test", "note_info": {"content_id": "note_test"}})])
        self.assertEqual(result["note_id"], "note_test")
        self.assertEqual(result["doc_id"], "note_test")

    def test_folder_is_optional_and_empty_note_id_is_rejected(self):
        client = RecordingKnowledgeClient()
        client.add_note("kb", "note", title="x", folder_id="folder")
        self.assertEqual(client.calls[0][1]["folder_id"], "folder")
        with self.assertRaisesRegex(ValueError, "note_id"):
            client.add_note("kb", " ", title="x")


if __name__ == "__main__":
    unittest.main()
