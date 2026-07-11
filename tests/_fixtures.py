from __future__ import annotations

import json
from pathlib import Path
from typing import Any


FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def load_fixture(relative_path: str) -> dict[str, Any]:
    path = (FIXTURE_ROOT / relative_path).resolve()
    try:
        path.relative_to(FIXTURE_ROOT.resolve())
    except ValueError as exc:
        raise AssertionError(f"Fixture path escapes fixture root: {relative_path}") from exc
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"Fixture must contain a JSON object: {relative_path}")
    return value


def load_data(relative_path: str) -> dict[str, Any]:
    envelope = load_fixture(relative_path)
    data = envelope.get("data")
    if not isinstance(data, dict):
        raise AssertionError(f"Fixture data must contain a JSON object: {relative_path}")
    return data
