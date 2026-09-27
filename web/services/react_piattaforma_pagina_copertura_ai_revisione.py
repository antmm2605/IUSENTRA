"""Pagina «Revisione della copertura AI» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/copertura-ai/review` (modello
`admin/legal_coverage_review.html` guidato da `admin_coverage_review.js` e
dalle API JSON `/admin/copertura-ai/api/drafts*`):

- coda delle bozze (`api_drafts`: archivio non raggiungibile o errore → coda
  vuota), filtrabile per sottobranca, procedura o stato come il filtro storico;
- scheda della bozza `?draft=<id>` (`api_draft_detail`), aperta sulla prima
  bozza della coda quando non se ne sceglie una, come lo script storico;
- azioni con la stessa validazione e lo stesso revisore delle API JSON
  (`REVISORE`, cioè `review-ui` come lo script): `salva` → `save_draft`,
  `approva` → `approve_draft`, `rifiuta` → `reject_draft` (motivo e firma
  obbligatori), `pubblica` → approvazione se serve e `publish_single_draft`
  (firma obbligatoria), `apri` → scheda della bozza.
"""

from __future__ import annotations

import json
from typing import Any

from web.services.react_piattaforma_copertura_ai_bozza import (
    azioni_decisione,
    dettaglio,
    sezioni_bozza,
    sezioni_validazione,
)
from web.services.react_piattaforma_copertura_ai_comune import (
    INDIRIZZO_CRUSCOTTO,
    INDIRIZZO_REVISIONE,
    REVISORE,
    indirizzo_bozza,
    repository,
    rischio,
    si_no,
    stato_bozza,
)
from web.services.react_piattaforma_sezioni import _t, azione, data_ora, esito, link, notes, table

MSG_MOTIVO = "Inserisci il motivo della decisione prima di continuare."
MSG_FIRMA = "Inserisci la firma del revisore per chiudere la revisione."


def _identificativo(valore: Any) -> int | None:
    testo = _t(valore)
    return int(testo) if testo.isdigit() and int(testo) > 0 else None


def _coda(repo: Any) -> list[dict[str, Any]]:
    """`api_drafts`: coda vuota se l'archivio non risponde o la lettura fallisce."""
    from flask import current_app

    try:
        return list(repo.list_drafts()) if repo.ping() else []
    except Exception:
        current_app.logger.exception("Errore api_drafts")
        return []


def costruisci(draft: str = "", q: str = "") -> dict[str, Any]:
    from flask import current_app

    repo = repository()
    bozze = _coda(repo)
    filtro = _t(q).lower()
    visibili = [b for b in bozze if filtro in f"{_t(b.get('subbranch_code'))} {_t(b.get('procedure_code'))} {_t(b.get('status'))}".lower()]
    scelta = _identificativo(draft)
    if scelta is None and visibili:
        scelta = _identificativo(visibili[0].get("id"))
    scheda, errore = None, ""
    if scelta is not None:
        try:
            scheda = dettaglio(repo, scelta)
            errore = "" if scheda else "Bozza non trovata."
        except Exception as exc:
            current_app.logger.exception("Errore api_draft_detail %s", scelta)
            errore = str(exc)
    return {"drafts": visibili, "total": len(bozze), "q": _t(q), "draft": scheda, "draft_error": errore, "selected": scelta}


def _riga(b: dict[str, Any], scelta: Any) -> dict[str, Any]:
    etichetta, tono = stato_bozza(b.get("status"))
    return {
        "subbranch": b.get("subbranch_code"),
        "procedure": _t(b.get("procedure_code")) or "-",
        "state": etichetta,
        "risk": rischio(b.get("risk_level")),
        "auto": si_no(b.get("auto_publish_eligible")),
        "created": data_ora(b.get("created_at")) or "-",
        "_href": indirizzo_bozza(b.get("id")),
        "_tone": "info" if _identificativo(b.get("id")) == scelta else tono,
        "_actions": [azione("apri", "Apri", params={"draft": b.get("id")}), *azioni_decisione(b)],
    }


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    bozze = payload.get("drafts") or []
    scelta = payload.get("selected")
    filtro = _t(payload.get("q"))
    if payload.get("total") and not bozze:
        vuota = "Nessuna bozza corrisponde al filtro inserito."
    else:
        vuota = "Nessuna bozza disponibile. Torna alla panoramica e genera prima verifica, coda delle lacune e bozze AI."
    sezioni: list[dict[str, Any]] = [
        notes("Come si usa questa schermata", [
            "1. Seleziona una bozza dalla coda. 2. Controlla metadati, report di validazione ed esempi usati.",
            "3. Correggi la specifica JSON solo se serve. 4. Inserisci firma del revisore e motivazione. 5. Approva o rifiuta la bozza.",
            "6. Pubblica solo dopo l'approvazione, per generare lo SQL reale con la traccia di revisione completa.",
        ], tone="info"),
        table(
            f"Coda delle bozze ({len(bozze)})",
            [("subbranch", "Sottobranca"), ("procedure", "Procedura"), ("state", "Stato"), ("risk", "Rischio"), ("auto", "Pubblicazione automatica"), ("created", "Creata il")],
            [_riga(b, scelta) for b in bozze],
            subtitle="Priorità, rischio e stato: prima le bozze idonee alla pubblicazione automatica, poi le più vecchie.",
            empty=vuota,
        ),
    ]
    bozza = payload.get("draft")
    if bozza:
        sezioni.extend(sezioni_bozza(bozza))
    elif payload.get("draft_error"):
        sezioni.append(notes("Bozza selezionata", [f"Impossibile caricare la bozza selezionata: {payload['draft_error']}"], tone="warning"))
    titolo_bozza = f" · {_t(bozza.get('subbranch_code'))} {_t(bozza.get('procedure_code'))}".rstrip() if bozza else ""
    return {
        "title": f"Coda di revisione delle bozze{titolo_bozza}",
        "subtitle": "Controlla le bozze generate automaticamente prima che vengano trasformate in SQL e pubblicate nel catalogo.",
        "links": [link("Torna alla panoramica", INDIRIZZO_CRUSCOTTO), *([link("Rimuovi il filtro", INDIRIZZO_REVISIONE)] if filtro else [])],
        "filter": {"name": "q", "label": "Filtra per sottobranca, procedura o stato", "value": filtro, "options": []},
        "sections": sezioni,
    }


