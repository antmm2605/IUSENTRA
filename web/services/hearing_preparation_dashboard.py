"""Dati e metadati del cruscotto Preparazione Udienza Guidata."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pct.agenda import TipoAppuntamento
from pct.fascicoli import Fascicolo, StatoFascicolo
from pct.wizard_pro import SessioneWizardPro, STEP_LABELS
from web.helpers import (
    get_agenda,
    get_clienti,
    get_fascicoli,
    get_scadenziario,
    get_soggetti,
    get_wizard_pro,
)
from web.services.ui_localization import EMPTY_UI_VALUE, format_date, format_datetime


HEARING_PREPARATION_STEPS = [
    "Selezione Fascicolo",
    "Dati Udienza",
    "Parti e Difensori",
    "Documenti e Allegati",
    "Note Strategiche",
    "Controllo Finale",
]

HEARING_PREPARATION_NAV = [
    {"label": "Dashboard", "icon": "bi-speedometer2", "endpoint": "dashboard"},
    {"label": "Fascicoli", "icon": "bi-folder2-open", "endpoint": "lista_fascicoli"},
    {"label": "Calendario", "icon": "bi-calendar3", "endpoint": "agenda_view", "query": {"vista": "settimana"}},
    {"label": "Udienze", "icon": "bi-calendar-event", "endpoint": "agenda_view", "query": {"vista": "settimana"}},
    {"label": "Atti", "icon": "bi-card-checklist", "endpoint": "checklist_atti"},
    {"label": "Scadenze", "icon": "bi-alarm", "endpoint": "scadenziario"},
    {"label": "Documenti", "icon": "bi-file-earmark-text", "endpoint": "cerca"},
    {"label": "Preparazione Udienza", "icon": "bi-diagram-3", "endpoint": "wizard_pro.index", "active": True},
    {"label": "Impostazioni", "icon": "bi-gear", "endpoint": "impostazioni.index"},
]

_STATO_FASCICOLO_LABELS = {
    StatoFascicolo.APERTO.value: "Aperto",
    StatoFascicolo.IN_CORSO.value: "In corso",
    StatoFascicolo.SOSPESO.value: "Sospeso",
    StatoFascicolo.DEFINITO.value: "Definito",
    StatoFascicolo.ARCHIVIATO.value: "Archiviato",
}

_STATO_FASCICOLO_TONES = {
    StatoFascicolo.APERTO.value: "info",
    StatoFascicolo.IN_CORSO.value: "primary",
    StatoFascicolo.SOSPESO.value: "warning",
    StatoFascicolo.DEFINITO.value: "success",
    StatoFascicolo.ARCHIVIATO.value: "secondary",
}

_STATO_PROGRESS = {
    StatoFascicolo.APERTO.value: 22,
    StatoFascicolo.IN_CORSO.value: 58,
    StatoFascicolo.SOSPESO.value: 44,
    StatoFascicolo.DEFINITO.value: 88,
    StatoFascicolo.ARCHIVIATO.value: 100,
}


def _parse_iso_date(value: str) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _parse_iso_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _giorni_alla_data(value: str) -> int | None:
    parsed = _parse_iso_date(value)
    if not parsed:
        return None
    return (parsed - date.today()).days


def _safe_lower(value: str) -> str:
    return str(value or "").strip().lower()


def _session_status(sessione: SessioneWizardPro | None) -> dict[str, Any] | None:
    if not sessione:
        return None
    if sessione.stato == "completato":
        return {"label": "Completa", "tone": "success"}
    if sessione.percentuale_completamento <= 20 and sessione.step_corrente <= 2:
        return {"label": "Bozza", "tone": "secondary"}
    return {"label": "In preparazione", "tone": "primary"}


def _build_session_index(sessioni: list[SessioneWizardPro]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for sessione in sessioni:
        if not sessione.id_fascicolo:
            continue
        bucket = grouped.setdefault(
            sessione.id_fascicolo,
            {"attiva": None, "completata": None, "archiviate": []},
        )
        if sessione.stato == "in_corso":
            corrente = bucket["attiva"]
            if corrente is None or (sessione.modificato_il or "") > (corrente.modificato_il or ""):
                bucket["attiva"] = sessione
        elif sessione.stato == "completato":
            corrente = bucket["completata"]
            if corrente is None or (sessione.completato_il or sessione.modificato_il or "") > (
                corrente.completato_il or corrente.modificato_il or ""
            ):
                bucket["completata"] = sessione
        elif sessione.stato == "archiviato":
            bucket["archiviate"].append(sessione)
    return grouped


def _match_udienza(fascicolo: Fascicolo, appuntamenti: list[Any]) -> Any | None:
    rg = _safe_lower(fascicolo.rg_completo or fascicolo.numero_rg)
    numero = _safe_lower(fascicolo.numero)
    tribunale = _safe_lower(fascicolo.tribunale)
    titolo = _safe_lower(fascicolo.titolo)
    cliente = _safe_lower(fascicolo.nome_cliente)

    ranked: list[tuple[int, str, Any]] = []
    for appuntamento in appuntamenti:
        if getattr(appuntamento, "tipo", None) != TipoAppuntamento.UDIENZA:
            continue
        data_ora = getattr(appuntamento, "data_ora", "")
        if data_ora and data_ora[:10] < date.today().isoformat():
            continue

        score = 0
        if fascicolo.id_cliente and getattr(appuntamento, "id_cliente", "") == fascicolo.id_cliente:
            score += 4
        if rg and rg in _safe_lower(getattr(appuntamento, "procedimento", "")):
            score += 5
        if numero and numero in _safe_lower(getattr(appuntamento, "titolo", "")):
            score += 2
        if tribunale and tribunale and tribunale in _safe_lower(getattr(appuntamento, "tribunale", "")):
            score += 2
        if cliente and cliente in _safe_lower(getattr(appuntamento, "cliente", "")):
            score += 1
        if titolo and titolo in _safe_lower(getattr(appuntamento, "titolo", "")):
            score += 1
        if score:
            ranked.append((score, data_ora or "9999-12-31T23:59:59", appuntamento))

    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[0][2]


def _note_compilate(sessione: SessioneWizardPro | None) -> int:
    if not sessione:
        return 0
    fields = [
        sessione.step1_note,
        sessione.note_preparazione,
        sessione.argomenti_principali,
        sessione.richieste_giudice,
        sessione.eccezioni_da_sollevare,
        sessione.precheck_note,
        sessione.esito_note_verbale,
        sessione.esito_azioni,
    ]
    return sum(1 for value in fields if str(value or "").strip())


def _modalita_udienza(appuntamento: Any | None) -> str:
    haystack = " ".join(
        [
            str(getattr(appuntamento, "titolo", "") or ""),
            str(getattr(appuntamento, "note", "") or ""),
            str(getattr(appuntamento, "luogo", "") or ""),
        ]
    ).lower()
    if "remoto" in haystack or "teams" in haystack or "meet" in haystack:
        return "Da remoto"
    if "cartolar" in haystack:
        return "Cartolare"
    if appuntamento:
        return "In presenza"
    return "Da confermare"


def _critical_badges(
    *,
    giorni_udienza: int | None,
    documenti_mancanti: int,
    has_draft: bool,
    has_completed: bool,
    open_scadenze: int,
) -> list[dict[str, str]]:
    badges: list[dict[str, str]] = []
    if giorni_udienza == 0:
        badges.append({"label": "Udienza oggi", "tone": "danger"})
    elif giorni_udienza is not None and giorni_udienza <= 3:
        badges.append({"label": f"Tra {giorni_udienza} giorni", "tone": "warning"})
    elif giorni_udienza is not None and giorni_udienza <= 7:
        badges.append({"label": "Udienza vicina", "tone": "warning"})
    if documenti_mancanti > 0:
        badges.append({"label": "Documenti mancanti", "tone": "danger"})
    if has_draft:
        badges.append({"label": "Bozza gia presente", "tone": "info"})
    if has_completed:
        badges.append({"label": "Preparazione completata", "tone": "success"})
    if open_scadenze > 0:
        badges.append({"label": f"{open_scadenze} attivita aperte", "tone": "secondary"})
    return badges[:4]


def _build_case_entry(
    fascicolo: Fascicolo,
    *,
    cliente: Any | None,
    parti: list[tuple[Any, Any]],
    appuntamento: Any | None,
    scadenze_collegate: list[Any],
    sessioni_fascicolo: dict[str, Any],
) -> dict[str, Any]:
    attiva: SessioneWizardPro | None = sessioni_fascicolo.get("attiva")
    completata: SessioneWizardPro | None = sessioni_fascicolo.get("completata")
    stato_sessione = _session_status(attiva or completata)

    documenti_mancanti = 0
    if attiva and attiva.docs_totali:
        documenti_mancanti = max(attiva.docs_totali - attiva.docs_pronti, 0)
    elif fascicolo.documenti_count == 0:
        documenti_mancanti = 1

    prossima_udienza_raw = getattr(appuntamento, "data_ora", "") or fascicolo.data_prossima_udienza
    giorni_udienza = _giorni_alla_data(prossima_udienza_raw)
    prossima_udienza_label = format_datetime(prossima_udienza_raw) if "T" in str(prossima_udienza_raw or "") else format_date(prossima_udienza_raw)
    if prossima_udienza_label == EMPTY_UI_VALUE:
        prossima_udienza_label = "Da pianificare"

    progress_value = attiva.percentuale_completamento if attiva else _STATO_PROGRESS.get(fascicolo.stato.value, 32)
    progress_label = STEP_LABELS.get(attiva.step_corrente, "Preparazione attiva") if attiva else _STATO_FASCICOLO_LABELS.get(fascicolo.stato.value, "Pratica")

    top_parti = [
        {"ruolo": parte.ruolo.label, "nome": soggetto.nome_completo}
        for parte, soggetto in parti[:5]
    ]

    criticita = _critical_badges(
        giorni_udienza=giorni_udienza,
        documenti_mancanti=documenti_mancanti,
        has_draft=bool(attiva),
        has_completed=bool(completata),
        open_scadenze=len(scadenze_collegate),
    )

    return {
        "id": fascicolo.id,
        "numero": fascicolo.numero,
        "titolo": fascicolo.titolo,
        "cliente": fascicolo.nome_cliente or getattr(cliente, "nome_completo", "") or "Cliente da completare",
        "cliente_email": getattr(getattr(cliente, "recapiti", None), "email", "") if cliente else "",
        "cliente_pec": getattr(getattr(cliente, "recapiti", None), "pec", "") if cliente else "",
        "cliente_telefono": (
            getattr(getattr(cliente, "recapiti", None), "cellulare", "")
            or getattr(getattr(cliente, "recapiti", None), "telefono", "")
        )
        if cliente
        else "",
        "controparte": fascicolo.controparte or "Controparte da completare",
        "materia": fascicolo.area_pratica or fascicolo.tipo_procedimento or fascicolo.tipo.value.title(),
        "ufficio_giudiziario": fascicolo.tribunale or getattr(appuntamento, "tribunale", "") or "Da definire",
        "prossima_udienza_raw": prossima_udienza_raw,
        "prossima_udienza_label": prossima_udienza_label,
        "giorni_udienza": giorni_udienza,
        "stato_pratica": fascicolo.stato.value,
        "stato_pratica_label": _STATO_FASCICOLO_LABELS.get(fascicolo.stato.value, fascicolo.stato.value.title()),
        "stato_pratica_tone": _STATO_FASCICOLO_TONES.get(fascicolo.stato.value, "secondary"),
        "status_badge": stato_sessione,
        "critical_badges": criticita,
        "progress_value": progress_value,
        "progress_label": progress_label,
        "id_appuntamento": getattr(appuntamento, "id", "") if appuntamento else "",
        "rg": fascicolo.rg_completo or "Pratica interna " + fascicolo.numero,
        "giudice": fascicolo.giudice or "Da completare",
        "sezione": fascicolo.sezione or "Da completare",
        "sede": getattr(appuntamento, "luogo", "") or fascicolo.tribunale or "Da confermare",
        "data_udienza_label": prossima_udienza_label,
        "tipo_udienza": getattr(appuntamento, "titolo", "") or "Udienza di trattazione",
        "modalita_udienza": _modalita_udienza(appuntamento),
        "fase_processuale": fascicolo.tipo_procedimento or fascicolo.area_pratica or _STATO_FASCICOLO_LABELS.get(fascicolo.stato.value, fascicolo.stato.value.title()),
        "documenti_acquisiti": fascicolo.documenti_count,
        "documenti_mancanti": documenti_mancanti,
        "note_inserite": _note_compilate(attiva or completata),
        "attivita_aperte": len(scadenze_collegate) + (1 if documenti_mancanti else 0),
        "scadenze_collegate": len(scadenze_collegate),
        "sessione_attiva": attiva,
        "sessione_completata": completata,
        "parti": top_parti,
        "ha_parti": bool(top_parti),
        "ha_udienza": bool(prossima_udienza_raw),
        "udienza_imminente": giorni_udienza is not None and giorni_udienza <= 7,
    }


def build_hearing_preparation_dashboard(selected_fascicolo_id: str = "") -> dict[str, Any]:
    fascicoli_manager = get_fascicoli()
    clienti_manager = get_clienti()
    soggetti_manager = get_soggetti()
    agenda_items = get_agenda().tutti()
    scadenze_tutte = get_scadenziario().tutte(solo_aperte=False)
    wizard_manager = get_wizard_pro()

    sessioni = wizard_manager.lista()
    sessioni.sort(key=lambda item: item.modificato_il or item.creato_il or "", reverse=True)
    session_index = _build_session_index(sessioni)

    scadenze_per_fascicolo: dict[str, list[Any]] = {}
    for scadenza in scadenze_tutte:
        if not getattr(scadenza, "id_fascicolo", ""):
            continue
        scadenze_per_fascicolo.setdefault(scadenza.id_fascicolo, []).append(scadenza)

    entries: list[dict[str, Any]] = []
    for fascicolo in fascicoli_manager.tutti():
        cliente = clienti_manager.get(fascicolo.id_cliente) if fascicolo.id_cliente else None
        parti = soggetti_manager.parti_fascicolo(fascicolo.id)
        appuntamento = _match_udienza(fascicolo, agenda_items)
        scadenze_collegate = scadenze_per_fascicolo.get(fascicolo.id, [])
        entry = _build_case_entry(
            fascicolo,
            cliente=cliente,
            parti=parti,
            appuntamento=appuntamento,
            scadenze_collegate=scadenze_collegate,
            sessioni_fascicolo=session_index.get(fascicolo.id, {}),
        )
        entries.append(entry)

    entries.sort(
        key=lambda entry: (
            0 if entry["sessione_attiva"] else 1,
            0 if entry["udienza_imminente"] else 1,
            entry["giorni_udienza"] if entry["giorni_udienza"] is not None else 9999,
            entry["stato_pratica"] != StatoFascicolo.IN_CORSO.value,
            entry["numero"],
        )
    )

    selected_case = next((entry for entry in entries if entry["id"] == selected_fascicolo_id), None)
    if selected_case is None and entries:
        selected_case = entries[0]

    attive = [sessione for sessione in sessioni if sessione.stato == "in_corso"]
    completate = [sessione for sessione in sessioni if sessione.stato == "completato"]
    resume_session = attive[0] if attive else None

    recent_drafts = []
    for sessione in attive[:4]:
        fascicolo = next((entry for entry in entries if entry["id"] == sessione.id_fascicolo), None)
        recent_drafts.append(
            {
                "sessione": sessione,
                "fascicolo": fascicolo,
                "status": _session_status(sessione),
            }
        )

    recent_completed = []
    for sessione in completate[:3]:
        fascicolo = next((entry for entry in entries if entry["id"] == sessione.id_fascicolo), None)
        recent_completed.append({"sessione": sessione, "fascicolo": fascicolo})

    def _distinct(key: str) -> list[str]:
        values = {str(entry.get(key, "")).strip() for entry in entries if str(entry.get(key, "")).strip()}
        return sorted(values)

    metrics = [
        {"label": "Fascicoli pronti", "value": len(entries), "icon": "bi-briefcase"},
        {"label": "Bozze attive", "value": len(attive), "icon": "bi-pencil-square"},
        {"label": "Preparazioni complete", "value": len(completate), "icon": "bi-check2-circle"},
        {
            "label": "Udienze imminenti",
            "value": sum(1 for entry in entries if entry["udienza_imminente"]),
            "icon": "bi-alarm",
        },
    ]

    return {
        "steps": HEARING_PREPARATION_STEPS,
        "nav_items": HEARING_PREPARATION_NAV,
        "cases": entries,
        "selected_case": selected_case,
        "metrics": metrics,
        "resume_session": resume_session,
        "recent_drafts": recent_drafts,
        "recent_completed": recent_completed,
        "filter_options": {
            "materie": _distinct("materia"),
            "uffici": _distinct("ufficio_giudiziario"),
            "clienti": _distinct("cliente"),
            "stati": sorted({_STATO_FASCICOLO_LABELS.get(entry["stato_pratica"], entry["stato_pratica"]) for entry in entries}),
        },
    }
