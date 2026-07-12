from __future__ import annotations

import argparse
from typing import Any
from urllib.parse import urlsplit

from .errors import InputError
from .knowledge_api import KnowledgeBaseResult, KnowledgeBaseSummary, KnowledgeEntry, KnowledgePathNode


def _json(parser: argparse.ArgumentParser) -> None: parser.add_argument("--json", action="store_true", dest="as_json")
def _pages(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--all", action="store_true"); parser.add_argument("--max-pages", type=int, default=100)


def add_kb_subcommands(subparsers: Any) -> None:
    search_base = subparsers.add_parser("search-base", help="Search knowledge bases.")
    search_base.add_argument("query"); search_base.add_argument("--cursor", default=""); search_base.add_argument("--limit", type=int, default=20); _pages(search_base); _json(search_base)
    show = subparsers.add_parser("show-base", help="Show a knowledge base."); show.add_argument("--kb-id", required=True); _json(show)
    browse = subparsers.add_parser("browse", help="Browse knowledge.")
    browse.add_argument("--kb-id", required=True); browse.add_argument("--folder-id"); browse.add_argument("--cursor", default=""); browse.add_argument("--limit", type=int, default=20); _pages(browse); _json(browse)
    search = subparsers.add_parser("search", help="Search knowledge.")
    search.add_argument("query"); search.add_argument("--kb-id", required=True); search.add_argument("--cursor", default=""); _pages(search); _json(search)
    addable = subparsers.add_parser("addable", help="List addable knowledge bases.")
    addable.add_argument("--cursor", default=""); addable.add_argument("--limit", type=int, default=20); _pages(addable); _json(addable)
    add_note = subparsers.add_parser("add-note", help="Add an IMA note.")
    add_note.add_argument("--kb-id", required=True)
    ids = add_note.add_mutually_exclusive_group(required=True); ids.add_argument("--note-id"); ids.add_argument("--doc-id", dest="deprecated_doc_id")
    add_note.add_argument("--title"); add_note.add_argument("--folder-id"); _json(add_note)
    add_url = subparsers.add_parser("add-url", help="Import web pages or supported remote files.")
    add_url.add_argument("--kb-id", required=True); add_url.add_argument("--url", dest="urls", action="append", required=True); add_url.add_argument("--folder-id")
    add_url.add_argument("--on-conflict", choices=("error", "rename"), default="error"); add_url.add_argument("--download-timeout", type=int, default=300); add_url.add_argument("--upload-timeout", type=int, default=300); _json(add_url)
    add_file = subparsers.add_parser("add-file", help="Upload supported local files.")
    add_file.add_argument("--kb-id", required=True); add_file.add_argument("--file", dest="files", action="append", required=True); add_file.add_argument("--folder-id"); add_file.add_argument("--content-type")
    add_file.add_argument("--on-conflict", choices=("error", "rename"), default="error"); add_file.add_argument("--upload-timeout", type=int, default=300); _json(add_file)
    info = subparsers.add_parser("media-info", help="Inspect original media."); info.add_argument("--media-id", required=True); _json(info)
    read = subparsers.add_parser("read", help="Read original media."); read.add_argument("--media-id", required=True); _json(read)
    export = subparsers.add_parser("export", help="Export original media."); export.add_argument("--media-id", required=True); export.add_argument("--output", required=True); export.add_argument("--force", action="store_true"); _json(export)


def handle_kb_command(args: argparse.Namespace, client: Any, media_service: Any = None):
    """Compatibility façade; rendering is owned by output.py."""
    from .commands.knowledge import execute
    return execute(args, client, media_service=media_service)


def kb_summary_to_dict(item: KnowledgeBaseSummary) -> dict[str, object]:
    return {"knowledge_base_id": item.knowledge_base_id, "name": item.name, "cover_url": item.cover_url}


def kb_detail_to_dict(item: KnowledgeBaseResult) -> dict[str, object]:
    return {"knowledge_base_id": item.knowledge_base_id, "name": item.name, "cover_url": item.cover_url, "description": item.description, "recommended_questions": list(item.recommended_questions)}


def kb_entry_to_dict(item: KnowledgeEntry) -> dict[str, object]:
    return {"kind": item.kind, "item_id": item.item_id, "media_id": item.media_id, "folder_id": item.folder_id, "title": item.title, "parent_folder_id": item.parent_folder_id, "highlight_content": item.highlight_content, "file_number": item.file_number, "folder_number": item.folder_number, "is_top": item.is_top}


def path_node_to_dict(item: KnowledgePathNode) -> dict[str, object]:
    return {"folder_id": item.folder_id, "name": item.name}


def validate_urls(urls: list[str]) -> None:
    if not 1 <= len(urls) <= 10: raise InputError("--url must be provided between 1 and 10 times.")
    for value in urls:
        try: parsed = urlsplit(value)
        except ValueError as exc: raise InputError("Each URL must be an absolute HTTP or HTTPS URL.") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InputError("Each URL must be an absolute HTTP or HTTPS URL.")
