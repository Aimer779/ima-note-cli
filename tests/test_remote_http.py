from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from ima_note_cli.errors import LocalIOError, RemoteFetchError
from ima_note_cli.remote_http import RemoteHttpClient


class Response:
    def __init__(self, status: int, headers=(), body: bytes = b"") -> None:
        self.status = status; self._headers = list(headers); self.body = BytesIO(body)
    def getheaders(self): return self._headers
    def read(self, size=-1): return self.body.read(size)
    def close(self): pass


class Connection:
    def __init__(self, response: Response) -> None: self.response = response; self.headers = None
    def request(self, method, path, headers): self.headers = headers
    def getresponse(self): return self.response
    def close(self): pass


def resolver(*args):
    return [(2, 1, 6, "", ("8.8.8.8", args[1]))]


class RemoteHttpTests(unittest.TestCase):
    def test_head_405_falls_back_to_header_only_get(self) -> None:
        responses = iter([Response(405), Response(200, [("Content-Type", "application/pdf")])])
        client = RemoteHttpClient(resolver=resolver, connection_factory=lambda *args: Connection(next(responses)))
        result = client.probe("https://public.test/file")
        self.assertEqual((result.method, result.content_type), ("GET", "application/pdf"))

    def test_length_mismatch_retries_three_total_attempts(self) -> None:
        calls = 0
        def factory(*args):
            nonlocal calls; calls += 1
            return Connection(Response(200, [("Content-Length", "2")], b"x"))
        client = RemoteHttpClient(resolver=resolver, connection_factory=factory)
        with TemporaryDirectory() as directory, self.assertRaises(RemoteFetchError):
            client.download("https://public.test/file", Path(directory) / "file", max_bytes=10)
        self.assertEqual(calls, 3)
