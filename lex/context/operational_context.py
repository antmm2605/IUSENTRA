"""Contesti operativi strutturati per Lex."""

from __future__ import annotations

from typing import Any, Callable

from flask import current_app, g

from pct.responsabile_conformita import build_fascicolo_compliance_summary
from pct.workspace_intelligente import WorkspaceIntelligenteService
from web.helpers import (
    get_agenda,
    get_calendar_sync,
    get_clienti,
    get_fascicoli,
    get_fatturazione,
    get_giurisprudenza,
    get_preventivi,
    get_scadenziario,
    get_soggetti,
)


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "").strip()


def _float_value(value: Any) -> float:
    try:
        return round(float(value or 0.0), 2)
    except Exception:
        return 0.0


def _get_value(row: Any, *keys: str) -> Any:
    if isinstance(row, dict):
        for key in keys:
            if key in row:
                return row.get(key)
        return None
    for key in keys:
        if hasattr(row, key):
            return getattr(row, key)
    return None


def _safe_repo(factory: Callable[[], Any]) -> Any | None:
    try:
        return factory()
    except Exception:
        return None


def _workspace_service() -> WorkspaceIntelligenteService:
    cached = getattr(g, "_lex_workspace_service", None)
    if cached is not None:
        return cached
    service = WorkspaceIntelligenteService(
        agenda=get_agenda(),
        scadenziario=get_scadenziario(),
        fascicoli=get_fascicoli(),
        calendar_sync=_safe_repo(get_calendar_sync),
        giurisprudenza=_safe_repo(get_giurisprudenza),
        snapshot_path=str(current_app.config.get("WORKSPACE_INTELLIGENCE_DB") or "").strip(),
    )
    g._lex_workspace_service = service
    return service


def _serialize_deadline(row: Any) -> dict[str, Any]:
    return {
        "id": _clean(_get_value(row, "id")),
        "titolo": _clean(_get_value(row, "titolo", "title")),
        "data": _clean(_get_value(row, "data_scadenza", "data")),
        "tipo": _enum_value(_get_value(row, "tipo")),
        "stato": _enum_value(_get_value(row, "stato")),
        "priorita": _enum_value(_get_value(row, "priorita")),
        "descrizione": _clean(_get_value(row, "descrizione", "note")),
        "giorni_alla_scadenza": _get_value(row, "giorni_alla_scadenza"),
        "judicial_office_name": _clean(_get_value(row, "judicial_office_name")),
    }


def _serialize_appointment(row: Any) -> dict[str, Any]:
    return {
        "id": _clean(_get_value(row, "id")),
        "titolo": _clean(_get_value(row, "titolo", "title")),
        "tipo": _enum_value(_get_value(row, "tipo")),
        "stato": _enum_value(_get_value(row, "stato")),
        "data_ora": _clean(_get_value(row, "data_ora", "inizio", "quando")),
        "luogo": _clean(_get_value(row, "luogo")),
        "tribunale": _clean(_get_value(row, "tribunale")),
        "procedimento": _clean(_get_value(row, "procedimento")),
        "cliente": _clean(_get_value(row, "cliente")),
        "id_cliente": _clean(_get_value(row, "id_cliente")),
        "note": _clean(_get_value(row, "note", "descrizione")),
    }


def _serialize_hot_case(row: dict[str, Any]) -> dict[str, Any]:
    presidio = dict(row.get("presidio") or {})
    documentale = dict(presidio.get("documentale") or {})
    return {
        "id": _clean(row.get("id")),
        "numero": _clean(row.get("numero")),
        "titolo": _clean(row.get("titolo")),
        "tribunale": _clean(row.get("tribunale")),
        "stato": _clean(row.get("stato")),
        "score": int(row.get("score") or 0),
        "azioni": [str(item).strip() for item in list(row.get("azioni") or []) if str(item).strip()][:3],
        "scadenze": [_serialize_deadline(item) for item in list(row.get("scadenze") or [])[:3]],
        "scadenze_scadute": [_serialize_deadline(item) for item in list(row.get("scadenze_scadute") or [])[:2]],
        "appuntamenti": [_serialize_appointment(item) for item in list(row.get("appuntamenti") or [])[:2]],
        "giurisprudenza_count": len(list(row.get("giurisprudenza") or [])),
        "provvedimenti_count": len(list(row.get("provvedimenti") or [])),
        "presidio": {
            "summary": _clean(presidio.get("summary")),
            "progress_percent": int(presidio.get("progress_percent") or 0),
            "tone": _clean(presidio.get("tone")),
            "documenti_portale_mancanti": int(documentale.get("documenti_portale_mancanti") or 0),
            "ha_provvedimento_finale": bool(documentale.get("ha_provvedimento_finale")),
        },
    }


