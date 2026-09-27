"""Assistente alla migrazione dei dati dello studio per la shell React.

Sostituisce la pagina storica `/admin/assistente-migrazione` (rotte
`assistente_migrazione` e `assistente_migrazione_esegui` in
`web/blueprints/admin.py`, template `web/templates/admin/assistente_migrazione.html`).

I dati restano quelli di `build_migration_assistant`; l'esecuzione chiama
`execute_migration_assistant` e tiene in sessione lo stesso stato
(`assistente_migrazione_last_execution`) del modulo storico, con gli stessi
messaggi pubblici di errore.
"""

from __future__ import annotations

from typing import Any

from web.services.react_piattaforma_sezioni import (
    _t,
    actions,
    azione,
    data_ora,
    facts,
    link,
    metrics,
    notes,
    status,
    table,
)

CHIAVE_SESSIONE = "assistente_migrazione_last_execution"

MODALITA = {"JSON": "JSON", "SQLITE": "SQL locale (SQLite)", "POSTGRESQL": "PostgreSQL", "MYSQL": "MySQL", "json": "JSON", "sqlite": "SQL locale (SQLite)", "postgresql": "PostgreSQL"}

STRUTTURE = {"core": "Dominio principale", "repository": "Archivio strutturato", "sqlite_repository": "Archivio SQL locale", "sql_pipeline": "Flusso SQL", "filesystem": "File dello studio", "json": "JSON"}

ESITI = {"success": "OK", "warning": "Attenzione", "danger": "Errore"}


def _modo(valore: Any) -> str:
    return MODALITA.get(_t(valore), _t(valore))


def _esito(stato: Any, altrimenti: str = "Nota") -> str:
    return ESITI.get(_t(stato), altrimenti)


# ------------------------------------------------------------------ lettura


def costruisci(slug: str) -> dict[str, Any]:
    """Payload della pagina, come la rotta storica `assistente_migrazione()`."""
    from flask import session

    from web.services.migration_assistant import build_migration_assistant

    return build_migration_assistant(selected_slug=str(slug or ""), execution_state=session.get(CHIAVE_SESSIONE))


