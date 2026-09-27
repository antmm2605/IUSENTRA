"""Pagina «Catalogazione» (analisi automatica) del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/aggiornamenti-legali/analisi` (rotta
`analysis_page`, modello `admin/legal_updates_analysis.html`): filtri per
classificazione e materia (`list_analyses(classification_type, matter_slug,
limit=120)`, materie di primo livello da `list_matters()`) ed elenco delle
analisi con classificazione, azione proposta, stato della revisione, fonte,
materia, confidenza e sintesi. `autopublish` è il pulsante storico «Pubblica
idonei» (`execute_action("autopublish")`).
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_aggiornamenti_comune import (
    CLASSIFICATION_LABELS,
    INDIRIZZI,
    TONI_STATO_REVISIONE,
    azione_motore,
    collegamenti,
    confidenza,
    esegui_motore,
    etichetta_azione,
    etichetta_classificazione,
    etichetta_stato,
    filtra,
    motore,
    opzioni,
    unisci,
)
from web.services.react_piattaforma_sezioni import _t, actions, campo, esito, form, link, table

FILTRI = ("classification", "materia")


def costruisci(classification: str = "", materia: str = "") -> dict[str, Any]:
    """Gli stessi elenchi della rotta storica `analysis_page` (senza la
    superficie completa del motore, che il modello non mostrava)."""
    pipeline = motore()
    return {
        "analyses": pipeline.repository.list_analyses(classification_type=classification, matter_slug=materia, limit=120),
        "matters": pipeline.repository.list_matters(),
        "classification_filter": classification,
        "matter_filter": materia,
    }


def _riga(a: dict[str, Any]) -> dict[str, Any]:
    stato = _t(a.get("review_status")).lower()
    return {
        "title": a.get("title"),
        "classification": etichetta_classificazione(a.get("classification_type")),
        "action": etichetta_azione(a.get("proposed_action")),
        "review": etichetta_stato(stato) if stato else "",
        "detail": unisci(a.get("source_name"), _t(a.get("matter_name")) or "materia da verificare", f"confidenza {confidenza(a.get('confidence_score'))}"),
        "summary": _t(a.get("summary_short")) or _t(a.get("body_short")) or "Sintesi non disponibile.",
        "_href": f"{INDIRIZZI['acquisizione']}/{_t(a.get('raw_document_id'))}" if _t(a.get("raw_document_id")) else "",
        "_tone": TONI_STATO_REVISIONE.get(stato, ""),
    }


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    materie = {_t(m.get("slug")): _t(m.get("name")) for m in payload.get("matters") or [] if str(m.get("level")) == "1" and _t(m.get("slug"))}
    analisi = payload.get("analyses") or []
    attivi = any(_t(payload.get(k)) for k in ("classification_filter", "matter_filter"))
    return {
        "title": "Analisi automatica",
        "subtitle": "Classificazione, materia, confidenza e decisione operativa prima dell'archiviazione. Le fonti affidabili ad alta confidenza vengono pubblicate automaticamente; in revisione restano solo i casi da controllare.",
        "links": [link("Coda revisioni", INDIRIZZI["revisione"], tone="primary"), *collegamenti("catalogazione"), *([link("Azzera i filtri", INDIRIZZI["catalogazione"])] if attivi else [])],
        "sections": [
            actions("Pubblicazione", [azione_motore("autopublish")]),
            form(
                "Filtra le analisi",
                "filtra",
                [
                    campo("classification", "Classificazione", "select", value=payload.get("classification_filter"), options=opzioni(CLASSIFICATION_LABELS, _t(payload.get("classification_filter")), tutte="Tutte le classificazioni")),
                    campo("materia", "Materia", "select", value=payload.get("matter_filter"), options=opzioni(materie, _t(payload.get("matter_filter")), tutte="Tutte le materie")),
                ],
                submit_label="Filtra",
            ),
            table(
                f"Analisi ({len(analisi)})",
                [("title", "Documento"), ("classification", "Classificazione"), ("action", "Azione proposta"), ("review", "Revisione"), ("detail", "Fonte, materia e confidenza"), ("summary", "Sintesi")],
                [_riga(a) for a in analisi],
                subtitle="Al massimo 120 analisi, le più recenti per prime.",
                empty="Nessuna analisi disponibile.",
            ),
        ],
    }


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    if chiave == "filtra":
        return filtra(INDIRIZZI["catalogazione"], values, FILTRI)
    if chiave == "autopublish":
        return esegui_motore("autopublish")
    return esito(False, "Azione non disponibile in questa pagina.")


AZIONI = {"filtra", "autopublish"}

__all__ = ["AZIONI", "adatta", "costruisci", "esegui"]
