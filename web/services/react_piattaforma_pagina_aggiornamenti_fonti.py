"""Pagina «Fonti degli aggiornamenti legali» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/aggiornamenti-legali/fonti` (rotta
`sources_page`, modello `admin/legal_updates_sources.html`): totali del
catalogo, ciclo giornaliero, regole contro lo spreco, archivi ufficiali locali,
nuova fonte e famiglie di fonti con agente, acquisizione e modifica.

Le azioni chiamano gli stessi servizi delle rotte storiche:

- `crea` → `create_source` (`_upsert_source_from_payload` + `upsert_sources`);
- `modifica` → `update_source` (`get_source_by_id` + `upsert_sources`);
- `acquisisci` → `fetch_source` (`fetch_source_by_id(id, auto_publish=True)`);
- `esegui-agente` → `scheduler_admin.run_job` (`request_scheduler_run`);
- `scan` → `execute_action("scan")`.
"""

from __future__ import annotations

from typing import Any

from flask import current_app

from web.services.react_piattaforma_aggiornamenti_comune import (
    INDIRIZZI,
    azione_motore,
    collegamenti,
    data,
    esegui_motore,
    identificativo,
    leggibile,
    lessico,
    motore,
    unisci,
)
from web.services.react_piattaforma_sezioni import (
    _t,
    actions,
    azione,
    campo,
    data_ora,
    esito,
    form,
    link,
    metrics,
    notes,
    status,
    table,
)

CLASSI_FIDUCIA = (("A", "A · fonte primaria"), ("B", "B · fonte istituzionale"), ("C", "C · fonte secondaria"))
ETICHETTE_AGENTE = {"Timeout": "Tempo scaduto"}


def costruisci() -> dict[str, Any]:
    """Il catalogo della rotta storica `sources_page`.

    La rotta storica calcolava anche la superficie completa del motore e
    l'elenco grezzo delle fonti, che il modello non mostrava: qui si legge
    solo il catalogo, che contiene tutto ciò che la pagina espone."""
    from web.services.legal_update_surface import build_legal_source_catalog

    return build_legal_source_catalog(motore())


def _opzioni_fiducia(attuale: Any) -> list[tuple[str, str]]:
    valore = _t(attuale)
    voci = list(CLASSI_FIDUCIA)
    if valore and valore not in {v for v, _ in voci}:
        voci.append((valore, valore))
    return voci


