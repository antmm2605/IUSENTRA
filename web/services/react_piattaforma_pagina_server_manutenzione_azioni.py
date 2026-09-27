"""Azioni della pagina «Server e manutenzione» (React).

Ogni azione replica un invio del blueprint storico
`web/blueprints/server_maintenance_admin.py`: stesso servizio, stessi
argomenti (radice dati, `tenant_slug`, `apply`/`dry_run`, applicazione Flask),
stesso messaggio. La categoria del messaggio storico (`flash`) diventa il tono
dell'esito; l'oggetto che la vista storica passava al template torna come
sezioni di risultato (`react_piattaforma_pagina_server_manutenzione_esiti`).

Le eccezioni impreviste si registrano nei log con lo stesso testo della vista
storica e l'utente riceve un messaggio generico in italiano.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

from flask import current_app

from web.services import react_piattaforma_pagina_server_manutenzione_esiti as esiti
from web.services import react_piattaforma_pagina_server_manutenzione_lessico as lessico
from web.services.react_piattaforma_sezioni import esito

it = lessico.it

#: Categoria del messaggio storico → tono dell'esito.
TONI_FLASH = {"info": "info", "success": "success", "warning": "warning", "danger": "danger"}

Gestore = Callable[[dict[str, str]], dict[str, Any]]


def _risposta(categoria: str, messaggio: str, sezioni: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    tono = TONI_FLASH.get(categoria, "info")
    return esito(tono != "danger", messaggio, tone=tono, sections=sezioni)


def _radice_dati() -> Path:
    """Come `_radice_dati()` del blueprint storico."""
    grezzo = current_app.config.get("PCT_DATA_ROOT") or current_app.config.get("DATA_ROOT") or "/data"
    return Path(str(grezzo)).expanduser()


def _studio(dati: dict[str, str]) -> str:
    """Il `tenant_slug` del modulo storico: `str(request.form.get("tenant_slug", "") or "").strip()`.

    Dalla pagina React arriva come `slug`: il presidio di sicurezza delle API
    `/api/v1/ui/*` (`backend_security.UNSAFE_BACKEND_CONTROL_KEYS`) respinge
    `tenant_slug` nel corpo della richiesta, come ogni chiave che sceglie lo studio.
    """
    return str(dati.get("slug", "") or "").strip()


def _livello_errori(risultato: dict[str, Any]) -> str:
    return "warning" if risultato.get("errors") else "success"


# ------------------------------------------------------------------ fascicoli, PEC, archivio di ricerca


def _copia_doppia(riscrivi: bool) -> Gestore:
    def gestore(_dati: dict[str, str]) -> dict[str, Any]:
        from pct.manutenzione_dati_json import esamina_tutti

        risultato = esamina_tutti(_radice_dati(), riscrivi=riscrivi)
        if riscrivi:
            messaggio = f"Riscritte {risultato['righe_riscritte']} righe. Le colonne con i documenti non sono state toccate."
            return _risposta("success", messaggio, esiti.copia_doppia(risultato))
        messaggio = f"Analisi completata: {risultato['mb_in_eccesso']} MB di copia in eccesso. Nessuna modifica eseguita."
        return _risposta("info", messaggio, esiti.copia_doppia(risultato))

    return gestore


def _collegamenti_pec(ricollegare: bool) -> Gestore:
    def gestore(_dati: dict[str, str]) -> dict[str, Any]:
        from web.services.collegamenti_pec_runtime import esamina_tutti

        risultato = esamina_tutti(current_app, ricollegare=ricollegare)
        categoria = ("success" if risultato["ok"] else "warning") if ricollegare else "info"
        return _risposta(categoria, risultato["messaggio"], esiti.collegamenti_pec(risultato))

    return gestore


def _frammenti_ricerca(rispezzare: bool) -> Gestore:
    def gestore(_dati: dict[str, str]) -> dict[str, Any]:
        from web.services.chunk_rag_runtime import esamina_tutti

        risultato = esamina_tutti(current_app, rispezzare=rispezzare)
        categoria = ("success" if risultato["ok"] else "warning") if rispezzare else "info"
        return _risposta(categoria, it(risultato["messaggio"]), esiti.frammenti_ricerca(risultato))

    return gestore


def _spazio_database(compattare: bool) -> Gestore:
    def gestore(_dati: dict[str, str]) -> dict[str, Any]:
        from pct.manutenzione_database import esamina_tutti

        risultato = esamina_tutti(_radice_dati(), compattare=compattare)
        categoria = ("success" if risultato["ok"] else "warning") if compattare else "info"
        return _risposta(categoria, it(risultato["messaggio"]), esiti.spazio_database(risultato))

    return gestore


# ------------------------------------------------------------------ archivi degli studi


def _compattazione(applica: bool) -> Gestore:
    def gestore(dati: dict[str, str]) -> dict[str, Any]:
        from web.services.server_maintenance_surface import run_storage_compaction

        risultato = run_storage_compaction(apply=applica, tenant_slug=_studio(dati))
        if applica:
            compattati = int(risultato.get("hardlinked_files", 0) or 0)
            messaggio = f"Compattazione completata: {compattati} file compattati ora, recuperati {risultato['bytes_reclaimed_label']}."
            return _risposta("success", messaggio, esiti.compattazione(risultato))
        duplicati = int(risultato.get("physical_duplicate_files", 0) or 0)
        messaggio = f"Analisi compattazione completata: {duplicati} file da compattare, spazio recuperabile {risultato['bytes_reclaimable_label']}."
        return _risposta("info", messaggio, esiti.compattazione(risultato))

    return gestore


def _ottimizzazione(applica: bool) -> Gestore:
    def gestore(dati: dict[str, str]) -> dict[str, Any]:
        from web.services.server_maintenance_surface import run_max_storage_optimization

        risultato = run_max_storage_optimization(apply=applica, tenant_slug=_studio(dati))
        if applica:
            return _risposta("success", f"Ottimizzazione completata: recuperati {risultato['bytes_reclaimed_label']}.", esiti.ottimizzazione_massima(risultato))
        messaggio = f"Analisi ottimizzazione completata: spazio recuperabile {risultato['bytes_reclaimable_label']}."
        return _risposta("info", messaggio, esiti.ottimizzazione_massima(risultato))

    return gestore


# ------------------------------------------------------------------ spazio sul disco


def _conservazione_backup(applica: bool) -> Gestore:
    def gestore(_dati: dict[str, str]) -> dict[str, Any]:
        from web.services.server_maintenance_surface import run_all_backup_retention

        r = run_all_backup_retention(apply=applica)
        if applica:
            messaggio = f"Conservazione dei backup applicata: {r['archives_deleted']} archivi rimossi, recuperati {r['bytes_reclaimed_label']}."
            return _risposta(_livello_errori(r), messaggio, esiti.conservazione_backup(r))
        messaggio = (
            "Analisi della conservazione dei backup completata: "
            f"{r['archives_to_delete']} archivi eliminabili, spazio recuperabile {r['bytes_reclaimable_label']}."
        )
        return _risposta("info", messaggio, esiti.conservazione_backup(r))

    return gestore


def _backup_ora(_dati: dict[str, str]) -> dict[str, Any]:
    from web.services.server_maintenance_surface import trigger_backup

    risultato = trigger_backup()
    if risultato["ok"]:
        return _risposta("success", f"Backup avviato in secondo piano (processo {risultato['pid']}).", esiti.avvio_backup(risultato))
    return _risposta("danger", f"Errore avvio backup: {risultato['error']}")


def _pulizia_servizi(_dati: dict[str, str]) -> dict[str, Any]:
    from web.services.server_maintenance_surface import run_docker_prune

    risultato = run_docker_prune(dry_run=False)
    if risultato.get("error"):
        messaggio = f"Pulizia della memoria temporanea dei servizi non completata: {risultato['error']}"
        return _risposta("warning", messaggio, esiti.pulizia_servizi(risultato))
    messaggio = f"Pulizia della memoria temporanea dei servizi completata: recuperati {risultato['bytes_reclaimed_label']}."
    return _risposta("success", messaggio, esiti.pulizia_servizi(risultato))


def _cartelle_escluse(applica: bool) -> Gestore:
    def gestore(_dati: dict[str, str]) -> dict[str, Any]:
        from web.services.server_maintenance_surface import run_inactive_tenant_cleanup

        r = run_inactive_tenant_cleanup(apply=applica)
        if applica:
            messaggio = f"Pulizia cartelle escluse completata: {r['directories_deleted']} cartelle rimosse, recuperati {r['bytes_reclaimed_label']}."
            return _risposta(_livello_errori(r), messaggio, esiti.cartelle_escluse(r))
        messaggio = f"Analisi cartelle escluse completata: {r['candidates_count']} cartelle eliminabili, spazio recuperabile {r['bytes_reclaimable_label']}."
        return _risposta("info", messaggio, esiti.cartelle_escluse(r))

    return gestore


def _analizza_manutenzione(_dati: dict[str, str]) -> dict[str, Any]:
    """Legge l'ultimo censimento notturno dello spazio, come la vista storica: non lo ricalcola."""
    from web.services.censimento_spazio import ORE_PRIMA_DI_DICHIARARLO_VECCHIO, eta_ore, ultimo_censimento

    censimento = ultimo_censimento(dict(current_app.config))
    if censimento is None:
        return _risposta(
            "warning",
            "Nessun censimento dello spazio disponibile: la scansione gira di notte. Per averlo subito, usa «Esegui adesso» "
            "sulla pianificazione «Censimento dello spazio su disco» in Pianificazioni.",
        )
    manutenzione = censimento["risultato"]
    ore = eta_ore(censimento)
    quando = "" if ore is None else f" (scansione di {int(ore)} ore fa)"
    livello = "warning" if (ore is not None and ore > ORE_PRIMA_DI_DICHIARARLO_VECCHIO) else "info"
    messaggio = f"Spazio recuperabile secondo l'ultimo censimento: {manutenzione.get('bytes_reclaimable_label')}{quando}."
    return _risposta(livello, messaggio, esiti.manutenzione_professionale(manutenzione))


