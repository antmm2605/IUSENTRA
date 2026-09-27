"""Pagina «Coda revisioni aggiornamenti» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/aggiornamenti-legali/review` (rotta
`review_page`, modello `admin/legal_updates_review.html`): le proposte di
`list_review_queue(limit=100)` con stato, classificazione, priorità, fonte,
data, confidenza, sintesi, azione proposta, materia e note di verifica.

Le azioni di riga chiamano gli stessi metodi del motore delle rotte storiche,
con il revisore uguale all'utente collegato (`_reviewer_name()`):

- `approva` → `approve_review(id, reviewer, notes=review_notes)`;
- `modifica-approva` → `edit_and_approve_review(id, reviewer, review_notes,
  summary_short, what_changes)`;
- `rifiuta` → `reject_review(id, reviewer, notes=review_notes)`;
- `pubblica` → `publish_review(id, reviewer)`;
- `autopublish` → `execute_action("autopublish")` («Pubblica idonei»).
"""

from __future__ import annotations

from typing import Any

from flask import current_app

from web.services.react_piattaforma_aggiornamenti_comune import (
    INDIRIZZI,
    TONI_STATO_REVISIONE,
    azione_motore,
    collegamenti,
    confidenza,
    data,
    esegui_motore,
    etichetta_azione,
    etichetta_classificazione,
    etichetta_stato,
    identificativo,
    motore,
    revisore,
    unisci,
)
from web.services.react_piattaforma_sezioni import _t, actions, azione, campo, esito, link, notes, table


def costruisci() -> dict[str, Any]:
    """La coda della rotta storica `review_page` (senza la superficie completa
    del motore, che il modello non mostrava)."""
    return {"review_items": motore().repository.list_review_queue(limit=100)}


def _azioni(r: dict[str, Any]) -> list[dict[str, Any]]:
    params = {"review_id": r.get("id")}
    voci = [
        azione("modifica-approva", "Modifica e approva", tone="primary", params=params, fields=[
            campo("summary_short", "Sintesi breve", value=r.get("summary_short")),
            campo("what_changes", "Cosa cambia", "textarea"),
            campo("review_notes", "Note del revisore"),
        ]),
        azione("approva", "Approva", tone="success", params=params, fields=[campo("review_notes", "Note di approvazione")]),
        azione("rifiuta", "Rifiuta", tone="danger", params=params, fields=[campo("review_notes", "Motivo del rifiuto")]),
    ]
    if _t(r.get("status")).lower() not in {"rejected", "published"}:
        voci.append(azione("pubblica", "Pubblica", tone="primary", params=params, confirm=f"Pubblicare ora «{_t(r.get('title'))}» negli archivi operativi?"))
    return voci


def _indicazione(r: dict[str, Any]) -> str:
    if _t(r.get("proposed_action")).upper() == "NEEDS_REVIEW":
        return "Questa proposta richiede controllo umano. Dopo la revisione, la pubblicazione userà l'azione coerente con classificazione e dati disponibili."
    if _t(r.get("status")).lower() == "approved":
        return "La proposta è già pronta: il prossimo ciclo automatico la porta negli archivi, oppure puoi pubblicarla subito."
    return ""


def _riga(r: dict[str, Any]) -> dict[str, Any]:
    stato = _t(r.get("status")).lower()
    materia = unisci(r.get("matter_name"), r.get("submatter_name"), separatore=" / ") if _t(r.get("matter_name")) else ""
    return {
        "title": r.get("title"),
        "state": etichetta_stato(stato),
        "kind": unisci(etichetta_classificazione(r.get("classification_type")), f"priorità {_t(r.get('priority'))}"),
        "source": unisci(r.get("source_name"), data(r.get("document_date")), f"confidenza {confidenza(r.get('confidence_score'))}"),
        "summary": _t(r.get("summary_short")) or "Sintesi non disponibile.",
        "detail": unisci(
            f"Azione proposta: {etichetta_azione(r.get('proposed_action'))}",
            f"Materia: {materia}" if materia else "",
            _indicazione(r),
            f"Verifica fonti: {_t(r.get('review_notes'))}" if _t(r.get("review_notes")) else "",
        ),
        "_tone": TONI_STATO_REVISIONE.get(stato, ""),
        "_actions": _azioni(r),
    }


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    voci = payload.get("review_items") or []
    return {
        "title": "Coda revisioni degli aggiornamenti",
        "subtitle": "Controlla solo le proposte che il motore non ha potuto pubblicare con certezza sufficiente.",
        "links": [link("Panoramica del motore", INDIRIZZI["cruscotto"], tone="primary"), *collegamenti("revisione")],
        "sections": [
            actions("Pubblicazione automatica", [azione_motore("autopublish")], subtitle="Coda condivisa: le fonti affidabili ad alta confidenza vengono archiviate automaticamente per tutti gli studi."),
            table(
                f"Proposte in revisione ({len(voci)})",
                [("title", "Proposta"), ("state", "Stato"), ("kind", "Classificazione e priorità"), ("source", "Fonte, data e confidenza"), ("summary", "Sintesi"), ("detail", "Decisione e verifica")],
                [_riga(r) for r in voci],
                empty="Nessuna proposta in revisione.",
            ),
            notes("Come si decide", [
                "«Modifica e approva» aggiorna sintesi e cosa cambia, poi approva la proposta.",
                "«Approva» la rende pronta alla pubblicazione; «Pubblica» la porta subito negli archivi operativi.",
                "Ogni decisione registra come revisore l'utente collegato.",
            ], tone="info"),
        ],
    }


# ------------------------------------------------------------------ azioni

AZIONI_REVISIONE = {
    "approva": ("Proposta approvata.", "success", "Errore approve review %s", "Errore approvazione"),
    "modifica-approva": ("Proposta aggiornata e approvata.", "success", "Errore edit_and_approve %s", "Errore modifica e approvazione"),
    "rifiuta": ("Proposta rifiutata.", "warning", "Errore reject review %s", "Errore rifiuto"),
    "pubblica": ("Contenuto pubblicato correttamente.", "success", "Errore publish review %s", "Errore pubblicazione"),
}


def _chiama(chiave: str, pipeline: Any, review_id: int, values: dict[str, str]) -> None:
    note = values.get("review_notes", "")
    if chiave == "approva":
        pipeline.approve_review(review_id, reviewer=revisore(), notes=note)
    elif chiave == "modifica-approva":
        pipeline.edit_and_approve_review(
            review_id,
            reviewer=revisore(),
            review_notes=note,
            summary_short=values.get("summary_short", ""),
            what_changes=values.get("what_changes", ""),
        )
    elif chiave == "rifiuta":
        pipeline.reject_review(review_id, reviewer=revisore(), notes=note)
    else:
        pipeline.publish_review(review_id, reviewer=revisore())


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    if chiave == "autopublish":
        return esegui_motore("autopublish")
    if chiave not in AZIONI_REVISIONE:
        return esito(False, "Azione non disponibile in questa pagina.")
    review_id = identificativo(params.get("review_id"))
    if review_id is None:
        return esito(False, "Proposta non trovata.", tone="warning")
    messaggio, tono, log, prefisso = AZIONI_REVISIONE[chiave]
    try:
        _chiama(chiave, motore(), review_id, values)
    except Exception as exc:
        current_app.logger.exception(log, review_id)
        return esito(False, f"{prefisso}: {exc}")
    return esito(True, messaggio, tone=tono)


AZIONI = {"autopublish", *AZIONI_REVISIONE}

__all__ = ["AZIONI", "adatta", "costruisci", "esegui"]
