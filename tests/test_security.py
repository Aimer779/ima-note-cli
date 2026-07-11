from __future__ import annotations

import unittest

from tests._bootstrap import ROOT  # noqa: F401
from ima_note_cli.errors import InputError
from ima_note_cli.security import build_and_validate_cos_origin, validate_ima_base_url, validate_media_source_url, validate_relative_endpoint


class SecurityTests(unittest.TestCase):
    def test_ima_endpoint_and_cos_boundaries(self) -> None:
        self.assertEqual(validate_ima_base_url("https://ima.qq.com/openapi/wiki/v1"), "https://ima.qq.com/openapi/wiki/v1")
        self.assertEqual(validate_relative_endpoint("get_media_info"), "get_media_info")
        self.assertEqual(build_and_validate_cos_origin("bucket-test", "ap-test"), "https://bucket-test.cos.ap-test.myqcloud.com")
        for value in ["https://evil.example/openapi/wiki/v1", "https://ima.qq.com@evil.example/openapi/wiki/v1"]:
            with self.assertRaises(InputError): validate_ima_base_url(value)
        for value in ["//evil", "https://evil"]:
            with self.assertRaises(InputError): validate_relative_endpoint(value)
        for bucket in ["bad@evil", "bad/path", "bad:443", "bad\nname"]:
            with self.assertRaises(InputError): build_and_validate_cos_origin(bucket, "ap-test")

    def test_media_url_allowlist(self) -> None:
        validate_media_source_url("https://ima.qq.com/test")
        validate_media_source_url("https://bucket.cos.ap-test.myqcloud.com/path")
        for value in ["http://ima.qq.com/x", "https://localhost/x", "https://127.0.0.1/x", "https://evilmyqcloud.com/x"]:
            with self.assertRaises(InputError): validate_media_source_url(value)
