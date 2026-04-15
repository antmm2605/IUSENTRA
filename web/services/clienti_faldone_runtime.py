"""Runtime helpers for the cliente workspace and faldone views."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def carica_note_faldone(note_db_path: str, id_cliente: str) -> dict[str, Any]:
    """Load persisted faldone notes for a cliente."""
    path = Path(note_db_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    value = payload.get(id_cliente)
    return value if isinstance(value, dict) else {}


def salva_note_faldone(note_db_path: str, id_cliente: str, note: dict[str, Any]) -> None:
    """Persist faldone notes in the shared JSON store."""
    path = Path(note_db_path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        payload = {}

    payload[id_cliente] = note
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
