"""Proposte di scadenza in bozza dalle date lette nei provvedimenti PEC.

Base normativa e principio: le comunicazioni e notificazioni telematiche di
cancelleria (D.M. 44/2011, artt. 16 ss.; art. 136 c.p.c.) sono la fonte
primaria dei termini processuali dello studio. La pipeline PEC estrae gia'
le date con il passaggio testuale di provenienza (``procedural_dates``);
questo modulo trasforma in *proposte di scadenza in stato BOZZA* le date
future che la matrice PEC non promuove ad auto-creazione (contesto non
classificato con certezza come termine o udienza), cosi' che nessuna data
letta vada perduta. Fail-closed: la bozza non e' un termine legale, non
alimenta agenda, notifiche o conteggi operativi finche' l'avvocato non la
conferma espressamente (revisione professionale obbligatoria).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Iterable

MAX_PROPOSTE_PER_MESSAGGIO = 5
MARCATORE_BOZZA = "PROPOSTA_DATA_PEC"


def _clean(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    return text[:limit].strip()


def select_draft_candidates(
    procedural_dates: Iterable[Any],
    *,
    today: date,
    classify: Callable[[dict[str, Any]], str],
    exclude_dates: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Date future lette dalla PEC ma non promosse ad auto-creazione.

    Sono i candidati con contesto non classificato (``classify`` restituisce
    stringa vuota): la matrice PEC li ignora e oggi la data andrebbe persa.
    Una sola proposta per giorno, ordinate dalla piu' vicina, con tetto
    prudenziale per messaggio.
    """

    excluded = set(exclude_dates or set())
    best_by_date: dict[str, dict[str, Any]] = {}
    for item in procedural_dates or []:
        if not isinstance(item, dict):
            continue
        raw_day = str(item.get("date") or "")
        try:
            day = date.fromisoformat(raw_day)
        except ValueError:
            continue
        if day < today or raw_day in excluded:
            continue
        if classify(item):
            continue  # promossa dalla matrice: non e' una proposta
        current = best_by_date.get(raw_day)
        if current is None or float(item.get("confidence") or 0.0) > float(current.get("confidence") or 0.0):
            best_by_date[raw_day] = item
    ordered = [best_by_date[key] for key in sorted(best_by_date)]
    return ordered[:MAX_PROPOSTE_PER_MESSAGGIO]


def bozza_marker(message_id: str, due_date: str) -> str:
    return f"PEC_AUDIT:{message_id} {MARCATORE_BOZZA}:{due_date}"


def bozza_scadenza_fields(
    candidate: dict[str, Any],
    *,
    subject: str,
    event_type: str,
    message_id: str,
    source_event_at: str,
    fascicolo_id: str,
) -> dict[str, Any]:
    """Campi per ``GestioneScadenziario.nuova`` di una proposta in BOZZA."""

    due_date = str(candidate.get("date") or "")
    label = _clean(candidate.get("label") or "Data letta", 80)
    source = _clean(candidate.get("source") or "allegato PEC", 160)
    context = _clean(candidate.get("context") or "", 520)
    subject_clean = _clean(subject, 90)
    return {
        "titolo": f"Verifica data {_date_it(due_date)} letta nella PEC: {subject_clean}"[:180],
        "data_scadenza": due_date,
        "descrizione": (
            "Proposta automatica: data futura letta nel provvedimento ricevuto via PEC, "
            "con contesto non qualificato come termine o udienza certi. "
            "Confermare o scartare dopo lettura del passaggio citato."
        ),
        "note": "\n".join(
            part
            for part in (
                bozza_marker(message_id, due_date),
                f"Tipo evento: {event_type or '-'}",
                f"Decorrenza letta: {source_event_at or '-'}",
                "Proposta in bozza: revisione professionale obbligatoria, nessun termine legale attestato.",
            )
            if part
        ),
        "id_fascicolo": fascicolo_id or "",
        "source_event_type": event_type or "",
        "source_event_at": source_event_at or "",
        "deadline_profile_code": "PEC_PROPOSTA_DATA",
        "source_snippet": context,
        "source_snippet_label": label,
        "source_document_name": source,
        "source_message_id": message_id,
        "source_confidence": float(candidate.get("confidence") or 0.0),
    }


def _date_it(iso_day: str) -> str:
    try:
        parsed = date.fromisoformat(iso_day)
    except ValueError:
        return iso_day
    return parsed.strftime("%d/%m/%Y")
