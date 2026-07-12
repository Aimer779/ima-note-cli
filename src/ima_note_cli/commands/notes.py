from __future__ import annotations

from typing import Any

from ..command_result import CommandResult, CommandStatus
from ..notes_cli import compose_markdown, folder_result_to_dict, load_markdown_input, search_result_to_dict
from ..notes_content import prepare_note_markdown
from ..pagination import collect_cursor_pages, collect_offset_pages
from ..validation import validate_max_pages

SEARCH_TYPE_MAP = {"title": 0, "content": 1}
SORT_TYPE_MAP = {"updated": 0, "created": 1, "title": 2}


def execute(args: Any, client: Any) -> CommandResult:
    action = args.note_action
    if action == "search":
        if args.all:
            pages = collect_offset_pages(lambda start: client.search_notes(args.query, args.limit, start=start, search_type=SEARCH_TYPE_MAP[args.search_type], sort_type=SORT_TYPE_MAP[args.sort]), "docs", initial_offset=args.start, max_pages=args.max_pages)
            docs = _dedupe(list(pages.items), lambda item: item.note_id); result = {"start": args.start, "total_hit_num": len(docs), "is_end": pages.complete, "docs": docs}
        else:
            result = client.search_notes(args.query, args.limit, start=args.start, search_type=SEARCH_TYPE_MAP[args.search_type], sort_type=SORT_TYPE_MAP[args.sort]); docs = result["docs"]
        payload = {"query": args.query, "search_type": args.search_type, "sort": args.sort, "start": result.get("start", args.start), "total_hit_num": result["total_hit_num"], "is_end": result["is_end"], "docs": [search_result_to_dict(item) for item in docs]}
        lines = [f"Search query: {args.query}", f"Matches: {result['total_hit_num']}"]
        for item in docs:
            lines.extend([item.title or "(untitled)", f"note_id: {item.note_id}"])
        return _paged(payload, docs, args, lines, pages if args.all else None)
    if action in {"folders", "list"}:
        key = "folders" if action == "folders" else "notes"
        initial = args.cursor
        fetch = (lambda cursor: client.list_folders(args.limit, cursor=cursor)) if action == "folders" else (lambda cursor: client.list_notes(args.limit, folder_id=args.folder_id, cursor=cursor, sort_type=SORT_TYPE_MAP[args.sort]))
        if args.all:
            pages = collect_cursor_pages(fetch, key, initial_cursor=initial, max_pages=args.max_pages)
            values = _dedupe(list(pages.items), lambda item: item.folder_id if action == "folders" else item.note_id); next_cursor = pages.next_cursor; is_end = pages.complete
        else:
            page = fetch(initial); values = page[key]; next_cursor = page["next_cursor"]; is_end = page["is_end"]
        serialized = [folder_result_to_dict(item) if action == "folders" else search_result_to_dict(item) for item in values]
        payload = {"cursor": initial, "next_cursor": next_cursor, "is_end": is_end, key: serialized}
        if action == "list": payload.update({"folder_id": args.folder_id, "sort": args.sort})
        lines = [f"Next cursor: {next_cursor or '(none)'}"]
        for item in values:
            if action == "folders":
                lines.extend([item.name or "(unnamed)", f"folder_id: {item.folder_id}"])
            else:
                lines.extend([item.title or "(unnamed)", f"note_id: {item.note_id}"])
        return _paged(payload, values, args, lines, pages if args.all else None)
    if action == "get":
        result = client.get_doc_content(args.note_id)
        return CommandResult(result, (f"note_id: {result['note_id']}", "", result["content"].rstrip() or "(empty)"))
    if action in {"create", "append"}:
        body = load_markdown_input(args.content, args.file)
        markdown = compose_markdown(args.title, body) if action == "create" else body
        prepared = prepare_note_markdown(markdown)
        result = client.create_note(prepared.content, folder_id=args.folder_id or None) if action == "create" else client.append_note(args.note_id, prepared.content)
        payload = {**result, "warnings": list(prepared.warnings), "removed_local_images": list(prepared.removed_local_images)}
        line = f"Created note: {result['note_id']}" if action == "create" else f"Appended to note: {result['note_id']}"
        warnings = tuple(prepared.warnings) + tuple(f"Removed local image: {item}" for item in prepared.removed_local_images)
        return CommandResult(payload, (line,), warnings)
    raise ValueError("unknown note command")


def _paged(payload: dict[str, Any], values: list[Any], args: Any, lines: list[str], page_info: Any = None) -> CommandResult:
    if args.all:
        payload["pagination"] = {
            "all_requested": True, "max_pages": args.max_pages,
            "pages_fetched": page_info.pages_fetched if page_info else 1,
            "truncated": not payload["is_end"],
            "start": payload.get("start", payload.get("cursor", "")),
            "next": payload.get("next_cursor", ""),
        }
        if not payload["is_end"]:
            item_lines = tuple(lines + ["Pagination stopped at --max-pages."])
            result = CommandResult.batch([{"status": "success"} for _ in values] + [{"status": "not_attempted"}], payload=payload, human_lines=item_lines)
            return result
    status = CommandStatus.SUCCESS if values else CommandStatus.EMPTY
    return CommandResult(payload, tuple(lines), status=status)


def _dedupe(values: list[Any], key: Any) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for value in values:
        identity = key(value)
        if identity not in seen:
            seen.add(identity); result.append(value)
    return result
