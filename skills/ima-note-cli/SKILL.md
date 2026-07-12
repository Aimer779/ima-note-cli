---
name: ima-note-cli
description: Install, verify, configure credentials for, and use the `ima` command-line tool for IMA notes and knowledge bases. Use when Agent needs to help a user set up the CLI with `uv tool` or a local checkout, troubleshoot command availability, validate credentials with `ima auth`, or run note and knowledge-base commands such as `ima note search`, `ima note create`, `ima kb browse`, `ima kb add-url`, and `ima kb add-file`. The legacy `ima-note` entry point remains available for note-only compatibility.
---

# Ima Note Cli

## Overview

Use this skill to guide users through installing `ima`, validating that the command works, configuring credentials, and running the supported note and knowledge-base workflows.

Prefer `uv tool install` for end users who want a globally available `ima` command. Prefer a local editable install for development, testing, and code changes.

Command layout:

- Top level:
  - `ima auth`
- Notes:
  - `ima note search`
  - `ima note folders`
  - `ima note list`
  - `ima note get`
  - `ima note create`
  - `ima note append`
- Knowledge base:
  - `ima kb search-base`
  - `ima kb show-base`
  - `ima kb browse`
  - `ima kb search`
  - `ima kb addable`
  - `ima kb add-note`
  - `ima kb add-url`
  - `ima kb add-file`
  - `ima kb media-info`
  - `ima kb read`
  - `ima kb export`

Compatibility:

- `ima-note` still exists as a legacy note-only entry point
- `note_id` is the canonical identifier; JSON temporarily includes an equal deprecated `doc_id` field
- `ima kb add-note --doc-id` remains a deprecated alias for `--note-id` during the compatibility period
- Prefer documenting and recommending `ima ...` going forward

## Quick Start

Choose one install path:

- Global tool install:
  - `uv tool install git+https://github.com/Aimer779/ima-note-cli`
  - Verify with `ima --help`
- Local development:
  - `git clone https://github.com/Aimer779/ima-note-cli`
  - `cd ima-note-cli`
  - `uv venv`
  - `uv pip install -e .`
  - Verify with `uv run python -m ima_note_cli --help`

## Credential Setup

Require these values:

```bash
IMA_OPENAPI_CLIENTID=your_client_id
IMA_OPENAPI_APIKEY=your_api_key
```

Use this precedence rule per field:

1. Process environment variables
2. Current working directory `.env`
3. `~/.config/ima/client_id` and `~/.config/ima/api_key`

When the CLI is installed via `uv tool`, prefer system environment variables because users will run `ima` from arbitrary directories.

Use these OS-specific commands when the user asks how to configure credentials:

- Windows PowerShell, current session:
  - `$env:IMA_OPENAPI_CLIENTID="your_client_id"`
  - `$env:IMA_OPENAPI_APIKEY="your_api_key"`
- Windows PowerShell, persistent:
  - `setx IMA_OPENAPI_CLIENTID "your_client_id"`
  - `setx IMA_OPENAPI_APIKEY "your_api_key"`
- Windows CMD, current session:
  - `set IMA_OPENAPI_CLIENTID=your_client_id`
  - `set IMA_OPENAPI_APIKEY=your_api_key`
- Windows CMD, persistent:
  - `setx IMA_OPENAPI_CLIENTID "your_client_id"`
  - `setx IMA_OPENAPI_APIKEY "your_api_key"`
- macOS/Linux bash or zsh, current session:
  - `export IMA_OPENAPI_CLIENTID="your_client_id"`
  - `export IMA_OPENAPI_APIKEY="your_api_key"`
- fish, current session:
  - `set -x IMA_OPENAPI_CLIENTID "your_client_id"`
  - `set -x IMA_OPENAPI_APIKEY "your_api_key"`

Tell users who ran `setx` to open a new terminal before retrying the CLI.

## Verification Workflow

Run these checks in order:

1. Command availability:
   - Global install: `ima --help`
   - Local checkout: `uv run python -m ima_note_cli --help`
2. Credential presence:
   - `ima auth`
   - Or `ima auth --json`
3. Optional local test suite for development:
   - `uv run python -m unittest discover -s tests -v`

Interpret the results this way:

- If `ima --help` fails, treat it as an install or `PATH` problem.
- If `ima auth` reports missing credentials, fix configuration before debugging API behavior.
- If the tests fail in a local checkout, keep the user on the local workflow instead of asking them to reinstall globally.

