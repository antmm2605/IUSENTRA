"""Pagine «Acquisizione» e «Dettaglio acquisizione» del pannello di piattaforma (React).

Sostituiscono le viste storiche `/admin/aggiornamenti-legali/staging` (rotta
`staging_page`, modello `admin/legal_updates_staging.html`) e
`/admin/aggiornamenti-legali/staging/<id>` (rotta `staging_detail_page`,
modello `admin/legal_updates_staging_detail.html`).

- L'elenco riconcilia la coda come la rotta storica
  (`reconcile_pending_reviews(limit=300, reviewer="system")`) e filtra con
  `list_raw_documents(source_code, classification_type, status, limit=120)`;
  i filtri (`filtra`) riaprono la pagina con la stessa query del modulo GET.
- `analizza` → `analyze_staging_document`
  (`analyze_raw_document(id, auto_publish=True)`), con gli stessi messaggi.
"""

from __future__ import annotations

from typing import Any

from flask import current_app

from web.services.react_piattaforma_aggiornamenti_comune import (
    CLASSIFICATION_LABELS,
    INDIRIZZI,
    STATUS_LABELS,
    collegamenti,
    confidenza,
    data,
    etichetta_azione,
    etichetta_classificazione,
    etichetta_lavorazione,
    filtra,
    identificativo,
    motore,
    opzioni,
    tono_lavorazione,
    unisci,
)
from web.services.react_piattaforma_sezioni import (
    _t,
    actions,
    azione,
    campo,
    esito,
    facts,
    form,
    link,
    notes,
    table,
)

FILTRI = ("source", "classification", "status")


def _azione_analizza(raw_id: Any, etichetta: str = "Rianalizza") -> dict[str, Any]:
    return azione("analizza", etichetta, params={"id": raw_id}, confirm="Rianalizzare il documento? Se le fonti sono sufficienti viene pubblicato automaticamente negli archivi operativi.")


# ------------------------------------------------------------------ elenco


def costruisci(source: str = "", classification: str = "", status: str = "") -> dict[str, Any]:
    """Gli stessi passi della rotta storica `staging_page` (senza la superficie
    completa del motore, che il modello non mostrava)."""
    pipeline = motore()
    try:
        pipeline.reconcile_pending_reviews(limit=300, reviewer="system")
    except Exception:
        current_app.logger.warning("Riconciliazione staging non completata", exc_info=True)
    return {
        "documents": pipeline.repository.list_raw_documents(source_code=source, classification_type=classification, status=status, limit=120),
        "sources": pipeline.repository.list_sources(enabled_only=False),
        "source_filter": source,
        "classification_filter": classification,
        "status_filter": status,
    }


def _riga(d: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": d.get("title"),
        "source": d.get("source_name"),
        "classification": etichetta_classificazione(d.get("classification_type")) if _t(d.get("classification_type")) else "",
        "state": etichetta_lavorazione(d),
        "where": unisci(data(d.get("published_at")), d.get("source_url")),
        "summary": d.get("body_short"),
        "_href": f"{INDIRIZZI['acquisizione']}/{_t(d.get('id'))}",
        "_tone": tono_lavorazione(d),
        "_actions": [_azione_analizza(d.get("id"))],
    }


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    fonti = {_t(s.get("code")): _t(s.get("name")) or _t(s.get("code")) for s in payload.get("sources") or [] if _t(s.get("code"))}
    attivi = any(_t(payload.get(f"{n}_filter")) for n in FILTRI)
    documenti = payload.get("documents") or []
    return {
        "title": "Area di acquisizione dei documenti",
        "subtitle": "I contenuti acquisiti vengono classificati e pubblicati automaticamente quando le fonti sono sufficienti. Acquisizione condivisa: una sola lavorazione alimenta tutti gli studi.",
        "links": [*collegamenti("acquisizione"), *([link("Azzera i filtri", INDIRIZZI["acquisizione"])] if attivi else [])],
        "sections": [
            form(
                "Filtra i documenti",
                "filtra",
                [
                    campo("source", "Fonte", "select", value=payload.get("source_filter"), options=opzioni(fonti, _t(payload.get("source_filter")), tutte="Tutte le fonti")),
                    campo("classification", "Classificazione", "select", value=payload.get("classification_filter"), options=opzioni(CLASSIFICATION_LABELS, _t(payload.get("classification_filter")), tutte="Tutte le classificazioni")),
                    campo("status", "Stato della lavorazione", "select", value=payload.get("status_filter"), options=opzioni(STATUS_LABELS, _t(payload.get("status_filter")), tutte="Tutti gli stati")),
                ],
                submit_label="Filtra",
            ),
            table(
                f"Documenti in acquisizione ({len(documenti)})",
                [("title", "Documento"), ("source", "Fonte"), ("classification", "Classificazione"), ("state", "Lavorazione"), ("where", "Data e indirizzo"), ("summary", "Sintesi")],
                [_riga(d) for d in documenti],
                subtitle="Al massimo 120 documenti, i più recenti per primi.",
                empty="Nessun documento in acquisizione con i filtri correnti.",
            ),
        ],
    }


