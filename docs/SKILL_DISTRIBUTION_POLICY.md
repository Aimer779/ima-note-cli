# Skill distribution policy

`skills/ima-note-cli` is the repository's only canonical and active agent skill. An active skill is discoverable below `skills/`; archived upstream files below `third_party/` are immutable provenance evidence and are not operational guidance.

Three versions remain independent: `skill_version` versions the agent workflow, `contract_version` identifies the IMA OpenAPI contract, and `tested_cli_version` identifies the CLI release verified by that skill. Their authoritative registry is [skills/manifest.json](../skills/manifest.json).

The Python wheel contains only the `ima_note_cli` package and the `ima` and legacy `ima-note` entry points. It does not contain or install the agent skill or archived sources. Install the CLI with `uv tool`; install or link the skill separately from a source checkout. Distribution remains `repository-only` until a later, explicit skill release design.

Facts flow from the parser and implementation to the generated [CLI reference](CLI_REFERENCE.md), the canonical [OpenAPI contract](IMA_OPENAPI_CONTRACT_1_1_7.md), README workflows, and finally the skill. Changes must update the relevant generated/reference files and pass `tools/check_repository_docs.py`.

The archived Node/CJS implementation is not adopted because the Python CLI already implements the supported workflows with stricter credential, redirect, SSRF, and upload controls. Stage 7 remains responsible for CI, the project-root license, unified project versioning, and release automation.