## Common Commands

Use these commands for normal operation:

- Check credentials:
  - `ima auth`
- Search notes by title:
  - `ima note search "meeting notes"`
- Search note content:
  - `ima note search "project schedule" --search-type content`
- List folders:
  - `ima note folders`
- List notes under a folder:
  - `ima note list --folder-id "user_list_xxx"`
- Read note content:
  - `ima note get "your_note_id"`
- Create a note from inline Markdown:
  - `ima note create --title "Test Title" --content "Body content"`
- Create a note from a file:
  - `ima note create --file "./note.md" --folder-id "folder_id"`
- Append Markdown to a note:
  - `ima note append "your_note_id" --content "\n## Update\n\nAppended text"`
- Search knowledge bases:
  - `ima kb search-base "product docs"`
- Show a knowledge base:
  - `ima kb show-base --kb-id "kb_xxx"`
- Browse a knowledge base:
  - `ima kb browse --kb-id "kb_xxx"`
- Search within a knowledge base:
  - `ima kb search "schedule" --kb-id "kb_xxx"`
- List addable knowledge bases:
  - `ima kb addable`
- Add a note to a knowledge base:
  - `ima kb add-note --kb-id "kb_xxx" --note-id "note_xxx" --title "Meeting Notes"`
- Import a URL into a knowledge base:
  - `ima kb add-url --kb-id "kb_xxx" --url "https://example.com/article"`
- Upload a local file into a knowledge base:
  - `ima kb add-file --kb-id "kb_xxx" --file "./report.pdf"`
- Inspect safe original-media metadata:
  - `ima kb media-info --media-id "media_xxx"`
- Read note or textual URL media:
  - `ima kb read --media-id "media_xxx"`
- Export media without overwriting an existing file:
  - `ima kb export --media-id "media_xxx" --output "./original.bin"`
- Emit JSON for scripting:
  - Add `--json` to `auth`, note subcommands, or kb subcommands that support machine-readable output

Before note create or append, the CLI validates UTF-8 and removes local/data/non-HTTP(S) image references. Human mode reports removed paths on stderr; JSON mode reports them in `warnings` and `removed_local_images` without contaminating stdout.

JSON success and failure are single documents with `schema_version`, `ok`, `command`, and `warnings`; JSON failures keep stderr empty. Never print or request full signed media URLs, Authorization/Cookie values, IMA credentials, or COS temporary secrets. `kb read` accepts only bounded textual content; use `kb export` for binary media. Export defaults to no overwrite and `--force` still uses atomic replacement.

When the user is in a local checkout and prefers not to install globally, replace `ima ...` with `uv run python -m ima_note_cli ...`.

Legacy note compatibility:

- `ima-note auth`
- `ima-note search "meeting notes"`
- `ima-note create --title "Test Title" --content "Body content"`

## Troubleshooting

- If the command is not found after `uv tool install`, check the UV tool bin directory with `uv tool dir --bin` and make sure it is on `PATH`.
- If credentials appear correct but API calls still fail, ask the user to run `ima auth` first, then a minimal read command such as `ima note search "test"`.
- If the user wants `.env`, remind them that the CLI only reads `.env` from the current working directory.
- If Windows terminals throw `'gbk' codec can't encode character ...`, explain that the terminal is using `GBK` while note output contains emoji or other non-GBK characters.
- `ima auth` now checks `PYTHONUTF8` and `PYTHONIOENCODING` on Windows and prints a shell-specific hint when they are missing, so use that as the first diagnostic step.
- For that encoding problem on Windows, suggest this order:
  - Set PowerShell session variables: `$env:PYTHONUTF8="1"` and `$env:PYTHONIOENCODING="utf-8"`
  - Or in CMD: `set PYTHONUTF8=1` and `set PYTHONIOENCODING=utf-8`
  - Retry with a minimal command such as `ima note search "coding"`
- If the user wants the UTF-8 behavior to persist on Windows, suggest `setx PYTHONUTF8 "1"` and `setx PYTHONIOENCODING "utf-8"`, then tell them to open a new terminal.
# Batch C behavior

- `ima kb add-url` classifies public web and supported file URLs. Never suggest bypassing the SSRF checks.
- `ima kb add-file --file PATH` may repeat; conflict policy is `error` unless `--on-conflict rename` is explicit.
- Use `--all --max-pages N` for bounded multi-page retrieval.
- Exit code 9 means itemized partial/failed batch output is available; inspect `results` and `stage`.
