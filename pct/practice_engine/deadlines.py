"""Scadenze suggerite dal profilo pratica."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any


def create_suggested_deadlines(scadenziario: Any, fascicolo_id: str, profile: Any) -> int:
    existing = scadenziario.tutte(id_fascicolo=fascicolo_id, solo_aperte=False) if scadenziario else []
    seen = {
        (str(getattr(item, "titolo", "") or "").lower(), str(getattr(item, "note", "") or ""))
        for item in existing
    }
    created = 0
    for index, item in enumerate(getattr(profile, "deadlines", []) or []):
        title = str(item.get("title") or item.get("label") or f"Scadenza suggerita {index + 1}").strip()
        note = f"Regia Operativa - profilo {getattr(profile, 'code', '')} v{getattr(profile, 'version', '')}"
        if (title.lower(), note) in seen:
            continue
        giorni = int(item.get("due_in_days") or item.get("days") or 7)
        try:
            scadenziario.nuova(
                titolo=title,
                data_scadenza=(date.today() + timedelta(days=giorni)).isoformat(),
                id_fascicolo=fascicolo_id,
                descrizione=str(item.get("description") or "Scadenza suggerita dal profilo pratica."),
                note=note,
            )
            created += 1
        except TypeError:
            scadenziario.nuova(title, (date.today() + timedelta(days=giorni)).isoformat(), id_fascicolo=fascicolo_id)
            created += 1
    return created
