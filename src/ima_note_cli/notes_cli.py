from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from .errors import InputError
from .notes_api import FolderResult, SearchResult


def _page_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--all", action="store_true", help="Collect all pages.")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum pages when using --all.")


def add_note_subcommands(subparsers: Any) -> None:
    search = subparsers.add_parser("search", help="Search notes by title or content.")
    search.add_argument("query")
    search.add_argument("--search-type", choices=("title", "content"), default="title")
    search.add_argument("--sort", choices=("updated", "created", "title", "size"), default="updated")
    search.add_argument("--start", type=int, default=0)
    search.add_argument("--limit", type=int, default=20)
    _page_options(search); search.add_argument("--json", action="store_true", dest="as_json")

    folders = subparsers.add_parser("folders", help="List note folders.")
    folders.add_argument("--cursor", default="0"); folders.add_argument("--limit", type=int, default=20)
    _page_options(folders); folders.add_argument("--json", action="store_true", dest="as_json")

    listing = subparsers.add_parser("list", help="List notes within a folder or the root notes view.")
    listing.add_argument("--folder-id", default=""); listing.add_argument("--cursor", default="")
    listing.add_argument("--sort", choices=("updated", "created", "title", "size"), default="updated")
    listing.add_argument("--limit", type=int, default=20)
    _page_options(listing); listing.add_argument("--json", action="store_true", dest="as_json")

    get = subparsers.add_parser("get", help="Read a note's plain-text content.")
    get.add_argument("note_id"); get.add_argument("--json", action="store_true", dest="as_json")

    create = subparsers.add_parser("create", help="Create a new note from Markdown content.")
    create.add_argument("--title"); create.add_argument("--folder-id", default="")
    group = create.add_mutually_exclusive_group(required=True); group.add_argument("--content"); group.add_argument("--file")
    create.add_argument("--json", action="store_true", dest="as_json")

    append = subparsers.add_parser("append", help="Append Markdown content to an existing note.")
    append.add_argument("note_id")
    group = append.add_mutually_exclusive_group(required=True); group.add_argument("--content"); group.add_argument("--file")
    append.add_argument("--json", action="store_true", dest="as_json")


def handle_note_command(args: argparse.Namespace, client: Any):
    """Compatibility façade; rendering is owned by output.py."""
    from .commands.notes import execute
    return execute(args, client)


def search_result_to_dict(result: SearchResult) -> dict[str, object]:
    return {"note_id": result.note_id, "doc_id": result.doc_id, "title": result.title, "summary": result.summary,
            "folder_id": result.folder_id, "folder_name": result.folder_name, "create_time": result.create_time,
            "modify_time": result.modify_time, "cover_image": result.cover_image, "status": result.status,
            "highlight_title": result.highlight_title}


def folder_result_to_dict(result: FolderResult) -> dict[str, object]:
    return {"folder_id": result.folder_id, "name": result.name, "note_number": result.note_number,
            "create_time": result.create_time, "modify_time": result.modify_time, "folder_type": result.folder_type,
            "status": result.status, "parent_folder_id": result.parent_folder_id}


def load_markdown_input(content: str | None, file_path: str | None) -> str:
    if content is not None:
        if not content.strip(): raise InputError("Content cannot be empty.")
        return content
    if file_path is None: raise InputError("Either --content or --file is required.")
    path = Path(file_path)
    if not path.is_file(): raise InputError(f"File not found: {file_path}")
    try: loaded = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc: raise InputError(f"Content file must be valid UTF-8: {file_path}") from exc
    if not loaded.strip(): raise InputError("Content file is empty.")
    return loaded


def compose_markdown(title: str | None, body: str) -> str:
    if title is None: return body
    title = title.strip()
    if not title: raise InputError("--title cannot be empty.")
    return f"# {title}\n\n{body.strip()}" if body.strip() else f"# {title}"
