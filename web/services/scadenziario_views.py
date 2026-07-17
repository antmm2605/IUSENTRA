"""Filtri di vista per lo scadenziario legale."""

from __future__ import annotations

from datetime import date
from typing import Any

from pct.scadenziario import PrioritaTermine, Scadenza, StatoTermine, TipoTermine
from pct.pec_operational_cleanup import is_legacy_pec_deadline


VISTE_SCADENZIARIO_AMMESSE = {
    "aperte",
    "critiche",
    "alte",
    "completate",
    "scadute",
    "imminenti",
    "avanzate",
    "operative",
    "pec",
    "da_presidiare",
    "tutte",
}

VISTA_LABEL_SCADENZIARIO = {
    "aperte": "scadenze aperte",
    "critiche": "scadenze critiche",
    "alte": "scadenze ad alta priorità",
    "completate": "scadenze completate",
    "scadute": "scadenze scadute",
    "imminenti": "scadenze entro 7 giorni",
    "avanzate": "scadenze con calcolo avanzato",
    "operative": "scadenze operative",
    "pec": "scadenze da PEC",
    "da_presidiare": "scadenze da presidiare",
    "tutte": "scadenze totali",
}


def is_scadenza_pec(scadenza: Scadenza) -> bool:
    return (
        str(getattr(scadenza, "deadline_profile_code", "") or "") == "PEC_AUTO_PRESIDIO"
        or "PEC_AUDIT:" in str(getattr(scadenza, "note", "") or "")
        or str(getattr(scadenza, "fonte_documento", "") or "") == "PEC_AUDIT_PIPELINE"
    )


def _deadline_days(scadenza: Scadenza) -> int | None:
    current = getattr(scadenza, "giorni_alla_scadenza", None)
    if isinstance(current, int):
        return current
    raw = str(getattr(scadenza, "data_scadenza", "") or "")[:10]
    if not raw:
        return None
    try:
        return (date.fromisoformat(raw) - date.today()).days
    except ValueError:
        return None


def _is_overdue(scadenza: Scadenza) -> bool:
    if getattr(scadenza, "stato", None) == StatoTermine.SCADUTO:
        return True
    days = _deadline_days(scadenza)
    return bool(days is not None and days < 0)


def _is_effectively_open(scadenza: Scadenza) -> bool:
    return getattr(scadenza, "stato", None) == StatoTermine.APERTO and not _is_overdue(scadenza)


def _is_currently_actionable(scadenza: Scadenza) -> bool:
    if getattr(scadenza, "stato", None) != StatoTermine.APERTO or _is_overdue(scadenza):
        return False
    days = _deadline_days(scadenza)
    return (
        getattr(scadenza, "priorita", None) == PrioritaTermine.CRITICA
        or bool(getattr(scadenza, "operational_due_at", ""))
        or bool(getattr(scadenza, "remote_hearing_detected", False))
        or bool(days is not None and 0 <= days <= 30)
    )


def normalizza_vista_scadenziario(value: str | None) -> str:
    vista = (value or "aperte").strip() or "aperte"
    return vista if vista in VISTE_SCADENZIARIO_AMMESSE else "aperte"


def label_vista_scadenziario(vista: str) -> str:
    return VISTA_LABEL_SCADENZIARIO.get(vista, "scadenze")


def scadenze_per_vista(
    gestione_scadenziario: Any,
    *,
    vista: str,
    tipo: TipoTermine | None = None,
    priorita: PrioritaTermine | None = None,
    id_fascicolo: str = "",
) -> list[Scadenza]:
    """Restituisce le scadenze della vista richiesta, mantenendo i filtri attivi."""
    gs = gestione_scadenziario
    vista = normalizza_vista_scadenziario(vista)

    def _base(solo_aperte: bool = True, stato: StatoTermine | None = None) -> list[Scadenza]:
        items = [
            item
            for item in gs.tutte(
                tipo=tipo,
                priorita=priorita,
                id_fascicolo=id_fascicolo,
                solo_aperte=False,
            )
            if not is_legacy_pec_deadline(item)
        ]
        if stato == StatoTermine.SCADUTO:
            return [item for item in items if _is_overdue(item)]
        if stato == StatoTermine.APERTO:
            return [item for item in items if _is_effectively_open(item)]
        if stato is not None:
            return [item for item in items if getattr(item, "stato", None) == stato]
        if solo_aperte:
            return [item for item in items if _is_effectively_open(item)]
        return items

    if vista == "completate":
        return _base(solo_aperte=False, stato=StatoTermine.COMPLETATO)
    if vista == "scadute":
        return _base(solo_aperte=False, stato=StatoTermine.SCADUTO)
    if vista == "critiche":
        return [s for s in _base(solo_aperte=True, stato=StatoTermine.APERTO) if s.priorita == PrioritaTermine.CRITICA]
    if vista == "alte":
        return [s for s in _base(solo_aperte=True, stato=StatoTermine.APERTO) if s.priorita == PrioritaTermine.ALTA]
    if vista == "imminenti":
        return [
            item
            for item in _base(solo_aperte=True, stato=StatoTermine.APERTO)
            if (days := _deadline_days(item)) is not None and 0 <= days <= 7
        ]
    if vista == "avanzate":
        return [s for s in _base(solo_aperte=False) if s.ha_calcolo_avanzato]
    if vista == "operative":
        return [
            s
            for s in _base(solo_aperte=True, stato=StatoTermine.APERTO)
            if bool(s.operational_due_at) and not _is_overdue(s)
        ]
    if vista == "pec":
        return [
            s
            for s in _base(solo_aperte=True, stato=StatoTermine.APERTO)
            if is_scadenza_pec(s)
        ]
    if vista == "da_presidiare":
        return [
            s
            for s in _base(solo_aperte=True, stato=StatoTermine.APERTO)
            if _is_currently_actionable(s)
        ]
    if vista == "tutte":
        return _base(solo_aperte=False)
    return _base(solo_aperte=True, stato=StatoTermine.APERTO)


