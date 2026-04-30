"""Bridge dati per la pagina React Centro Servizi Telematici."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from flask import url_for

from web.services.telematico_control_tower import build_telematico_control_tower

PORTALS = ("pst", "pdp", "pat", "ptt")
SERVICE_MAP = {
    "pst": "polisweb_consultazione",
    "pdp": "pdp_penale",
    "pat": "pat_siga",
    "ptt": "ptt_sigit",
}
PORTAL_LABELS = {
    "pst": "PST / PolisWeb",
    "pdp": "PDP Penale",
    "pat": "PAT / SIGA",
    "ptt": "PTT / SIGIT",
}
PORTAL_TITLES = {
    "pst": "PST / PolisWeb",
    "pdp": "PDP Penale",
    "pat": "PAT Amministrativo",
    "ptt": "PTT Tributario",
}
PORTAL_DESCRIPTIONS = {
    "pst": "Consultazione civile, SIGP e import autorizzato dei fascicoli già scaricati.",
    "pdp": "Workflow penale, esiti, documenti collegati e controllo manual review.",
    "pat": "Portale avvocato, fascicolo amministrativo e import guidato documenti.",
    "ptt": "Telecontenzioso, SIGIT, fascicoli tributari e ricevute importate.",
}
PORTAL_TONES = {"pst": "primary", "pdp": "danger", "pat": "success", "ptt": "warning"}
PORTAL_HOME_ENDPOINTS = {"pst": "polisWeb_home", "pdp": "pdp_home", "pat": "pat_home", "ptt": "sigit_home"}
PORTAL_HOME_FALLBACKS = {"pst": "/polisWeb", "pdp": "/pdp", "pat": "/pat", "ptt": "/sigit/ricerca"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _safe(label: str, func: Callable[[], Any], fallback: Any, logger: Any | None = None) -> Any:
    try:
        return func()
    except Exception as exc:  # pragma: no cover - guardrail operativo
        if logger:
            logger.exception("Bridge React telematico: sorgente non disponibile (%s): %s", label, exc)
        return fallback


def _safe_url(endpoint: str, fallback: str, **values: Any) -> str:
    try:
        return url_for(endpoint, **values)
    except Exception:
        return fallback


def _int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _text(value: Any, fallback: str = "") -> str:
    return str(value or fallback).strip()


def _portal_from_service(value: Any) -> str:
    raw = _text(value).lower()
    if raw in PORTALS:
        return raw
    for portal, code in SERVICE_MAP.items():
        if raw == code or portal in raw:
            return portal
    if "polis" in raw:
        return "pst"
    if "penale" in raw:
        return "pdp"
    if "siga" in raw or "amministr" in raw:
        return "pat"
    if "sigit" in raw or "tribut" in raw:
        return "ptt"
    return "altro"


def _tone_for_status(status: str, portal: str = "") -> str:
    raw = _text(status).lower()
    if any(marker in raw for marker in ("rifiut", "errore", "blocked", "blocc")):
        return "danger"
    if any(marker in raw for marker in ("warning", "manual", "incomplet", "attesa", "pending")):
        return "warning"
    if any(marker in raw for marker in ("import", "sincron", "accepted", "complet")):
        return "success"
    return PORTAL_TONES.get(portal, "neutral")


def _channel_badges(payload: dict[str, Any]) -> list[str]:
    badges: list[str] = []
    if payload.get("pkcs11_mode"):
        badges.append("Local Signer")
    if payload.get("browser_channel_required"):
        badges.append("Accesso guidato")
    if payload.get("demo_mode"):
        badges.append("Assistita")
    if not badges:
        badges.append("Operativo")
    return badges


def _build_channel(portal: str, stats: dict[str, Any], access_payload: dict[str, Any]) -> dict[str, Any]:
    spec = dict(access_payload.get("spec") or {})
    service_stats = dict((stats.get("per_service") or {}).get(SERVICE_MAP[portal]) or {})
    home_href = _safe_url(PORTAL_HOME_ENDPOINTS[portal], PORTAL_HOME_FALLBACKS[portal])
    import_href = _safe_url(
        "portale_acquisizione_wizard",
        f"/portali/{portal}/acquisizione",
        portale=portal,
    )
    status_text = _text(access_payload.get("status_text"), "Da configurare")
    attention_needed = _int(service_stats.get("attention_needed"))
    tone = "warning" if attention_needed else PORTAL_TONES[portal]
    if access_payload.get("demo_mode"):
        tone = "warning"
    return {
        "id": portal,
        "label": spec.get("label") or PORTAL_LABELS[portal],
        "title": spec.get("title") or PORTAL_TITLES[portal],
        "description": spec.get("subtitle") or PORTAL_DESCRIPTIONS[portal],
        "tone": tone,
        "statusText": status_text,
        "environmentLabel": access_payload.get("environment_label") or "",
        "cases": _int(service_stats.get("totale")),
        "importCompleted": _int(service_stats.get("import_completed")),
        "attentionNeeded": attention_needed,
        "lastSyncAt": access_payload.get("last_sync_at") or "",
        "homeHref": home_href,
        "importHref": import_href,
        "presideHref": f"/telematico?focus={portal}",
        "browserChannelRequired": bool(access_payload.get("browser_channel_required")),
        "demoMode": bool(access_payload.get("demo_mode")),
        "pkcs11Mode": bool(access_payload.get("pkcs11_mode")),
        "badges": _channel_badges(access_payload),
        "quickActions": [
            {"label": "Apri portale", "href": home_href, "tone": PORTAL_TONES[portal]},
            {"label": "Importa da portale", "href": import_href, "tone": "primary"},
            {"label": "Presidia", "href": f"/telematico?focus={portal}", "tone": "warning"},
        ],
    }


def _practice_href(row: dict[str, Any], fascicoli_index: dict[str, Any]) -> str:
    practice_id = _text(row.get("practice_id") or row.get("id_fascicolo"))
    if practice_id and practice_id in fascicoli_index:
        return _safe_url("dettaglio_fascicolo", f"/fascicoli/{practice_id}", id_fasc=practice_id)
    return "/telematico"


def _case_row(row: dict[str, Any], index: int, fascicoli_index: dict[str, Any]) -> dict[str, Any]:
    portal = _portal_from_service(row.get("service_code") or row.get("portale"))
    practice_id = _text(row.get("practice_id") or row.get("id_fascicolo"))
    fasc = fascicoli_index.get(practice_id)
    title = (
        _text(row.get("title"))
        or _text(row.get("practice_title"))
        or _text(getattr(fasc, "titolo", ""))
        or _text(row.get("registry_number"))
        or "Pratica telematica"
    )
    rg = _text(row.get("registry_number") or row.get("numero_rg") or getattr(fasc, "rg_completo", "") or getattr(fasc, "numero", ""))
    court = _text(row.get("office_name") or row.get("ufficio") or getattr(fasc, "tribunale", ""))
    status = _text(row.get("internal_status") or row.get("status") or row.get("status_text"), "Da verificare")
    return {
        "id": _text(row.get("id") or practice_id, f"case-{index}"),
        "portal": portal,
        "portalLabel": PORTAL_LABELS.get(portal, "Telematico"),
        "title": title,
        "subtitle": " · ".join(part for part in [court, rg] if part) or "Fascicolo telematico importato",
        "subject": _text(row.get("subject") or row.get("oggetto") or getattr(fasc, "oggetto", "")),
        "statusText": status.replace("_", " ").title(),
        "documentsCount": _int(row.get("documents_count") or row.get("documents") or row.get("document_count")),
        "openTasks": _int(row.get("open_tasks") or row.get("task_aperti") or row.get("tasks")),
        "syncedAt": _text(row.get("updated_at") or row.get("last_sync_at") or row.get("synced_at")),
        "href": _practice_href(row, fascicoli_index),
        "tone": _tone_for_status(status, portal),
        "badges": [PORTAL_LABELS.get(portal, "TEL")],
    }


def _event_row(row: dict[str, Any], index: int, fascicoli_index: dict[str, Any]) -> dict[str, Any]:
    portal = _portal_from_service(row.get("service_code") or row.get("portale"))
    title = _text(row.get("title") or row.get("event_type") or row.get("tipo"), "Attività telematica")
    status = _text(row.get("status") or row.get("outcome") or row.get("badge"))
    return {
        "id": _text(row.get("id"), f"event-{index}"),
        "portal": portal,
        "title": title,
        "subtitle": _text(row.get("description") or row.get("message") or row.get("practice_title")),
        "timestamp": _text(row.get("created_at") or row.get("timestamp") or row.get("time")),
        "href": _practice_href(row, fascicoli_index),
        "tone": _tone_for_status(status, portal),
        "badge": status,
    }


def _control_item(value: Any, index: int, badge: str, fallback_tone: str, fascicoli_index: dict[str, Any]) -> dict[str, Any]:
    row = dict(value or {}) if isinstance(value, dict) else {}
    portal = _portal_from_service(row.get("service_code") or row.get("portale") or row.get("portal"))
    status = _text(row.get("status") or row.get("badge"), badge)
    return {
        "id": _text(row.get("id") or row.get("practice_id"), f"{badge}-{index}"),
        "portal": portal,
        "title": _text(row.get("title") or row.get("practice_title") or row.get("subject"), "Elemento telematico da presidiare"),
        "subtitle": _text(row.get("subtitle") or row.get("description") or row.get("office_name") or row.get("message")),
        "href": _practice_href(row, fascicoli_index),
        "tone": _tone_for_status(status, portal) if status else fallback_tone,
        "badge": status,
    }


def _control_tower_payload(control_tower: dict[str, Any], fascicoli_index: dict[str, Any]) -> dict[str, Any]:
    return {
        "pendingOutcomes": [
            _control_item(item, index, "esito", "warning", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("pending_outcomes") or []))
        ],
        "incompleteImports": [
            _control_item(item, index, "import", "warning", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("incomplete_imports") or []))
        ],
        "warnings": [
            _control_item(item, index, "warning", "warning", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("warning_cases") or []))
        ],
        "blockedCases": [
            _control_item(item, index, "bloccato", "danger", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("blocked_cases") or []))
        ],
        "predeposito": [
            _control_item(item, index, "predeposito", "primary", fascicoli_index)
            for index, item in enumerate(list(control_tower.get("predeposito") or []))
        ],
    }


def _lex_suggestions(summary: dict[str, int], channels: list[dict[str, Any]]) -> list[str]:
    suggestions: list[str] = []
    if summary.get("blocked"):
        suggestions.append("Prima del deposito risolvi i fascicoli bloccati nei controlli predeposito.")
    if summary.get("pendingOutcomes"):
        suggestions.append("Controlla gli esiti in attesa e collega ricevute o comunicazioni al fascicolo corretto.")
    if summary.get("incompleteImports"):
        suggestions.append("Completa gli import parziali prima di chiudere il presidio telematico giornaliero.")
    if any(channel.get("demoMode") or channel.get("browserChannelRequired") for channel in channels):
        suggestions.append("Per i canali browser-guided apri il portale ufficiale e importa solo payload o file autorizzati.")
    return suggestions[:4]


def build_react_telematico_payload(
    *,
    get_telematico: Callable[[], Any],
    get_fascicoli: Callable[[], Any],
    build_access_status_payload: Callable[[str], dict[str, Any]],
    logger: Any | None = None,
) -> dict[str, Any]:
    """Costruisce il payload reale per ``/api/v1/ui/telematico``."""

    repo = _safe("telematico_repo", get_telematico, None, logger)
    stats = _safe("case_stats", lambda: repo.case_stats() if repo else {}, {"totale": 0, "per_service": {}}, logger)
    recent_cases = _safe("list_cases", lambda: repo.list_cases(limit=18) if repo else [], [], logger)
    recent_events = _safe("list_recent_events", lambda: repo.list_recent_events(limit=12) if repo else [], [], logger)
    fascicoli = _safe("fascicoli", lambda: get_fascicoli().tutti(), [], logger)
    fascicoli_index = {str(getattr(fascicolo, "id", "")): fascicolo for fascicolo in fascicoli}
    control_tower = _safe(
        "control_tower",
        lambda: build_telematico_control_tower(get_telematico=get_telematico, get_fascicoli=get_fascicoli),
        {
            "summary": {"pending_outcomes": 0, "imports_incomplete": 0, "warnings": 0, "blocked": 0},
            "pending_outcomes": [],
            "incomplete_imports": [],
            "warning_cases": [],
            "blocked_cases": [],
            "predeposito": [],
            "recent_events": [],
        },
        logger,
    )
    access_payloads = {
        portal: _safe("access_status", lambda portal=portal: build_access_status_payload(portal), {}, logger)
        for portal in PORTALS
    }
    channels = [_build_channel(portal, stats, access_payloads[portal]) for portal in PORTALS]
    control_payload = _control_tower_payload(control_tower, fascicoli_index)
    summary_raw = dict(control_tower.get("summary") or {})
    summary = {
        "total": _int(stats.get("totale")) or sum(_int(channel.get("cases")) for channel in channels),
        "pst": _int(channels[0].get("cases")),
        "pdp": _int(channels[1].get("cases")),
        "pat": _int(channels[2].get("cases")),
        "ptt": _int(channels[3].get("cases")),
        "pendingOutcomes": _int(summary_raw.get("pending_outcomes") or len(control_payload["pendingOutcomes"])),
        "incompleteImports": _int(summary_raw.get("imports_incomplete") or len(control_payload["incompleteImports"])),
        "warnings": _int(summary_raw.get("warnings") or len(control_payload["warnings"])),
        "blocked": _int(summary_raw.get("blocked") or len(control_payload["blockedCases"])),
        "attentionNeeded": sum(_int(channel.get("attentionNeeded")) for channel in channels),
    }
    notices = []
    if summary["blocked"] or summary["warnings"]:
        notices.append(
            {
                "tone": "warning",
                "title": "Regia telematica da presidiare",
                "body": f"Sono presenti {summary['warnings']} warning e {summary['blocked']} blocchi nei controlli telematici.",
            }
        )
    if any(channel.get("demoMode") for channel in channels):
        notices.append(
            {
                "tone": "warning",
                "title": "Canale assistito",
                "body": "Almeno un portale richiede apertura guidata o import manuale autorizzato: non usare scraping HTML.",
            }
        )
    return {
        "source": "repository_reali",
        "generatedAt": _iso_now(),
        "contracts": {
            "mock_fallback": False,
            "read_only": True,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "summary": summary,
        "channels": channels,
        "recentCases": [_case_row(dict(row or {}), index, fascicoli_index) for index, row in enumerate(recent_cases)],
        "recentEvents": [_event_row(dict(row or {}), index, fascicoli_index) for index, row in enumerate(list(recent_events) + list(control_tower.get("recent_events") or []))][:14],
        "controlTower": control_payload,
        "notices": notices,
        "actions": {
            "checklistHref": _safe_url("checklist_deposito", "/deposito/checklist"),
            "firmaDigitaleHref": "/guida/firma-digitale",
            "localSignerHref": "/local-signer",
            "connectionStatusHref": "/api/telematico/connection-status",
            "lexHref": "/lex?context=telematico",
            "emailHref": "/email/",
        },
        "lexSuggestions": _lex_suggestions(summary, channels),
    }
