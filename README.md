# ima-note-cli

`ima-note-cli` is a small Python CLI for the IMA note OpenAPI. The MVP focuses on two workflows from `skills/ima-note`:

- Search notes by title
- Read a note's plain-text content by `doc_id`

## Installation

Using `uv`:

```bash
uv pip install -e .
```

Using `pip`:

```bash
pip install -e .
```

## Credentials

The CLI reads credentials from:

1. Project root `.env`
2. Process environment variables

Environment variables always win over `.env` values.

Required keys:

```bash
IMA_OPENAPI_CLIENTID=your_client_id
IMA_OPENAPI_APIKEY=your_api_key
```

This repo now includes:

- `.env.example`: a committed template
- `.env`: a local placeholder file for development

Recommended setup:

```bash
cp .env.example .env
```

Then update `.env` with the credentials from `https://ima.qq.com/agent-interface`.

Example `.env`:

```dotenv
IMA_OPENAPI_CLIENTID=your_client_id
IMA_OPENAPI_APIKEY=your_api_key
```

## Usage

Search notes by title:

```bash
ima-note search "会议纪要"
```

Read a note by `doc_id`:

```bash
ima-note get "your_doc_id"
```

Get JSON output:

```bash
ima-note search "会议纪要" --json
ima-note get "your_doc_id" --json
```

You can also run the CLI without installing it globally:

```bash
uv run ima-note search "会议纪要"
python -m ima_note_cli get "your_doc_id"
```

## Development

Run tests:

```bash
$env:PYTHONPATH="src"
python -m unittest discover -s tests -v
```
