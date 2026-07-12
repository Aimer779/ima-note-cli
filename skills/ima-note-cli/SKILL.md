---
name: ima-note-cli
description: Install, verify, configure, and troubleshoot the `ima` Python CLI; use it to search, read, create, and append IMA Notes, browse and search Knowledge bases, inspect or export original media, import public URLs, and upload local or remote files. Use when a user needs CLI setup, credential guidance, JSON automation, pagination, safe writes/uploads, or compatibility help for the legacy `ima-note` executable and deprecated `--doc-id` alias.
---

# Use the IMA CLI

## Start quickly

1. Install the CLI with `uv tool install git+https://github.com/Aimer779/ima-note-cli`.
2. Verify it with `ima --help`.
3. Configure credentials without printing their values.
4. Check configuration with `ima auth` or `ima auth --json`.
5. Inspect exact current arguments with `ima <group> <command> --help` before a consequential write.

Use `uv run python -m ima_note_cli ...` instead of `ima ...` when working from an uninstalled source checkout.

## Keep CLI and skill installation separate

Treat `uv tool install` as installation of the Python CLI only. It does not install this agent skill. Use or link `skills/ima-note-cli` separately from a repository checkout. Do not claim that this skill is bundled in the wheel.

## Configure credentials safely

Require `IMA_OPENAPI_CLIENTID` and `IMA_OPENAPI_APIKEY`. Resolve each field independently in this order:

1. Process environment.
2. `.env` in the current working directory.
3. `~/.config/ima/client_id` or `~/.config/ima/api_key`.

Prefer environment variables for a globally installed CLI. Never request, echo, log, or embed real credential values in commands. Use `setx` only when persistent Windows configuration is requested, and remind the user to open a new terminal. Use `ima auth` as the first credential diagnostic.

## Read Notes

Use all six Note commands:

- `ima note search QUERY` to search titles or content.
- `ima note folders` to list notebooks.
- `ima note list` to list notes, optionally under a folder.
- `ima note get NOTE_ID` to read one note.
- `ima note create --title TITLE --content TEXT` to create one note.
- `ima note append NOTE_ID --content TEXT` to append to one note.

Use `note_id` as the canonical identifier. Confirm the intended target before create or append. Prefer `--file` for substantial Markdown input; the CLI validates UTF-8 and removes unsafe local, data, and non-HTTP(S) image references before writes.

## Work with Knowledge bases

Use all eleven Knowledge commands:

- `ima kb search-base QUERY`
- `ima kb show-base --kb-id KB_ID`
- `ima kb browse --kb-id KB_ID`
- `ima kb search QUERY --kb-id KB_ID`
- `ima kb addable`
- `ima kb add-note --kb-id KB_ID --note-id NOTE_ID --title TITLE`
- `ima kb add-url --kb-id KB_ID --url URL`
- `ima kb add-file --kb-id KB_ID --file PATH`
- `ima kb media-info --media-id MEDIA_ID`
- `ima kb read --media-id MEDIA_ID`
- `ima kb export --media-id MEDIA_ID --output PATH`

Confirm the knowledge base and content before any add/import/upload operation. Repeat `--file` for a multi-file upload. Use `--on-conflict error` by default and use `--on-conflict rename` only when automatic renaming is acceptable. Set `--download-timeout` and `--upload-timeout` when network conditions require explicit bounds.

## Preserve URL and upload safety

Let `ima kb add-url` classify supported public web pages and remote files. Do not bypass its SSRF, redirect, DNS, scheme, port, or size checks. Unsupported video hosts fail before network access. Remote supported files are downloaded with bounded streaming and uploaded through the same guarded workflow as local files.

Do not recommend direct raw API calls, archived Node/CJS scripts, arbitrary service base URLs, or self-updating skill code. Send long-lived IMA credentials only through the CLI's official-host client. Treat signed COS URLs and temporary headers as secrets.

Use `media-info` for redacted metadata. Use `read` only for bounded textual original content. Use `export` for binary content; it refuses overwrite unless `--force` is explicit and writes atomically.

## Paginate and automate

Add `--json` for machine-readable output. Expect one JSON document containing `schema_version`, `ok`, `status`, `command`, `warnings`, and command data or a stable error. Keep stderr empty for JSON failures.

Use `--all --max-pages N` for bounded multi-page list/search operations. A page cap or mixed batch can produce itemized partial output. Interpret exit code 9 as partial or itemized batch failure and inspect `results`, `summary`, and each `stage`.

Recognize the remaining exit codes: 0 success, 2 input, 3 configuration, 4 network, 5 IMA business, 6 protocol, 7 local/original-content I/O, 8 upload, 70 internal, and 130 interruption.

## Maintain legacy compatibility

Recommend `ima` as the formal entry point. Treat `ima-note` as a legacy note-only executable that remains available. Treat `--doc-id` and the equal JSON `doc_id` field only as deprecated compatibility for canonical `--note-id` and `note_id`; do not present them as current API fields.

## Troubleshoot in order

1. Run `ima --help` to distinguish installation or PATH failures.
2. Run `ima auth` without exposing values.
3. Run a minimal read such as `ima note search "test"`.
4. Use the command's `--help` output as the argument truth source.
5. In a checkout, run `uv run python -m unittest discover -s tests -v` only when code diagnostics are needed.

On Windows encoding failures, set `PYTHONUTF8=1` and `PYTHONIOENCODING=utf-8` for the relevant shell, then retry in a new terminal if persistent variables were set.
