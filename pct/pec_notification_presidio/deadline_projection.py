"""Identità e data delle scadenze del presidio, senza inventare termini di legge."""
from datetime import date, datetime
from zoneinfo import ZoneInfo
import re


def deadline_marker(item_id: str) -> str:
    value = str(item_id or "")
    if value.startswith(("legal-notification-presidio:", "legal-notification:")) and value.count(":") == 2:
        value = value.rsplit(":", 1)[0]
    return f"IUSENTRA_LEGAL_NOTIFICATION:{value}"


def deadline_date(item: dict) -> str:
    """Solo un termine esplicito può diventare una scadenza; 'da verificare' è un'attività."""
    value = str(item.get("explicitDueAt") or "").strip()
    try:
        if len(value) == 10:
            return date.fromisoformat(value).isoformat()
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.tzinfo is not None:
            timestamp = timestamp.astimezone(ZoneInfo("Europe/Rome"))
        return timestamp.date().isoformat()
    except (ValueError, OverflowError):
        return ""


def deadline_matches(note: str, marker: str) -> bool:
    """Confronto dell'identità intera, compatibile con i marcatori storici con stato."""
    return any(deadline_marker(value) == marker for value in re.findall(r"IUSENTRA_LEGAL_NOTIFICATION:([^\s]+)", str(note or "")))


def annotation(reason: str) -> str:
    return f"[Audit IUSENTRA] Scadenza automatica annullata: {reason}. Il presidio e le fonti restano consultabili; nessuna notifica è registrata come eseguita."