def _applica_manutenzione(_dati: dict[str, str]) -> dict[str, Any]:
    from web.services.server_maintenance_surface import run_professional_server_maintenance

    r = run_professional_server_maintenance(apply=True)
    messaggio = f"Manutenzione professionale completata: recuperati {r['bytes_reclaimed_label']}."
    return _risposta(_livello_errori(r), messaggio, esiti.manutenzione_professionale(r))


def _pulizia_registri(_dati: dict[str, str]) -> dict[str, Any]:
    from web.services.server_maintenance_surface import run_system_log_cleanup

    r = run_system_log_cleanup(apply=True)
    return _risposta(_livello_errori(r), "Pulizia dei registri di sistema completata.", esiti.pulizia_registri(r))


def _normativa_globale(applica: bool) -> Gestore:
    def gestore(_dati: dict[str, str]) -> dict[str, Any]:
        from web.services.server_maintenance_surface import run_normativa_global_cleanup

        r = run_normativa_global_cleanup(apply=applica)
        if applica:
            return _risposta(_livello_errori(r), f"Pulizia normativa globale completata: recuperati {r['bytes_reclaimed_label']}.", esiti.normativa_globale(r))
        messaggio = f"Analisi normativa globale completata: backup duplicati recuperabili {r['bytes_reclaimable_label']}."
        return _risposta("info", messaggio, esiti.normativa_globale(r))

    return gestore


