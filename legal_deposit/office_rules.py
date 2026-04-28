from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


RULES_PATH = Path(__file__).resolve().parents[1] / "legal_rules" / "ppt_office_rules.json"


def _norm(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


@lru_cache(maxsize=1)
def load_office_rules(path: str | None = None) -> dict[str, Any]:
    rules_path = Path(path) if path else RULES_PATH
    if not rules_path.exists():
        return {"default": {}, "offices": []}
    return json.loads(rules_path.read_text(encoding="utf-8"))


def resolve_office_rule(office_name: str, *, path: str | None = None) -> dict[str, Any]:
    rules = load_office_rules(path)
    default = dict(rules.get("default") or {})
    office_norm = _norm(office_name)
    for row in list(rules.get("offices") or []):
        matches = [_norm(value) for value in list(row.get("match") or [])]
        if any(match and match in office_norm for match in matches):
            merged = dict(default)
            merged.update(dict(row))
            return merged
    return default
