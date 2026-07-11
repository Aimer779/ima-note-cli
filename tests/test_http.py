from __future__ import annotations

import io
import json
import unittest
from unittest import mock
from urllib import error

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.config import Credentials
from ima_note_cli.http import ApiError, ImaApiClient

from tests._fixtures import load_fixture


class FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size: int = -1) -> bytes:
        return self.body if size < 0 else self.body[:size]


class HttpContractTests(unittest.TestCase):
    def setUp(self) -> None:
        credentials = Credentials("client-test", "key-test", "test", "test")
        self.client = ImaApiClient(credentials, base_url="https://ima.qq.com/openapi/note/v1", timeout=4)

    def post(self, value):
        body = value if isinstance(value, bytes) else json.dumps(value).encode("utf-8")
        with mock.patch("ima_note_cli.http.request.urlopen", return_value=FakeResponse(body)) as opened:
            result = self.client.post_json("endpoint", {"text": "中文"})
        return result, opened.call_args

    def test_success_unwraps_object_data_and_builds_utf8_request(self):
        result, call = self.post({"code": 0, "msg": "success", "data": {"ok": True}})
        self.assertEqual(result, {"ok": True})
        request_arg = call.args[0]
        self.assertEqual(json.loads(request_arg.data.decode("utf-8")), {"text": "中文"})
        self.assertEqual(request_arg.get_header("Content-type"), "application/json")
        self.assertEqual(request_arg.get_header("Ima-openapi-clientid"), "client-test")
        self.assertEqual(request_arg.get_header("Ima-openapi-apikey"), "key-test")
        self.assertEqual(call.kwargs["timeout"], 4)

    def test_string_zero_is_accepted(self):
        result, _ = self.post({"code": "0", "msg": "success", "data": {}})
        self.assertEqual(result, {})

    def test_boolean_and_complex_code_values_are_rejected_as_api_errors(self):
        for code in (False, True, [], {}):
            with self.subTest(code=code):
                with self.assertRaises(ApiError):
                    self.post({"code": code, "msg": "invalid code", "data": {}})

    def test_business_error_uses_backend_message(self):
        with self.assertRaisesRegex(ApiError, "invalid request"):
            self.post(load_fixture("notes/business_error.json"))

    def test_missing_code_fails(self):
        with self.assertRaisesRegex(ApiError, "missing.*code"):
            self.post(load_fixture("notes/malformed_missing_code.json"))
        with self.assertRaisesRegex(ApiError, "missing.*code"):
            self.post({"retcode": 0, "data": {}})

    def test_non_object_data_fails(self):
        with self.assertRaisesRegex(ApiError, "non-object data"):
            self.post(load_fixture("notes/malformed_data_array.json"))
        with self.assertRaisesRegex(ApiError, "non-object data"):
            self.post({"code": 0, "result": {}})

    def test_invalid_json_and_non_object_top_level_fail(self):
        with self.assertRaisesRegex(ApiError, "invalid JSON"):
            self.post(b"not json")
        with self.assertRaisesRegex(ApiError, "non-object response"):
            self.post([])

    def test_non_utf8_response_is_wrapped_as_api_error(self):
        with self.assertRaisesRegex(ApiError, "endpoint endpoint.*valid UTF-8"):
            self.post(b"\xff")

    def test_transport_errors_are_wrapped(self):
        cases = [
            (error.HTTPError("https://example.com", 500, "server error", {}, io.BytesIO(b"failed")), "HTTP 500"),
            (error.URLError("offline"), "Unable to reach"),
            (TimeoutError(), "timed out"),
        ]
        for exception, message in cases:
            with self.subTest(exception=type(exception).__name__):
                with mock.patch("ima_note_cli.http.request.urlopen", side_effect=exception):
                    with self.assertRaisesRegex(ApiError, message):
                        self.client.post_json("endpoint", {})


if __name__ == "__main__":
    unittest.main()
