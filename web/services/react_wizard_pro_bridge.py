"""Bridge JSON reale per le superfici React Preparazione Udienza Guidata."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pct.document_signature_state import document_has_real_digital_signature
from pct.wizard_pro import ESITI, STEP_ICONS, STEP_LABELS
from web.helpers import get_agenda, get_fascicoli, get_scadenziario, get_soggetti, get_wizard_pro
from web.services.hearing_preparation_dashboard import build_hearing_preparation_dashboard
from web.services.ui_localization import EMPTY_UI_VALUE, format_date, format_datetime


N_STEP = 5

DOCUMENT_STATUS_LABELS = {
    "da_portare": "Da portare",
    "pronto": "Pronto",
    "non_necessario": "Non necessario",
}

DOCUMENT_STATUS_TONES = {
    "da_portare": "warning",
    "pronto": "success",
    "non_necessario": "neutral",
}


def _safe_text(value: Any, fallback: str = "") -> str:
    text = str(value or "").strip()
    return text or fallback


def _contracts() -> dict[str, Any]:
    return {
        "mock_fallback": False,
        "read_only": False,
        "writes": "operational_routes",
        "route_owner": "react_shell",
    }


def _label_date(value: Any) -> str:
    raw = _safe_text(value)
    if not raw:
        return "Non indicata"
    label = format_datetime(raw) if "T" in raw else format_date(raw)
    return raw if label == EMPTY_UI_VALUE else label


def _session_payload(sessione: Any | None) -> dict[str, Any] | None:
    if not sessione:
        return None
    session_id = _safe_text(getattr(sessione, "id", ""))
    step = int(getattr(sessione, "step_corrente", 1) or 1)
    return {
        "id": session_id,
        "title": _safe_text(getattr(sessione, "titolo", ""), "Preparazione udienza"),
        "status": _safe_text(getattr(sessione, "stato", ""), "in_corso"),
        "statusLabel": _status_label(getattr(sessione, "stato", "")),
        "step": step,
        "progress": int(getattr(sessione, "percentuale_completamento", 0) or 0),
        "modifiedAt": _safe_text(getattr(sessione, "modificato_il", "")),
        "modifiedAtLabel": _label_date(getattr(sessione, "modificato_il", "")),
        "completedAt": _safe_text(getattr(sessione, "completato_il", "")),
        "completedAtLabel": _label_date(getattr(sessione, "completato_il", "")),
        "stepHref": f"/wizard-pro/{session_id}/step/{step}",
        "summaryHref": f"/wizard-pro/{session_id}/completo",
        "archiveHref": f"/wizard-pro/{session_id}/archivia",
        "deleteHref": f"/wizard-pro/{session_id}/elimina",
    }


def _status_label(value: Any) -> str:
    status = _safe_text(value, "in_corso")
    return {
        "in_corso": "In corso",
        "completato": "Completata",
        "archiviato": "Archiviata",
    }.get(status, status)


def _badge_payload(value: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return {
            "label": _safe_text(value.get("label")),
            "tone": _safe_text(value.get("tone"), "neutral"),
        }
    return {"label": _safe_text(value), "tone": "neutral"}


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
        "statusTone": _safe_text(entry.get("stato_pratica_tone"), "neutral"),
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


def _steps_payload(sessione: Any, current_step: int | None = None) -> list[dict[str, Any]]:
    flags = [
        bool(getattr(sessione, "step1_confermato", False)),
        bool(getattr(sessione, "step2_confermato", False)),
        bool(getattr(sessione, "step3_confermato", False)),
        bool(getattr(sessione, "step4_confermato", False)),
        bool(getattr(sessione, "step5_confermato", False)),
    ]
    session_id = _safe_text(getattr(sessione, "id", ""))
    active = current_step or int(getattr(sessione, "step_corrente", 1) or 1)
    return [
        {
            "n": index,
            "label": STEP_LABELS.get(index, f"Step {index}"),
            "icon": STEP_ICONS.get(index, ""),
            "confirmed": flags[index - 1],
            "active": index == active,
            "href": f"/wizard-pro/{session_id}/step/{index}",
            "available": index <= max(int(getattr(sessione, "step_corrente", 1) or 1), active),
        }
        for index in range(1, N_STEP + 1)
    ]


def _fascicolo_payload(fascicolo: Any | None) -> dict[str, Any] | None:
    if not fascicolo:
        return None
    case_id = _safe_text(getattr(fascicolo, "id", ""))
    return {
        "id": case_id,
        "number": _safe_text(getattr(fascicolo, "numero", "")),
        "title": _safe_text(getattr(fascicolo, "titolo", ""), "Fascicolo senza titolo"),
        "client": _safe_text(getattr(fascicolo, "nome_cliente", ""), "Cliente da completare"),
        "opponent": _safe_text(getattr(fascicolo, "controparte", ""), "Controparte da completare"),
        "matter": _safe_text(getattr(fascicolo, "area_pratica", "") or getattr(fascicolo, "tipo_procedimento", "")),
        "court": _safe_text(getattr(fascicolo, "tribunale", ""), "Ufficio da definire"),
        "rg": _safe_text(getattr(fascicolo, "rg_completo", "") or getattr(fascicolo, "numero_rg", "")),
        "judge": _safe_text(getattr(fascicolo, "giudice", ""), "Da completare"),
        "section": _safe_text(getattr(fascicolo, "sezione", ""), "Da completare"),
        "status": _safe_text(getattr(getattr(fascicolo, "stato", ""), "value", "")),
        "statusLabel": _safe_text(getattr(getattr(fascicolo, "stato", ""), "label", "")),
        "nextHearing": _safe_text(getattr(fascicolo, "data_prossima_udienza", "")),
        "nextHearingLabel": _label_date(getattr(fascicolo, "data_prossima_udienza", "")),
        "documentsCount": int(getattr(fascicolo, "documenti_count", 0) or len(getattr(fascicolo, "documenti", []) or [])),
        "href": f"/fascicoli/{case_id}",
        "documentsHref": f"/fascicoli/{case_id}",
        "timesheetHref": f"/timesheet?id_fascicolo={case_id}",
        "deadlineHref": f"/scadenziario?fascicolo={case_id}",
    }


def _appointment_payload(appuntamento: Any | None) -> dict[str, Any] | None:
    if not appuntamento:
        return None
    appointment_id = _safe_text(getattr(appuntamento, "id", ""))
    raw_date = _safe_text(getattr(appuntamento, "data_ora", ""))
    return {
        "id": appointment_id,
        "title": _safe_text(getattr(appuntamento, "titolo", ""), "Udienza"),
        "date": raw_date,
        "dateLabel": _label_date(raw_date),
        "place": _safe_text(getattr(appuntamento, "luogo", "")),
        "notes": _safe_text(getattr(appuntamento, "note", "")),
        "href": f"/agenda/{appointment_id}" if appointment_id else "/agenda",
    }


def _document_payload(documento: Any, index: int, case_id: str) -> dict[str, Any]:
    status = _safe_text(getattr(documento, "stato", ""), "da_portare")
    doc_id = _safe_text(getattr(documento, "id_documento", ""))
    return {
        "index": index,
        "idDocument": doc_id,
        "label": _safe_text(getattr(documento, "label", ""), "Documento"),
        "type": _safe_text(getattr(documento, "tipo", "")),
        "mandatory": bool(getattr(documento, "obbligatorio", False)),
        "status": status,
        "statusLabel": DOCUMENT_STATUS_LABELS.get(status, status),
        "statusTone": DOCUMENT_STATUS_TONES.get(status, "neutral"),
        "notes": _safe_text(getattr(documento, "note", "")),
        "fileName": _safe_text(getattr(documento, "nome_file", "")),
        "signed": document_has_real_digital_signature(documento),
        "href": f"/fascicoli/{case_id}/documenti/{doc_id}/scarica" if case_id and doc_id else "",
    }


def _deadline_payload(scadenza: Any) -> dict[str, Any]:
    deadline_id = _safe_text(getattr(scadenza, "id", ""))
    return {
        "id": deadline_id,
        "title": _safe_text(getattr(scadenza, "titolo", ""), "Scadenza"),
        "date": _safe_text(getattr(scadenza, "data_scadenza", "")),
        "dateLabel": _label_date(getattr(scadenza, "data_scadenza", "")),
        "priority": _safe_text(getattr(getattr(scadenza, "priorita", ""), "value", "")),
        "completed": bool(getattr(scadenza, "completata", False)),
        "href": f"/scadenziario/{deadline_id}" if deadline_id else "/scadenziario",
    }


def _activity_payload(activity: Any) -> dict[str, Any]:
    return {
        "title": _safe_text(getattr(activity, "titolo", ""), "Attivita"),
        "date": _safe_text(getattr(activity, "data", "")),
        "dateLabel": _label_date(getattr(activity, "data", "")),
        "description": _safe_text(getattr(activity, "descrizione", "")),
        "notes": _safe_text(getattr(activity, "note", "")),
    }


def _case_related_payload(fascicolo: Any | None) -> dict[str, Any]:
    if not fascicolo:
        return {"parts": [], "deadlines": [], "activities": [], "documents": []}
    case_id = _safe_text(getattr(fascicolo, "id", ""))
    try:
        parts = [
            {
                "role": _safe_text(getattr(getattr(parte, "ruolo", ""), "label", "")),
                "name": _safe_text(getattr(soggetto, "nome_completo", ""), "Soggetto"),
            }
            for parte, soggetto in get_soggetti().parti_fascicolo(case_id)
        ]
    except Exception:
        parts = []
    try:
        deadlines = [
            _deadline_payload(scadenza)
            for scadenza in get_scadenziario().tutte(solo_aperte=False)
            if _safe_text(getattr(scadenza, "id_fascicolo", "")) == case_id
        ]
    except Exception:
        deadlines = []
    activities = [_activity_payload(item) for item in list(getattr(fascicolo, "attivita", []) or [])[-8:]]
    documents = [
        {
            "id": _safe_text(getattr(doc, "id", "")),
            "name": _safe_text(getattr(doc, "nome", ""), "Documento"),
            "type": _safe_text(getattr(getattr(doc, "tipo", ""), "value", "") or getattr(doc, "tipo", "")),
            "signed": document_has_real_digital_signature(doc),
            "href": f"/fascicoli/{case_id}/documenti/{getattr(doc, 'id', '')}/scarica" if _safe_text(getattr(doc, "id", "")) else "",
        }
        for doc in getattr(fascicolo, "documenti", []) or []
    ]
    return {"parts": parts, "deadlines": deadlines, "activities": activities, "documents": documents}


def _load_session_context(id_sessione: str) -> tuple[Any | None, Any | None, Any | None]:
    sessione = get_wizard_pro().carica(id_sessione)
    if not sessione:
        return None, None, None
    fascicolo = get_fascicoli().get(sessione.id_fascicolo) if sessione.id_fascicolo else None
    appuntamento = None
    if sessione.id_appuntamento:
        try:
            appuntamento = get_agenda().get(sessione.id_appuntamento)
        except Exception:
            appuntamento = None
    return sessione, fascicolo, appuntamento


def _step_notes(sessione: Any) -> dict[str, Any]:
    return {
        "step1_note": _safe_text(getattr(sessione, "step1_note", "")),
        "note_preparazione": _safe_text(getattr(sessione, "note_preparazione", "")),
        "argomenti_principali": _safe_text(getattr(sessione, "argomenti_principali", "")),
        "richieste_giudice": _safe_text(getattr(sessione, "richieste_giudice", "")),
        "eccezioni_da_sollevare": _safe_text(getattr(sessione, "eccezioni_da_sollevare", "")),
        "precheck_firma_ok": bool(getattr(sessione, "precheck_firma_ok", False)),
        "precheck_docs_pronti": bool(getattr(sessione, "precheck_docs_pronti", False)),
        "precheck_cliente_notificato": bool(getattr(sessione, "precheck_cliente_notificato", False)),
        "precheck_trasporto_ok": bool(getattr(sessione, "precheck_trasporto_ok", False)),
        "precheck_note": _safe_text(getattr(sessione, "precheck_note", "")),
        "esito": _safe_text(getattr(sessione, "esito", "")),
        "esito_rinvio_data": _safe_text(getattr(sessione, "esito_rinvio_data", "")),
        "esito_note_verbale": _safe_text(getattr(sessione, "esito_note_verbale", "")),
        "esito_azioni": _safe_text(getattr(sessione, "esito_azioni", "")),
        "esito_aggiorna_fascicolo": bool(getattr(sessione, "esito_aggiorna_fascicolo", True)),
    }


def build_react_wizard_pro_payload(selected_fascicolo_id: str = "") -> dict[str, Any]:
    dashboard = build_hearing_preparation_dashboard(selected_fascicolo_id=selected_fascicolo_id)
    cases = [_case_payload(entry) for entry in dashboard.get("cases", [])]
    selected_id = _safe_text((dashboard.get("selected_case") or {}).get("id")) if isinstance(dashboard.get("selected_case"), dict) else ""
    selected = next((item for item in cases if item["id"] == selected_id), cases[0] if cases else None)
    documents_missing = sum(int(item.get("documentsMissing") or 0) for item in cases)
    documents_ready = sum(int(item.get("documentsReady") or 0) for item in cases)
    linked_deadlines = sum(int(item.get("linkedDeadlines") or 0) for item in cases)
    return {
        "source": "repository_reali",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "contracts": _contracts(),
        "summary": {
            "totalCases": len(cases),
            "activeDrafts": int((dashboard.get("metrics") or [{}, {"value": 0}])[1].get("value", 0)) if len(dashboard.get("metrics") or []) > 1 else 0,
            "completed": int((dashboard.get("metrics") or [{}, {}, {"value": 0}])[2].get("value", 0)) if len(dashboard.get("metrics") or []) > 2 else 0,
            "upcomingHearings": int((dashboard.get("metrics") or [{}, {}, {}, {"value": 0}])[3].get("value", 0)) if len(dashboard.get("metrics") or []) > 3 else 0,
            "documentsReady": documents_ready,
            "documentsMissing": documents_missing,
            "linkedDeadlines": linked_deadlines,
        },
        "steps": list(dashboard.get("steps", [])),
        "cases": cases,
        "selectedCase": selected,
        "recentDrafts": [_recent_payload(item) for item in dashboard.get("recent_drafts", [])],
        "recentCompleted": [_recent_payload(item) for item in dashboard.get("recent_completed", [])],
        "filters": dashboard.get("filter_options", {}),
        "actions": {
            "start": "/wizard-pro/nuovo",
            "agenda": "/agenda",
            "deadlines": "/scadenziario",
            "newDeadline": "/scadenziario/nuova",
            "newAppointment": "/agenda/nuovo",
            "lex": "#lex",
        },
    }


def build_react_wizard_pro_step_payload(id_sessione: str, n: int) -> dict[str, Any] | None:
    sessione, fascicolo, appuntamento = _load_session_context(id_sessione)
    if not sessione:
        return None
    case_id = _safe_text(getattr(sessione, "id_fascicolo", ""))
    related = _case_related_payload(fascicolo)
    documents = [_document_payload(documento, index, case_id) for index, documento in enumerate(getattr(sessione, "docs_checklist", []) or [])]
    missing_documents = [documento for documento in documents if documento["status"] == "da_portare"]
    return {
        "source": "repository_reali",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "contracts": _contracts(),
        "session": _session_payload(sessione),
        "currentStep": n,
        "currentStepLabel": STEP_LABELS.get(n, f"Step {n}"),
        "steps": _steps_payload(sessione, n),
        "case": _fascicolo_payload(fascicolo),
        "appointment": _appointment_payload(appuntamento),
        "parts": related["parts"],
        "deadlines": related["deadlines"],
        "activities": related["activities"],
        "caseDocuments": related["documents"],
        "documents": documents,
        "missingDocuments": missing_documents,
        "fields": _step_notes(sessione),
        "precheck": {
            "completed": bool(getattr(sessione, "precheck_completato", False)),
            "done": int(getattr(sessione, "precheck_n_ok", 0) or 0),
            "total": 4,
        },
        "esiti": [{"value": value, "label": label} for value, label in ESITI],
        "actions": {
            "form": f"/wizard-pro/{id_sessione}/step/{n}",
            "next": f"/wizard-pro/{id_sessione}/step/{min(n + 1, N_STEP)}",
            "complete": f"/wizard-pro/{id_sessione}/completo",
            "folder": f"/fascicoli/{case_id}" if case_id else "/fascicoli",
            "agenda": _safe_text((_appointment_payload(appuntamento) or {}).get("href"), "/agenda"),
            "deadlines": f"/scadenziario?fascicolo={case_id}" if case_id else "/scadenziario",
            "signature": "/guida/firma-digitale",
            "timesheet": f"/timesheet?id_fascicolo={case_id}" if case_id else "/timesheet",
            "lex": "#lex",
        },
        "emptyStates": {
            "noDocuments": not documents,
            "noMissingDocuments": not missing_documents,
            "noActivities": not related["activities"],
            "noDeadlines": not related["deadlines"],
        },
    }


def build_react_wizard_pro_complete_payload(id_sessione: str) -> dict[str, Any] | None:
    sessione, fascicolo, appuntamento = _load_session_context(id_sessione)
    if not sessione:
        return None
    case_id = _safe_text(getattr(sessione, "id_fascicolo", ""))
    related = _case_related_payload(fascicolo)
    documents = [_document_payload(documento, index, case_id) for index, documento in enumerate(getattr(sessione, "docs_checklist", []) or [])]
    return {
        "source": "repository_reali",
        "generatedAt": datetime.now().isoformat(timespec="seconds"),
        "contracts": _contracts(),
        "session": _session_payload(sessione),
        "steps": _steps_payload(sessione, N_STEP),
        "case": _fascicolo_payload(fascicolo),
        "appointment": _appointment_payload(appuntamento),
        "parts": related["parts"],
        "deadlines": related["deadlines"],
        "activities": related["activities"],
        "documents": documents,
        "fields": _step_notes(sessione),
        "outcome": {
            "value": _safe_text(getattr(sessione, "esito", "")),
            "label": _safe_text(getattr(sessione, "label_esito", "")),
            "tone": _safe_text(getattr(sessione, "colore_esito", ""), "neutral"),
            "postponementDate": _safe_text(getattr(sessione, "esito_rinvio_data", "")),
            "postponementDateLabel": _label_date(getattr(sessione, "esito_rinvio_data", "")),
            "hearingNotes": _safe_text(getattr(sessione, "esito_note_verbale", "")),
            "nextActions": _safe_text(getattr(sessione, "esito_azioni", "")),
            "matterUpdated": bool(getattr(sessione, "esito_aggiorna_fascicolo", False)),
        },
        "actions": {
            "folder": f"/fascicoli/{case_id}" if case_id else "/fascicoli",
            "agenda": _safe_text((_appointment_payload(appuntamento) or {}).get("href"), "/agenda"),
            "deadlines": f"/scadenziario?fascicolo={case_id}" if case_id else "/scadenziario",
            "newDeadline": "/scadenziario/nuova",
            "timesheet": f"/timesheet?id_fascicolo={case_id}" if case_id else "/timesheet",
            "archive": f"/wizard-pro/{id_sessione}/archivia",
            "delete": f"/wizard-pro/{id_sessione}/elimina",
            "lex": "#lex",
        },
    }
