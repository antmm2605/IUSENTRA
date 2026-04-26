"""Permessi e isolamento tenant per la Ricerca Studio."""

from __future__ import annotations

from typing import Any


def can_view_result(user: Any, row: dict[str, Any]) -> bool:
    """Controllo difensivo: il filtro tenant avviene gia' in repository."""
    visibility = str(row.get("visibility") or "studio")
    if visibility == "privato":
        owner = str(row.get("metadata", {}).get("owner_id") or "")
        user_id = str(getattr(user, "id", "") or "")
        return bool(owner and user_id and owner == user_id)
    scope = str(row.get("permission_scope") or "studio")
    if scope and scope not in {"studio", "utente", "admin"}:
        return True
    return True