# ------------------------------------------------------------------ dettaglio


def costruisci_scheda(raw_id: str = "") -> dict[str, Any]:
    """`staging_detail_page`: il documento dell'acquisizione condivisa."""
    numero = identificativo(raw_id)
    documento = motore().repository.get_staging_document(numero) if numero is not None else None
    return {"id": _t(raw_id), "document": documento}


def _paragrafi(testo: str) -> list[str]:
    """Il testo della vista storica era preformattato: si mantengono i capoversi
    (righe vuote) o, per un blocco unico e lungo, le singole righe."""
    normalizzato = testo.replace("\r\n", "\n")
    blocchi = [" ".join(b.split()) for b in normalizzato.split("\n\n")]
    if len(blocchi) == 1 and len(blocchi[0]) > 2000:
        blocchi = [" ".join(r.split()) for r in normalizzato.split("\n")]
    return [b for b in blocchi if b]


def adatta_scheda(payload: dict[str, Any]) -> dict[str, Any]:
    d = payload.get("document")
    if not d:
        return {
            "title": "Dettaglio acquisizione",
            "subtitle": "Documento nell'acquisizione condivisa.",
            "links": [link("Torna all'acquisizione", INDIRIZZI["acquisizione"], tone="primary")],
            "sections": [notes("Documento non trovato", ["Documento di acquisizione non trovato: potrebbe essere stato rimosso o accorpato."], tone="warning")],
        }
    testo = _t(d.get("raw_text")) or _t(d.get("body_text")) or "Nessun testo disponibile."
    return {
        "title": _t(d.get("title")) or "Dettaglio acquisizione",
        "subtitle": unisci(d.get("source_name"), data(d.get("published_at")), "Documento nell'acquisizione condivisa."),
        "links": [
            link("Torna all'acquisizione", INDIRIZZI["acquisizione"]),
            *([link("Apri la coda revisioni", INDIRIZZI["revisione"], tone="primary")] if d.get("review_id") else []),
        ],
        "sections": [
            actions("Lavorazione", [_azione_analizza(d.get("id"), "Rianalizza adesso")]),
            facts("Analisi e decisione", [
                ("Classificazione", etichetta_classificazione(d.get("classification_type") or "INCERTO")),
                ("Confidenza", confidenza(d.get("confidence_score"))),
                ("Azione proposta", etichetta_azione(d.get("proposed_action") or "NEEDS_REVIEW")),
                ("Materia", _t(d.get("matter_name")) or "da assegnare"),
                ("Sottomateria", _t(d.get("submatter_name")) or "non assegnata"),
                ("Lavorazione", etichetta_lavorazione(d)),
            ]),
            notes("Sintesi breve", [d.get("summary_short")], tone="info"),
            notes("Cosa cambia", [d.get("what_changes")], tone="info"),
            notes("Documento grezzo", [f"Indirizzo della fonte: {_t(d.get('source_url'))}", *_paragrafi(testo)], tone="info"),
        ],
    }


# ------------------------------------------------------------------ azioni


def _analizza(raw_id: int) -> dict[str, Any]:
    try:
        risultato = motore().analyze_raw_document(raw_id, auto_publish=True)
        if int(((risultato.get("autopublished") or {}).get("count")) or 0):
            return esito(True, "Documento analizzato e pubblicato automaticamente negli archivi operativi.")
        return esito(True, "Documento analizzato: resta in revisione solo se serve controllo umano.")
    except Exception as exc:
        current_app.logger.exception("Errore analyze_staging_document %s", raw_id)
        return esito(False, f"Errore rianalisi documento: {exc}")


def _esegui_analizza(params: dict[str, str]) -> dict[str, Any]:
    raw_id = identificativo(params.get("id"))
    if raw_id is None:
        return esito(False, "Documento di acquisizione non trovato.", tone="warning")
    return _analizza(raw_id)


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    if chiave == "filtra":
        return filtra(INDIRIZZI["acquisizione"], values, FILTRI)
    if chiave == "analizza":
        return _esegui_analizza(params)
    return esito(False, "Azione non disponibile in questa pagina.")


def esegui_scheda(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    if chiave == "analizza":
        return _esegui_analizza(params)
    return esito(False, "Azione non disponibile in questa pagina.")


AZIONI = {"filtra", "analizza"}
AZIONI_SCHEDA = {"analizza"}

__all__ = ["AZIONI", "AZIONI_SCHEDA", "adatta", "adatta_scheda", "costruisci", "costruisci_scheda", "esegui", "esegui_scheda"]