def _serialize_giurisprudenza(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _clean(row.get("id")),
        "titolo": _clean(row.get("titolo")),
        "data_deposito": _clean(row.get("data_deposito")),
        "massima": _clean(row.get("massima")),
        "area": _clean(row.get("area")),
        "source_system": _clean(row.get("source_system")),
    }


def _serialize_documentale(documentale: dict[str, Any]) -> dict[str, Any]:
    return {
        "documenti_totali": int(documentale.get("documenti_totali") or 0),
        "documenti_portale": int(documentale.get("documenti_portale") or 0),
        "documenti_portale_allineati": int(documentale.get("documenti_portale_allineati") or 0),
        "documenti_portale_mancanti": int(documentale.get("documenti_portale_mancanti") or 0),
        "metadati_mancanti": [
            _clean(getattr(doc, "nome_portale", "") or getattr(doc, "nome", ""))
            for doc in list(documentale.get("metadati_mancanti") or [])[:5]
            if _clean(getattr(doc, "nome_portale", "") or getattr(doc, "nome", ""))
        ],
        "provvedimenti": [dict(item) for item in list(documentale.get("provvedimenti") or [])[:5]],
        "ha_provvedimento_finale": bool(documentale.get("ha_provvedimento_finale")),
    }


def _serialize_preventivo(row: Any) -> dict[str, Any]:
    return {
        "id": _clean(getattr(row, "id", "")),
        "numero": _clean(getattr(row, "numero", "")),
        "oggetto": _clean(getattr(row, "oggetto", "")),
        "stato": _enum_value(getattr(row, "stato", "")),
        "workflow_channel": _clean(getattr(row, "workflow_channel", "")),
        "tipo_compenso": _clean(getattr(row, "tipo_compenso", "")),
        "area_pratica": _clean(getattr(row, "area_pratica", "")),
        "id_pratica": _clean(getattr(row, "id_pratica", "")),
        "data_emissione": _clean(getattr(row, "data_emissione", "")),
        "data_scadenza": _clean(getattr(row, "data_scadenza", "")),
        "totale": _float_value(getattr(row, "totale", 0.0)),
        "campi_mancanti": list(getattr(row, "campi_mancanti", []) or []),
    }


def _serialize_conferimento(row: Any) -> dict[str, Any]:
    return {
        "id": _clean(getattr(row, "id", "")),
        "numero": _clean(getattr(row, "numero", "")),
        "oggetto": _clean(getattr(row, "oggetto", "")),
        "stato": _enum_value(getattr(row, "stato", "")),
        "workflow_channel": _clean(getattr(row, "workflow_channel", "")),
        "tipo_compenso": _clean(getattr(row, "tipo_compenso", "")),
        "area_pratica": _clean(getattr(row, "area_pratica", "")),
        "id_pratica": _clean(getattr(row, "id_pratica", "")),
        "data_incarico": _clean(getattr(row, "data_incarico", "")),
        "compenso_pattuito": _float_value(
            getattr(row, "compenso_pattuito", getattr(row, "onorario_pattuito", 0.0))
        ),
    }


def _serialize_parcella(row: Any) -> dict[str, Any]:
    return {
        "id": _clean(getattr(row, "id", "")),
        "numero": _clean(getattr(row, "numero", "")),
        "stato": _enum_value(getattr(row, "stato", "")),
        "data_emissione": _clean(getattr(row, "data_emissione", "")),
        "data_scadenza": _clean(getattr(row, "data_scadenza", "")),
        "data_pagamento": _clean(getattr(row, "data_pagamento", "")),
        "origine": _clean(getattr(row, "origine", "")),
        "totale": _float_value(getattr(row, "totale", 0.0)),
        "netto_a_pagare": _float_value(getattr(row, "netto_a_pagare", getattr(row, "totale", 0.0))),
    }


