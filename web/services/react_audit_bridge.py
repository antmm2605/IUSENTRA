"""Bridge read-only per audit e registro attivita React."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from web.services.audit_surface import build_audit_view


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tone_for_result(value: str) -> str:
    result = value.strip().upper()
    if result == "OK":
        return "success"
    if result == "NEGATO":
        return "warning"
    if result == "ERRORE":
        return "danger"
    return "neutral"


def _resource_tone(value: str) -> str:
    state = value.strip().lower()
    if state == "attivo":
        return "success"
    if state == "riconciliato":
        return "info"
    if state == "storico":
        return "warning"
    return "neutral"


def _safe_user_label(user: Any) -> str:
    return (
        _text(getattr(user, "nome_completo", ""))
        or _text(getattr(user, "username", ""))
        or _text(getattr(user, "email", ""))
        or _text(getattr(user, "id", ""))
    )


def _filters_from_query(query: Any) -> dict[str, str]:
    getter = getattr(query, "get", None)
    if not callable(getter):
        return {"id_utente": "", "azione": ""}
    return {
        "id_utente": _text(getter("id_utente", "")),
        "azione": _text(getter("azione", "")),
    }


def _normalise_record(row: dict[str, Any]) -> dict[str, Any]:
    result = _text(row.get("esito") or "OK").upper()
    resource_state = _text(row.get("resource_state"))
    return {
        "id": _text(row.get("id") or row.get("timestamp") or row.get("azione")),
        "timestamp": _text(row.get("timestamp")),
        "userId": _text(row.get("id_utente")),
        "username": _text(row.get("username")) or "Utente non indicato",
        "action": _text(row.get("azione")) or "azione non indicata",
        "resourceType": _text(row.get("risorsa_tipo")),
        "resourceId": _text(row.get("risorsa_id")),
        "details": _text(row.get("dettagli")),
        "ip": _text(row.get("ip")),
        "result": result,
        "resultTone": _tone_for_result(result),
        "resourceState": resource_state,
        "resourceTone": _resource_tone(resource_state),
        "resourceLabel": _text(row.get("resource_label")),
        "resourceNote": _text(row.get("resource_note")),
        "resourceUrl": _text(row.get("resource_url")),
        "resourceBadgeLabel": _text(row.get("resource_badge_label")),
    }


def build_react_audit_payload(
    *,
    get_utenti: Callable[[], Any],
    query: Any = None,
    route: str = "/audit",
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    filters = _filters_from_query(query)
    manager = get_utenti()

    eventi = manager.audit_log(
        id_utente=filters["id_utente"],
        azione=filters["azione"],
        limit=200,
    )
    try:
        audit_view = build_audit_view(eventi)
    except Exception as exc:
        warnings.append({
            "code": "audit_arricchimento_non_disponibile",
            "message": f"Arricchimento audit non disponibile: {type(exc).__name__}.",
        })
        audit_view = {"eventi": [evento.to_dict() for evento in eventi], "summary": {}}

    raw_rows = [row for row in audit_view.get("eventi", []) if isinstance(row, dict)]
    records = [_normalise_record(row) for row in raw_rows]
    users = list(manager.tutti())

    by_result = Counter(record["result"] for record in records)
    by_action = Counter(record["action"] for record in records)
    by_user = Counter(record["username"] for record in records)
    summary = audit_view.get("summary") if isinstance(audit_view.get("summary"), dict) else {}

    metrics = [
        {"id": "eventi", "label": "Eventi visualizzati", "value": len(records), "note": "Ultimi 200 eventi filtrati", "tone": "primary"},
        {"id": "ok", "label": "Esito OK", "value": by_result.get("OK", 0), "note": "Operazioni completate", "tone": "success"},
        {"id": "negati", "label": "Negati", "value": by_result.get("NEGATO", 0), "note": "Tentativi non autorizzati", "tone": "warning"},
        {"id": "errori", "label": "Errori", "value": by_result.get("ERRORE", 0), "note": "Eventi con errore", "tone": "danger"},
        {"id": "attivi", "label": "Risorse attive", "value": int(summary.get("attivi", 0) or 0), "note": "Riconosciute nel database", "tone": "success"},
        {"id": "storici", "label": "Risorse storiche", "value": int(summary.get("storici", 0) or 0), "note": "Non piu presenti con lo stesso ID", "tone": "warning"},
    ]

    sections = [
        {
            "id": "filtri",
            "title": "Filtri applicati",
            "kind": "filters",
            "items": [
                {"id": "utente", "label": "Utente", "value": filters["id_utente"] or "Tutti", "note": "", "tone": "neutral"},
                {"id": "azione", "label": "Azione", "value": filters["azione"] or "Tutte", "note": "", "tone": "neutral"},
            ],
            "emptyMessage": "",
        },
        {
            "id": "azioni_frequenti",
            "title": "Azioni piu frequenti",
            "kind": "distribution",
            "items": [
                {"id": f"azione-{index}", "label": label, "value": count, "note": "", "tone": "primary"}
                for index, (label, count) in enumerate(by_action.most_common(8))
            ],
            "emptyMessage": "Nessuna azione audit nel filtro corrente.",
        },
        {
            "id": "utenti_attivi",
            "title": "Utenti nel registro",
            "kind": "distribution",
            "items": [
                {"id": f"utente-{index}", "label": label, "value": count, "note": "", "tone": "info"}
                for index, (label, count) in enumerate(by_user.most_common(8))
            ],
            "emptyMessage": "Nessun utente nel filtro corrente.",
        },
        {
            "id": "utenti_filtro",
            "title": "Utenti disponibili per filtro",
            "kind": "users",
            "items": [
                {
                    "id": _text(getattr(user, "id", "")),
                    "label": _safe_user_label(user),
                    "value": _text(getattr(getattr(user, "ruolo", ""), "value", getattr(user, "ruolo", ""))),
                    "note": _text(getattr(user, "email", "")),
                    "tone": "success" if bool(getattr(user, "attivo", False)) else "neutral",
                }
                for user in users
            ],
            "emptyMessage": "Nessun utente disponibile.",
        },
    ]

    actions = [
        {"id": "refresh", "label": "Aggiorna registro", "href": route, "method": "GET", "tone": "primary"},
        {"id": "export_csv", "label": "Esporta CSV", "href": "/audit/esporta.csv", "method": "GET", "tone": "neutral"},
        {"id": "audit", "label": "Apri audit", "href": "/audit", "method": "GET", "tone": "neutral"},
        {"id": "registro", "label": "Apri registro attivita", "href": "/registro-attivita", "method": "GET", "tone": "neutral"},
    ]

    return {
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "legacy_contract": (
                "artifacts/react-migration/legacy-contracts/registro-attivita.json"
                if route == "/registro-attivita"
                else "artifacts/react-migration/legacy-contracts/audit.json"
            ),
        },
        "metrics": metrics,
        "sections": sections,
        "records": records,
        "actions": actions,
        "warnings": warnings,
    }


def build_react_audit_error_payload(message: str = "Registro audit non disponibile.", *, route: str = "/audit") -> dict[str, Any]:
    return {
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "writes": "none",
            "route_owner": "react_shell",
            "legacy_contract": (
                "artifacts/react-migration/legacy-contracts/registro-attivita.json"
                if route == "/registro-attivita"
                else "artifacts/react-migration/legacy-contracts/audit.json"
            ),
        },
        "metrics": [],
        "sections": [],
        "records": [],
        "actions": [{"id": "legacy", "label": "Apri modulo legacy", "href": f"{route}?_legacy=1", "method": "GET", "tone": "neutral"}],
        "warnings": [{"code": "audit_errore_controllato", "message": message}],
    }
