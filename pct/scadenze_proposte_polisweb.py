"""Proposte di scadenza in BOZZA dagli eventi letti nei registri di cancelleria.

Gemello di ``pct/scadenze_proposte_pec.py`` per la fonte "registro PST".
Base normativa: consultazione dei registri (D.M. 44/2011). Fail-closed: gli
eventi con data futura letti dal registro non diventano termini legali ma
proposte in stato BOZZA da confermare; la fonte primaria dei termini resta
la comunicazione/notificazione ricevuta via PEC (art. 136 c.p.c.). Le
proposte da registro sono deduplicate contro quelle gia' create dalla PEC:
se PEC e registro indicano stessa data sullo stesso fascicolo, non si crea
un doppione.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable

MARCATORE_BOZZA = "PROPOSTA_EVENTO_PST"


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split()).strip()[:limit]


def bozza_marker(fascicolo_id: str, ufficio: str, rg: str, chiave_evento: str) -> str:
    token = f"{ufficio}:{rg}:{chiave_evento}".strip(":")
    return f"POLISWEB:{fascicolo_id} {MARCATORE_BOZZA}:{token}"[:220]


def select_event_candidates(
    eventi: Iterable[Any],
    *,
    today: date,
    date_gia_presenti: set[str] | None = None,
) -> list[Any]:
    """Solo eventi con data futura, esclusi quelli gia' coperti da altra fonte."""

    escluse = set(date_gia_presenti or set())
    scelti: list[Any] = []
    for evento in eventi or []:
        data = str(getattr(evento, "data", "") or "")
        if not data or data in escluse:
            continue
        try:
            if date.fromisoformat(data) < today:
                continue
        except ValueError:
            continue
        # solo udienze e scadenze prospettiche diventano proposte operative
        if getattr(evento, "tipo", "") not in {"udienza", "scadenza"}:
            continue
        scelti.append(evento)
    return scelti


def bozza_scadenza_fields(
    evento: Any,
    *,
    fascicolo_id: str,
    ufficio: str,
    rg: str,
) -> dict[str, Any]:
    """Campi per ``GestioneScadenziario.nuova`` di una proposta da registro."""

    tipo = getattr(evento, "tipo", "scadenza")
    data = str(getattr(evento, "data", "") or "")
    descrizione = _clean(getattr(evento, "descrizione", ""), 400) or (
        "Udienza" if tipo == "udienza" else "Scadenza processuale"
    )
    etichetta = "Udienza da registro" if tipo == "udienza" else "Scadenza da registro"
    giudice = _clean(getattr(evento, "giudice", ""), 120)
    fonte = f"Registro di cancelleria (PST) - ufficio {ufficio}".strip()
    return {
        "titolo": f"Verifica {etichetta.lower()} {_date_it(data)}: {descrizione}"[:180],
        "data_scadenza": data,
        "descrizione": (
            "Proposta automatica: evento letto nel registro di cancelleria (PST). "
            "Confermare o scartare dopo verifica; il registro non attesta un termine legale."
        ),
        "note": "\n".join(
            part
            for part in (
                bozza_marker(fascicolo_id, ufficio, rg, evento.chiave()),
                f"Fonte: {fonte}",
                f"Giudice: {giudice}" if giudice else "",
                "Proposta in bozza: revisione professionale obbligatoria, nessun termine legale attestato.",
            )
            if part
        ),
        "id_fascicolo": fascicolo_id or "",
        "source_event_type": "polisweb_registro",
        "source_event_at": data,
        "deadline_profile_code": "PST_PROPOSTA_EVENTO",
        "source_snippet": descrizione,
        "source_snippet_label": etichetta,
        "source_document_name": fonte,
        "source_message_id": "",
        "source_confidence": 0.0,
    }


def _date_it(iso_day: str) -> str:
    try:
        return date.fromisoformat(iso_day).strftime("%d/%m/%Y")
    except ValueError:
        return iso_day