def _fascicolo_appointment_rows(fascicolo: Any) -> list[Any]:
    candidates = {
        _clean(getattr(fascicolo, "id", "")).lower(),
        _clean(getattr(fascicolo, "id_cliente", "")).lower(),
        _clean(getattr(fascicolo, "numero", "")).lower(),
        _clean(getattr(fascicolo, "numero_rg", "")).lower(),
        _clean(getattr(fascicolo, "rg_completo", "")).lower(),
    }
    candidates.discard("")
    if not candidates:
        return []
    rows = []
    for item in get_agenda().tutti():
        if _clean(getattr(item, "id_cliente", "")).lower() in candidates:
            rows.append(item)
            continue
        procedimento = _clean(getattr(item, "procedimento", "")).lower()
        if procedimento and procedimento in candidates:
            rows.append(item)
    return rows


def _all_fascicoli() -> list[Any]:
    gestore = get_fascicoli()
    try:
        return list(gestore.tutti(archiviati=True))
    except TypeError:
        return list(gestore.tutti())


def _status_count(rows: list[Any], *states: str) -> int:
    wanted = {state.upper() for state in states}
    return sum(1 for row in rows if _enum_value(getattr(row, "stato", "")).upper() in wanted)


def load_studio_operational_context(*, question: str = "", horizon_days: int = 14) -> dict[str, Any]:
    service = _workspace_service()
    overview = service.panoramica(horizon_days=horizon_days, hot_limit=8)
    clienti = list(get_clienti().tutti())
    gestore_soggetti = _safe_repo(get_soggetti)
    soggetti = list(gestore_soggetti.tutti()) if gestore_soggetti is not None else []
    fascicoli = _all_fascicoli()
    gestore_preventivi = get_preventivi()
    preventivi = list(gestore_preventivi.tutti_preventivi())
    conferimenti = list(gestore_preventivi.tutti_conferimenti())
    gestore_fatturazione = _safe_repo(get_fatturazione)
    parcelle = list(gestore_fatturazione.tutte()) if gestore_fatturazione is not None else []

    fatturato = round(
        sum(
            _float_value(getattr(item, "totale", 0.0))
            for item in parcelle
            if _enum_value(getattr(item, "stato", "")).upper() not in {"BOZZA", "ANNULLATA"}
        ),
        2,
    )
    incassato = round(
        sum(_float_value(getattr(item, "totale", 0.0)) for item in parcelle if _enum_value(getattr(item, "stato", "")).upper() == "PAGATA"),
        2,
    )
    return {
        "question": _clean(question),
        "generated_at": _clean(overview.get("generated_at")),
        "summary": dict(overview.get("summary") or {}),
        "actions": [dict(item) for item in list(overview.get("actions") or [])[:6]],
        "urgent_deadlines": [_serialize_deadline(item) for item in list(overview.get("urgent_deadlines") or [])[:6]],
        "upcoming_deadlines": [_serialize_deadline(item) for item in list(overview.get("upcoming_deadlines") or [])[:8]],
        "upcoming_appointments": [_serialize_appointment(item) for item in list(overview.get("upcoming_appointments") or [])[:8]],
        "fascicoli_hot": [_serialize_hot_case(item) for item in list(overview.get("fascicoli_hot") or [])[:8]],
        "sync_profiles": [dict(item) for item in list(overview.get("sync_profiles") or [])[:6]],
        "domains": {
            "clienti": {"total": len(clienti)},
            "soggetti": {"total": len(soggetti)},
            "fascicoli": {
                "total": len(fascicoli),
                "aperti": _status_count(fascicoli, "APERTO", "IN_CORSO"),
                "definiti": _status_count(fascicoli, "DEFINITO"),
                "archiviati": _status_count(fascicoli, "ARCHIVIATO"),
            },
            "preventivi": {
                "total": len(preventivi),
                "in_lavorazione": _status_count(preventivi, "BOZZA", "IN_CALCOLO", "GENERATO", "VERIFICATO", "INVIATO", "APERTO"),
                "accettati": _status_count(preventivi, "ACCETTATO"),
                "scaduti": _status_count(preventivi, "SCADUTO"),
            },
            "conferimenti": {
                "total": len(conferimenti),
                "attivi": _status_count(conferimenti, "ATTIVO"),
                "definiti": _status_count(conferimenti, "DEFINITO"),
                "revocati": _status_count(conferimenti, "REVOCATO"),
            },
            "parcelle": {
                "total": len(parcelle),
                "emesse": _status_count(parcelle, "EMESSA"),
                "pagate": _status_count(parcelle, "PAGATA"),
                "scadute": _status_count(parcelle, "SCADUTA"),
                "totale_emesso": fatturato,
                "totale_incassato": incassato,
                "saldo_aperto": round(max(fatturato - incassato, 0.0), 2),
            },
        },
    }


