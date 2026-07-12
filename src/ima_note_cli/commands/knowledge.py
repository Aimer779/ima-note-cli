from __future__ import annotations

from typing import Any

from ..command_result import CommandResult, CommandStatus
from ..errors import ExitCode, ImaCliError
from ..knowledge_cli import kb_detail_to_dict, kb_entry_to_dict, kb_summary_to_dict, path_node_to_dict
from ..pagination import collect_cursor_pages


def execute(args: Any, client: Any, *, media_service: Any = None, upload_service: Any = None, url_service: Any = None) -> CommandResult:
    action = args.kb_action
    if action == "search-base":
        return _cursor(args, lambda cursor: client.search_knowledge_bases(args.query, args.limit, cursor=cursor), "knowledge_bases", kb_summary_to_dict, {"query": args.query})
    if action == "addable":
        return _cursor(args, lambda cursor: client.list_addable_knowledge_bases(args.limit, cursor=cursor), "knowledge_bases", kb_summary_to_dict, {})
    if action == "browse":
        return _cursor(args, lambda cursor: client.list_knowledge(args.kb_id, args.limit, cursor=cursor, folder_id=args.folder_id), "items", kb_entry_to_dict, {"knowledge_base_id": args.kb_id, "folder_id": args.folder_id or ""})
    if action == "search":
        return _cursor(args, lambda cursor: client.search_knowledge(args.query, args.kb_id, cursor=cursor), "items", kb_entry_to_dict, {"query": args.query, "knowledge_base_id": args.kb_id})
    if action == "show-base":
        value = client.get_knowledge_base(args.kb_id)
        payload = {"knowledge_base": kb_detail_to_dict(value) if value else None}
        lines = (f"Knowledge base: {value.name}", value.description, *value.recommended_questions) if value else ("Knowledge base not found.",)
        return CommandResult(payload, tuple(lines), status=CommandStatus.SUCCESS if value else CommandStatus.EMPTY)
    if action == "add-note":
        deprecated = getattr(args, "deprecated_doc_id", None)
        note_id = args.note_id or deprecated
        result = client.add_note(args.kb_id, note_id, title=args.title or note_id, folder_id=args.folder_id)
        warnings = ("--doc-id is deprecated; use --note-id.",) if deprecated else ()
        return CommandResult(result, (f"Added note: {note_id}",), warnings)
    if action == "add-file":
        results = upload_service.upload_many(args.kb_id, args.files, folder_id=args.folder_id, content_type=args.content_type, on_conflict=args.on_conflict, timeout=args.upload_timeout)
        payload = {"knowledge_base_id": args.kb_id}
        if len(results) == 1:
            payload.update({key: value for key, value in results[0].items() if key in {"media_id", "file_name", "stage"}})
            payload["title"] = results[0]["file_name"]
            payload["folder_id"] = args.folder_id or ""
        lines = tuple(f"{index}. {item['file_name']} {item['status']} ({item['stage']})" for index, item in enumerate(results, 1))
        batch = CommandResult.batch(results, payload=payload, human_lines=lines)
        if any(item.get("stage") == "interrupted" for item in results):
            error = ImaCliError("Interrupted.", code="interrupted", exit_code=ExitCode.INTERRUPTED)
            return CommandResult(batch.payload, batch.human_lines, batch.warnings, batch.status, int(ExitCode.INTERRUPTED), error)
        return batch
    if action == "add-url":
        return url_service.ingest(args.kb_id, args.urls, folder_id=args.folder_id, on_conflict=args.on_conflict, download_timeout=args.download_timeout, upload_timeout=args.upload_timeout)
    if action == "media-info":
        payload = media_service.inspect_media(args.media_id).to_safe_dict()
        return CommandResult(payload, tuple(f"{key}: {value}" for key, value in payload.items()))
    if action == "read":
        value = media_service.read_media(args.media_id)
        payload = {"media_id": value.media_id, "media_type": value.media_type, "source_kind": value.source_kind, "content": value.content, "content_type": value.content_type}
        return CommandResult(payload, (payload["content"],))
    if action == "export":
        value = media_service.export_media(args.media_id, args.output, force=args.force)
        payload = {"media_id": value.media_id, "media_type": value.media_type, "source_kind": value.source_kind, "output": value.output, "bytes": value.bytes_count, "sha256": value.sha256, "content_type": value.content_type}
        return CommandResult(payload, (f"Exported: {payload['output']}",))
    raise ValueError("unknown knowledge command")


def _cursor(args: Any, fetch: Any, key: str, serialize: Any, base: dict[str, Any]) -> CommandResult:
    if args.all:
        collection = collect_cursor_pages(fetch, key, initial_cursor=args.cursor, max_pages=args.max_pages)
        raw_values = list(collection.items)
        values = _dedupe(raw_values, lambda item: item.knowledge_base_id if key == "knowledge_bases" else item.item_id)
        next_cursor = collection.next_cursor; is_end = collection.complete
    else:
        page = fetch(args.cursor); values = page[key]; next_cursor = page["next_cursor"]; is_end = page["is_end"]
    payload = {**base, "cursor": args.cursor, "next_cursor": next_cursor, "is_end": is_end, key: [serialize(item) for item in values]}
    if args.all:
        payload["pagination"] = {
            "all_requested": True, "max_pages": args.max_pages,
            "pages_fetched": collection.pages_fetched, "truncated": not is_end,
            "start": args.cursor, "next": next_cursor,
        }
        if not is_end:
            lines = tuple([f"Returned: {len(values)}", "Pagination stopped at --max-pages."])
            return CommandResult.batch([{"status": "success"} for _ in values] + [{"status": "not_attempted"}], payload=payload, human_lines=lines)
    return CommandResult(payload, (f"Returned: {len(values)}",), status=CommandStatus.SUCCESS if values else CommandStatus.EMPTY)


def _dedupe(values: list[Any], key: Any) -> list[Any]:
    seen: set[str] = set(); result: list[Any] = []
    for value in values:
        identity = key(value)
        if identity not in seen:
            seen.add(identity); result.append(value)
    return result
