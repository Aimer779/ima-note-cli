from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import urlparse

from .errors import InputError
from .knowledge_api import KnowledgeBaseApiClient, KnowledgeBaseResult, KnowledgeBaseSummary, KnowledgeEntry
from .knowledge_upload import build_file_info_payload, inspect_upload_file, upload_to_cos
from .media_service import MediaContentService


def add_kb_subcommands(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    search_base_parser = subparsers.add_parser("search-base", help="Search knowledge bases by name.")
    search_base_parser.add_argument("query", help="Knowledge base query text.")
    search_base_parser.add_argument("--cursor", default="", help='Cursor for pagination (default: "").')
    search_base_parser.add_argument("--limit", type=int, default=20, help="Maximum number of results to request.")
    search_base_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    search_base_parser.set_defaults(kb_action="search-base")

    show_base_parser = subparsers.add_parser("show-base", help="Show a knowledge base by ID.")
    show_base_parser.add_argument("--kb-id", required=True, help="Knowledge base ID.")
    show_base_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    show_base_parser.set_defaults(kb_action="show-base")

    browse_parser = subparsers.add_parser("browse", help="Browse the contents of a knowledge base.")
    browse_parser.add_argument("--kb-id", required=True, help="Knowledge base ID.")
    browse_parser.add_argument("--folder-id", help="Optional folder ID inside the knowledge base.")
    browse_parser.add_argument("--cursor", default="", help='Cursor for pagination (default: "").')
    browse_parser.add_argument("--limit", type=int, default=20, help="Maximum number of results to request.")
    browse_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    browse_parser.set_defaults(kb_action="browse")

    search_parser = subparsers.add_parser("search", help="Search within a knowledge base.")
    search_parser.add_argument("query", help="Query text to search for.")
    search_parser.add_argument("--kb-id", required=True, help="Knowledge base ID.")
    search_parser.add_argument("--cursor", default="", help='Cursor for pagination (default: "").')
    search_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    search_parser.set_defaults(kb_action="search")

    addable_parser = subparsers.add_parser("addable", help="List knowledge bases you can add content to.")
    addable_parser.add_argument("--cursor", default="", help='Cursor for pagination (default: "").')
    addable_parser.add_argument("--limit", type=int, default=20, help="Maximum number of results to request.")
    addable_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    addable_parser.set_defaults(kb_action="addable")

    add_note_parser = subparsers.add_parser("add-note", help="Add an existing note to a knowledge base.")
    add_note_parser.add_argument("--kb-id", required=True, help="Knowledge base ID.")
    note_id_group = add_note_parser.add_mutually_exclusive_group(required=True)
    note_id_group.add_argument("--note-id", help="Note ID.")
    note_id_group.add_argument(
        "--doc-id",
        dest="deprecated_doc_id",
        help="Deprecated compatibility alias for --note-id.",
    )
    add_note_parser.add_argument("--title", help="Title to show inside the knowledge base. Defaults to the note ID.")
    add_note_parser.add_argument("--folder-id", help="Optional folder ID inside the knowledge base.")
    add_note_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    add_note_parser.set_defaults(kb_action="add-note")

    add_url_parser = subparsers.add_parser("add-url", help="Import one or more URLs into a knowledge base.")
    add_url_parser.add_argument("--kb-id", required=True, help="Knowledge base ID.")
    add_url_parser.add_argument("--url", dest="urls", action="append", required=True, help="URL to import.")
    add_url_parser.add_argument("--folder-id", help="Optional folder ID inside the knowledge base.")
    add_url_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    add_url_parser.set_defaults(kb_action="add-url")

    add_file_parser = subparsers.add_parser("add-file", help="Upload a file into a knowledge base.")
    add_file_parser.add_argument("--kb-id", required=True, help="Knowledge base ID.")
    add_file_parser.add_argument("--file", required=True, help="Path to the local file.")
    add_file_parser.add_argument("--folder-id", help="Optional folder ID inside the knowledge base.")
    add_file_parser.add_argument("--content-type", help="Optional MIME type override.")
    add_file_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    add_file_parser.set_defaults(kb_action="add-file")

    media_info = subparsers.add_parser("media-info", help="Inspect safe metadata for original media.")
    media_info.add_argument("--media-id", required=True, help="Media ID.")
    media_info.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    media_info.set_defaults(kb_action="media-info")

    read_parser = subparsers.add_parser("read", help="Read note or textual URL media.")
    read_parser.add_argument("--media-id", required=True, help="Media ID.")
    read_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    read_parser.set_defaults(kb_action="read")

    export_parser = subparsers.add_parser("export", help="Export original media to a file.")
    export_parser.add_argument("--media-id", required=True, help="Media ID.")
    export_parser.add_argument("--output", required=True, help="Destination file path.")
    export_parser.add_argument("--force", action="store_true", help="Replace an existing destination atomically.")
    export_parser.add_argument("--json", action="store_true", dest="as_json", help="Print structured JSON.")
    export_parser.set_defaults(kb_action="export")


def handle_kb_command(args: argparse.Namespace, client: KnowledgeBaseApiClient, media_service: MediaContentService | None = None) -> int:
    if args.kb_action == "search-base":
        return handle_search_base(client, args.query, args.limit, args.cursor, args.as_json)
    if args.kb_action == "show-base":
        return handle_show_base(client, args.kb_id, args.as_json)
    if args.kb_action == "browse":
        return handle_browse(client, args.kb_id, args.limit, args.cursor, args.folder_id, args.as_json)
    if args.kb_action == "search":
        return handle_search(client, args.query, args.kb_id, args.cursor, args.as_json)
    if args.kb_action == "addable":
        return handle_addable(client, args.limit, args.cursor, args.as_json)
    if args.kb_action == "add-note":
        note_id = args.note_id or args.deprecated_doc_id
        return handle_add_note(
            client,
            args.kb_id,
            note_id,
            args.title,
            args.folder_id,
            args.as_json,
            used_deprecated_doc_id=args.deprecated_doc_id is not None,
        )
    if args.kb_action == "add-url":
        return handle_add_url(client, args.kb_id, args.urls, args.folder_id, args.as_json)
    if args.kb_action == "add-file":
        return handle_add_file(client, args.kb_id, args.file, args.folder_id, args.content_type, args.as_json)
    if args.kb_action in {"media-info", "read", "export"}:
        if media_service is None:
            raise RuntimeError("media service was not configured")
        if args.kb_action == "media-info":
            return handle_media_info(media_service, args.media_id, args.as_json)
        if args.kb_action == "read":
            return handle_media_read(media_service, args.media_id, args.as_json)
        return handle_media_export(media_service, args.media_id, args.output, args.force, args.as_json)
    raise InputError("Unknown knowledge-base command.")


def handle_media_info(service: MediaContentService, media_id: str, as_json: bool) -> int:
    payload = service.inspect_media(media_id).to_safe_dict()
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    for key in ("media_id", "media_type", "source_kind", "available", "note_id", "safe_host"):
        if key in payload:
            print(f"{key}: {payload[key]}")
    if payload.get("header_names"):
        print("header_names: " + ", ".join(payload["header_names"]))
    return 0


def handle_media_read(service: MediaContentService, media_id: str, as_json: bool) -> int:
    result = service.read_media(media_id)
    payload = {"media_id": result.media_id, "media_type": result.media_type, "source_kind": result.source_kind,
               "content_type": result.content_type, "content": result.content}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Source: {result.source_kind} ({result.content_type})")
        print()
        print(result.content)
    return 0


def handle_media_export(service: MediaContentService, media_id: str, output: str, force: bool, as_json: bool) -> int:
    result = service.export_media(media_id, output, force=force)
    payload = {"media_id": result.media_id, "media_type": result.media_type, "source_kind": result.source_kind,
               "content_type": result.content_type, "output": result.output, "bytes": result.bytes_count, "sha256": result.sha256}
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Exported: {result.output}")
        print(f"Bytes: {result.bytes_count}")
        print(f"SHA-256: {result.sha256}")
    return 0


def handle_search_base(
    client: KnowledgeBaseApiClient,
    query: str,
    limit: int,
    cursor: str,
    as_json: bool,
) -> int:
    if limit <= 0:
        raise InputError("--limit must be between 1 and 20.")
    result = client.search_knowledge_bases(query, limit, cursor=cursor)
    if as_json:
        print(
            json.dumps(
                {
                    "query": query,
                    "next_cursor": result["next_cursor"],
                    "is_end": result["is_end"],
                    "knowledge_bases": [kb_summary_to_dict(item) for item in result["knowledge_bases"]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(f"Query: {query}")
    print(f"Next cursor: {result['next_cursor'] or '(none)'}")
    print(f"Complete: {bool(result['is_end'])}")
    print()
    print_kb_summaries(result["knowledge_bases"], empty_text="No knowledge bases matched the query.")
    return 0


def handle_show_base(client: KnowledgeBaseApiClient, knowledge_base_id: str, as_json: bool) -> int:
    result = client.get_knowledge_base(knowledge_base_id)
    if result is None:
        raise InputError(f"Knowledge base not found: {knowledge_base_id}")
    if as_json:
        print(json.dumps(kb_detail_to_dict(result), ensure_ascii=False, indent=2))
        return 0
    print(f"Knowledge Base: {result.name or '(unnamed knowledge base)'}")
    print(f"kb_id: {result.knowledge_base_id}")
    if result.description:
        print(f"Description: {result.description}")
    if result.recommended_questions:
        print("Recommended questions:")
        for question in result.recommended_questions:
            print(f"  - {question}")
    return 0


def handle_browse(
    client: KnowledgeBaseApiClient,
    knowledge_base_id: str,
    limit: int,
    cursor: str,
    folder_id: str | None,
    as_json: bool,
) -> int:
    if limit <= 0:
        raise InputError("--limit must be between 1 and 50.")
    result = client.list_knowledge(knowledge_base_id, limit, cursor=cursor, folder_id=folder_id)
    if as_json:
        print(
            json.dumps(
                {
                    "knowledge_base_id": knowledge_base_id,
                    "folder_id": folder_id or "",
                    "current_path": [path_node_to_dict(node) for node in result["current_path"]],
                    "next_cursor": result["next_cursor"],
                    "is_end": result["is_end"],
                    "items": [kb_entry_to_dict(item) for item in result["items"]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    path_label = " / ".join(node.name for node in result["current_path"]) or "(root)"
    print(f"Knowledge base: {knowledge_base_id}")
    print(f"Path: {path_label}")
    print(f"Next cursor: {result['next_cursor'] or '(none)'}")
    print(f"Complete: {bool(result['is_end'])}")
    print()
    print_kb_entries(result["items"], empty_text="No knowledge items returned.")
    return 0


def handle_search(
    client: KnowledgeBaseApiClient,
    query: str,
    knowledge_base_id: str,
    cursor: str,
    as_json: bool,
) -> int:
    result = client.search_knowledge(query, knowledge_base_id, cursor=cursor)
    if as_json:
        print(
            json.dumps(
                {
                    "query": query,
                    "knowledge_base_id": knowledge_base_id,
                    "next_cursor": result["next_cursor"],
                    "is_end": result["is_end"],
                    "items": [kb_entry_to_dict(item) for item in result["items"]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(f"Knowledge base: {knowledge_base_id}")
    print(f"Query: {query}")
    print(f"Next cursor: {result['next_cursor'] or '(none)'}")
    print(f"Complete: {bool(result['is_end'])}")
    print()
    print_kb_entries(result["items"], empty_text="No knowledge items matched the query.")
    return 0


def handle_addable(client: KnowledgeBaseApiClient, limit: int, cursor: str, as_json: bool) -> int:
    if limit <= 0:
        raise InputError("--limit must be between 1 and 50.")
    result = client.list_addable_knowledge_bases(limit, cursor=cursor)
    if as_json:
        print(
            json.dumps(
                {
                    "next_cursor": result["next_cursor"],
                    "is_end": result["is_end"],
                    "knowledge_bases": [kb_summary_to_dict(item) for item in result["knowledge_bases"]],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(f"Next cursor: {result['next_cursor'] or '(none)'}")
    print(f"Complete: {bool(result['is_end'])}")
    print()
    print_kb_summaries(result["knowledge_bases"], empty_text="No addable knowledge bases returned.")
    return 0


def handle_add_note(
    client: KnowledgeBaseApiClient,
    knowledge_base_id: str,
    note_id: str,
    title: str | None,
    folder_id: str | None,
    as_json: bool,
    *,
    used_deprecated_doc_id: bool = False,
) -> int:
    result = client.add_note(
        knowledge_base_id,
        note_id,
        title=title.strip() if title and title.strip() else note_id,
        folder_id=folder_id,
    )
    if as_json:
        output = dict(result)
        output["warnings"] = (
            ["--doc-id is deprecated; use --note-id instead."] if used_deprecated_doc_id else []
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    if used_deprecated_doc_id:
        print("Warning: --doc-id is deprecated; use --note-id instead.", file=sys.stderr)
    print(f"Added note to knowledge base: {result['media_id'] or '(pending media id)'}")
    print(f"kb_id: {result['knowledge_base_id']}")
    print(f"note_id: {result['note_id']}")
    if result["folder_id"]:
        print(f"folder_id: {result['folder_id']}")
    return 0


def handle_add_url(
    client: KnowledgeBaseApiClient,
    knowledge_base_id: str,
    urls: list[str],
    folder_id: str | None,
    as_json: bool,
) -> int:
    validate_urls(urls)
    result = client.import_urls(knowledge_base_id, urls, folder_id=folder_id)
    payload = {
        "knowledge_base_id": knowledge_base_id,
        "folder_id": folder_id or "",
        "results": [import_url_result_to_dict(item) for item in result["results"]],
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"Knowledge base: {knowledge_base_id}")
    if folder_id:
        print(f"Folder: {folder_id}")
    print()
    if not result["results"]:
        print("No URL results returned.")
        return 0
    for item in result["results"]:
        status = "ok" if item.ret_code in (0, None) else f"error({item.ret_code})"
        print(f"- {item.url} [{status}]")
        if item.media_id:
            print(f"  media_id: {item.media_id}")
    return 0


def handle_add_file(
    client: KnowledgeBaseApiClient,
    knowledge_base_id: str,
    file_path: str,
    folder_id: str | None,
    content_type: str | None,
    as_json: bool,
) -> int:
    file_info = inspect_upload_file(file_path, content_type=content_type)
    repeated = client.check_repeated_names(
        knowledge_base_id,
        [{"name": file_info.file_name, "media_type": file_info.media_type}],
        folder_id=folder_id,
    )
    if any(item.is_repeated for item in repeated):
        raise InputError(f"File already exists in the target knowledge base: {file_info.file_name}")
    media = client.create_media(
        knowledge_base_id,
        file_name=file_info.file_name,
        file_size=file_info.file_size,
        content_type=file_info.content_type,
        file_ext=file_info.file_ext,
    )
    upload_to_cos(file_info, media["cos_credential"])
    result = client.add_file(
        knowledge_base_id,
        media_type=file_info.media_type,
        media_id=media["media_id"],
        title=file_info.file_name,
        file_info=build_file_info_payload(file_info, media["cos_credential"]),
        folder_id=folder_id,
    )
    payload = {
        "knowledge_base_id": knowledge_base_id,
        "folder_id": folder_id or "",
        "media_id": result["media_id"],
        "title": result["title"],
        "file_name": file_info.file_name,
        "media_type": file_info.media_type,
    }
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    print(f"Added file to knowledge base: {result['title']}")
    print(f"kb_id: {knowledge_base_id}")
    if folder_id:
        print(f"folder_id: {folder_id}")
    print(f"media_id: {result['media_id']}")
    return 0


def print_kb_summaries(items: list[KnowledgeBaseSummary], *, empty_text: str) -> None:
    if not items:
        print(empty_text)
        return
    for index, item in enumerate(items, start=1):
        print(f"{index}. {item.name or '(unnamed knowledge base)'}")
        print(f"   kb_id: {item.knowledge_base_id}")
        if item.cover_url:
            print(f"   cover_url: {item.cover_url}")
        print()


def print_kb_entries(items: list[KnowledgeEntry], *, empty_text: str) -> None:
    if not items:
        print(empty_text)
        return
    for index, item in enumerate(items, start=1):
        print(f"{index}. {item.title or '(untitled)'}")
        print(f"   type: {item.kind}")
        print(f"   id: {item.item_id}")
        if item.parent_folder_id:
            print(f"   parent_folder_id: {item.parent_folder_id}")
        if item.kind == "folder":
            if item.file_number is not None:
                print(f"   files: {item.file_number}")
            if item.folder_number is not None:
                print(f"   folders: {item.folder_number}")
        elif item.highlight_content:
            print(f"   highlight: {item.highlight_content}")
        print()


def kb_summary_to_dict(item: KnowledgeBaseSummary) -> dict[str, object]:
    return {
        "knowledge_base_id": item.knowledge_base_id,
        "name": item.name,
        "cover_url": item.cover_url,
    }


def kb_detail_to_dict(item: KnowledgeBaseResult) -> dict[str, object]:
    return {
        "knowledge_base_id": item.knowledge_base_id,
        "name": item.name,
        "cover_url": item.cover_url,
        "description": item.description,
        "recommended_questions": list(item.recommended_questions),
    }


def kb_entry_to_dict(item: KnowledgeEntry) -> dict[str, object]:
    return {
        "kind": item.kind,
        "item_id": item.item_id,
        "title": item.title,
        "parent_folder_id": item.parent_folder_id,
        "highlight_content": item.highlight_content,
        "file_number": item.file_number,
        "folder_number": item.folder_number,
        "is_top": item.is_top,
    }


def path_node_to_dict(item: object) -> dict[str, object]:
    return {
        "folder_id": getattr(item, "folder_id", ""),
        "name": getattr(item, "name", ""),
    }


def import_url_result_to_dict(item: object) -> dict[str, object]:
    return {
        "url": getattr(item, "url", ""),
        "ret_code": getattr(item, "ret_code", None),
        "media_id": getattr(item, "media_id", ""),
    }


def validate_urls(urls: list[str]) -> None:
    if not urls:
        raise InputError("At least one --url is required.")
    if len(urls) > 10:
        raise InputError("No more than 10 URLs can be imported at once.")
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise InputError("A URL uses an unsupported scheme; only HTTP and HTTPS are accepted.")
        if url.startswith("file://"):
            raise InputError("Local HTML files are not supported. Only supported in the IMA desktop app.")
        normalized_host = parsed.netloc.lower()
        normalized_path = parsed.path.lower()
        if normalized_host == "www.bilibili.com" and normalized_path.startswith("/video/"):
            raise InputError("Bilibili video URLs are not supported. Only supported in the IMA desktop app.")
        if normalized_host == "www.youtube.com" and normalized_path == "/watch":
            raise InputError("YouTube video URLs are not supported. Only supported in the IMA desktop app.")
        file_ext = normalized_path.rsplit(".", 1)[-1] if "." in normalized_path else ""
        if file_ext in {"pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx", "csv", "md", "markdown", "txt", "xmind"}:
            raise InputError("A file-like URL was detected. Download it first and use `ima kb add-file`.")
