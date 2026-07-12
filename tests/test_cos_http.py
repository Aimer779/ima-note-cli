from __future__ import annotations

from time import time
import tracemalloc
import unittest

from ima_note_cli.cos_http import CosHttpClient
from ima_note_cli.knowledge_api import CosCredential


class Stream:
    def __init__(self, remaining: int) -> None: self.remaining = remaining; self.max_read = 0
    def read(self, size: int) -> bytes:
        self.max_read = max(self.max_read, size)
        count = min(size, self.remaining); self.remaining -= count
        return b"x" * count


class Response:
    status = 200
    def read(self, size): return b""


class Connection:
    def putrequest(self, *args, **kwargs): pass
    def putheader(self, *args): pass
    def endheaders(self): pass
    def send(self, value): pass
    def getresponse(self): return Response()
    def close(self): pass


class CosHttpTests(unittest.TestCase):
    def test_200_mib_stream_is_bounded_to_64_kib_reads(self) -> None:
        size = 200 * 1024 * 1024
        stream = Stream(size); now = int(time())
        credential = CosCredential("token", "sid", "key", now - 1, now + 1000, "app", "bucket", "ap-test", "ignored", "folder/file.bin")
        tracemalloc.start()
        CosHttpClient(lambda host, timeout: Connection()).put(stream, size=size, content_type="application/octet-stream", credential=credential, authorization="safe", timeout=300)
        _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        self.assertLessEqual(stream.max_read, 64 * 1024)
        self.assertLess(peak, 2 * 1024 * 1024)