def _campi_fonte(fonte: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    f = fonte or {}
    nuova = fonte is None
    return [
        campo("name", "Nome", value=f.get("name"), required=nuova, placeholder="Ente o sezione ufficiale"),
        *([campo("code", "Codice", required=True, placeholder="fonte_ufficiale", help="Identificativo tecnico unico della fonte.")] if nuova else []),
        campo("base_url", "Indirizzo della fonte", value=f.get("base_url"), required=nuova, placeholder="https://..."),
        campo("category", "Materia prevalente", value=f.get("category", "news"), placeholder="prassi"),
        campo("parser_type", "Metodo di lettura", value=f.get("parser_type", "html"), placeholder="html"),
        campo("trust_class", "Affidabilità", "select", value=f.get("trust_class", "B"), options=_opzioni_fiducia(f.get("trust_class", "B"))),
        campo("polling_minutes", "Frequenza in minuti", "number", value=f.get("polling_minutes", 720)),
        *([campo("source_type", "Canale", value="web", placeholder="web")] if nuova else []),
        campo("notes", "Scopo", "textarea", value=f.get("notes"), placeholder="Cosa deve presidiare per lo studio"),
        campo("is_official", "Fonte ufficiale", "checkbox", value=f.get("is_official", True)),
        campo("enabled", "Fonte attiva", "checkbox", value=f.get("enabled", True)),
    ]


def _agente(a: dict[str, Any]) -> str:
    origine = f"Ultimo controllo di prova: {_t(a.get('last_canary_message'))}" if a.get("is_canary") else (f"Origine del controllo: {_t(a.get('trigger_label_display'))}" if _t(a.get("trigger_label_display")) else "")
    concluso = unisci(data_ora(a.get("finished_at")), a.get("duration_label"), separatore=" - ")
    return unisci(ETICHETTE_AGENTE.get(_t(a.get("label")), a.get("label")), a.get("message"), origine, concluso)


def _riga_fonte(f: dict[str, Any]) -> dict[str, Any]:
    agente = f.get("agent") or {}
    presidio = unisci(f.get("method_label"), f.get("interval_label"), leggibile(f.get("category")), f"Elementi: {_t(f.get('item_strategy_label'))}", f"Dettaglio: {_t(f.get('detail_strategy_label'))}")
    stato = unisci(
        f.get("status_label"),
        f"classe {_t(f.get('trust_class'))}",
        f"Destinazione: {_t(f.get('publication_destination_label'))}",
        f"RAG: {_t(f.get('rag_destination'))}",
        f"Archivio giurisprudenza: {_t(f.get('jurisprudence_destination'))}" if _t(f.get("jurisprudence_destination_raw")) != "none" else "",
    )
    archivio = unisci(
        f"{_t(f.get('raw_documents'))} documenti",
        f"{_t(f.get('analyses'))} analisi",
        f"{_t(f.get('review_pending'))} in verifica" if f.get("review_pending") else "",
        "PDF richiesto" if f.get("pdf_required") else "PDF e allegati se presenti",
        f"OCR: {'abilitato' if f.get('ocr_allowed') else 'non previsto'}",
        f"Riferimenti e domande: {'attivi' if f.get('reference_extraction_enabled') and f.get('context_question_enabled') else 'non pubblicati'}",
    )
    controllo = unisci(
        data_ora(f.get("last_check_at")) or "Mai eseguito",
        f"ultimo contenuto {data(f.get('latest_source_date'), '')}" if _t(f.get("latest_source_date")) else "",
        f"Filtro: {_t(f.get('relevance_policy_label'))}",
        f"Scarto: {_t(f.get('exclusion_policy_label'))}",
    )
    nome = _t(f.get("name"))
    azioni = []
    if f.get("enabled"):
        azioni.append(azione("esegui-agente", "Esegui agente", tone="primary", params={"job_id": agente.get("job_id")}, confirm=f"Richiedere ora il controllo dell'agente di «{nome}»? Il worker lo prende in carico entro un minuto."))
        azioni.append(azione("acquisisci", "Acquisisci", params={"source_id": f.get("id")}, confirm=f"Acquisire ora i documenti di «{nome}»? L'operazione legge la fonte e pubblica i contenuti idonei."))
    azioni.append(azione("modifica", "Modifica", params={"source_id": f.get("id"), "code": f.get("code")}, fields=_campi_fonte(f)))
    return {
        "source": unisci(nome, f.get("base_url"), "aggiunta al catalogo professionale" if f.get("was_added_by_catalog") else ""),
        "presidio": presidio,
        "state": stato,
        "agent": _agente(agente),
        "archive": archivio,
        "checked": controllo,
        "_href": _t(f.get("base_url")),
        "_external": True,
        "_tone": "success" if f.get("enabled") else "",
        "_actions": azioni,
    }


def _famiglia(fam: dict[str, Any]) -> dict[str, Any]:
    conteggi = unisci(
        f"{_t(fam.get('active_count'))} attive",
        f"{_t(fam.get('official_count'))} ufficiali",
        f"{_t(fam.get('raw_documents'))} documenti",
        f"{_t(fam.get('review_pending'))} in verifica" if fam.get("review_pending") else "",
    )
    return table(
        lessico(fam.get("label")),
        [("source", "Fonte"), ("presidio", "Presidio"), ("state", "Stato"), ("agent", "Agente"), ("archive", "Archivio"), ("checked", "Ultimo controllo")],
        [_riga_fonte(f) for f in fam.get("sources") or []],
        subtitle=unisci(lessico(fam.get("description")), conteggi),
        empty="Nessuna fonte in questa famiglia.",
    )


def adatta(catalogo: dict[str, Any]) -> dict[str, Any]:
    tot = catalogo.get("totals") or {}
    runtime = catalogo.get("runtime") or {}
    ciclo = catalogo.get("progressive_scheduler") or {}
    arch = catalogo.get("official_archives") or {}
    normattiva, gazzetta = arch.get("normattiva") or {}, arch.get("gazzetta") or {}
    return {
        "title": "Gestore delle fonti",
        "subtitle": "Catalogo professionale delle fonti pubbliche: il ciclo giornaliero controlla prima ciò che abbiamo già, acquisisce solo novità o variazioni e avvia la verifica web con allegati quando serve.",
        "links": [link("Acquisizione", INDIRIZZI["acquisizione"], tone="primary"), *collegamenti("fonti")],
        "sections": [
            actions("Ricerca nelle fonti", [azione_motore("scan")]),
            metrics([
                {"label": "Fonti attive", "value": tot.get("active", 0), "note": f"su {_t(tot.get('sources', 0))} canali censiti"},
                {"label": "Ufficiali", "value": tot.get("official", 0), "note": "fonti primarie o istituzionali"},
                {"label": "Documenti letti", "value": tot.get("raw_documents", 0), "note": "deduplicati per fonte"},
                {"label": "Aggiunte IUSENTRA", "value": tot.get("added_by_catalog", 0), "note": "presidi scelti per studi legali"},
            ]),
            status("Ciclo giornaliero", [{"title": lessico(s.get("title")), "summary": lessico(s.get("body")), "status": "info", "statusLabel": s.get("time")} for s in catalogo.get("schedule") or []]),
            notes("Passo 1 del ciclo", [
                f"Passo 1: {', '.join(_t(c) for c in ciclo.get('enabled_source_codes') or [])}.",
                f"Ogni elemento ha un limite di {_t(runtime.get('item_timeout_seconds'))} secondi; vengono pubblicati al massimo {_t(runtime.get('publish_max_items'))} aggiornamenti idonei per ciclo, sempre con pubblicazione presidiata.",
                "Fonti fuori dal passo 1: ANAC e Garante restano in osservazione; Normattiva e Gazzetta sono presidiate dagli archivi ufficiali locali.",
            ], tone="info"),
            notes("Regole contro lo spreco", [lessico(r) for r in catalogo.get("policy") or []], tone="info"),
            metrics([
                {"label": "Normattiva locale", "value": normattiva.get("documents", 0), "note": f"{_t(normattiva.get('articles', 0))} articoli, {_t(normattiva.get('chunks', 0))} parti indicizzate · archivio già letto da Lex"},
                {"label": "Gazzetta locale", "value": gazzetta.get("documents", 0), "note": f"{_t(gazzetta.get('chunks', 0))} parti indicizzate da {_t(gazzetta.get('sources', 0))} raccolte · solo nuove uscite"},
            ], title="Archivi ufficiali locali"),
            form("Aggiungi una fonte", "crea", _campi_fonte(), submit_label="Salva fonte"),
            *[_famiglia(fam) for fam in catalogo.get("families") or []],
        ],
    }


# ------------------------------------------------------------------ azioni


def _crea(values: dict[str, str]) -> dict[str, Any]:
    from web.blueprints.legal_updates_admin import _upsert_source_from_payload

    try:
        riga = _upsert_source_from_payload(dict(values))
        motore().repository.upsert_sources([riga])
        return esito(True, "Fonte salvata correttamente.")
    except Exception as exc:
        current_app.logger.exception("Errore create_source")
        return esito(False, f"Errore salvataggio fonte: {exc}")


def _modifica(fonte_id: int, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    from web.blueprints.legal_updates_admin import _upsert_source_from_payload

    try:
        pipeline = motore()
        attuale = pipeline.repository.get_source_by_id(fonte_id)
        if not attuale:
            return esito(False, "Fonte non trovata.", tone="warning")
        # Come il modulo storico: il codice viaggia nascosto insieme ai campi modificati.
        pipeline.repository.upsert_sources([_upsert_source_from_payload({**values, "code": params.get("code", "")}, current_source=attuale)])
        return esito(True, "Fonte aggiornata.")
    except Exception as exc:
        current_app.logger.exception("Errore update_source %s", fonte_id)
        return esito(False, f"Errore aggiornamento fonte: {exc}")


def _acquisisci(fonte_id: int) -> dict[str, Any]:
    try:
        risultato = motore().fetch_source_by_id(fonte_id, auto_publish=True)
        return esito(True, f"Acquisizione completata: {risultato.get('documents_found', 0)} documenti trovati e {risultato.get('processed', 0)} processati.")
    except Exception as exc:
        current_app.logger.exception("Errore fetch_source %s", fonte_id)
        return esito(False, f"Errore acquisizione fonte: {exc}")


def _esegui_agente(job_id: str) -> dict[str, Any]:
    """`scheduler_admin.run_job`: stesso servizio, stesso utente, stessi messaggi."""
    from web.blueprints.scheduler_admin import _username
    from web.services.scheduler_admin_surface import request_scheduler_run

    try:
        request_scheduler_run(job_id, username=_username())
        return esito(True, "Esecuzione richiesta. Il worker la prende in carico senza bloccare la console.")
    except Exception:
        current_app.logger.exception("Errore richiesta esecuzione %s", job_id)
        return esito(False, "Esecuzione non richiesta. Dettaglio tecnico registrato nei log del server.")


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    if chiave == "scan":
        return esegui_motore("scan")
    if chiave == "crea":
        return _crea(values)
    if chiave == "esegui-agente":
        job_id = _t(params.get("job_id"))
        return _esegui_agente(job_id) if job_id else esito(False, "Agente della fonte non indicato.")
    fonte_id = identificativo(params.get("source_id"))
    if chiave in {"modifica", "acquisisci"} and fonte_id is None:
        return esito(False, "Fonte non trovata.", tone="warning")
    if chiave == "modifica":
        return _modifica(fonte_id, params, values)
    if chiave == "acquisisci":
        return _acquisisci(fonte_id)
    return esito(False, "Azione non disponibile in questa pagina.")


AZIONI = {"scan", "crea", "modifica", "acquisisci", "esegui-agente"}

__all__ = ["AZIONI", "adatta", "costruisci", "esegui"]
