"""Stanza cliente dell'assistenza remota (``/support/join/<token>``).

Costruisce il bootstrap della stanza e decide la resa: pagina React
(``support/customer_room_react.html`` -> ``SupportCustomerRoom.tsx``) oppure,
con ``?_legacy=1``, la vista classica (``support/customer_room.html`` +
``static/js/support_customer_room.js``) finché resta in servizio.

Il cliente riceve solo il proprio token (``client_token``) e una vista ridotta
della sessione: nessun token o link dell'operatore, nessuna nota interna.
Base: GDPR 2016/679 art. 5, par. 1, lett. c (minimizzazione) e art. 32.
"""

from __future__ import annotations

from typing import Any

from flask import current_app, make_response, render_template, request
from web.services.piattaforma_shell_runtime import vista_classica_richiesta
from web.services.support_runtime import support_session_payload

DEFAULT_LOCAL_CONTROL_BASE = "http://127.0.0.1:27273"
DEFAULT_LOCAL_SIGNER_BASE = "http://127.0.0.1:27272"

CUSTOMER_SESSION_FIELDS = (
    "public_id",
    "status",
    "status_label",
    "customer_name",
    "practice_label",
    "advanced_control_requested",
    "advanced_control_approved",
)


def _local_signer_latest_version() -> str:
    try:
        from web.services.local_signer_release import latest_local_signer_release

        return str(latest_local_signer_release().get("version", "") or "")
    except Exception:
        return ""


def build_customer_room_bootstrap(row: dict[str, Any]) -> dict[str, Any]:
    """Dati di avvio della stanza cliente (stessi campi della vista classica)."""
    return {
        "publicId": row["public_id"],
        "role": "client",
        "authToken": row["client_token"],
        "apiPrefix": f"/support/api/{row['public_id']}",
        "wsBase": "/support/ws",
        "localControlBase": str(current_app.config.get("SUPPORT_LOCAL_CONTROL_BASE") or DEFAULT_LOCAL_CONTROL_BASE),
        "localSignerBase": DEFAULT_LOCAL_SIGNER_BASE,
        "localSignerLatestVersion": _local_signer_latest_version(),
        "customerName": row["customer_name"] or "",
        "status": row["status"],
        "closed": row["status"] == "closed",
    }


def customer_session_view(payload: dict[str, Any]) -> dict[str, Any]:
    """Sottoinsieme della sessione esposto nella pagina del cliente."""
    view = {field: payload.get(field) for field in CUSTOMER_SESSION_FIELDS}
    view["advanced_control_requested"] = bool(view["advanced_control_requested"])
    view["advanced_control_approved"] = bool(view["advanced_control_approved"])
    presence = payload.get("presence") if isinstance(payload.get("presence"), dict) else {}
    view["presence"] = {
        "client": bool(presence.get("client")),
        "operator": bool(presence.get("operator")),
    }
    return view


def render_customer_room(row: dict[str, Any]):
    bootstrap = build_customer_room_bootstrap(row)
    sessione = support_session_payload(row)
    if vista_classica_richiesta():
        return render_template(
            "support/customer_room.html",
            bootstrap=bootstrap,
            sessione=sessione,
        )

    from web.blueprints.react_shell import _vite_entry

    response = make_response(
        render_template(
            "support/customer_room_react.html",
            react_assets=_vite_entry(request.path),
            bootstrap=bootstrap,
            sessione=customer_session_view(sessione),
        )
    )
    # La pagina porta il token del cliente: niente copie in cache condivise o del browser.
    response.headers["Cache-Control"] = "no-store"
    return response


__all__ = [
    "CUSTOMER_SESSION_FIELDS",
    "build_customer_room_bootstrap",
    "customer_session_view",
    "render_customer_room",
]
