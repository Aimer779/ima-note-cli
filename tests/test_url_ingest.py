from __future__ import annotations

import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from ima_note_cli.remote_http import RemoteResponseInfo
from ima_note_cli.url_ingest import classify_response, sanitize_filename
from ima_note_cli.url_ingest import UrlIngestService
from ima_note_cli.errors import RemoteFetchError


class UrlIngestTests(unittest.TestCase):
    def info(self, url: str, content_type: str, disposition: str = "") -> RemoteResponseInfo:
        headers = {"content-type": content_type}
        if disposition: headers["content-disposition"] = disposition
        return RemoteResponseInfo(url, url, 200, headers, "HEAD")

    def test_html_wins_over_pdf_path_and_video_hosts_fail(self) -> None:
        self.assertEqual(classify_response(self.info("https://site.test/a.pdf", "text/html")).route, "web")
        self.assertEqual(classify_response(self.info("https://youtube.com/watch", "text/html")).route, "unsupported")

    def test_disposition_and_octet_stream_route_to_file(self) -> None:
        result = classify_response(self.info("https://site.test/download", "application/octet-stream", "attachment; filename*=UTF-8''report.pdf"))
        self.assertEqual((result.route, result.file_name), ("file", "report.pdf"))

    def test_filename_is_sanitized(self) -> None:
        self.assertEqual(sanitize_filename("../CON.txt"), "_CON.txt")

    def test_probe_failure_is_not_downgraded_to_web(self) -> None:
        class Remote:
            def probe(self, *args, **kwargs): raise RemoteFetchError("failed")
        class Knowledge:
            def import_urls(self, *args, **kwargs): raise AssertionError("must not import")
        result = UrlIngestService(Knowledge(), object(), Remote()).ingest("kb", ["https://public.test/a"])
        self.assertEqual(result.payload["results"][0]["stage"], "probe")

    def test_file_mime_is_forwarded_to_upload(self) -> None:
        class Remote:
            def probe(self, *args, **kwargs):
                return RemoteResponseInfo("https://public.test/a", "https://public.test/a", 200, {"content-type": "application/pdf", "content-disposition": "attachment; filename=report.txt"}, "HEAD")
            def download(self, url, destination, **kwargs): destination.write_bytes(b"pdf")
        class Upload:
            content_type = None
            def upload_one(self, *args, **kwargs):
                self.content_type = kwargs["content_type"]
                return {"status": "success", "stage": "complete", "media_id": "m"}
        upload = Upload()
        UrlIngestService(object(), upload, Remote()).ingest("kb", ["https://public.test/a"])
        self.assertEqual(upload.content_type, "application/pdf")

    def test_arxiv_and_github_raw_fixtures_route_to_files(self) -> None:
        fixture_dir = Path(__file__).parent / "fixtures" / "url_ingest"
        for name in ("arxiv_pdf.json", "github_raw.json"):
            data = json.loads((fixture_dir / name).read_text(encoding="utf-8"))
            info = RemoteResponseInfo(data["original_url"], data["final_url"], data["status"], data["headers"], data["method"])
            with self.subTest(name=name): self.assertEqual(classify_response(info).route, "file")
