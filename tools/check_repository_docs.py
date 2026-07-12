#!/usr/bin/env python3
"""Offline stage-6 consistency checks for docs, skills, and provenance."""

from __future__ import annotations

import hashlib
import json
import re
import stat
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ima_note_cli import __version__  # noqa: E402

from render_cli_reference import leaf_commands, render, stable_parser, walk_parsers  # noqa: E402

ERRORS: list[str] = []
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def fail(message: str) -> None:
    ERRORS.append(message)


def markdown_files() -> list[Path]:
    files = [ROOT / "README.md", ROOT / "THIRD_PARTY_NOTICES.md"]
    files.extend((ROOT / "docs").rglob("*.md"))
    files.extend(ROOT.glob("*PLAN*.md"))
    files.append(ROOT / "skills/ima-note-cli/SKILL.md")
    files.extend((ROOT / "third_party/ima-skills/1.1.7/original").rglob("*.md"))
    return sorted({p.resolve() for p in files if p.exists()})


def slug(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"[^\w\-\s\u4e00-\u9fff]", "", text)
    return re.sub(r"[\s]+", "-", text).strip("-")


def anchors(path: Path) -> set[str]:
    seen: dict[str, int] = {}
    result: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if not match:
            continue
        base = slug(match.group(1))
        count = seen.get(base, 0)
        seen[base] = count + 1
        result.add(base if count == 0 else f"{base}-{count}")
    return result


def link_destinations(line: str) -> list[str]:
    """Return inline image/link and reference-definition destinations."""
    destinations: list[str] = []
    definition = re.match(r"^\s{0,3}\[[^\]]+\]:\s*(?:<([^>]+)>|(\S+))", line)
    if definition:
        destinations.append(definition.group(1) or definition.group(2))
    position = 0
    while True:
        label = line.find("](", position)
        if label < 0:
            break
        start = label + 2
        depth = 1
        index = start
        angle = False
        while index < len(line):
            char = line[index]
            if char == "<" and index == start:
                angle = True
            elif char == ">" and angle:
                angle = False
            elif not angle and char == "(":
                depth += 1
            elif not angle and char == ")":
                depth -= 1
                if depth == 0:
                    raw = line[start:index].strip()
                    if raw.startswith("<") and ">" in raw:
                        raw = raw[1:raw.index(">")]
                    else:
                        raw = re.split(r"\s+[\"']", raw, maxsplit=1)[0]
                    destinations.append(raw)
                    position = index + 1
                    break
            index += 1
        else:
            break
    return destinations


def check_links() -> None:
    root = ROOT.resolve()
    for source in markdown_files():
        in_fence = False
        for lineno, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"^\s*(```|~~~)", line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            visible = re.sub(r"`[^`]*`", "", line)
            for raw in link_destinations(visible):
                raw = raw.strip().strip("<>")
                if not raw:
                    continue
                parsed_uri = urlsplit(raw)
                scheme = parsed_uri.scheme.lower()
                if scheme in {"http", "https"}:
                    split = parsed_uri
                    if not split.netloc or any(ch.isspace() for ch in split.netloc):
                        fail(f"{source.relative_to(ROOT)}:{lineno}: malformed external link: {raw}")
                    continue
                if scheme == "mailto":
                    if "@" not in raw[7:]:
                        fail(f"{source.relative_to(ROOT)}:{lineno}: malformed mailto link: {raw}")
                    continue
                split = urlsplit(unquote(raw.replace("\\", "/")))
                target = (source.parent / split.path).resolve() if split.path else source
                try:
                    target.relative_to(root)
                except ValueError:
                    fail(f"{source.relative_to(ROOT)}:{lineno}: link escapes repository: {raw}")
                    continue
                if not target.exists():
                    fail(f"{source.relative_to(ROOT)}:{lineno}: missing link target: {raw}")
                    continue
                if split.fragment and target.suffix.lower() == ".md" and split.fragment not in anchors(target):
                    fail(f"{source.relative_to(ROOT)}:{lineno}: missing anchor: {raw}")


