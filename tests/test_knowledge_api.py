from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.errors import ApiProtocolError, InputError
from ima_note_cli.knowledge_api import KnowledgeBaseApiClient
from tests._fixtures import load_data


class RecordingKnowledgeClient(KnowledgeBaseApiClient):
    def __init__(self, responses=None) -> None:
        self.calls = []
        self.responses = responses or {}

    def _record(self, endpoint: str, payload: dict):
        self.calls.append((endpoint, payload))
        return self.responses.get(endpoint, {"media_id": "media_test_001"})

    post_read_json = _record
    post_write_json = _record


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


class MediaInfoTests(unittest.TestCase):
    def client(self, fixture: str) -> RecordingKnowledgeClient:
        return RecordingKnowledgeClient({"get_media_info": load_data(f"knowledge/{fixture}")})

    def test_url_note_and_unavailable_branches(self) -> None:
        url = self.client("get_media_info_url_success.json").get_media_info("media_test_url")
        self.assertEqual((url.source_kind, url.access.safe_host), ("url", "bucket-test.cos.ap-test.myqcloud.com"))
        self.assertNotIn("fixture-authorization", repr(url))
        note = self.client("get_media_info_note_success.json").get_media_info("media_test_note")
        self.assertEqual((note.source_kind, note.note_id), ("note", "note_test_1"))
        unavailable = self.client("get_media_info_unavailable_success.json").get_media_info("media_test_none")
        self.assertEqual(unavailable.source_kind, "unavailable")

    def test_invalid_media_contract_and_input_fail_before_guessing(self) -> None:
        with self.assertRaises(ApiProtocolError):
            self.client("get_media_info_missing_media_type.json").get_media_info("m")
        with self.assertRaises(ApiProtocolError):
            self.client("get_media_info_invalid_headers.json").get_media_info("m")
        with self.assertRaises(InputError):
            self.client("get_media_info_unavailable_success.json").get_media_info("")


class KnowledgeContractTests(unittest.TestCase):
    def client(self, mapping) -> RecordingKnowledgeClient:
        return RecordingKnowledgeClient({name: load_data(f"knowledge/{fixture}") for name, fixture in mapping.items()})

    def test_read_contract_fixtures(self) -> None:
        client = self.client({
            "search_knowledge_base": "search_knowledge_base_success.json",
            "get_knowledge_base": "get_knowledge_base_success.json",
            "get_knowledge_list": "get_knowledge_list_mixed_success.json",
            "search_knowledge": "search_knowledge_success.json",
            "get_addable_knowledge_base_list": "get_addable_knowledge_base_list_success.json",
        })
        self.assertEqual(client.search_knowledge_bases("test", 20)["knowledge_bases"][0].knowledge_base_id, "kb_test_1")
        self.assertEqual(client.get_knowledge_base("kb_test_1").name, "Test KB")
        self.assertEqual([item.kind for item in client.list_knowledge("kb_test_1", 50)["items"]], ["folder", "file"])
        self.assertEqual(client.search_knowledge("x", "kb_test_1")["items"][0].media_id, "media_test_1")
        self.assertEqual(client.list_addable_knowledge_bases(50)["knowledge_bases"][0].name, "Test KB")

    def test_write_contract_fixtures_and_limits(self) -> None:
        client = self.client({
            "import_urls": "import_urls_partial_success.json",
            "check_repeated_names": "check_repeated_names_success.json",
            "create_media": "create_media_success.json",
            "add_knowledge": "add_knowledge_success.json",
        })
        results = client.import_urls("kb_test_1", ["https://ima.qq.com/test/article"])["results"]
        self.assertEqual(results[0].media_id, "media_test_url")
        self.assertFalse(client.check_repeated_names("kb_test_1", [{"name": "file.txt", "media_type": 13}])[0].is_repeated)
        self.assertEqual(client.create_media("kb_test_1", file_name="file.txt", file_size=1, content_type="text/plain", file_ext="txt")["media_id"], "media_test_upload")
        self.assertEqual(client.add_file("kb_test_1", media_type=13, media_id="media_test_upload", title="file.txt", file_info={})["media_id"], "media_test_added")
        for call in [lambda: client.search_knowledge_bases("x", 21), lambda: client.list_knowledge("kb", 51),
                     lambda: client.list_addable_knowledge_bases(0), lambda: client.get_knowledge_bases(["x"] * 21),
                     lambda: client.get_knowledge_bases(["x", "x"]), lambda: client.import_urls("kb", ["x"] * 11),
                     lambda: client.check_repeated_names("kb", [])]:
            with self.assertRaises(InputError): call()


if __name__ == "__main__":
    unittest.main()
