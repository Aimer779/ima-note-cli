from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from .notes_api import FolderResult, NotesApiClient, SearchResult


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


def add_note_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
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
    search_parser.add_argument("--start", type=int, default=0, help="Offset for the search request (default: 0).")
    search_parser.add_argument("--limit", type=int, default=20, help="Maximum number of results to request.")
    search_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    search_parser.set_defaults(note_action="search")

    folders_parser = subparsers.add_parser("folders", help="List note folders.")
    folders_parser.add_argument("--cursor", default="0", help='Cursor for folder pagination (default: "0").')
    folders_parser.add_argument("--limit", type=int, default=20, help="Maximum number of folders to request.")
    folders_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    folders_parser.set_defaults(note_action="folders")

    list_parser = subparsers.add_parser("list", help="List notes within a folder or the root notes view.")
    list_parser.add_argument("--folder-id", default="", help="Folder ID to list. Omit for the root notes view.")
    list_parser.add_argument("--cursor", default="", help='Cursor for note pagination (default: "").')
    list_parser.add_argument("--limit", type=int, default=20, help="Maximum number of notes to request.")
    list_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    list_parser.set_defaults(note_action="list")

    get_parser = subparsers.add_parser("get", help="Read a note's plain-text content.")
    get_parser.add_argument("doc_id", help="Document ID returned by search.")
    get_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    get_parser.set_defaults(note_action="get")

    create_parser = subparsers.add_parser("create", help="Create a new note from Markdown content.")
    create_parser.add_argument("--title", help="Optional title to wrap around the provided body content.")
    create_parser.add_argument("--folder-id", default="", help="Optional folder ID to create the note inside.")
    create_parser_content = create_parser.add_mutually_exclusive_group(required=True)
    create_parser_content.add_argument("--content", help="Markdown content for the new note.")
    create_parser_content.add_argument("--file", help="Path to a UTF-8 Markdown file for the new note.")
    create_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    create_parser.set_defaults(note_action="create")

    append_parser = subparsers.add_parser("append", help="Append Markdown content to an existing note.")
    append_parser.add_argument("doc_id", help="Document ID to append to.")
    append_parser_content = append_parser.add_mutually_exclusive_group(required=True)
    append_parser_content.add_argument("--content", help="Markdown content to append.")
    append_parser_content.add_argument("--file", help="Path to a UTF-8 Markdown file with the content to append.")
    append_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    append_parser.set_defaults(note_action="append")


def handle_note_command(args: argparse.Namespace, client: NotesApiClient) -> int:
    if args.note_action == "search":
        return handle_search(
            client,
            args.query,
            args.limit,
            args.as_json,
            start=args.start,
            search_type=args.search_type,
            sort=args.sort,
        )
    if args.note_action == "folders":
        return handle_folders(client, args.limit, args.cursor, args.as_json)
    if args.note_action == "list":
        return handle_list(client, args.limit, args.folder_id, args.cursor, args.as_json)
    if args.note_action == "get":
        return handle_get(client, args.doc_id, args.as_json)
    if args.note_action == "create":
        return handle_create(client, args.title, args.content, args.file, args.folder_id, args.as_json)
    if args.note_action == "append":
        return handle_append(client, args.doc_id, args.content, args.file, args.as_json)
    raise ValueError("Unknown note command.")


