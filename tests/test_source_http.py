from __future__ import annotations

from email.message import Message
from io import BytesIO
from http.client import IncompleteRead
import unittest

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.errors import LocalIOError, MediaUnavailableError
from ima_note_cli.knowledge_api import MediaAccessInfo
from ima_note_cli.source_http import MAX_TEXT_BYTES, SourceHttpClient
from ima_note_cli.source_http import _SafeRedirectHandler
from urllib import request


class Response(BytesIO):
    def __init__(self, body: bytes, content_type: str = "text/plain; charset=utf-8", length: int | None = None) -> None:
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if length is not None: self.headers["Content-Length"] = str(length)
    def __enter__(self): return self
    def __exit__(self, *args): self.close(); return False


class SourceHttpTests(unittest.TestCase):
    def access(self) -> MediaAccessInfo:
        return MediaAccessInfo("https://ima.qq.com/test/object?signature=fixture", {"Authorization": "fixture"}, "ima.qq.com", ("Authorization",))

    def test_text_request_contains_only_temporary_headers(self) -> None:
        calls = []
        def open_(req, timeout):
            calls.append(req)
            return Response("正文".encode())
        result = SourceHttpClient(opener=open_).read_text(self.access())
        self.assertEqual(result.content, "正文")
        headers = {key.lower(): value for key, value in calls[0].header_items()}
        self.assertEqual(headers["authorization"], "fixture")
        self.assertNotIn("ima-openapi-clientid", headers)
        self.assertNotIn("ima-openapi-apikey", headers)

    def test_binary_and_size_limits(self) -> None:
        with self.assertRaisesRegex(MediaUnavailableError, "export"):
            SourceHttpClient(opener=lambda *_args, **_kwargs: Response(b"x", "application/octet-stream")).read_text(self.access())
        with self.assertRaises(LocalIOError):
            SourceHttpClient(opener=lambda *_args, **_kwargs: Response(b"", length=MAX_TEXT_BYTES + 1)).read_text(self.access())

    def test_stream_preserves_bytes(self) -> None:
        output = BytesIO()
        result = SourceHttpClient(opener=lambda *_args, **_kwargs: Response(b"\x00\xff", "application/octet-stream")).stream_to(self.access(), output)
        self.assertEqual(output.getvalue(), b"\x00\xff")
        self.assertEqual(result.bytes_count, 2)

    def test_temporary_headers_cannot_cross_origin_redirect(self) -> None:
        handler = _SafeRedirectHandler()
        original = request.Request("https://ima.qq.com/start", headers={"Authorization": "fixture"})
        with self.assertRaises(MediaUnavailableError):
            handler.redirect_request(original, None, 302, "Found", Message(), "https://bucket.cos.ap-test.myqcloud.com/end")
        redirected = handler.redirect_request(original, None, 302, "Found", Message(), "https://ima.qq.com/end")
        self.assertEqual(redirected.get_header("Authorization"), "fixture")
        for target in ("https://evil.example/end", "https://127.0.0.1/end"):
            with self.subTest(target=target), self.assertRaises(MediaUnavailableError) as caught:
                handler.redirect_request(original, None, 302, "Found", Message(), target)
            self.assertEqual(caught.exception.exit_code, 7)

    def test_missing_mime_is_binary_and_length_mismatch_fails(self) -> None:
        no_type = Response(b"text")
        del no_type.headers["Content-Type"]
        with self.assertRaises(MediaUnavailableError):
            SourceHttpClient(opener=lambda *_a, **_k: no_type).read_text(self.access())
        with self.assertRaises(LocalIOError):
            SourceHttpClient(opener=lambda *_a, **_k: Response(b"short", length=20)).read_text(self.access())

    def test_interrupted_body_has_media_error_classification(self) -> None:
        class Broken(Response):
            def read(self, size=-1): raise IncompleteRead(b"partial", 10)
        with self.assertRaises(MediaUnavailableError) as caught:
            SourceHttpClient(opener=lambda *_a, **_k: Broken(b"")).read_text(self.access())
        self.assertEqual(caught.exception.exit_code, 7)
        with self.assertRaises(LocalIOError) as caught:
            SourceHttpClient(opener=lambda *_a, **_k: Broken(b"", "application/octet-stream")).stream_to(self.access(), BytesIO())
        self.assertEqual(caught.exception.exit_code, 7)

    def test_destination_write_failure_is_not_network_retryable(self) -> None:
        class BrokenWriter:
            def write(self, value): raise OSError("disk full")
        with self.assertRaises(LocalIOError) as caught:
            SourceHttpClient(opener=lambda *_a, **_k: Response(b"bytes", "application/octet-stream")).stream_to(self.access(), BrokenWriter())
        self.assertEqual(caught.exception.code, "media_export_failed")
        self.assertFalse(caught.exception.retryable)