def _safe_get(manager: Any, item_id: str):
    if not manager or not item_id:
        return None
    getter = getattr(manager, "get", None)
    if not callable(getter):
        return None
    try:
        return getter(item_id)
    except Exception:
        return None


def _safe_all(manager: Any) -> list[Any]:
    tutti = getattr(manager, "tutti", None)
    if not callable(tutti):
        return []
    try:
        return list(tutti())
    except Exception:
        return []


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _resolve_fascicolo_for_scadenza(sc: Scadenza, gestione_fascicoli: Any):
    fascicolo = _safe_get(gestione_fascicoli, sc.id_fascicolo)
    if fascicolo:
        return fascicolo
    haystack = " ".join(
        [
            str(sc.titolo or ""),
            str(sc.descrizione or ""),
            str(sc.note or ""),
            str(sc.source_event_type or ""),
            str(sc.source_event_at or ""),
        ]
    ).lower()
    if not haystack.strip():
        return None
    for candidate in _safe_all(gestione_fascicoli):
        rg = _first_text(getattr(candidate, "rg_completo", ""), getattr(candidate, "numero_rg", ""))
        numero = _first_text(getattr(candidate, "numero", ""))
        if rg and rg.lower() in haystack:
            return candidate
        if numero and numero.lower() in haystack:
            return candidate
    return None


def _label_fascicolo(fascicolo: Any, fallback_id: str = "") -> str:
    if not fascicolo:
        return fallback_id or ""
    rg = _first_text(getattr(fascicolo, "rg_completo", ""), getattr(fascicolo, "numero", ""))
    titolo = _first_text(getattr(fascicolo, "oggetto", ""), getattr(fascicolo, "titolo", ""))
    if rg and titolo:
        return f"{rg} - {titolo}"
    return rg or titolo or fallback_id


def _label_responsabile(sc: Scadenza, gestione_utenti: Any, fascicolo: Any = None) -> str:
    utente = _safe_get(gestione_utenti, sc.id_utente_responsabile)
    if not utente and sc.id_utente_responsabile:
        by_username = getattr(gestione_utenti, "get_by_username", None)
        if callable(by_username):
            try:
                utente = by_username(sc.id_utente_responsabile)
            except Exception:
                utente = None
    return _first_text(
        getattr(utente, "nome_completo", ""),
        getattr(utente, "username", ""),
        getattr(fascicolo, "avvocato_referente", ""),
        sc.id_utente_responsabile,
    )


def _event_context(sc: Scadenza, gestione_agenda: Any):
    appuntamento = _safe_get(gestione_agenda, sc.id_appuntamento)
    return {
        "appuntamento": appuntamento,
        "titolo": _first_text(getattr(appuntamento, "titolo", ""), sc.source_event_type_label),
        "tribunale": _first_text(getattr(appuntamento, "tribunale", "")),
        "procedimento": _first_text(getattr(appuntamento, "procedimento", "")),
        "note": _first_text(getattr(appuntamento, "note", "")),
    }


def _trace_operativo(sc: Scadenza, fascicolo: Any, event_ctx: dict[str, Any]) -> list[str]:
    trace = list(sc.trace or [])
    if trace:
        return trace
    inferred: list[str] = []
    if sc.source_event_at or sc.data_decorrenza:
        inferred.append(
            "Evento origine acquisito: "
            + _first_text(sc.source_event_at, sc.data_decorrenza)
        )
    if fascicolo:
        inferred.append("Contesto fascicolo collegato: " + _label_fascicolo(fascicolo))
    if event_ctx.get("procedimento"):
        inferred.append("Procedimento rilevato dall'evento: " + event_ctx["procedimento"])
    if sc.data_scadenza:
        inferred.append("Scadenza corrente registrata: " + sc.data_scadenza)
    return inferred


def scadenza_detail_context(
    sc: Scadenza,
    *,
    gestione_fascicoli: Any,
    gestione_utenti: Any,
    gestione_agenda: Any,
    studio_cfg: Any,
    profili_termine: dict[str, Any],
) -> dict[str, Any]:
    fascicolo = _resolve_fascicolo_for_scadenza(sc, gestione_fascicoli)
    event_ctx = _event_context(sc, gestione_agenda)
    judicial_office_label = _first_text(
        sc.judicial_office_name,
        getattr(fascicolo, "tribunale", ""),
        event_ctx.get("tribunale", ""),
    )
    descrizione = _first_text(
        sc.descrizione,
        event_ctx.get("note", ""),
        getattr(fascicolo, "oggetto", ""),
        getattr(fascicolo, "titolo", ""),
    )
    return {
        "sc": sc,
        "studio_cfg": studio_cfg,
        "profili_termine": profili_termine,
        "fascicolo_ctx": fascicolo,
        "fascicolo_label": _label_fascicolo(fascicolo, sc.id_fascicolo),
        "responsabile_label": _label_responsabile(sc, gestione_utenti, fascicolo),
        "descrizione_label": descrizione,
        "judicial_office_label": judicial_office_label,
        "event_context": event_ctx,
        "trace_operativo": _trace_operativo(sc, fascicolo, event_ctx),
    }