def handle_search(
    client: NotesApiClient,
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
        print(
            json.dumps(
                {
                    "query": query,
                    "search_type": search_type,
                    "sort": sort,
                    "start": result.get("start", start),
                    "total_hit_num": result["total_hit_num"],
                    "is_end": result["is_end"],
                    "docs": [search_result_to_dict(doc) for doc in result["docs"]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print_search_results(query, result["docs"], result["total_hit_num"], search_type)
    return 0


def handle_get(client: NotesApiClient, doc_id: str, as_json: bool) -> int:
    result = client.get_doc_content(doc_id)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Doc ID: {result['doc_id']}")
    print()
    content = result["content"].rstrip()
    print(content if content else "(empty)")
    return 0


def handle_folders(client: NotesApiClient, limit: int, cursor: str, as_json: bool) -> int:
    if limit <= 0:
        raise ValueError("--limit must be greater than 0.")

    result = client.list_folders(limit, cursor=cursor)
    if as_json:
        print(
            json.dumps(
                {
                    "cursor": cursor,
                    "next_cursor": result["next_cursor"],
                    "is_end": result["is_end"],
                    "folders": [folder_result_to_dict(folder) for folder in result["folders"]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
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
        modify_time = format_timestamp(folder.modify_time)
        print(f"{index}. {folder.name or '(unnamed folder)'}")
        print(f"   folder_id: {folder.folder_id}")
        print(f"   type: {folder_type}")
        if folder.note_number is not None:
            print(f"   notes: {folder.note_number}")
        if modify_time:
            print(f"   updated: {modify_time}")
        print()
    return 0


def handle_list(client: NotesApiClient, limit: int, folder_id: str, cursor: str, as_json: bool) -> int:
    if limit <= 0:
        raise ValueError("--limit must be greater than 0.")

    result = client.list_notes(limit, folder_id=folder_id, cursor=cursor)
    if as_json:
        print(
            json.dumps(
                {
                    "folder_id": folder_id,
                    "cursor": cursor,
                    "next_cursor": result["next_cursor"],
                    "is_end": result["is_end"],
                    "notes": [search_result_to_dict(note) for note in result["notes"]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    print(f"Folder: {folder_id or '(root notes view)'}")
    print(f"Cursor: {cursor or '(start)'}")
    print(f"Next cursor: {result['next_cursor'] or '(none)'}")
    print(f"Complete: {bool(result['is_end'])}")
    print()
    if not result["notes"]:
        print("No notes returned.")
        return 0

    print_note_summaries(result["notes"])
    return 0


def handle_create(
    client: NotesApiClient,
    title: str | None,
    content: str | None,
    file_path: str | None,
    folder_id: str,
    as_json: bool,
) -> int:
    markdown_body = load_markdown_input(content, file_path)
    markdown = compose_markdown(title, markdown_body)
    result = client.create_note(markdown, folder_id=folder_id or None)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Created note: {result['doc_id']}")
    if result["folder_id"]:
        print(f"Folder: {result['folder_id']}")
    return 0


def handle_append(
    client: NotesApiClient,
    doc_id: str,
    content: str | None,
    file_path: str | None,
    as_json: bool,
) -> int:
    markdown = load_markdown_input(content, file_path)
    result = client.append_note(doc_id, markdown)
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(f"Appended to note: {result['doc_id']}")
    return 0


def print_search_results(query: str, docs: list[SearchResult], total_hit_num: int, search_type: str) -> None:
    print(f"Search query: {query}")
    print(f"Search type: {search_type}")
    print(f"Matches: {total_hit_num}")
    print()
    if not docs:
        print("No notes matched the query.")
        return
    print_note_summaries(docs)


def print_note_summaries(docs: list[SearchResult]) -> None:
    for index, doc in enumerate(docs, start=1):
        title = clean_text(doc.highlight_title) or doc.title or "(untitled)"
        summary = clean_text(doc.summary)
        modify_time = format_timestamp(doc.modify_time)
        print(f"{index}. {title}")
        print(f"   doc_id: {doc.doc_id}")
        if doc.folder_name:
            print(f"   folder: {doc.folder_name}")
        if modify_time:
            print(f"   updated: {modify_time}")
        if summary:
            print(f"   summary: {summary}")
        print()


def search_result_to_dict(result: SearchResult) -> dict[str, object]:
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


def folder_result_to_dict(result: FolderResult) -> dict[str, object]:
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


def clean_text(text: str) -> str:
    return HTML_TAG_RE.sub("", text).strip()


def format_timestamp(timestamp_ms: int | None) -> str:
    if timestamp_ms is None:
        return ""
    dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc).astimezone()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def load_markdown_input(content: str | None, file_path: str | None) -> str:
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


def compose_markdown(title: str | None, body: str) -> str:
    if title is None:
        return body
    title_text = title.strip()
    if not title_text:
        raise ValueError("--title cannot be empty.")
    body_text = body.strip()
    if not body_text:
        return f"# {title_text}"
    return f"# {title_text}\n\n{body_text}"
