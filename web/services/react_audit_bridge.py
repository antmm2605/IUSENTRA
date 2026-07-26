"""Bridge operativo per audit e registro attivita React."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Callable

from web.services.audit_surface import build_audit_view


_SENSITIVE_KEYS = (
    "password",
    "passwd",
    "hash",
    "token",
    "api_key",
    "apikey",
    "secret",
    "authorization",
    "stack",
    "traceback",
)


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


def _safe_string(value: Any) -> str:
    rendered = _text(value)
    lowered = rendered.lower()
    if any(marker in lowered for marker in ("traceback", "exception:", "authorization:", "bearer ")):
        return "[redatto]"
    if len(rendered) > 600:
        return rendered[:600] + "..."
    return rendered


def _redact_payload(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, raw in value.items():
            rendered_key = _text(key)
            lowered = rendered_key.lower()
            if any(marker in lowered for marker in _SENSITIVE_KEYS):
                result[rendered_key] = "[redatto]"
            else:
                result[rendered_key] = _redact_payload(raw)
        return result
    if isinstance(value, list):
        return [_redact_payload(item) for item in value[:40]]
    return _safe_string(value)


def _details_payload(details: str) -> dict[str, Any]:
    if not details:
        return {}
    try:
        parsed = json.loads(details)
    except Exception:
        return {"testo": _safe_string(details)}
    return _redact_payload(parsed) if isinstance(parsed, dict) else {"valore": _redact_payload(parsed)}


def _normalise_record(row: dict[str, Any]) -> dict[str, Any]:
    result = _text(row.get("esito") or "OK").upper()
    resource_state = _text(row.get("resource_state"))
    details = _safe_string(row.get("dettagli"))
    return {
        "id": _text(row.get("id") or row.get("timestamp") or row.get("azione")),
        "timestamp": _text(row.get("timestamp")),
        "userId": _text(row.get("id_utente")),
        "username": _text(row.get("username")) or "Utente non indicato",
        "action": _text(row.get("azione")) or "azione non indicata",
        "resourceType": _text(row.get("risorsa_tipo")),
        "resourceId": _text(row.get("risorsa_id")),
        "details": details,
        "ip": _text(row.get("ip")),
        "result": result,
        "resultTone": _tone_for_result(result),
        "resourceState": resource_state,
        "resourceTone": _resource_tone(resource_state),
        "resourceLabel": _text(row.get("resource_label")),
        "resourceNote": _safe_string(row.get("resource_note")),
        "resourceUrl": _text(row.get("resource_url")),
        "resourceBadgeLabel": _text(row.get("resource_badge_label")),
        "payloadSanitized": True,
    }


def _contracts(route: str) -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "writes": "json_api",
        "route_owner": "react_shell",
        "operational": True,
        "sensitive_payloads_redacted": True,
        "legacy_contract": (
            "artifacts/react-migration/legacy-contracts/registro-attivita.json"
            if route == "/registro-attivita"
            else "artifacts/react-migration/legacy-contracts/audit.json"
        ),
    }


def _action(
    aid: str,
    label: str,
    href: str,
    tone: str = "neutral",
    *,
    enabled: bool = True,
    legacy_fallback: bool = False,
) -> dict[str, Any]:
    return {
        "id": aid,
        "label": label,
        "href": href,
        "method": "GET",
        "tone": tone,
        "enabled": enabled,
        "legacy_fallback": legacy_fallback,
    }


def _base_actions(route: str) -> dict[str, Any]:
    return {
        "canMarkRead": False,
        "canResolve": False,
        "canAddNote": False,
        "canExport": True,
        "links": [
            _action("refresh", "Aggiorna registro", route, "primary"),
            _action("export_csv", "Esporta CSV", "/audit/esporta.csv", "neutral"),
            _action("audit", "Apri audit", "/audit", "neutral"),
            _action("registro", "Apri registro attivita", "/registro-attivita", "neutral"),
            _action("percorso_recupero", "Percorso di recupero", f"{route}?_legacy=1", "warning", legacy_fallback=True),
        ],
    }


def _events_for_view(manager: Any, filters: dict[str, str], limit: int = 200) -> list[Any]:
    return manager.audit_log(
        id_utente=filters["id_utente"],
        azione=filters["azione"],
        limit=limit,
    )


def build_react_audit_payload(
    *,
    get_utenti: Callable[[], Any],
    query: Any = None,
    route: str = "/audit",
) -> dict[str, Any]:
    warnings: list[dict[str, str]] = []
    filters = _filters_from_query(query)
    manager = get_utenti()
    eventi = _events_for_view(manager, filters)
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

    return {
        "ok": True,
        "source": "repository_reali",
        "generated_at": _iso_now(),
        "contracts": _contracts(route),
        "metrics": metrics,
        "events": records,
        "filters": filters,
        "sections": sections,
        "records": records,
        "actions": _base_actions(route),
        "warnings": warnings,
    }


def build_react_audit_detail_payload(
    *,
    get_utenti: Callable[[], Any],
    id_evento: str,
) -> tuple[dict[str, Any], int]:
    wanted = _text(id_evento)
    if not wanted:
        return {"ok": False, "message": "ID evento richiesto.", "errors": {"id_evento": "Campo obbligatorio."}, "item": None}, 400
    manager = get_utenti()
    eventi = manager.audit_log(limit=10000)
    raw_event = next((event for event in eventi if _text(getattr(event, "id", "")) == wanted), None)
    if raw_event is None:
        return {"ok": False, "message": "Evento audit non trovato.", "errors": {"id_evento": "Evento inesistente."}, "item": None}, 404
    row = raw_event.to_dict()
    normalised = _normalise_record(row)
    detail = {
        **normalised,
        "payload": _details_payload(_text(row.get("dettagli"))),
        "payloadSanitized": True,
        "rawAvailable": False,
    }
    return {"ok": True, "message": "Dettaglio evento caricato.", "errors": {}, "item": detail}, 200


def build_react_audit_error_payload(message: str = "Registro attivita non disponibile.", *, route: str = "/audit") -> dict[str, Any]:
    return {
        "ok": False,
        "source": "errore_controllato",
        "generated_at": _iso_now(),
        "contracts": _contracts(route),
        "metrics": [],
        "events": [],
        "filters": {},
        "sections": [],
        "records": [],
        "actions": _base_actions(route),
        "warnings": [{"code": "audit_errore_controllato", "message": message}],
    }
