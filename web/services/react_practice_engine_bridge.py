"""Bridge API/UI per Regia Operativa Fascicolo."""

from __future__ import annotations

from typing import Any, Callable
from urllib.parse import quote

from pct.practice_engine.evaluator import build_regia_payload


def _safe(label: str, func: Callable[[], Any], fallback: Any) -> Any:
    try:
        return func()
    except Exception:
        return fallback


def _all_conferimenti(preventivi_manager: Any) -> list[Any]:
    if hasattr(preventivi_manager, "tutti_conferimenti"):
        return list(preventivi_manager.tutti_conferimenti())
    return []


def _call_scoped(manager: Any, method_name: str, fascicolo_id: str, fallback: Callable[[], Any]) -> list[Any]:
    method = getattr(manager, method_name, None)
    if callable(method):
        return list(method(fascicolo_id) or [])
    return list(fallback() or [])


_STATI_CERTI_CATALOGO = {"confirmed"}
_CONFIDENZA_CERTA_CATALOGO = 90


def _etichette_catalogo(fascicolo_id: str) -> list[str]:
    """Le voci certe del catalogo documentale: confermate o riconosciute dal titolo dell'atto (>= 90)."""
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id

    assegnazioni = build_document_ai_service().repository.list_catalog_assignments(document_ai_tenant_id(), fascicolo_id)
    return [
        str(voce.document_label or "").strip()
        for voce in assegnazioni
        if str(voce.document_label or "").strip() and str(voce.status or "") != "review_required"
        and (str(voce.status or "") in _STATI_CERTI_CATALOGO or int(voce.confidence or 0) >= _CONFIDENZA_CERTA_CATALOGO)
    ]


def _profilo_salvato(engine: Any, fascicolo_id: str) -> bool:
    return bool(_safe("profilo", lambda: engine.get_profile_snapshot(fascicolo_id), None))


def _ricevute_cancelleria_depositi(fid: str) -> dict[str, Any]:
    import sqlite3

    from flask import g, has_request_context
    from pct.pec_deposit_query_repository import PecDepositQueryRepository
    from web.services.notification_presidia_runtime import _tenant_id
    from web.services.pec_audit_query_connection import pec_audit_query_connection
    from web.services.tenant_api_auth import api_key_valid_for_request

    if not has_request_context():
        return {"items": [], "error": ""}
    utente = g.get("utente_corrente")
    if not (api_key_valid_for_request() or (utente and utente.ha_permesso("fascicoli.leggi"))):
        return {"items": [], "error": ""}
    tenant = _tenant_id()
    try:
        with pec_audit_query_connection(tenant=tenant) as conn:
            rows = PecDepositQueryRepository(conn, tenant).accettazioni_cancelleria_fascicolo(fid)
    except (RuntimeError, sqlite3.Error, PermissionError):
        return {"items": [], "error": "Catalogo delle ricevute PEC in aggiornamento o non disponibile."}
    return {
        "items": [
            {
                "id": row["message_id"],
                "date": row["event_at"],
                "title": row["title"] or "Accettazione del deposito",
                "idBusta": row["correlation_key"].removeprefix("idbusta:")
                if row["correlation_key"].startswith("idbusta:") else "",
                "href": f"/email/?audit_id={quote(row['message_id'], safe='')}",
            }
            for row in rows
        ],
        "error": "",
    }


def build_react_practice_engine_payload(
    *,
    fascicolo_id: str,
    get_fascicoli: Callable[[], Any],
    get_clienti: Callable[[], Any],
    get_preventivi: Callable[[], Any],
    get_fatturazione: Callable[[], Any],
    get_practice_engine: Callable[[], Any],
    actor: str = "",
    manual_code: str = "",
) -> dict[str, Any]:
    gf = get_fascicoli()
    fascicolo = _safe("fascicolo", lambda: gf.get(fascicolo_id), None)
    if not fascicolo:
        return {
            "source": "repository reale",
            "mock_fallback": False,
            "page_state": "non_trovato",
            "message": "Fascicolo non trovato.",
        }
    cliente = _safe("cliente", lambda: get_clienti().get(getattr(fascicolo, "id_cliente", "")), None)
    gp = get_preventivi()
    preventivi = _safe(
        "preventivi",
        lambda: _call_scoped(gp, "preventivi_per_fascicolo", fascicolo_id, lambda: gp.tutti_preventivi()),
        [],
    )
    conferimenti = _safe(
        "conferimenti",
        lambda: _call_scoped(gp, "conferimenti_per_fascicolo", fascicolo_id, lambda: _all_conferimenti(gp)),
        [],
    )
    fatturazione = get_fatturazione()
    parcelle = _safe(
        "fatturazione",
        lambda: _call_scoped(fatturazione, "per_fascicolo", fascicolo_id, lambda: fatturazione.tutte()),
        [],
    )
    engine = get_practice_engine()
    gia_salvato = _profilo_salvato(engine, fascicolo_id)
    payload = build_regia_payload(
        engine,
        fascicolo=fascicolo,
        cliente=cliente,
        preventivi=preventivi,
        conferimenti=conferimenti,
        parcelle=parcelle,
        fascicoli_manager=gf,
        actor=actor,
        manual_code=manual_code,
        etichette_documenti=_safe("catalogo", lambda: _etichette_catalogo(fascicolo_id), []),
    )
    if not gia_salvato and _profilo_salvato(engine, fascicolo_id):
        # Profilo impostato ora dai dati certi: la Lettura del fascicolo non deve più chiederne la conferma.
        _safe("lettura", lambda: _invalida_lettura(fascicolo_id), None)
    payload["courtDepositReceipts"] = _ricevute_cancelleria_depositi(fascicolo.id)
    return payload


def _invalida_lettura(fascicolo_id: str) -> None:
    from web.services.lettura_cache import invalida_lettura

    invalida_lettura(fascicolo_id)
