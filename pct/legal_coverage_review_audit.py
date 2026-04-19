"""Utility per diff e audit della review Coverage AI."""

from __future__ import annotations

from typing import Any


def _summarize_value(value: Any) -> str:
    if isinstance(value, dict):
        return f"oggetto con {len(value)} campi"
    if isinstance(value, list):
        return f"lista con {len(value)} elementi"
    if value in (None, "", [], {}):
        return "vuoto"
    text = str(value).strip()
    if len(text) > 120:
        return f"{text[:117]}..."
    return text


def _field_changes(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value == after_value:
            continue
        changes.append(
            {
                "field": key,
                "change": _change_kind(before_value, after_value),
                "before": _summarize_value(before_value),
                "after": _summarize_value(after_value),
            }
        )
    return changes


def _change_kind(before: Any, after: Any) -> str:
    if before in (None, "", [], {}):
        return "added"
    if after in (None, "", [], {}):
        return "removed"
    return "updated"


def build_review_diff(before_spec: dict[str, Any] | None, after_spec: dict[str, Any] | None) -> dict[str, Any]:
    before = dict(before_spec or {})
    after = dict(after_spec or {})
    sections: list[dict[str, Any]] = []
    for key in sorted(set(before) | set(after)):
        before_value = before.get(key)
        after_value = after.get(key)
        if before_value == after_value:
            continue
        entry = {
            "section": key,
            "change": _change_kind(before_value, after_value),
            "before": _summarize_value(before_value),
            "after": _summarize_value(after_value),
        }
        if isinstance(before_value, dict) and isinstance(after_value, dict):
            field_changes = _field_changes(before_value, after_value)
            if field_changes:
                entry["fields"] = field_changes[:12]
        sections.append(entry)

    return {
        "changed": bool(sections),
        "summary": {
            "changed_sections": len(sections),
            "from_procedure": str((before.get("procedure") or {}).get("code") or ""),
            "to_procedure": str((after.get("procedure") or {}).get("code") or ""),
        },
        "sections": sections,
    }
