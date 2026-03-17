from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
from typing import Sequence

from .api import ApiError, FolderResult, ImaNoteApiClient, SearchResult
from .config import ConfigError, CredentialStatus, inspect_credentials, load_credentials


HTML_TAG_RE = re.compile(r"<[^>]+>")
SORT_TYPE_MAP = {
    "updated": 0,
    "created": 1,
    "title": 2,
    "size": 3,
}
SEARCH_TYPE_MAP = {
    "title": 0,
    "content": 1,
}
FOLDER_TYPE_LABELS = {
    0: "custom",
    1: "all-notes",
    2: "uncategorized",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ima-note",
        description="Manage IMA notes from the command line.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    auth_parser = subparsers.add_parser("auth", help="Check whether IMA credentials are configured.")
    auth_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print structured JSON instead of human-readable output.",
    )

    search_parser = subparsers.add_parser("search", help="Search notes by title or content.")
    search_parser.add_argument("query", help="Query text to search for.")
    search_parser.add_argument(
        "--search-type",
        choices=tuple(SEARCH_TYPE_MAP.keys()),
        default="title",
        help="Search by title or note content (default: title).",
    )
    search_parser.add_argument(
        "--sort",
        choices=tuple(SORT_TYPE_MAP.keys()),
        default="updated",
        help="Sort order for search results (default: updated).",
    )
    search_parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Offset for the search request (default: 0).",
    )
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

    folders_parser = subparsers.add_parser("folders", help="List note folders.")
    folders_parser.add_argument(
        "--cursor",
        default="0",
        help='Cursor for folder pagination (default: "0").',
    )
    folders_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of folders to request from the API (default: 20).",
    )
    folders_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print structured JSON instead of human-readable output.",
    )

    list_parser = subparsers.add_parser("list", help="List notes within a folder or the root notes view.")
    list_parser.add_argument(
        "--folder-id",
        default="",
        help="Folder ID to list. Omit to list the root notes view.",
    )
    list_parser.add_argument(
        "--cursor",
        default="",
        help='Cursor for note pagination (default: "").',
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of notes to request from the API (default: 20).",
    )
    list_parser.add_argument(
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

    create_parser = subparsers.add_parser("create", help="Create a new note from Markdown content.")
    create_parser.add_argument(
        "--title",
        help="Optional title to wrap around the provided body content.",
    )
    create_parser.add_argument(
        "--folder-id",
        default="",
        help="Optional folder ID to create the note inside.",
    )
    create_parser_content = create_parser.add_mutually_exclusive_group(required=True)
    create_parser_content.add_argument(
        "--content",
        help="Markdown content for the new note.",
    )
    create_parser_content.add_argument(
        "--file",
        help="Path to a UTF-8 Markdown file for the new note.",
    )
    create_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print structured JSON instead of human-readable output.",
    )

    append_parser = subparsers.add_parser("append", help="Append Markdown content to an existing note.")
    append_parser.add_argument("doc_id", help="Document ID to append to.")
    append_parser_content = append_parser.add_mutually_exclusive_group(required=True)
    append_parser_content.add_argument(
        "--content",
        help="Markdown content to append.",
    )
    append_parser_content.add_argument(
        "--file",
        help="Path to a UTF-8 Markdown file with the content to append.",
    )
    append_parser.add_argument(
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
        status = inspect_credentials(Path.cwd())

        if args.command == "auth":
            return _handle_auth(status, args.as_json)

        credentials = load_credentials(Path.cwd())
        client = ImaNoteApiClient(credentials)

        if args.command == "search":
            return _handle_search(
                client,
                args.query,
                args.limit,
                args.as_json,
                start=args.start,
                search_type=args.search_type,
                sort=args.sort,
            )
        if args.command == "folders":
            return _handle_folders(client, args.limit, args.cursor, args.as_json)
        if args.command == "list":
            return _handle_list(client, args.limit, args.folder_id, args.cursor, args.as_json)
        if args.command == "get":
            return _handle_get(client, args.doc_id, args.as_json)
        if args.command == "create":
            return _handle_create(client, args.title, args.content, args.file, args.folder_id, args.as_json)
        if args.command == "append":
            return _handle_append(client, args.doc_id, args.content, args.file, args.as_json)
    except (ConfigError, ApiError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    parser.error("Unknown command")
    return 2


def _handle_auth(status: CredentialStatus, as_json: bool) -> int:
    payload = {
        "configured": status.is_configured,
        "credentials": {
            "IMA_OPENAPI_CLIENTID": {
                "set": bool(status.client_id),
                "source": status.client_id_source,
            },
            "IMA_OPENAPI_APIKEY": {
                "set": bool(status.api_key),
                "source": status.api_key_source,
            },
        },
    }

    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if status.is_configured else 1

    print(f"Status: {'configured' if status.is_configured else 'missing credentials'}")
    print(
        "IMA_OPENAPI_CLIENTID: "
        f"{'set' if status.client_id else 'missing'}"
        f"{_format_source_suffix(status.client_id_source)}"
    )
    print(
        "IMA_OPENAPI_APIKEY: "
        f"{'set' if status.api_key else 'missing'}"
        f"{_format_source_suffix(status.api_key_source)}"
    )

    if status.is_configured:
        return 0

    print()
    print("Configure the missing values in the environment or a project-root .env file.", file=sys.stderr)
    return 1


def _handle_search(
    client: ImaNoteApiClient,
    query: str,
    limit: int,
    as_json: bool,
    *,
    start: int,
    search_type: str,
    sort: str,
) -> int:
    if limit <= 0:
        raise ValueError("--limit must be greater than 0.")
    if start < 0:
        raise ValueError("--start must be greater than or equal to 0.")

    result = client.search_notes(
        query,
        limit,
        start=start,
        search_type=SEARCH_TYPE_MAP[search_type],
        sort_type=SORT_TYPE_MAP[sort],
    )
    if as_json:
        json_payload = {
            "query": query,
            "search_type": search_type,
            "sort": sort,
            "start": result.get("start", start),
            "total_hit_num": result["total_hit_num"],
            "is_end": result["is_end"],
            "docs": [_search_result_to_dict(doc) for doc in result["docs"]],
        }
        print(json.dumps(json_payload, ensure_ascii=False, indent=2))
        return 0

    _print_search_results(query, result["docs"], result["total_hit_num"], search_type)
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


def _handle_folders(client: ImaNoteApiClient, limit: int, cursor: str, as_json: bool) -> int:
    if limit <= 0:
        raise ValueError("--limit must be greater than 0.")

    result = client.list_folders(limit, cursor=cursor)
    if as_json:
        payload = {
            "cursor": cursor,
            "next_cursor": result["next_cursor"],
            "is_end": result["is_end"],
            "folders": [_folder_result_to_dict(folder) for folder in result["folders"]],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"Cursor: {cursor}")
    print(f"Next cursor: {result['next_cursor'] or '(none)'}")
    print(f"Complete: {bool(result['is_end'])}")
    print()
    if not result["folders"]:
        print("No folders returned.")
        return 0

    for index, folder in enumerate(result["folders"], start=1):
        folder_type = FOLDER_TYPE_LABELS.get(folder.folder_type, "unknown")
        modify_time = _format_timestamp(folder.modify_time)
        print(f"{index}. {folder.name or '(unnamed folder)'}")
        print(f"   folder_id: {folder.folder_id}")
        print(f"   type: {folder_type}")
        if folder.note_number is not None:
            print(f"   notes: {folder.note_number}")
        if modify_time:
            print(f"   updated: {modify_time}")
        print()
    return 0


def _handle_list(
    client: ImaNoteApiClient,
    limit: int,
    folder_id: str,
    cursor: str,
    as_json: bool,
) -> int:
    if limit <= 0:
        raise ValueError("--limit must be greater than 0.")

    result = client.list_notes(limit, folder_id=folder_id, cursor=cursor)
    if as_json:
        payload = {
            "folder_id": folder_id,
            "cursor": cursor,
            "next_cursor": result["next_cursor"],
            "is_end": result["is_end"],
            "notes": [_search_result_to_dict(note) for note in result["notes"]],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    scope_label = folder_id or "(root notes view)"
    print(f"Folder: {scope_label}")
    print(f"Cursor: {cursor or '(start)'}")
    print(f"Next cursor: {result['next_cursor'] or '(none)'}")
    print(f"Complete: {bool(result['is_end'])}")
    print()
    if not result["notes"]:
        print("No notes returned.")
        return 0

    _print_note_summaries(result["notes"])
    return 0


def _handle_create(
    client: ImaNoteApiClient,
    title: str | None,
    content: str | None,
    file_path: str | None,
    folder_id: str,
    as_json: bool,
) -> int:
    markdown_body = _load_markdown_input(content, file_path)
    markdown = _compose_markdown(title, markdown_body)
    result = client.create_note(markdown, folder_id=folder_id or None)

    if as_json:
        payload = {
            "doc_id": result["doc_id"],
            "folder_id": result["folder_id"],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print(f"Created note: {result['doc_id']}")
    if result["folder_id"]:
        print(f"Folder: {result['folder_id']}")
    return 0


def _handle_append(
    client: ImaNoteApiClient,
    doc_id: str,
    content: str | None,
    file_path: str | None,
    as_json: bool,
) -> int:
    markdown = _load_markdown_input(content, file_path)
    result = client.append_note(doc_id, markdown)

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Appended to note: {result['doc_id']}")
    return 0


def _print_search_results(query: str, docs: list[SearchResult], total_hit_num: int, search_type: str) -> None:
    print(f"Search query: {query}")
    print(f"Search type: {search_type}")
    print(f"Matches: {total_hit_num}")
    print()

    if not docs:
        print("No notes matched the query.")
        return

    _print_note_summaries(docs)


def _print_note_summaries(docs: list[SearchResult]) -> None:
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


def _folder_result_to_dict(result: FolderResult) -> dict[str, object]:
    return {
        "folder_id": result.folder_id,
        "name": result.name,
        "note_number": result.note_number,
        "create_time": result.create_time,
        "modify_time": result.modify_time,
        "folder_type": result.folder_type,
        "status": result.status,
        "parent_folder_id": result.parent_folder_id,
    }


def _clean_text(text: str) -> str:
    return HTML_TAG_RE.sub("", text).strip()


def _format_timestamp(timestamp_ms: int | None) -> str:
    if timestamp_ms is None:
        return ""
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _format_source_suffix(source: str | None) -> str:
    if not source:
        return ""
    return f" ({source})"


def _load_markdown_input(content: str | None, file_path: str | None) -> str:
    if content is not None:
        if not content.strip():
            raise ValueError("Content cannot be empty.")
        return content

    if file_path is None:
        raise ValueError("Either --content or --file is required.")

    path = Path(file_path)
    if not path.is_file():
        raise ValueError(f"File not found: {file_path}")

    loaded = path.read_text(encoding="utf-8")
    if not loaded.strip():
        raise ValueError("Content file is empty.")
    return loaded


def _compose_markdown(title: str | None, body: str) -> str:
    if title is None:
        return body
    title_text = title.strip()
    if not title_text:
        raise ValueError("--title cannot be empty.")
    body_text = body.strip()
    if not body_text:
        return f"# {title_text}"
    return f"# {title_text}\n\n{body_text}"
