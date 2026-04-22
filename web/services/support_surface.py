"""Superficie admin per la console di assistenza remota."""

from __future__ import annotations

from typing import Any

from flask import current_app, request, url_for

from web.services.support_runtime import support_repository, support_session_payload


def _is_secure_runtime() -> bool:
    host = str(request.host or "").split(":")[0].strip().lower()
    if host in {"localhost", "127.0.0.1"}:
        return True
    return bool(request.is_secure or current_app.config.get("PREFERRED_URL_SCHEME") == "https")


def _turn_ready() -> bool:
    return bool(
        (current_app.config.get("SUPPORT_TURN_URLS") or [])
        and str(current_app.config.get("SUPPORT_TURN_SHARED_SECRET") or "").strip()
    )


def build_support_console_payload(
    *,
    selected_public_id: str = "",
    status_filter: str = "",
    query: str = "",
) -> dict[str, Any]:
    repo = support_repository()
    rows = repo.list_sessions(
        limit=80,
        status=status_filter,
        search=query,
    )
    selected = None
    if selected_public_id:
        selected = repo.get_session_by_public_id(selected_public_id)
    if selected is None and rows:
        selected = rows[0]

    sessions = [support_session_payload(row) for row in rows]
    selected_payload = support_session_payload(selected) if selected else None
    events = repo.list_events(selected_payload["public_id"]) if selected_payload else []
    warnings: list[str] = []
    if not _is_secure_runtime():
        warnings.append(
            "La condivisione schermo del cliente richiede HTTPS o localhost: da remoto il link cliente deve passare da contesto sicuro."
        )
    if not _turn_ready():
        warnings.append(
            "TURN non configurato: in reti esterne o NAT restrittivi alcune sessioni WebRTC possono non partire."
        )
    if not current_app.config.get("SUPPORT_STUN_URLS"):
        warnings.append(
            "Nessun server STUN configurato: aggiungi almeno un endpoint per migliorare la negoziazione WebRTC."
        )
    if not str(current_app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE") or "").strip():
        warnings.append(
            "Controllo remoto avanzato non configurato: lo screen sharing parte subito, ma l'escalation esterna resta disattivata."
        )

    return {
        "stats": repo.stats(),
        "filters": {
            "status": status_filter,
            "q": query,
        },
        "sessions": sessions,
        "selected_session": selected_payload,
        "events": events,
        "warnings": warnings,
        "create_action": url_for("support_remote.create_session_api"),
        "operator_rule": "L'assistenza remota parte sempre dal SUPERADMIN. Il cliente entra solo dal link firmato della sessione.",
        "advanced_ready": bool(str(current_app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE", "") or "").strip()),
    }
