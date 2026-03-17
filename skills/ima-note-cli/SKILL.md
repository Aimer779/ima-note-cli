---
name: ima-note-cli
description: Install, verify, configure credentials for, and use the `ima-note` command-line tool for IMA notes. Use when Agent needs to help a user set up the CLI with `uv tool` or a local checkout, troubleshoot command availability, validate credentials with `ima-note auth`, or run common note commands such as search, folders, list, get, create, and append.
---

# Ima Note Cli

## Overview

Use this skill to guide users through installing `ima-note`, validating that the command works, configuring credentials, and running the supported note workflows.

Prefer `uv tool install` for end users who want a globally available `ima-note` command. Prefer a local editable install for development, testing, and code changes.

## Quick Start

Choose one install path:

- Global tool install:
  - `uv tool install git+https://github.com/Aimer779/ima-note-cli`
  - Verify with `ima-note --help`
- Local development:
  - `git clone https://github.com/Aimer779/ima-note-cli`
  - `cd ima-note-cli`
  - `uv venv`
  - `uv pip install -e .`
  - Verify with `uv run ima-note --help`

## Credential Setup

Require these values:

```bash
IMA_OPENAPI_CLIENTID=your_client_id
IMA_OPENAPI_APIKEY=your_api_key
```

Use this precedence rule:

1. Current working directory `.env`
2. Process environment variables

When the CLI is installed via `uv tool`, prefer system environment variables because users will run `ima-note` from arbitrary directories.

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
   - Global install: `ima-note --help`
   - Local checkout: `uv run ima-note --help`
2. Credential presence:
   - `ima-note auth`
   - Or `ima-note auth --json`
3. Optional local test suite for development:
   - `uv run python -m unittest discover -s tests -v`

Interpret the results this way:

- If `ima-note --help` fails, treat it as an install or `PATH` problem.
- If `ima-note auth` reports missing credentials, fix configuration before debugging API behavior.
- If the tests fail in a local checkout, keep the user on the local workflow instead of asking them to reinstall globally.

## Common Commands

Use these commands for normal operation:

- Check credentials:
  - `ima-note auth`
- Search notes by title:
  - `ima-note search "meeting notes"`
- Search note content:
  - `ima-note search "project schedule" --search-type content`
- List folders:
  - `ima-note folders`
- List notes under a folder:
  - `ima-note list --folder-id "user_list_xxx"`
- Read note content:
  - `ima-note get "your_doc_id"`
- Create a note from inline Markdown:
  - `ima-note create --title "Test Title" --content "Body content"`
- Create a note from a file:
  - `ima-note create --file "./note.md" --folder-id "folder_id"`
- Append Markdown to a note:
  - `ima-note append "your_doc_id" --content "\n## Update\n\nAppended text"`
- Emit JSON for scripting:
  - Add `--json` to `auth`, `search`, `folders`, `list`, `get`, `create`, or `append`

When the user is in a local checkout and prefers not to install globally, replace `ima-note` with `uv run ima-note`.

## Troubleshooting

- If the command is not found after `uv tool install`, check the UV tool bin directory with `uv tool dir --bin` and make sure it is on `PATH`.
- If credentials appear correct but API calls still fail, ask the user to run `ima-note auth` first, then a minimal read command such as `ima-note search "test"`.
- If the user wants `.env`, remind them that the CLI only reads `.env` from the current working directory.
- If Windows terminals throw `'gbk' codec can't encode character ...`, explain that the terminal is using `GBK` while note output contains emoji or other non-GBK characters.
- For that encoding problem on Windows, suggest this order:
  - Set PowerShell session variables: `$env:PYTHONUTF8="1"` and `$env:PYTHONIOENCODING="utf-8"`
  - Or in CMD: `set PYTHONUTF8=1` and `set PYTHONIOENCODING=utf-8`
  - Retry with a minimal command such as `ima-note search "coding"`
- If the user wants the UTF-8 behavior to persist on Windows, suggest `setx PYTHONUTF8 "1"` and `setx PYTHONIOENCODING "utf-8"`, then tell them to open a new terminal.