def check_skill() -> None:
    skills = ROOT / "skills"
    entries = sorted(p.name for p in skills.iterdir())
    if entries != ["ima-note-cli", "manifest.json"]:
        fail(f"skills must contain only canonical directory and manifest, found {entries}")
    manifest = json.loads((skills / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1 or manifest.get("canonical_skill") != "ima-note-cli":
        fail("invalid skills manifest identity")
    records = manifest.get("skills")
    if not isinstance(records, list) or len(records) != 1:
        fail("skills manifest must contain exactly one skill")
        return
    record = records[0]
    expected_record = {
        "name": "ima-note-cli",
        "path": "skills/ima-note-cli",
        "contract_version": "1.1.7",
        "skill_path": "skills/ima-note-cli/SKILL.md",
        "agents_metadata_path": "skills/ima-note-cli/agents/openai.yaml",
    }
    for field, expected in expected_record.items():
        if record.get(field) != expected:
            fail(f"manifest {field} must be {expected!r}")
    for field in ("skill_version", "contract_version", "tested_cli_version"):
        if not SEMVER_RE.fullmatch(str(record.get(field, ""))):
            fail(f"manifest {field} is not semver")
    if record.get("tested_cli_version") != __version__:
        fail("tested_cli_version does not match package __version__")
    if record.get("distribution") != "repository-only":
        fail("canonical skill distribution must be repository-only")
    skill_path = ROOT / record.get("skill_path", "")
    text = skill_path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0] != "":
        fail("SKILL.md must start with YAML frontmatter")
        return
    keys = [line.split(":", 1)[0].strip() for line in parts[1].splitlines() if ":" in line]
    description_lines = [line.partition(":")[2].strip() for line in parts[1].splitlines() if line.startswith("description:")]
    if keys != ["name", "description"] or "name: ima-note-cli" not in parts[1] or not description_lines or not description_lines[0]:
        fail("SKILL.md frontmatter must contain only matching name and description")
    if len(text.splitlines()) >= 500:
        fail("SKILL.md must be under 500 lines")
    for token in ("search_note_book", "list_note_folder_by_cursor", "list_note_by_folder_id", "docid", "IMA_BASE_URL", ".cjs"):
        if token.lower() in text.lower():
            fail(f"SKILL.md contains forbidden token: {token}")
    for command in leaf_commands():
        if command not in text:
            fail(f"SKILL.md does not cover parser leaf command: {command}")
    metadata = (ROOT / record.get("agents_metadata_path", "")).read_text(encoding="utf-8")
    metadata_values = {match.group(1): match.group(2) for match in re.finditer(r'^\s{2}([a-z_]+):\s+"([^"\r\n]*)"\s*$', metadata, re.MULTILINE)}
    if metadata_values.get("display_name") != "IMA Note CLI":
        fail("agents/openai.yaml display_name is invalid")
    short = metadata_values.get("short_description", "")
    if not 25 <= len(short) <= 64:
        fail("agents/openai.yaml short_description must be 25-64 characters")
    prompt = metadata_values.get("default_prompt", "")
    if "$ima-note-cli" not in prompt or not any(word in prompt.lower() for word in ("configure", "run", "install", "use")):
        fail("agents/openai.yaml default_prompt must match the skill workflow and mention $ima-note-cli")
    for forbidden in ("icon_small:", "icon_large:", "brand_color:", "dependencies:"):
        if forbidden in metadata:
            fail(f"agents/openai.yaml contains unrequested field {forbidden}")


def check_upstream() -> None:
    base = ROOT / "third_party/ima-skills/1.1.7"
    upstream = json.loads((base / "UPSTREAM.json").read_text(encoding="utf-8"))
    expected = {"schema_version": 1, "name": "ima-skills", "version": "1.1.7", "slug": "ima-skills", "license": "MIT-0", "license_evidence": "original/skill-card.md", "manifest": "SHA256SUMS", "role": "reference-only", "active_skill": False, "included_in_wheel": False}
    for key, value in expected.items():
        if upstream.get(key) != value:
            fail(f"UPSTREAM.json {key} must be {value!r}")
    manifest_bytes = (base / "SHA256SUMS").read_bytes()
    if hashlib.sha256(manifest_bytes).hexdigest() != upstream.get("aggregate_manifest_sha256"):
        fail("aggregate manifest SHA-256 mismatch")
    original_root = (base / "original").resolve()
    for archived in (base / "original").rglob("*"):
        attributes = getattr(archived.lstat(), "st_file_attributes", 0)
        is_junction = getattr(archived, "is_junction", lambda: False)()
        if archived.is_symlink() or is_junction or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            fail(f"upstream archive contains symlink/junction/reparse point: {archived.relative_to(base / 'original')}")
        try:
            archived.resolve().relative_to(original_root)
        except ValueError:
            fail(f"upstream archive path resolves outside original/: {archived.relative_to(base / 'original')}")
    lines = manifest_bytes.decode("utf-8").splitlines()
    paths: list[str] = []
    for line in lines:
        match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
        if not match:
            fail(f"invalid SHA256SUMS line: {line}")
            continue
        digest, relative = match.groups()
        paths.append(relative)
        target = base / "original" / relative
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            fail(f"upstream hash mismatch: {relative}")
    actual = sorted(p.relative_to(base / "original").as_posix() for p in (base / "original").rglob("*") if p.is_file())
    if paths != sorted(paths) or len(paths) != len(set(paths)) or sorted(paths) != actual:
        fail("SHA256SUMS paths must be sorted, unique, and exhaustive")
    if (ROOT / "ima-skills-1.1.7 (1)").exists():
        fail("legacy intake directory still exists")
    original_meta = json.loads((base / "original/_meta.json").read_text(encoding="utf-8"))
    if upstream.get("version") != original_meta.get("version") or upstream.get("slug") != original_meta.get("slug"):
        fail("UPSTREAM identity does not match original/_meta.json")
    if upstream.get("publisher", {}).get("owner_id") != original_meta.get("ownerId"):
        fail("UPSTREAM publisher owner_id does not match original/_meta.json")
    if upstream.get("published_at_ms") != original_meta.get("publishedAt") or not isinstance(upstream.get("published_at_ms"), int):
        fail("UPSTREAM published_at_ms does not match original/_meta.json")
    try:
        date.fromisoformat(upstream.get("recorded_at", ""))
    except (TypeError, ValueError):
        fail("UPSTREAM recorded_at must be an ISO calendar date")
    card = (base / "original/skill-card.md").read_text(encoding="utf-8")
    for evidence in (upstream.get("publisher", {}).get("name", ""), upstream.get("source_url", ""), upstream.get("license", "")):
        if not evidence or evidence not in card:
            fail(f"UPSTREAM value lacks skill-card evidence: {evidence!r}")


def check_active_drift() -> None:
    active = [ROOT / "README.md", ROOT / "docs/IMA_OPENAPI_CONTRACT_1_1_7.md", ROOT / "docs/SKILL_DISTRIBUTION_POLICY.md", ROOT / "skills/ima-note-cli/SKILL.md"]
    forbidden = ("search_note_book", "list_note_folder_by_cursor", "list_note_by_folder_id", "docid", "1.1.2", "ima-skills-1.1.7 (1)", "URL 探测属于后续批次")
    for path in active:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token.lower() in text.lower():
                fail(f"active surface {path.relative_to(ROOT)} contains forbidden token {token}")
    contracts = sorted((ROOT / "docs").glob("*CONTRACT_1_1_7.md"))
    if contracts != [ROOT / "docs/IMA_OPENAPI_CONTRACT_1_1_7.md"]:
        fail(f"expected one canonical contract, found {[p.name for p in contracts]}")
    compatibility_surfaces = [ROOT / "README.md", ROOT / "docs/IMA_OPENAPI_CONTRACT_1_1_7.md", ROOT / "skills/ima-note-cli/SKILL.md"]
    for path in compatibility_surfaces:
        for paragraph in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            if "doc_id" in paragraph and not ("note_id" in paragraph and any(word in paragraph.lower() for word in ("deprecated", "compat", "canonical", "兼容", "弃用"))):
                fail(f"{path.relative_to(ROOT)} describes doc_id without canonical compatibility context")


def check_generated_and_distribution() -> None:
    reference = ROOT / "docs/CLI_REFERENCE.md"
    if not reference.exists() or reference.read_text(encoding="utf-8") != render():
        fail("docs/CLI_REFERENCE.md is stale; run tools/render_cli_reference.py")
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    if 'where = ["src"]' not in pyproject or "package-data" in pyproject:
        fail("wheel package discovery must remain src-only without package data")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    required = ("repository-only", "does not install", "ima-note", "legacy", "--all", "--max-pages", "--on-conflict", "--download-timeout", "--upload-timeout", "exit code 9")
    for phrase in required:
        if phrase.lower() not in readme.lower():
            fail(f"README missing critical distribution/workflow phrase: {phrase}")
    skill = (ROOT / "skills/ima-note-cli/SKILL.md").read_text(encoding="utf-8")
    for command in leaf_commands():
        if command not in readme:
            fail(f"README does not cover parser leaf command: {command}")
    parser = stable_parser()
    parser_options = {option for _, current in walk_parsers(parser) for action in current._actions for option in action.option_strings}
    key_options = {"--json", "--note-id", "--doc-id", "--all", "--max-pages", "--on-conflict", "--download-timeout", "--upload-timeout", "--force"}
    missing_parser = key_options - parser_options
    if missing_parser:
        fail(f"parser is missing required compatibility options: {sorted(missing_parser)}")
    reference_text = reference.read_text(encoding="utf-8")
    for option in key_options:
        if option not in reference_text or option not in skill:
            fail(f"generated reference or canonical skill is missing key option: {option}")


def main() -> int:
    check_skill()
    check_upstream()
    check_active_drift()
    check_generated_and_distribution()
    check_links()
    if ERRORS:
        for error in ERRORS:
            print(error, file=sys.stderr)
        return 1
    print("repository docs, skill, distribution, and provenance are consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
