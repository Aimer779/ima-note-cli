from __future__ import annotations

from dataclasses import dataclass
import re

from .errors import InputError


FENCE_OPEN_RE = re.compile(r"^[ ]{0,3}(`{3,}|~{3,})")
REFERENCE_DEFINITION_RE = re.compile(r"^[ \t]{0,3}\[([^\]\n]+)\]:[ \t]*(.*)$")
TITLE_SUFFIX_RE = re.compile(r"^(.*?)(?:\s+[\"'][^\"']*[\"'])$", re.DOTALL)


@dataclass(frozen=True)
class PreparedNoteMarkdown:
    content: str
    removed_local_images: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _ImageToken:
    end: int
    destination: str


def ensure_valid_utf8(value: str, field_name: str) -> None:
    if not isinstance(value, str):
        raise InputError(f"{field_name} must be a string.")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise InputError(f"{field_name} must contain valid UTF-8 text.") from exc


def _normalise_reference_label(value: str) -> str:
    return " ".join(value.split()).casefold()


def _fenced_code_ranges(content: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    offset = 0
    open_start: int | None = None
    fence_character = ""
    fence_length = 0

    for line in content.splitlines(keepends=True):
        line_body = line.rstrip("\r\n")
        if open_start is None:
            match = FENCE_OPEN_RE.match(line_body)
            if match:
                marker = match.group(1)
                open_start = offset
                fence_character = marker[0]
                fence_length = len(marker)
        else:
            closing = re.match(
                rf"^[ ]{{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*$",
                line_body,
            )
            if closing:
                ranges.append((open_start, offset + len(line)))
                open_start = None
        offset += len(line)

    if open_start is not None:
        ranges.append((open_start, len(content)))
    return ranges


def _reference_destination(value: str) -> str:
    value = value.strip()
    if value.startswith("<"):
        closing = value.find(">", 1)
        return value[1:closing].strip() if closing >= 0 else ""

    depth = 0
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
        elif character == "(":
            depth += 1
        elif character == ")" and depth:
            depth -= 1
        elif character.isspace() and depth == 0:
            return value[:index].strip()
    return value


def _collect_references(content: str, fenced_ranges: list[tuple[int, int]]) -> dict[str, str]:
    references: dict[str, str] = {}
    offset = 0
    fence_index = 0
    for line in content.splitlines(keepends=True):
        while fence_index < len(fenced_ranges) and offset >= fenced_ranges[fence_index][1]:
            fence_index += 1
        is_fenced = (
            fence_index < len(fenced_ranges)
            and fenced_ranges[fence_index][0] <= offset < fenced_ranges[fence_index][1]
        )
        if not is_fenced:
            match = REFERENCE_DEFINITION_RE.match(line.rstrip("\r\n"))
            if match:
                destination = _reference_destination(match.group(2))
                if destination:
                    references[_normalise_reference_label(match.group(1))] = destination
        offset += len(line)
    return references


def _find_balanced(content: str, start: int, opening: str, closing: str) -> int | None:
    depth = 0
    index = start
    while index < len(content):
        character = content[index]
        if character == "\\":
            index += 2
            continue
        if character == opening:
            depth += 1
        elif character == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _inline_destination(value: str) -> str:
    value = value.strip()
    if value.startswith("<") and value.endswith(">"):
        return value[1:-1].strip()
    titled = TITLE_SUFFIX_RE.match(value)
    return (titled.group(1) if titled else value).strip()


def _markdown_image_at(content: str, start: int, references: dict[str, str]) -> _ImageToken | None:
    if not content.startswith("![", start):
        return None
    alt_end = _find_balanced(content, start + 1, "[", "]")
    if alt_end is None:
        return None
    alt_text = content[start + 2:alt_end]
    following = alt_end + 1

    if following < len(content) and content[following] == "(":
        target_end = _find_balanced(content, following, "(", ")")
        if target_end is None:
            return None
        return _ImageToken(target_end + 1, _inline_destination(content[following + 1:target_end]))

    if following < len(content) and content[following] == "[":
        label_end = _find_balanced(content, following, "[", "]")
        if label_end is None:
            return None
        raw_label = content[following + 1:label_end] or alt_text
        label = _normalise_reference_label(raw_label)
        if label in references:
            return _ImageToken(label_end + 1, references[label])
        return None

    label = _normalise_reference_label(alt_text)
    if label in references:
        return _ImageToken(alt_end + 1, references[label])
    return None


def _inline_code_end(content: str, start: int) -> int | None:
    run_length = 1
    while start + run_length < len(content) and content[start + run_length] == "`":
        run_length += 1
    marker = "`" * run_length
    search_from = start + run_length
    while True:
        closing = content.find(marker, search_from)
        if closing < 0:
            return None
        before_is_tick = closing > 0 and content[closing - 1] == "`"
        after = closing + run_length
        after_is_tick = after < len(content) and content[after] == "`"
        if not before_is_tick and not after_is_tick:
            return after
        search_from = closing + run_length


def _html_image_end(content: str, start: int) -> int | None:
    if content[start:start + 4].lower() != "<img":
        return None
    following = start + 4
    if following < len(content) and not (content[following].isspace() or content[following] in "/>"):
        return None
    quote: str | None = None
    index = following
    while index < len(content):
        character = content[index]
        if quote:
            if character == quote:
                quote = None
        elif character in "\"'":
            quote = character
        elif character == ">":
            return index + 1
        index += 1
    return None


def _html_src(tag: str) -> str | None:
    index = 4
    while index < len(tag):
        while index < len(tag) and (tag[index].isspace() or tag[index] == "/"):
            index += 1
        if index >= len(tag) or tag[index] == ">":
            return None

        name_start = index
        while index < len(tag) and not (tag[index].isspace() or tag[index] in "=/>"):
            index += 1
        name = tag[name_start:index].casefold()
        if not name:
            index += 1
            continue

        while index < len(tag) and tag[index].isspace():
            index += 1
        value: str | None = None
        if index < len(tag) and tag[index] == "=":
            index += 1
            while index < len(tag) and tag[index].isspace():
                index += 1
            if index < len(tag) and tag[index] in "\"'":
                quote = tag[index]
                index += 1
                value_start = index
                while index < len(tag) and tag[index] != quote:
                    index += 1
                value = tag[value_start:index]
                if index < len(tag):
                    index += 1
            else:
                value_start = index
                while index < len(tag) and not (tag[index].isspace() or tag[index] == ">"):
                    index += 1
                value = tag[value_start:index]
        if name == "src":
            return "" if value is None else value.strip()
    return None


def _is_network_image(destination: str) -> bool:
    return destination.lower().startswith(("http://", "https://"))


def _has_visible_content(content: str) -> bool:
    fenced_ranges = _fenced_code_ranges(content)
    offset = 0
    fence_index = 0
    for line in content.splitlines(keepends=True):
        while fence_index < len(fenced_ranges) and offset >= fenced_ranges[fence_index][1]:
            fence_index += 1
        is_fenced = (
            fence_index < len(fenced_ranges)
            and fenced_ranges[fence_index][0] <= offset < fenced_ranges[fence_index][1]
        )
        if is_fenced and line.strip():
            return True
        if not is_fenced and not REFERENCE_DEFINITION_RE.match(line.rstrip("\r\n")) and line.strip():
            return True
        offset += len(line)
    return False


def prepare_note_markdown(content: str) -> PreparedNoteMarkdown:
    ensure_valid_utf8(content, "content")
    fenced_ranges = _fenced_code_ranges(content)
    references = _collect_references(content, fenced_ranges)
    removed: list[str] = []
    output: list[str] = []
    index = 0
    fence_index = 0

    while index < len(content):
        if fence_index < len(fenced_ranges) and index == fenced_ranges[fence_index][0]:
            fence_end = fenced_ranges[fence_index][1]
            output.append(content[index:fence_end])
            index = fence_end
            fence_index += 1
            continue

        character = content[index]
        if character == "\\" and index + 1 < len(content):
            output.append(content[index:index + 2])
            index += 2
            continue
        if character == "`":
            code_end = _inline_code_end(content, index)
            if code_end is not None:
                output.append(content[index:code_end])
                index = code_end
                continue
        if content.startswith("![", index):
            image = _markdown_image_at(content, index, references)
            if image is not None:
                if _is_network_image(image.destination):
                    output.append(content[index:image.end])
                else:
                    removed.append(image.destination)
                index = image.end
                continue
        if character == "<":
            if content.startswith("<!--", index):
                comment_end = content.find("-->", index + 4)
                comment_end = len(content) if comment_end < 0 else comment_end + 3
                output.append(content[index:comment_end])
                index = comment_end
                continue
            html_end = _html_image_end(content, index)
            if html_end is not None:
                tag = content[index:html_end]
                destination = _html_src(tag)
                if destination is None:
                    output.append(tag)
                else:
                    if _is_network_image(destination):
                        output.append(tag)
                    else:
                        removed.append(destination)
                index = html_end
                continue
        output.append(character)
        index += 1

    cleaned = "".join(output)
    ensure_valid_utf8(cleaned, "content")
    if not _has_visible_content(cleaned):
        raise InputError("Content is empty after removing unsupported local images.")
    warnings: tuple[str, ...] = ()
    if removed:
        warnings = ("Local images are not supported and were removed before writing the note.",)
    return PreparedNoteMarkdown(cleaned, tuple(removed), warnings)