def load_fascicolo_intelligence_context(*, pratica_id: str = "", fascicolo_id: str = "") -> dict[str, Any]:
    target_id = _clean(pratica_id) or _clean(fascicolo_id)
    if not target_id:
        return {}
    fascicolo = get_fascicoli().get(target_id)
    if not fascicolo:
        return {}
    scadenze = list(get_scadenziario().tutte(id_fascicolo=fascicolo.id, solo_aperte=True))
    appuntamenti = _fascicolo_appointment_rows(fascicolo)
    quadro = _workspace_service().per_fascicolo(fascicolo, apps=appuntamenti, scadenze=scadenze)
    presidio = dict(quadro.get("presidio") or {})
    presidio["scadenze_future"] = [_serialize_deadline(item) for item in list(presidio.get("scadenze_future") or [])[:4]]
    presidio["scadenze_scadute"] = [_serialize_deadline(item) for item in list(presidio.get("scadenze_scadute") or [])[:4]]
    presidio["documentale"] = _serialize_documentale(dict(presidio.get("documentale") or {}))
    return {
        "has_items": bool(quadro.get("has_items")),
        "area_hint": _clean(quadro.get("area_hint")),
        "keywords": list(quadro.get("keywords") or []),
        "next_actions": [str(item).strip() for item in list(quadro.get("next_actions") or []) if str(item).strip()][:4],
        "scadenze": [_serialize_deadline(item) for item in list(quadro.get("scadenze") or [])[:4]],
        "scadenze_scadute": [_serialize_deadline(item) for item in list(quadro.get("scadenze_scadute") or [])[:4]],
        "appuntamenti": [_serialize_appointment(item) for item in list(quadro.get("appuntamenti") or [])[:4]],
        "giurisprudenza": [_serialize_giurisprudenza(item) for item in list(quadro.get("giurisprudenza") or [])[:5]],
        "provvedimenti": [dict(item) for item in list(quadro.get("provvedimenti") or [])[:5]],
        "presidio": presidio,
        "office_sources": list(quadro.get("office_sources") or []),
    }


def load_fascicolo_compliance_context(*, pratica_id: str = "", fascicolo_id: str = "") -> dict[str, Any]:
    target_id = _clean(pratica_id) or _clean(fascicolo_id)
    if not target_id:
        return {}
    fascicolo = get_fascicoli().get(target_id)
    if not fascicolo:
        return {}
    if not bool(getattr(fascicolo, "compliance_controls_enabled", True)):
        return {
            "available": True,
            "controls_enabled": False,
            "overall_state": "disabled",
            "readiness_label": "Controlli automatici disattivati per il fascicolo.",
            "summary": "La verifica di conformita' e' stata sospesa manualmente su questa pratica.",
            "general": {"state": "disabled", "label": "Disattivati", "score": 0, "blocking_count": 0, "warning_count": 0},
            "sections": {},
            "blocking_issues": [],
            "warning_issues": [],
            "missing_documents": [],
            "next_steps": ["Riattiva i controlli automatici per rigenerare il report di conformita'."],
            "action_gates": {},
            "sources": [],
        }

    cliente = get_clienti().get(getattr(fascicolo, "id_cliente", "") or "") if getattr(fascicolo, "id_cliente", "") else None
    gestore_preventivi = get_preventivi()
    preventivi = list(gestore_preventivi.preventivi_per_fascicolo(fascicolo.id))
    conferimenti = list(gestore_preventivi.conferimenti_per_fascicolo(fascicolo.id))
    gestore_soggetti = _safe_repo(get_soggetti)
    parti = list(gestore_soggetti.parti_fascicolo(fascicolo.id)) if gestore_soggetti is not None else []
    summary = build_fascicolo_compliance_summary(
        fascicolo=fascicolo,
        cliente=cliente,
        preventivo=preventivi[0] if preventivi else None,
        conferimento=conferimenti[0] if conferimenti else None,
        config=current_app.config,
        utente=getattr(g, "utente_corrente", None),
        office_cache_path=str(current_app.config.get("UFFICI_GIUDIZIARI_DB") or "").strip(),
        parti=parti,
    )
    payload = dict(summary or {})
    payload.pop("resolver", None)
    payload["controls_enabled"] = True
    return payload


