"""Helper piccoli per job incrementali e budgettati.

I job frequenti non devono rispazzolare archivi gia' completati: salvano un
cursore stabile, processano nuovi elementi e mantengono la full scan solo come
bootstrap o richiesta esplicita.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def clean_cursor_value(value: Any) -> str:
    return str(value or "").strip()


def cursor_tuple(sort_key: Any, item_id: Any = "") -> tuple[str, str]:
    return clean_cursor_value(sort_key), clean_cursor_value(item_id)


def is_after_cursor(
    sort_key: Any,
    item_id: Any,
    cursor: dict[str, Any] | None,
    *,
    include_boundary: bool = False,
) -> bool:
    """True quando un elemento deve essere letto rispetto al cursore salvato."""

    if not cursor:
        return True
    current = cursor_tuple(sort_key, item_id)
    saved = cursor_tuple(cursor.get("sort_key"), cursor.get("item_id"))
    if include_boundary and current[0] and current[0] == saved[0]:
        return True
    return current > saved


def file_mtime_ns(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return 0


def newest_file_cursor(paths: list[Path]) -> dict[str, Any]:
    """Cursore monotono per archivi documentali ordinati per modifica file."""

    newest_path = ""
    newest_ns = 0
    for path in paths:
        mtime_ns = file_mtime_ns(path)
        token = str(path)
        if (mtime_ns, token) > (newest_ns, newest_path):
            newest_ns = mtime_ns
            newest_path = token
    return {
        "sort_key": str(newest_ns) if newest_ns else "",
        "item_id": newest_path,
        "mtime_ns": newest_ns,
        "path": newest_path,
    }
