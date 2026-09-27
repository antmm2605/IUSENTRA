"""Lessico e servizi comuni delle pagine React «Copertura AI».

Le pagine `copertura-ai` e `copertura-ai-revisione` sostituiscono le viste
storiche di `web/blueprints/legal_coverage_admin.py` (modelli
`admin/legal_coverage_dashboard.html`, `admin/legal_coverage_review.html` e lo
script `admin_coverage_review.js`). La pipeline restituisce codici tecnici
inglesi (stati delle bozze, rischio, stato di copertura, tipi di lacuna,
blocchi mancanti, azioni di revisione): qui stanno le etichette italiane; i
codici restano nei dettagli.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_sezioni import _t

BASE = "/admin/copertura-ai"
INDIRIZZO_CRUSCOTTO = f"{BASE}/"
INDIRIZZO_REVISIONE = f"{BASE}/review"

# Il revisore registrato dalla schermata storica di revisione: lo script
# `admin_coverage_review.js` inviava sempre `reviewer: "review-ui"` alle API
# JSON (`/api/drafts/<id>/save|approve|reject|publish`).
REVISORE = "review-ui"

STATI_BOZZA = {
    "generated": ("Generata", "warning"),
    "validated": ("Validata", "info"),
    "needs_review": ("Da rivedere", "warning"),
    "approved": ("Approvata", "success"),
    "rejected": ("Rifiutata", "danger"),
    "published": ("Pubblicata", "success"),
}
RISCHI = {"LOW": "Basso", "MEDIUM": "Medio", "HIGH": "Alto", "SPECIALIST": "Specialistico"}
STATI_COPERTURA = {"READY": ("Pronta", "success"), "PARTIAL": ("Parziale", "warning"), "EMPTY": ("Vuota", "")}
LACUNE = {
    "MISSING_PROCEDURE": "Procedura mancante",
    "MISSING_TEMPLATE": "Modello mancante",
    "MISSING_RULES": "Regole mancanti",
    "MISSING_REQUIREMENTS": "Requisiti mancanti",
    "MISSING_DOCUMENTS": "Documenti mancanti",
    "LOW_SCORE": "Punteggio basso",
}
BLOCCHI = {
    "profile": "profilo",
    "procedure": "procedura",
    "variant": "variante",
    "phases": "fasi",
    "acts": "atti",
    "documents": "documenti",
    "norms": "norme",
    "checklists": "liste di controllo",
    "requirements": "requisiti",
    "outcomes": "esiti",
    "rules": "regole",
    "templates": "modelli",
}
AZIONI_REVISIONE = {
    "generated": "Generazione",
    "saved": "Salvataggio",
    "approved": "Approvazione",
    "rejected": "Rifiuto",
    "published": "Pubblicazione",
}
MODIFICHE = {"added": "Aggiunta", "removed": "Rimossa", "updated": "Modificata"}
ORIGINI = {"AI": "Generata dall'assistente", "HUMAN": "Scritta dal revisore", "MANUAL": "Scritta dal revisore"}

NOMI_AZIONE = {"audit": "Verifica della copertura", "gaps": "Coda delle lacune", "drafts": "Generazione delle bozze", "publish": "Pubblicazione delle bozze approvate"}


def _leggibile(value: Any) -> str:
    return " ".join(_t(value).replace("_", " ").split()).capitalize()


def stato_bozza(value: Any) -> tuple[str, str]:
    codice = _t(value).lower()
    return STATI_BOZZA.get(codice, (_leggibile(codice) or "Da verificare", ""))


def rischio(value: Any) -> str:
    codice = _t(value).upper() or "MEDIUM"
    return RISCHI.get(codice, _leggibile(codice))


def stato_copertura(value: Any) -> tuple[str, str]:
    codice = _t(value).upper()
    return STATI_COPERTURA.get(codice, (_leggibile(codice) or "Da verificare", ""))


def lacuna(value: Any) -> str:
    codice = _t(value).upper()
    return LACUNE.get(codice, _leggibile(codice))


def blocchi(valori: Any) -> str:
    return ", ".join(BLOCCHI.get(_t(v).lower(), _t(v)) for v in valori or [] if _t(v))


def azione_revisione(value: Any) -> str:
    codice = _t(value).lower()
    return AZIONI_REVISIONE.get(codice, _leggibile(codice) or "Evento")


def modifica(value: Any) -> str:
    return MODIFICHE.get(_t(value).lower(), _leggibile(value) or "Modificata")


def si_no(value: Any) -> str:
    return "sì" if value else "no"


def indirizzo_bozza(draft_id: Any) -> str:
    return f"{INDIRIZZO_REVISIONE}?draft={_t(draft_id)}"


def repository():
    """Lo stesso archivio delle API JSON storiche (`build_repository(tenant_slug="")`)."""
    from web.services.legal_coverage_surface import build_repository

    return build_repository(tenant_slug="")


__all__ = [
    "INDIRIZZO_CRUSCOTTO",
    "INDIRIZZO_REVISIONE",
    "NOMI_AZIONE",
    "ORIGINI",
    "REVISORE",
    "azione_revisione",
    "blocchi",
    "indirizzo_bozza",
    "lacuna",
    "modifica",
    "repository",
    "rischio",
    "si_no",
    "stato_bozza",
    "stato_copertura",
]
