"""Elementi comuni alle pagine React degli studi nel pannello di piattaforma.

Le pagine `studi`, `studio-nuovo`, `studio`, `studio-utenti`,
`studio-database` e `utenti-piattaforma` sostituiscono le viste storiche di
`web/blueprints/admin.py`. Qui vivono solo le etichette italiane, la lettura dei
valori inviati dal modulo React (riportati alla forma di `request.form`) e le
risposte ricorrenti; la logica resta quella delle rotte storiche.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_sezioni import _t, data_ora, esito, link

STATI_STUDIO = {
    "ATTIVO": ("Attivo", "success"),
    "TRIAL": ("In prova", "info"),
    "SOSPESO": ("Sospeso", "danger"),
    "SCADUTO": ("Scaduto", "warning"),
}

STATI_ATTIVAZIONE = {
    "active": "Attivo",
    "local-pending": "In attesa di predisposizione locale",
    "external-ready": "Connessione pronta, attivazione da eseguire",
    "external-pending": "In attesa di configurazione e verifica",
    "external-tested": "Connessione verificata",
}

ARCHIVI_EFFETTIVI = {"json": "JSON locale", "sqlite": "SQLite per studio", "postgresql": "PostgreSQL", "mysql": "MySQL / MariaDB"}

VALORI_VERI = {"1", "true", "on", "si", "sì", "yes"}

MESSAGGIO_GENERICO = "Operazione non completata. Il dettaglio tecnico è nei log del server."


# ------------------------------------------------------------------ valori inviati


def valore(values: dict[str, Any], nome: str, predefinito: str | None = None) -> str | None:
    """Come `request.form.get(nome, predefinito)`: il campo assente restituisce il predefinito."""
    if nome not in values or values.get(nome) is None:
        return predefinito
    return str(values.get(nome))


def testo(values: dict[str, Any], nome: str, predefinito: str = "") -> str:
    """Come `request.form.get(nome, predefinito).strip()`."""
    return str(valore(values, nome, predefinito) or "").strip()


def spuntato(values: dict[str, Any], nome: str) -> bool:
    """Casella del modulo: il ponte React invia «1»/«0», il modulo storico la inviava solo se spuntata."""
    return str(values.get(nome) or "").strip().lower() in VALORI_VERI


def unisci(params: dict[str, Any], values: dict[str, Any]) -> dict[str, str]:
    """I parametri fissi dell'azione prevalgono sui valori compilati (come l'indirizzo della rotta storica)."""
    return {**{str(k): str(v) for k, v in (values or {}).items()}, **{str(k): str(v) for k, v in (params or {}).items()}}


def slug_di(params: dict[str, Any]) -> str:
    return str((params or {}).get("slug") or "").strip()


# ------------------------------------------------------------------ contesto


def gestore_studi():
    from web.blueprints.admin import _tenant_manager

    return _tenant_manager()


def indirizzo_ip() -> str:
    from flask import request

    return request.remote_addr or ""


def utente_corrente():
    from flask import g

    return getattr(g, "utente_corrente", None)


# ------------------------------------------------------------------ etichette


def etichetta_stato(stato: Any) -> tuple[str, str]:
    chiave = _t(stato).upper()
    return STATI_STUDIO.get(chiave, (chiave.capitalize() or "n.d.", "neutral"))


def nome_piano(piano: Any) -> str:
    from pct.tenant import PIANI

    chiave = _t(piano)
    return _t((PIANI.get(chiave) or {}).get("nome")) or chiave


def data(value: Any) -> str:
    """Solo la data (gg/mm/aaaa), come il filtro `fmt_data` dei modelli storici."""
    return data_ora(value)[:10]


def trattino(value: Any) -> str:
    return _t(value) or "—"


def scadenza(studio: Any) -> tuple[str, str]:
    """Testo e tono della scadenza, come la colonna della lista storica."""
    if not _t(getattr(studio, "data_scadenza", "")):
        return "—", ""
    giorni = getattr(studio, "giorni_alla_scadenza", None)
    if giorni is not None and giorni <= 0:
        return "Scaduta", "danger"
    if giorni is not None and giorni <= 14:
        return f"{giorni} gg", "warning"
    return data(studio.data_scadenza), ""


def ruolo(utente: Any) -> str:
    return _t(getattr(getattr(utente, "ruolo", None), "value", getattr(utente, "ruolo", "")))


def collegamenti_studio(slug: str, *, attuale: str = "") -> list[dict[str, Any]]:
    voci = [
        ("studio", "Dettaglio studio", f"/admin/studi/{slug}"),
        ("studio-utenti", "Utenti dello studio", f"/admin/studi/{slug}/utenti"),
        ("studio-database", "Configurazione archivio", f"/admin/studi/{slug}/database"),
    ]
    return [link(etichetta, href) for chiave, etichetta, href in voci if chiave != attuale] + [link("Tutti gli studi", "/admin/studi")]


# ------------------------------------------------------------------ risposte


def con_navigazione(risultato: dict[str, Any], indirizzo: str) -> dict[str, Any]:
    """Aggiunge l'indirizzo interno che il browser apre dopo l'azione (chiave `navigate` di `esito`)."""
    return {**risultato, "navigate": indirizzo}


def studio_non_trovato() -> dict[str, Any]:
    return esito(False, "Studio non trovato.")


def errore_imprevisto(messaggio_log: str, *argomenti: Any, messaggio: str = MESSAGGIO_GENERICO) -> dict[str, Any]:
    from flask import current_app

    current_app.logger.exception(messaggio_log, *argomenti)
    return esito(False, messaggio)


def pagina_studio_assente(slug: str, titolo: str) -> dict[str, Any]:
    from web.services.react_piattaforma_sezioni import notes

    return {
        "title": titolo,
        "subtitle": f"Nessuno studio registrato con l'identificativo «{slug}».",
        "links": [link("Tutti gli studi", "/admin/studi", tone="primary")],
        "sections": [notes("Studio non trovato", ["Lo studio richiesto non esiste o è stato rimosso dal registro della piattaforma."], tone="danger")],
    }


__all__ = [
    "ARCHIVI_EFFETTIVI",
    "MESSAGGIO_GENERICO",
    "STATI_ATTIVAZIONE",
    "collegamenti_studio",
    "con_navigazione",
    "data",
    "errore_imprevisto",
    "etichetta_stato",
    "gestore_studi",
    "indirizzo_ip",
    "nome_piano",
    "pagina_studio_assente",
    "ruolo",
    "scadenza",
    "slug_di",
    "spuntato",
    "studio_non_trovato",
    "testo",
    "trattino",
    "unisci",
    "utente_corrente",
    "valore",
]