# ------------------------------------------------------------------ azioni


def _salva(draft_id: int, values: dict[str, str]) -> dict[str, Any]:
    from pct.legal_coverage_pipeline import save_draft

    try:
        spec = json.loads(values.get("spec_json") or "")
    except ValueError:
        return esito(False, "JSON non valido. Correggi il contenuto prima di salvare.", tone="warning")
    if not isinstance(spec, dict):
        return esito(False, "Specifica non valida: serve un oggetto JSON.", tone="warning")
    validazione = save_draft(repository(), draft_id, spec, reviewer=REVISORE, review_signature=_t(values.get("review_signature")))
    return esito(True, "Bozza salvata correttamente.", sections=sezioni_validazione(validazione, "Validazione della bozza salvata"))


def _decidi(chiave: str, draft_id: int, values: dict[str, str]) -> dict[str, Any]:
    """`_review_payload(required_reason=True)` + `approve_draft` / `reject_draft`."""
    from pct.legal_coverage_pipeline import approve_draft, reject_draft

    motivo, firma = _t(values.get("review_reason")), _t(values.get("review_signature"))
    if not motivo:
        return esito(False, MSG_MOTIVO, tone="warning")
    if not firma:
        return esito(False, MSG_FIRMA, tone="warning")
    funzione = approve_draft if chiave == "approva" else reject_draft
    funzione(repository(), draft_id, REVISORE, review_reason=motivo, review_signature=firma)
    if chiave == "approva":
        return esito(True, "Bozza approvata con traccia di revisione registrata.")
    return esito(True, "Bozza rifiutata con traccia di revisione registrata.", tone="warning")


def _pubblica(draft_id: int, values: dict[str, str]) -> dict[str, Any]:
    """`api_draft_publish`: firma obbligatoria, approvazione se manca, poi `publish_single_draft`."""
    from pct.legal_coverage_pipeline import publish_single_draft

    motivo, firma = _t(values.get("review_reason")), _t(values.get("review_signature"))
    if not firma:
        return esito(False, MSG_FIRMA, tone="warning")
    repo = repository()
    bozza = repo.get_draft(draft_id)
    if not bozza:
        return esito(False, "Bozza non trovata.", tone="warning")
    if bozza.get("status") != "approved":
        repo.set_draft_status(
            draft_id,
            "approved",
            REVISORE or "review-ui",
            review_reason=motivo or str(bozza.get("review_reason") or ""),
            review_signature=firma or str(bozza.get("review_signature") or ""),
        )
    publish_single_draft(repo, draft_id, apply_to_db=True)
    return esito(True, "Bozza pubblicata e archivio aggiornato.")


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    from flask import current_app

    if chiave not in AZIONI:
        return esito(False, "Azione non disponibile in questa pagina.")
    draft_id = _identificativo(params.get("draft"))
    if draft_id is None:
        return esito(False, "Bozza non trovata.", tone="warning")
    if chiave == "apri":
        return esito(True, "Apertura della bozza.", tone="info", navigate=indirizzo_bozza(draft_id))
    try:
        if chiave == "salva":
            return _salva(draft_id, values)
        if chiave == "pubblica":
            return _pubblica(draft_id, values)
        return _decidi(chiave, draft_id, values)
    except Exception as exc:
        current_app.logger.exception("Errore revisione copertura %s %s", chiave, draft_id)
        return esito(False, str(exc))


AZIONI = {"apri", "salva", "approva", "rifiuta", "pubblica"}

__all__ = ["AZIONI", "adatta", "costruisci", "esegui"]