# ------------------------------------------------------------------ collegamento all'archivio dello studio


def _apri_archivio_studio(dati: dict[str, str]) -> dict[str, Any]:
    """Apre `/admin/studi/<slug>/database` (collegamento «Archivio» della riga dello studio)."""
    slug = str(dati.get("slug", "") or "").strip()
    if not slug or "/" in slug or slug.startswith("."):
        return esito(False, "Studio non indicato.", tone="warning")
    indirizzo = f"/admin/studi/{quote(slug, safe='')}/database"
    return {**esito(True, "Apertura dell'archivio dello studio.", tone="info"), "navigate": indirizzo}


#: chiave → (gestore, testo nei log, messaggio all'utente in caso di errore imprevisto).
AZIONI: dict[str, tuple[Gestore, str, str]] = {
    "analizza-copia-doppia-fascicoli": (_copia_doppia(False), "Analisi copia doppia fascicoli fallita", "Analisi non completata. Il dettaglio tecnico è nei log del server."),
    "applica-copia-doppia-fascicoli": (_copia_doppia(True), "Riscrittura copia doppia fascicoli fallita", "Riscrittura non completata. Il dettaglio tecnico è nei log del server."),
    "analizza-collegamenti-pec": (_collegamenti_pec(False), "Analisi collegamenti PEC fallita", "Analisi non completata. Il dettaglio tecnico è nei log del server."),
    "applica-collegamenti-pec": (_collegamenti_pec(True), "Ricollegamento PEC fallito", "Ricollegamento non completato. Il dettaglio tecnico è nei log del server."),
    "analizza-chunk-rag": (_frammenti_ricerca(False), "Analisi chunk RAG fallita", "Analisi non completata. Il dettaglio tecnico è nei log del server."),
    "applica-chunk-rag": (_frammenti_ricerca(True), "Rispezzatura chunk RAG fallita", "Rifacimento dei frammenti non completato. Il dettaglio tecnico è nei log del server."),
    "analizza-spazio-database": (_spazio_database(False), "Analisi spazio database fallita", "Analisi non completata. Il dettaglio tecnico è nei log del server."),
    "applica-compattazione-database": (_spazio_database(True), "Compattazione database fallita", "Compattazione non completata. Il dettaglio tecnico è nei log del server."),
    "analizza-compattazione": (_compattazione(False), "Errore analisi compattazione storage", "Errore durante l'analisi della compattazione degli archivi."),
    "compatta": (_compattazione(True), "Errore compattazione storage", "Errore durante la compattazione degli archivi."),
    "analizza-ottimizzazione-massima": (_ottimizzazione(False), "Errore analisi ottimizzazione storage", "Errore durante l'analisi dell'ottimizzazione degli archivi."),
    "applica-ottimizzazione-massima": (_ottimizzazione(True), "Errore ottimizzazione storage", "Errore durante l'ottimizzazione degli archivi."),
    "analizza-retention-backup": (_conservazione_backup(False), "Errore analisi retention backup", "Errore durante l'analisi della conservazione dei backup."),
    "applica-retention-backup": (_conservazione_backup(True), "Errore retention backup", "Errore durante l'applicazione della conservazione dei backup."),
    "backup-ora": (_backup_ora, "Errore avvio backup", "Errore durante l'avvio del backup."),
    "docker-prune": (_pulizia_servizi, "Errore docker prune", "Errore durante la pulizia della memoria temporanea dei servizi."),
    "analizza-cartelle-escluse": (_cartelle_escluse(False), "Errore analisi cartelle escluse", "Errore durante l'analisi delle cartelle escluse."),
    "elimina-cartelle-escluse": (_cartelle_escluse(True), "Errore pulizia cartelle escluse", "Errore durante la pulizia delle cartelle escluse."),
    "analizza-manutenzione-professionale": (_analizza_manutenzione, "Errore lettura censimento spazio", "Censimento dello spazio non leggibile. Il dettaglio tecnico è nei log del server."),
    "applica-manutenzione-professionale": (_applica_manutenzione, "Errore manutenzione professionale", "Errore durante la manutenzione professionale."),
    "pulisci-log-sistema": (_pulizia_registri, "Errore pulizia log sistema", "Errore durante la pulizia dei registri di sistema."),
    "analizza-normativa-globale": (_normativa_globale(False), "Errore analisi normativa globale", "Errore durante l'analisi della normativa globale."),
    "pulisci-normativa-globale": (_normativa_globale(True), "Errore pulizia normativa globale", "Errore durante la pulizia della normativa globale."),
    "apri-archivio-studio": (_apri_archivio_studio, "Errore apertura archivio dello studio", "Archivio dello studio non disponibile."),
}


def esegui(azione: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    voce = AZIONI.get(str(azione or "").strip())
    if voce is None:
        return esito(False, "Azione non disponibile in questa pagina.")
    gestore, registro, errore = voce
    try:
        return gestore({**(values or {}), **(params or {})})
    except Exception:
        current_app.logger.exception(registro)
        return esito(False, errore, tone="danger")


__all__ = ["AZIONI", "TONI_FLASH", "esegui"]
