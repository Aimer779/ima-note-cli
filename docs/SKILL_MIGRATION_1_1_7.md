# Skill migration to the 1.1.7 contract

This matrix records every retired skill family, its owner, disposition, and verification evidence.

| Source | Content | Owner | Disposition | Target or evidence |
| --- | --- | --- | --- | --- |
| `skills/ima-note` | Intent routing, create/append confirmation, UTF-8 and image safety | project | Migrated | Canonical skill write and safety sections; CLI validation tests |
| `skills/ima-note` | Raw request/response tables | project | Not migrated | Unique [contract](IMA_OPENAPI_CONTRACT_1_1_7.md) |
| `skills/ima-skills-1.1.2` | Legacy endpoints and identifiers | upstream/project | Deleted | 1.1.7 API tests and negative repository checks |
| 1.1.2 CJS | Upload/preflight workflow | upstream/project | Not runtime | Python upload services and tests |
| upstream 1.1.7 | Original skill, references, metadata, and scripts | iampennyli | Archived byte-for-byte | [UPSTREAM.json](../third_party/ima-skills/1.1.7/UPSTREAM.json) and `SHA256SUMS` |
| upstream 1.1.7 | Self-update, arbitrary base URL, direct API/CJS execution | iampennyli | Explicitly rejected | Canonical skill requires the Python CLI and official-host safety boundaries |

The `ima-note` executable is retained only as a legacy note-only CLI entry point. `note_id` is canonical; `--doc-id` and the equal JSON `doc_id` value remain deprecated compatibility surfaces. Git history preserves the removed active skill files.