def _filtro_studio(studi: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not studi:
        return None
    return {
        "name": "slug",
        "label": "Studio",
        "value": next((_t(s.get("slug")) for s in studi if s.get("selected")), ""),
        "options": [{"value": _t(s.get("slug")), "label": f"{_t(s.get('nome'))} · {_t(s.get('slug'))} · {_modo(s.get('db_mode'))}"} for s in studi],
    }


def _sezioni_studio(payload: dict[str, Any]) -> list[dict[str, Any]]:
    studio = payload.get("selected_studio") or {}
    slug = _t(studio.get("slug"))
    postgres = bool(payload.get("can_run_postgres"))
    voci = [
        azione(
            "esegui",
            "Esegui migrazione completa su SQL locale",
            tone="primary",
            params={"slug": slug, "target": "sqlite"},
            confirm="Eseguire ora la migrazione completa dello studio sul database SQL locale? L'archivio configurato dello studio verrà aggiornato.",
        )
    ]
    if postgres:
        voci.append(azione(
            "esegui",
            "Esegui migrazione completa su PostgreSQL",
            params={"slug": slug, "target": "postgresql"},
            confirm="Eseguire ora precontrollo della connessione, migrazione completa e passaggio definitivo dello studio su PostgreSQL?",
        ))
    if postgres and _t(studio.get("selected_mode")) != "POSTGRESQL":
        nota = "Credenziali PostgreSQL già rilevate per questo studio: il pulsante esegue precontrollo della connessione, migrazione completa e passaggio reale."
    elif not postgres:
        nota = "Per il passaggio a PostgreSQL servono host, database, utente e password salvati nello studio selezionato."
    else:
        nota = ""
    return [
        facts("Studio selezionato", [
            ("Studio", studio.get("nome")),
            ("Archivio configurato", _modo(studio.get("selected_mode"))),
            ("Archivio effettivo", _modo(studio.get("effective_runtime_kind"))),
        ]),
        actions("Esecuzione della migrazione", voci, subtitle=nota),
    ]


def _sezioni_ultima_esecuzione(esecuzione: dict[str, Any]) -> list[dict[str, Any]]:
    riuscita = bool(esecuzione.get("success"))
    return [
        facts("Ultima esecuzione reale", [
            ("Esito", esecuzione.get("status_label")),
            ("Sintesi", esecuzione.get("headline")),
            ("Destinazione", esecuzione.get("target_label")),
            ("Generato il", data_ora(esecuzione.get("generated_at"))),
            ("Report persistito", esecuzione.get("report_path")),
        ]),
        metrics(
            [{"label": c.get("label"), "value": c.get("value"), "note": c.get("detail"), "tone": "success" if riuscita else "danger"} for c in esecuzione.get("summary_cards") or []],
            title="Risultato vero dell'ultimo lancio, non un riepilogo teorico",
        ),
        status("Punti di controllo", [
            {"title": c.get("title"), "summary": c.get("detail"), "status": c.get("status"), "statusLabel": _esito(c.get("status"))}
            for c in esecuzione.get("checkpoints") or []
        ]),
    ]


def _sezione_ultimo_report(report: dict[str, Any]) -> dict[str, Any]:
    riga = " · ".join([
        f"Destinazione: {(_t(report.get('target')) or 'n.d.').upper()}",
        f"Generato il {data_ora(report.get('generated_at')) or 'n.d.'}",
        f"Esito: {'OK' if report.get('success') else 'ATTENZIONE'}",
    ])
    return notes("Ultimo report disponibile", [riga, report.get("_path")], tone="info")


def _sezione_domini(esecuzione: dict[str, Any]) -> dict[str, Any]:
    if esecuzione.get("show_consistency_table"):
        colonne = [("label", "Dominio"), ("json_count", "JSON"), ("sqlite_count", "SQLite"), ("postgres_count", "PostgreSQL")]
    else:
        colonne = [("label", "Dominio"), ("migrated_count", "Record migrati")]
    colonne += [("status_label", "Esito"), ("note", "Note")]
    righe = [{**r, "_tone": _t(r.get("status"))} for r in esecuzione.get("core_rows") or []]
    return table("Dettaglio dei domini principali", colonne, righe, empty="Nessun dominio principale disponibile nel report corrente.")


def _sezione_archivi(esecuzione: dict[str, Any]) -> dict[str, Any]:
    righe = esecuzione.get("repository_rows") or []
    if not righe:
        return notes("Archivi strutturati", ["Nessun archivio laterale disponibile nel report corrente."], tone="info")
    return status("Archivi strutturati", [{"title": r.get("label"), "summary": r.get("detail"), "status": r.get("status"), "statusLabel": r.get("status_label")} for r in righe])


def _sezioni_errori(esecuzione: dict[str, Any]) -> list[dict[str, Any]]:
    errori = esecuzione.get("errors") or []
    passi = [f"{n}. {_t(p)}" for n, p in enumerate(esecuzione.get("resolution_steps") or [], start=1)]
    return [
        notes("Errori reali emersi", errori, tone="danger") if errori else notes("Errori reali emersi", ["Nessun errore bloccante nel report corrente."], tone="success"),
        notes("Come risolvere" if errori else "Verifiche finali consigliate", passi, tone="info"),
        notes("Avvisi del motore", list(esecuzione.get("warnings") or []), tone="warning"),
    ]


def _sezione_differenze(esecuzione: dict[str, Any]) -> list[dict[str, Any]]:
    righe = esecuzione.get("diff_rows") or []
    if not righe:
        return []
    sommario = esecuzione.get("diff_summary") or {}
    return [table(
        "Differenze prima e dopo la migrazione",
        [("title", "Dominio"), ("source_count", _t(sommario.get("source_label")) or "Origine"), ("destination_count", _t(sommario.get("destination_label")) or "Destinazione"), ("delta", "Differenza"), ("status_label", "Esito")],
        [{**r, "_tone": _t(r.get("status"))} for r in righe],
        subtitle=f"{sommario.get('matched') or 0}/{sommario.get('rows_total') or 0} allineati",
    )]


def _sezione_istantanea(esecuzione: dict[str, Any]) -> dict[str, Any]:
    istantanea = esecuzione.get("precheck_snapshot") or {}
    if not istantanea:
        return notes("Istantanea prima della migrazione", ["Nessuna istantanea pre-migrazione disponibile nel report corrente."], tone="info")
    return facts("Istantanea prima della migrazione", [
        ("Generata il", data_ora(istantanea.get("generated_at")) or "n.d."),
        ("Sorgente", _t(istantanea.get("source_label")) or "n.d."),
        ("Destinazione", _t(istantanea.get("destination_label")) or "n.d."),
        ("Domini censiti", istantanea.get("domains_total") or 0),
        ("Backup dello studio", _t(istantanea.get("backup_dir")) or "n.d."),
        ("Istantanea persistita", istantanea.get("snapshot_path")),
        ("Nota", istantanea.get("note")),
    ])


def _sezione_registro(esecuzione: dict[str, Any]) -> dict[str, Any]:
    voci = esecuzione.get("operation_log") or []
    if not voci:
        return notes("Registro operativo della migrazione", ["Nessun registro operativo disponibile nel report corrente."], tone="info")
    return status("Registro operativo della migrazione", [
        {"title": v.get("label"), "summary": v.get("detail"), "status": v.get("status"), "statusLabel": _esito(v.get("status"), "Errore")} for v in voci
    ])


def _sezione_anomalie(esecuzione: dict[str, Any]) -> dict[str, Any]:
    titolo = "Dati dello studio non coerenti e modalità di guasto"
    rilievi = esecuzione.get("dirty_findings") or []
    if rilievi:
        return status(titolo, [
            {"title": r.get("title"), "summary": r.get("detail"), "detail": f"Ripristino: {_t(r.get('recovery'))}", "status": "danger" if r.get("severity") == "danger" else "warning", "statusLabel": r.get("code")}
            for r in rilievi
        ])
    guasti = esecuzione.get("failure_modes") or []
    if guasti:
        return status(titolo, [
            {"title": g.get("title"), "summary": g.get("recovery"), "status": "danger" if g.get("severity") == "danger" else "warning", "statusLabel": g.get("code")}
            for g in guasti
        ])
    return notes(titolo, ["Nessun dato non coerente rilevato nel report corrente: nessun riferimento orfano, disallineamento o modalità di guasto aperta."], tone="success")


def _sezioni_ripristino(esecuzione: dict[str, Any]) -> list[dict[str, Any]]:
    ripristino = esecuzione.get("rollback") or {}
    titolo = "Ritorno indietro e ripristino guidato"
    if not ripristino:
        return [notes(titolo, ["Nessuna procedura di ritorno indietro disponibile nel report corrente."], tone="info")]
    stato = _t(ripristino.get("status"))
    return [
        status(titolo, [{
            "title": ripristino.get("label"),
            "summary": ripristino.get("detail"),
            "detail": f"Comando guidato: {_t(ripristino.get('command'))}" if _t(ripristino.get("command")) else "",
            "status": stato or "info",
            "statusLabel": "OK" if stato == "success" else "Attenzione" if stato == "warning" else "Nota",
        }]),
        notes("Passi di ripristino", [f"{n}. {_t(p)}" for n, p in enumerate(ripristino.get("steps") or [], start=1)], tone="info"),
    ]


def _sezioni_esecuzione(payload: dict[str, Any]) -> list[dict[str, Any]]:
    esecuzione = payload.get("last_execution")
    if not esecuzione:
        report = payload.get("latest_report")
        return [_sezione_ultimo_report(report)] if report else []
    return [
        *_sezioni_ultima_esecuzione(esecuzione),
        _sezione_domini(esecuzione),
        _sezione_archivi(esecuzione),
        *_sezioni_errori(esecuzione),
        *_sezione_differenze(esecuzione),
        _sezione_istantanea(esecuzione),
        _sezione_registro(esecuzione),
        _sezione_anomalie(esecuzione),
        *_sezioni_ripristino(esecuzione),
    ]


def _sezioni_inventario(payload: dict[str, Any]) -> list[dict[str, Any]]:
    inventario = payload.get("inventory") or {}
    programma = payload.get("migration_program") or {}
    righe = [
        {**d, "domain": f"{_t(d.get('title'))} ({_t(d.get('code'))})", "kind": STRUTTURE.get(_t(d.get("storage_kind")), _t(d.get("storage_kind")))}
        for d in inventario.get("domains") or []
    ]
    return [
        notes("Percorso consigliato", list(payload.get("workflow") or []), tone="info"),
        metrics(
            [
                {"label": m.get("title"), "value": m.get("count"), "note": f"{'Pronto' if m.get('status') == 'ok' else 'Da completare'} · {_t(m.get('next_step'))}", "tone": "success" if m.get("status") == "ok" else "warning"}
                for m in payload.get("modules") or []
            ] + [{"label": "Modelli base disponibili", "value": payload.get("built_in_templates", 0), "note": "Modelli predefiniti pronti come base per l'importazione e la standardizzazione."}],
            title="Elementi attualmente disponibili",
        ),
        table(
            "Inventario reale degli archivi",
            [("domain", "Dominio"), ("json_count", "Origine"), ("sqlite_count", "SQLite / SQL locale"), ("postgres_count", "PostgreSQL"), ("kind", "Struttura"), ("note", "Note")],
            righe,
            subtitle=f"PostgreSQL raggiungibile: {'sì' if inventario.get('postgres_online') else 'no'}",
        ),
        status(
            "Programma di migrazione degli archivi",
            [
                {"title": f.get("title"), "summary": f.get("objective"), "detail": f"Controlli di coerenza: {' | '.join(_t(x) for x in f.get('consistency_checks') or [])} · Ripiego: {' | '.join(_t(x) for x in f.get('fallback_rules') or [])}", "status": "info", "statusLabel": f"Fase {n}"}
                for n, f in enumerate(programma.get("phases") or [], start=1)
            ],
            subtitle=f"Domini SQLite pronti in lettura e scrittura: {_t((payload.get('storage_parity') or {}).get('sqlite_rw_ready')) or '0'}",
        ),
    ]


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    pagina = {
        "title": "Assistente migrazione dati",
        "subtitle": (
            "Esegue davvero la migrazione dello studio per clienti, fascicoli, agenda, scadenze, documenti e archivi SQL estesi, "
            "con report persistito nel backup dello studio."
        ),
    }
    if not payload.get("selected_studio"):
        return {
            **pagina,
            "links": [link("Nuovo studio", "/admin/studi/nuovo", tone="primary")],
            "sections": [notes("Nessuno studio disponibile", ["Nessuno studio disponibile. Crea prima uno studio dal pannello di amministrazione."], tone="warning")],
        }
    return {
        **pagina,
        "filter": _filtro_studio(list(payload.get("studios") or [])),
        "sections": [*_sezioni_studio(payload), *_sezioni_esecuzione(payload), *_sezioni_inventario(payload)],
    }


# ------------------------------------------------------------------ azioni


def _testo(dati: dict[str, Any], nome: str) -> str:
    valore = dati.get(nome)
    return str("" if valore is None else valore).strip().lower()


def _esegui_migrazione(dati: dict[str, Any]) -> dict[str, Any]:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from flask import current_app, session

    from web.services.migration_assistant import execute_migration_assistant

    selected_slug = _testo(dati, "slug")
    target = _testo(dati, "target")
    try:
        report = execute_migration_assistant(selected_slug=selected_slug, target=target)
        session[CHIAVE_SESSIONE] = {
            "slug": selected_slug,
            "target": target,
            "report_path": str(report.get("report_path") or "").strip(),
            "generated_at": str(report.get("generated_at") or datetime.now(ZoneInfo("Europe/Rome")).replace(microsecond=0).isoformat()),
        }
    except Exception as exc:
        current_app.logger.exception("Errore assistente migrazione %s", target)
        error_text = str(exc or "").strip().lower()
        public_error = (
            "Connessione PostgreSQL non disponibile."
            if target == "postgresql" and ("connessione" in error_text or "connect" in error_text)
            else "Migrazione non completata."
        )
        session[CHIAVE_SESSIONE] = {
            "slug": selected_slug,
            "target": target,
            "generated_at": datetime.now(ZoneInfo("Europe/Rome")).replace(microsecond=0).isoformat(),
            "error_message": public_error,
        }
        return {"ok": False, "message": "Errore durante la migrazione completa.", "tone": "danger", "sections": []}
    messaggio = (
        "Migrazione completa su PostgreSQL eseguita con report reale."
        if target == "postgresql"
        else "Migrazione completa su SQL locale eseguita con report reale."
    )
    percorso = str(report.get("report_path") or "").strip()
    sezioni = [notes("Report", [f"Report generato: {percorso}"], tone="info")] if percorso else []
    return {"ok": True, "message": messaggio, "tone": "success", "sections": sezioni}


AZIONI = {"esegui": _esegui_migrazione}


def esegui(azione: str, params: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    gestore = AZIONI.get(str(azione or "").strip())
    if gestore is None:
        return {"ok": False, "message": "Azione non disponibile in questa pagina.", "tone": "danger", "sections": []}
    return gestore({**(values or {}), **(params or {})})


__all__ = ["adatta", "costruisci", "esegui"]
