from __future__ import annotations

from email.message import Message
from io import BytesIO
from http.client import IncompleteRead
import json
import unittest
from urllib import error

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.config import Credentials
from ima_note_cli.errors import ApiBusinessError, ApiProtocolError, ApiTransportError, InputError
from ima_note_cli.http import ImaApiClient, MAX_JSON_BYTES


class Response(BytesIO):
    def __init__(self, body: bytes, length: int | None = None):
        super().__init__(body); self.headers = Message()
        if length is not None: self.headers["Content-Length"] = str(length)
    def __enter__(self): return self
    def __exit__(self, *args): self.close(); return False


class HttpBatchBTests(unittest.TestCase):
    def credentials(self): return Credentials("client", "api-key", "test", "test")

    def test_official_origin_endpoint_and_headers(self) -> None:
        with self.assertRaises(InputError): ImaApiClient(self.credentials(), base_url="https://example.com/openapi/note/v1")
        calls = []
        def opener(req, timeout): calls.append(req); return Response(b'{"code":0,"data":{}}')
        client = ImaApiClient(self.credentials(), base_url="https://ima.qq.com/openapi/note/v1", opener=opener)
        client.post_read_json("search_note", {})
        headers = {k.lower(): v for k, v in calls[0].header_items()}
        self.assertEqual(headers["accept"], "application/json"); self.assertIn("ima-note-cli/", headers["user-agent"])
        with self.assertRaises(InputError): client.post_read_json("//evil", {})

    def test_read_retries_but_write_does_not(self) -> None:
        events = [TimeoutError(), error.HTTPError("https://ima.qq.com", 503, "bad", Message(), BytesIO(b"{}")), Response(b'{"code":0,"data":{}}')]
        sleeps = []
        def opener(*_args, **_kwargs):
            value = events.pop(0)
            if isinstance(value, BaseException): raise value
            return value
        client = ImaApiClient(self.credentials(), base_url="https://ima.qq.com/openapi/wiki/v1", opener=opener, sleep=sleeps.append)
        self.assertEqual(client.post_read_json("get_media_info", {}), {})
        self.assertEqual(sleeps, [0.25, 0.5])
        calls = 0
        def timeout(*_args, **_kwargs):
            nonlocal calls; calls += 1; raise TimeoutError()
        client = ImaApiClient(self.credentials(), base_url="https://ima.qq.com/openapi/wiki/v1", opener=timeout, sleep=lambda _: None)
        with self.assertRaises(ApiTransportError): client.post_write_json("add_knowledge", {})
        self.assertEqual(calls, 1)

    def test_success_response_size_is_bounded(self) -> None:
        client = ImaApiClient(self.credentials(), base_url="https://ima.qq.com/openapi/wiki/v1", opener=lambda *_a, **_k: Response(b"", MAX_JSON_BYTES + 1))
        with self.assertRaises(ApiProtocolError): client.post_read_json("get_media_info", {})

    def test_business_error_redacts_credentials_and_signed_url(self) -> None:
        body = json.dumps({"code": 1, "msg": "client api-key https://ima.qq.com/object?signature=secret", "data": {}}).encode()
        client = ImaApiClient(self.credentials(), base_url="https://ima.qq.com/openapi/wiki/v1", opener=lambda *_a, **_k: Response(body))
        with self.assertRaises(ApiBusinessError) as caught:
            client.post_read_json("get_media_info", {})
        message = str(caught.exception)
        self.assertNotIn("api-key", message); self.assertNotIn("signature=secret", message)

    def test_protocol_fields_and_error_read_bound(self) -> None:
        client = ImaApiClient(self.credentials(), base_url="https://ima.qq.com/openapi/wiki/v1", opener=lambda *_a, **_k: Response(b"{}"))
        with self.assertRaises(ApiProtocolError) as caught:
            client.post_read_json("get_media_info", {})
        self.assertEqual(caught.exception.details["field"], "code")
        class RecordingBody(BytesIO):
            requested = None
            def read(self, size=-1): self.requested = size; return super().read(size)
        body = RecordingBody(b'{"msg":"bad"}')
        http_error = error.HTTPError("https://ima.qq.com", 400, "bad", Message(), body)
        client = ImaApiClient(self.credentials(), base_url="https://ima.qq.com/openapi/wiki/v1", opener=lambda *_a, **_k: (_ for _ in ()).throw(http_error))
        with self.assertRaises(ApiTransportError): client.post_read_json("get_media_info", {})
        self.assertEqual(body.requested, 16 * 1024)

    def test_interrupted_response_retries_reads_only(self) -> None:
        class BrokenResponse(Response):
            def read(self, size=-1): raise IncompleteRead(b"partial", 10)
        events = [BrokenResponse(b""), BrokenResponse(b""), Response(b'{"code":0,"data":{}}')]
        calls = 0
        def opener(*_a, **_k):
            nonlocal calls; calls += 1; return events.pop(0)
        client = ImaApiClient(self.credentials(), base_url="https://ima.qq.com/openapi/wiki/v1", opener=opener, sleep=lambda _: None)
        self.assertEqual(client.post_read_json("get_media_info", {}), {}); self.assertEqual(calls, 3)
        calls = 0
        client = ImaApiClient(self.credentials(), base_url="https://ima.qq.com/openapi/wiki/v1", opener=lambda *_a, **_k: (globals(), BrokenResponse(b""))[1])
        with self.assertRaises(ApiTransportError): client.post_write_json("add_knowledge", {})
