"""Pagina «Archivio strutturato» degli aggiornamenti legali (React).

Sostituisce la vista storica `/admin/aggiornamenti-legali/archivio` (rotta
`archive_page`, modello `admin/legal_updates_archive.html`): controllo dei
duplicati, archivi ufficiali locali (Normattiva, Gazzetta Ufficiale) e le
schede `?tab=` normative, giurisprudenza, prassi, notizie e registro, scelte
con il filtro `tab` della pagina. `cleanup` è il pulsante storico «Pulisci
duplicati» (`execute_action("cleanup")`).
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_aggiornamenti_comune import (
    INDIRIZZI,
    azione_motore,
    collegamenti,
    esegui_motore,
    leggibile,
    motore,
    superficie,
    unisci,
)
from web.services.react_piattaforma_sezioni import _t, actions, data_ora, esito, link, metrics, notes, table

SCHEDE = {
    "normative": "Normative",
    "jurisprudence": "Giurisprudenza",
    "prassi": "Prassi",
    "news": "Notizie",
    "audit": "Registro delle attività",
}
STATI_NOTIZIA = {"published": "Pubblicata", "draft": "Bozza", "archived": "Archiviata", "rejected": "Rifiutata"}


def _scheda(tab: str) -> str:
    scelta = _t(tab).lower() or "normative"
    return scelta if scelta in SCHEDE else "normative"


def _elenco(pipeline: Any, scelta: str) -> list[dict[str, Any]]:
    """Gli stessi elenchi della rotta storica; si legge solo quello della scheda mostrata."""
    repo = pipeline.repository
    if scelta == "normative":
        return repo.list_published_normative(limit=120)
    if scelta == "jurisprudence":
        return repo.list_published_jurisprudence(limit=120)
    if scelta == "prassi":
        return repo.list_published_prassi(limit=120)
    if scelta == "news":
        return repo.list_news(limit=120, include_drafts=True)
    return repo.list_audit(limit=120)


def costruisci(tab: str = "") -> dict[str, Any]:
    pipeline = motore()
    scelta = _scheda(tab)
    payload = superficie(pipeline)
    return {"payload": payload, "selected_tab": scelta, "items": _elenco(pipeline, scelta)}


def _numero(numero: Any, anno: Any) -> str:
    return "/".join(_t(v) for v in (numero, anno) if _t(v))


def _tabella(scelta: str, voci: list[dict[str, Any]]) -> dict[str, Any]:
    if scelta == "normative":
        return table("Normative pubblicate", [("title", "Titolo"), ("ref", "Riferimento"), ("issuer", "Autorità emanante"), ("summary", "Sintesi")], [
            {"title": v.get("title"), "ref": unisci(v.get("norm_type"), f"n. {_numero(v.get('norm_number'), v.get('norm_year'))}" if _numero(v.get("norm_number"), v.get("norm_year")) else "", separatore=" "), "issuer": v.get("issuer"), "summary": v.get("summary")}
            for v in voci
        ], empty="Nessuna normativa pubblicata.")
    if scelta == "jurisprudence":
        return table("Giurisprudenza pubblicata", [("title", "Titolo"), ("court", "Autorità giudiziaria"), ("ref", "Numero"), ("summary", "Sintesi")], [
            {"title": v.get("title"), "court": v.get("court_name"), "ref": _numero(v.get("decision_number"), v.get("decision_year")), "summary": v.get("summary")}
            for v in voci
        ], empty="Nessuna sentenza pubblicata.")
    if scelta == "prassi":
        return table("Prassi pubblicata", [("title", "Titolo"), ("body", "Ente"), ("ref", "Atto"), ("summary", "Sintesi")], [
            {"title": v.get("title"), "body": v.get("issuing_body"), "ref": unisci(v.get("act_type"), _numero(v.get("act_number"), v.get("act_year")), separatore=" "), "summary": v.get("summary")}
            for v in voci
        ], empty="Nessuna prassi pubblicata.")
    if scelta == "news":
        return table("Notizie", [("title", "Titolo"), ("kind", "Tipo"), ("matter", "Materia"), ("state", "Stato"), ("summary", "Sintesi")], [
            {
                "title": v.get("title"),
                "kind": leggibile(v.get("news_type")),
                "matter": _t(v.get("matter_name")) or "materia da verificare",
                "state": STATI_NOTIZIA.get(_t(v.get("publication_status")).lower(), leggibile(v.get("publication_status"))),
                "summary": v.get("short_summary"),
                "_tone": "success" if _t(v.get("publication_status")).lower() == "published" else "",
            }
            for v in voci
        ], empty="Nessuna notizia disponibile.")
    return table("Registro delle attività", [("event", "Evento"), ("by", "Eseguito da"), ("when", "Quando")], [
        {"event": unisci(leggibile(v.get("entity_type")), leggibile(v.get("action"))), "by": _t(v.get("performed_by")) or "sistema", "when": data_ora(v.get("created_at"))}
        for v in voci
    ], subtitle="Tipo di elemento e operazione registrati dal motore.", empty="Nessun evento registrato.")


def adatta(dati: dict[str, Any]) -> dict[str, Any]:
    payload = dati.get("payload") or {}
    scelta = _t(dati.get("selected_tab")) or "normative"
    duplicati = (payload.get("quality") or {}).get("duplicates") or {}
    arch = payload.get("official_archives") or {}
    normattiva, gazzetta = arch.get("normattiva") or {}, arch.get("gazzetta") or {}
    return {
        "title": "Archivio strutturato",
        "subtitle": "Normative, giurisprudenza, prassi, notizie e registro del motore di aggiornamento. Archivio comune: le pubblicazioni sono disponibili per tutti gli studi.",
        "links": [link("Panoramica del motore", INDIRIZZI["cruscotto"], tone="primary"), *collegamenti("archivio")],
        "filter": {"name": "tab", "label": "Sezione dell'archivio", "value": scelta, "options": [{"value": k, "label": v} for k, v in SCHEDE.items()]},
        "sections": [
            actions("Pulizia dell'archivio", [azione_motore("cleanup")]),
            notes("Controllo archivio attivo", ["Le nuove ricerche verificano prima quello che è già presente e non ripropongono sentenze, ordinanze, norme o prassi già catalogate."], tone="info"),
            metrics([
                {"label": "Duplicati rilevati", "value": duplicati.get("duplicate_items", 0), "tone": "warning" if duplicati.get("duplicate_items") else "success"},
                {"label": "Gruppi da accorpare", "value": duplicati.get("groups", 0)},
            ], title="Controllo dei duplicati"),
            metrics([
                {"label": "Documenti", "value": normattiva.get("documents", 0)},
                {"label": "Articoli", "value": normattiva.get("articles", 0)},
                {"label": "Estratti per la ricerca", "value": normattiva.get("chunks", 0)},
            ], title="Normattiva locale · archivio ufficiale importato e usato dalla Ricerca legale"),
            metrics([
                {"label": "Uscite", "value": gazzetta.get("documents", 0)},
                {"label": "Estratti per la ricerca", "value": gazzetta.get("chunks", 0)},
                {"label": "Stato", "value": "collegata" if gazzetta.get("available") else "da collegare", "tone": "success" if gazzetta.get("available") else "warning"},
            ], title="Gazzetta Ufficiale locale · uscite e testi indicizzati per verifica e confronto"),
            _tabella(scelta, dati.get("items") or []),
        ],
    }


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    if chiave == "cleanup":
        return esegui_motore("cleanup")
    return esito(False, "Azione non disponibile in questa pagina.")


AZIONI = {"cleanup"}

__all__ = ["AZIONI", "SCHEDE", "adatta", "costruisci", "esegui"]
