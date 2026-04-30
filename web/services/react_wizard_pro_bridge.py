"""Bridge JSON per la pagina React Preparazione Udienza Guidata."""

from __future__ import annotations

from typing import Any

from web.services.hearing_preparation_dashboard import build_hearing_preparation_dashboard


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _session_payload(sessione: Any | None) -> dict[str, Any] | None:
    if not sessione:
        return None
    session_id = _safe_text(getattr(sessione, "id", ""))
    step = int(getattr(sessione, "step_corrente", 1) or 1)
    return {
        "id": session_id,
        "title": _safe_text(getattr(sessione, "titolo", ""), "Preparazione udienza"),
        "status": _safe_text(getattr(sessione, "stato", ""), "in_corso"),
        "step": step,
        "progress": int(getattr(sessione, "percentuale_completamento", 0) or 0),
        "modifiedAt": _safe_text(getattr(sessione, "modificato_il", "")),
        "completedAt": _safe_text(getattr(sessione, "completato_il", "")),
        "stepHref": f"/wizard-pro/{session_id}/step/{step}",
        "summaryHref": f"/wizard-pro/{session_id}/completo",
        "archiveHref": f"/wizard-pro/{session_id}/archivia",
        "deleteHref": f"/wizard-pro/{session_id}/elimina",
    }


def _badge_payload(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "label": _safe_text(value.get("label")),
            "tone": _safe_text(value.get("tone"), "secondary"),
        }
    return {"label": _safe_text(value), "tone": "secondary"}


def _case_payload(entry: dict[str, Any]) -> dict[str, Any]:
    case_id = _safe_text(entry.get("id"))
    active = _session_payload(entry.get("sessione_attiva"))
    completed = _session_payload(entry.get("sessione_completata"))
    appointment_id = _safe_text(entry.get("id_appuntamento"))
    return {
        "id": case_id,
        "number": _safe_text(entry.get("numero")),
        "title": _safe_text(entry.get("titolo"), "Fascicolo senza titolo"),
        "client": _safe_text(entry.get("cliente"), "Cliente da completare"),
        "opponent": _safe_text(entry.get("controparte"), "Controparte da completare"),
        "matter": _safe_text(entry.get("materia"), "Materia da completare"),
        "court": _safe_text(entry.get("ufficio_giudiziario"), "Ufficio da definire"),
        "rg": _safe_text(entry.get("rg")),
        "judge": _safe_text(entry.get("giudice"), "Da completare"),
        "section": _safe_text(entry.get("sezione"), "Da completare"),
        "hearingLabel": _safe_text(entry.get("prossima_udienza_label"), "Da pianificare"),
        "hearingRaw": _safe_text(entry.get("prossima_udienza_raw")),
        "hearingDays": entry.get("giorni_udienza"),
        "hearingMode": _safe_text(entry.get("modalita_udienza"), "Da confermare"),
        "hearingType": _safe_text(entry.get("tipo_udienza"), "Udienza"),
        "statusLabel": _safe_text(entry.get("stato_pratica_label"), "Pratica"),
        "statusTone": _safe_text(entry.get("stato_pratica_tone"), "secondary"),
        "progress": int(entry.get("progress_value") or 0),
        "progressLabel": _safe_text(entry.get("progress_label"), "Preparazione"),
        "documentsReady": int(entry.get("documenti_acquisiti") or 0),
        "documentsMissing": int(entry.get("documenti_mancanti") or 0),
        "openActivities": int(entry.get("attivita_aperte") or 0),
        "linkedDeadlines": int(entry.get("scadenze_collegate") or 0),
        "badges": [_badge_payload(item) for item in entry.get("critical_badges", [])],
        "parts": entry.get("parti") if isinstance(entry.get("parti"), list) else [],
        "activeSession": active,
        "completedSession": completed,
        "href": f"/fascicoli/{case_id}",
        "folderHref": f"/fascicoli/{case_id}",
        "agendaHref": f"/agenda/{appointment_id}" if appointment_id else "/agenda",
        "deadlineHref": f"/scadenziario?fascicolo={case_id}",
        "startHref": "/wizard-pro/nuovo",
        "startPayload": {"id_fascicolo": case_id, "id_appuntamento": appointment_id},
    }


def _recent_payload(value: dict[str, Any]) -> dict[str, Any]:
    sessione = _session_payload(value.get("sessione"))
    fascicolo = value.get("fascicolo") or {}
    return {
        "session": sessione,
        "caseTitle": _safe_text(fascicolo.get("titolo") if isinstance(fascicolo, dict) else "", "Fascicolo"),
        "client": _safe_text(fascicolo.get("cliente") if isinstance(fascicolo, dict) else "", "Cliente"),
        "court": _safe_text(fascicolo.get("ufficio_giudiziario") if isinstance(fascicolo, dict) else "", "Ufficio"),
        "status": value.get("status") if isinstance(value.get("status"), dict) else None,
    }


def build_react_wizard_pro_payload(selected_fascicolo_id: str = "") -> dict[str, Any]:
    dashboard = build_hearing_preparation_dashboard(selected_fascicolo_id=selected_fascicolo_id)
    cases = [_case_payload(entry) for entry in dashboard.get("cases", [])]
    selected_id = _safe_text((dashboard.get("selected_case") or {}).get("id")) if isinstance(dashboard.get("selected_case"), dict) else ""
    selected = next((item for item in cases if item["id"] == selected_id), cases[0] if cases else None)
    return {
        "source": "repository_reali",
        "generatedAt": "",
        "contracts": {
            "mock_fallback": False,
            "read_only": False,
            "writes": "operational_routes",
            "route_owner": "react_shell",
        },
        "summary": {
            "totalCases": len(cases),
            "activeDrafts": int((dashboard.get("metrics") or [{}, {"value": 0}])[1].get("value", 0)) if len(dashboard.get("metrics") or []) > 1 else 0,
            "completed": int((dashboard.get("metrics") or [{}, {}, {"value": 0}])[2].get("value", 0)) if len(dashboard.get("metrics") or []) > 2 else 0,
            "upcomingHearings": int((dashboard.get("metrics") or [{}, {}, {}, {"value": 0}])[3].get("value", 0)) if len(dashboard.get("metrics") or []) > 3 else 0,
        },
        "steps": list(dashboard.get("steps", [])),
        "cases": cases,
        "selectedCase": selected,
        "recentDrafts": [_recent_payload(item) for item in dashboard.get("recent_drafts", [])],
        "recentCompleted": [_recent_payload(item) for item in dashboard.get("recent_completed", [])],
        "filters": dashboard.get("filter_options", {}),
        "actions": {
            "start": "/wizard-pro/nuovo",
            "legacy": "/wizard-pro/?_legacy=1",
            "agenda": "/agenda",
            "deadlines": "/scadenziario",
            "newDeadline": "/scadenziario/nuova",
            "newAppointment": "/agenda/nuovo",
            "lex": "/lex?context=preparazione-udienza",
        },
    }