def load_economic_context(
    *,
    question: str = "",
    pratica_id: str = "",
    fascicolo_id: str = "",
) -> dict[str, Any]:
    gestore_preventivi = get_preventivi()
    gestore_fatturazione = _safe_repo(get_fatturazione)
    target_id = _clean(pratica_id) or _clean(fascicolo_id)
    fascicolo = get_fascicoli().get(target_id) if target_id else None

    if fascicolo is not None:
        preventivi = list(gestore_preventivi.preventivi_per_fascicolo(fascicolo.id))
        conferimenti = list(gestore_preventivi.conferimenti_per_fascicolo(fascicolo.id))
        parcelle = list(gestore_fatturazione.per_fascicolo(fascicolo.id)) if gestore_fatturazione else []
        scope = "fascicolo"
    else:
        preventivi = list(gestore_preventivi.tutti_preventivi())
        conferimenti = list(gestore_preventivi.tutti_conferimenti())
        parcelle = list(gestore_fatturazione.tutte()) if gestore_fatturazione else []
        scope = "studio"

    totale_preventivi = round(sum(_float_value(getattr(item, "totale", 0.0)) for item in preventivi), 2)
    totale_conferimenti = round(
        sum(
            _float_value(getattr(item, "compenso_pattuito", getattr(item, "onorario_pattuito", 0.0)))
            for item in conferimenti
        ),
        2,
    )
    totale_fatturato = round(
        sum(
            _float_value(getattr(item, "totale", 0.0))
            for item in parcelle
            if _enum_value(getattr(item, "stato", "")).upper() not in {"BOZZA", "ANNULLATA"}
        ),
        2,
    )
    totale_incassato = round(
        sum(_float_value(getattr(item, "totale", 0.0)) for item in parcelle if _enum_value(getattr(item, "stato", "")).upper() == "PAGATA"),
        2,
    )
    search_key = _clean(question) or _clean(getattr(fascicolo, "oggetto", "")) or _clean(getattr(fascicolo, "titolo", ""))
    best_runtime = dict(gestore_preventivi.select_best_preventivi_runtime(search_key, limit=3) or {}) if search_key else {}
    best_practice = dict(gestore_preventivi.select_best_pratiche_preventivo(search_key, limit=3) or {}) if search_key else {}
    return {
        "scope": scope,
        "question": _clean(question),
        "fascicolo": {
            "id": _clean(getattr(fascicolo, "id", "")),
            "numero": _clean(getattr(fascicolo, "numero", "")),
            "titolo": _clean(getattr(fascicolo, "titolo", "")),
            "cliente": _clean(getattr(fascicolo, "nome_cliente", "")),
        }
        if fascicolo is not None
        else {},
        "summary": {
            "preventivi_count": len(preventivi),
            "conferimenti_count": len(conferimenti),
            "parcelle_count": len(parcelle),
            "preventivi_attivi": _status_count(preventivi, "BOZZA", "IN_CALCOLO", "GENERATO", "VERIFICATO", "INVIATO", "APERTO"),
            "conferimenti_attivi": _status_count(conferimenti, "ATTIVO"),
            "parcelle_emesse": _status_count(parcelle, "EMESSA"),
            "parcelle_pagate": _status_count(parcelle, "PAGATA"),
            "parcelle_scadute": _status_count(parcelle, "SCADUTA"),
            "totale_preventivato": totale_preventivi,
            "totale_conferito": totale_conferimenti,
            "totale_fatturato": totale_fatturato,
            "totale_incassato": totale_incassato,
            "saldo_aperto": round(max(totale_fatturato - totale_incassato, 0.0), 2),
        },
        "preventivi": [_serialize_preventivo(item) for item in preventivi[:6]],
        "conferimenti": [_serialize_conferimento(item) for item in conferimenti[:6]],
        "parcelle": [_serialize_parcella(item) for item in parcelle[:6]],
        "best_preventivo": dict(best_runtime.get("best_preventivo") or {}),
        "best_practice": dict(best_practice.get("best_practice") or {}),
    }
