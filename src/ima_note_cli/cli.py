from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Sequence

from .api import ApiError, ImaNoteApiClient, SearchResult
from .config import ConfigError, load_credentials


HTML_TAG_RE = re.compile(r"<[^>]+>")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ima-note",
        description="Search and read IMA notes from the command line.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search", help="Search notes by title.")
    search_parser.add_argument("query", help="Title query to search for.")
    search_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of results to request from the API (default: 20).",
    )
    search_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print structured JSON instead of human-readable output.",
    )

    get_parser = subparsers.add_parser("get", help="Read a note's plain-text content.")
    get_parser.add_argument("doc_id", help="Document ID returned by search.")
    get_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print structured JSON instead of human-readable output.",
    )

    return parser


def run(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        credentials = load_credentials(Path.cwd())
        client = ImaNoteApiClient(credentials)

        if args.command == "search":
            return _handle_search(client, args.query, args.limit, args.as_json)
        if args.command == "get":
            return _handle_get(client, args.doc_id, args.as_json)
    except (ConfigError, ApiError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.error("Unknown command")
    return 2


def _handle_search(client: ImaNoteApiClient, query: str, limit: int, as_json: bool) -> int:
    if limit <= 0:
        raise ValueError("--limit must be greater than 0.")

    result = client.search_notes(query, limit)
    if as_json:
        json_payload = {
            "query": query,
            "total_hit_num": result["total_hit_num"],
            "is_end": result["is_end"],
            "docs": [_search_result_to_dict(doc) for doc in result["docs"]],
        }
        print(json.dumps(json_payload, ensure_ascii=False, indent=2))
        return 0

    _print_search_results(query, result["docs"], result["total_hit_num"])
    return 0


def _handle_get(client: ImaNoteApiClient, doc_id: str, as_json: bool) -> int:
    result = client.get_doc_content(doc_id)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Doc ID: {result['doc_id']}")
    print()
    content = result["content"].rstrip()
    if content:
        print(content)
    else:
        print("(empty)")
    return 0


def _print_search_results(query: str, docs: list[SearchResult], total_hit_num: int) -> None:
    print(f"Search query: {query}")
    print(f"Matches: {total_hit_num}")
    print()

    if not docs:
        print("No notes matched the query.")
        return

    for index, doc in enumerate(docs, start=1):
        title = _clean_text(doc.highlight_title) or doc.title or "(untitled)"
        summary = _clean_text(doc.summary)
        modify_time = _format_timestamp(doc.modify_time)

        print(f"{index}. {title}")
        print(f"   doc_id: {doc.doc_id}")
        if doc.folder_name:
            print(f"   folder: {doc.folder_name}")
        if modify_time:
            print(f"   updated: {modify_time}")
        if summary:
            print(f"   summary: {summary}")
        print()


def _search_result_to_dict(result: SearchResult) -> dict[str, object]:
    return {
        "doc_id": result.doc_id,
        "title": result.title,
        "summary": result.summary,
        "folder_id": result.folder_id,
        "folder_name": result.folder_name,
        "create_time": result.create_time,
        "modify_time": result.modify_time,
        "status": result.status,
        "highlight_title": result.highlight_title,
    }


def _clean_text(text: str) -> str:
    return HTML_TAG_RE.sub("", text).strip()


def _format_timestamp(timestamp_ms: int | None) -> str:
    if timestamp_ms is None:
        return ""
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")
