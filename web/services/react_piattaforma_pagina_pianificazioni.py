"""Pagina «Pianificazioni» del pannello di piattaforma (React).

Sostituisce la vista storica `/admin/pianificazioni` (template
`admin/pianificazioni.html`): archivio legale verificato, totali, creazione di
una pianificazione da un agente autorizzato, controlli per famiglia con
esecuzione e modifica, esecuzioni recenti. Le azioni chiamano gli stessi
servizi di `web/blueprints/scheduler_admin.py`.
"""

from __future__ import annotations

from typing import Any

from flask import current_app, g

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

TIPI = (("cron", "Orario giornaliero"), ("interval", "Intervallo"), ("manual", "Solo manuale"))
TONI_BADGE = {"success": "success", "danger": "danger", "warning": "warning", "info": "info", "primary": "info"}


def costruisci() -> dict[str, Any]:
    from web.services.scheduler_admin_surface import build_scheduler_admin_surface

    return build_scheduler_admin_surface()


def _utente() -> str:
    return str(getattr(g.get("utente_corrente"), "username", "") or "superadmin")


def _campi_modifica(job: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        campo("name", "Nome", value=job.get("name")),
        campo("description", "Descrizione", value=job.get("description")),
        campo("trigger_kind", "Tipo", "select", value=job.get("trigger_kind"), options=(("cron", "Orario"), ("interval", "Intervallo"), ("manual", "Manuale"))),
        campo("hour", "Ora", value=job.get("hour")),
        campo("minute", "Minuto", value=job.get("minute")),
        campo("interval_minutes", "Intervallo in minuti", "number", value=job.get("interval_minutes")),
        campo("enabled", "Attiva", "select", value="1" if job.get("enabled") else "0", options=(("1", "Sì"), ("0", "No"))),
    ]


def _riga_job(job: dict[str, Any]) -> dict[str, Any]:
    ultimo = job.get("latest_run") or {}
    stato = job.get("status") or {}
    manuale_attiva = bool(job.get("enabled") and job.get("manual_only"))
    azioni = []
    if job.get("enabled"):
        azioni.append(azione("esegui", "Esegui", tone="primary", params={"job_id": job.get("job_id")}, confirm=f"Richiedere ora l'esecuzione di «{_t(job.get('name'))}»? Il worker la prende in carico entro un minuto."))
    if job.get("editable"):
        azioni.append(azione("salva", "Modifica", params={"job_id": job.get("job_id")}, fields=_campi_modifica(job)))
    esito_ultimo = " · ".join(
        x for x in (_t(ultimo.get("status_label")), data_ora(ultimo.get("finished_at") or ultimo.get("created_at")), _t(ultimo.get("message"))) if x
    ) if ultimo else "Nessun esito registrato"
    classe = "" if manuale_attiva else _t(stato.get("class"))
    return {
        "job": f"{_t(job.get('name'))} — {_t(job.get('description'))}" if _t(job.get("description")) else _t(job.get("name")),
        "schedule": f"{_t(job.get('schedule_label'))} · {'presidio di sistema' if job.get('built_in') else 'agente delegato'}",
        "state": _t(job.get("availability_label")) if manuale_attiva else _t(stato.get("label")),
        "last": esito_ultimo,
        "_tone": TONI_BADGE.get(classe, ""),
        "_actions": azioni,
    }


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    archivio = payload.get("legal_archive") or {}
    totali = payload.get("totals") or {}
    agenti = payload.get("agent_templates") or []
    sezioni: list[dict[str, Any]] = [
        actions("Controlli delle fonti legali", [
            azione("annulla-fonti", "Annulla controlli fonti legali", tone="danger", confirm="Chiudere le esecuzioni aperte dei controlli delle fonti legali che non hanno dato riscontro?"),
        ]),
        metrics(
            [
                {"label": "Riferimenti letti", "value": archivio.get("raw_documents", 0)},
                {"label": "Analisi create", "value": archivio.get("analyses", 0)},
                {"label": "Schede pubblicate", "value": archivio.get("published_cards", 0)},
                {"label": "Evidenze web", "value": archivio.get("web_evidence", 0)},
                {"label": "Allegati salvati", "value": archivio.get("web_evidence_attachments", 0)},
                {"label": "Da completare", "value": int(archivio.get("pending_reviews") or 0) + int(archivio.get("approved_reviews") or 0)},
            ],
            title=f"Archivio legale verificato · {_t(archivio.get('status_label'))}",
        ),
        notes("Archivio legale", [archivio.get("message"), "La console conta solo ciò che resta nel database e può essere recuperato dalla ricerca."], tone=TONI_BADGE.get(_t(archivio.get("status_class")), "info")),
        metrics([
            {"label": "Pianificazioni periodiche attive", "value": f"{totali.get('jobs_active_periodic', 0)} / {totali.get('jobs_periodic', 0)}", "note": f"solo manuali {totali.get('jobs_active_manual', 0)} / {totali.get('jobs_manual', 0)} · totale {totali.get('jobs_active', 0)} su {totali.get('jobs_total', 0)}"},
            {"label": "Create dalla console", "value": totali.get("jobs_custom", 0), "note": "solo da agenti autorizzati"},
            {"label": "Richieste in coda", "value": totali.get("runs_requested", 0), "note": "prese dal worker entro un minuto", "tone": "warning" if totali.get("runs_requested") else "neutral"},
            {"label": "Esiti da verificare", "value": totali.get("runs_failed", 0), "note": "ultime esecuzioni registrate", "tone": "danger" if totali.get("runs_failed") else "success"},
        ]),
    ]
    if agenti:
        sezioni.append(form(
            "Crea pianificazione",
            "crea",
            [
                campo("template_key", "Agente", "select", options=[(a.get("key"), a.get("name")) for a in agenti], required=True, value=agenti[0].get("key")),
                campo("name", "Nome della pianificazione", placeholder="Controllo serale clienti e soggetti"),
                campo("trigger_kind", "Tipo", "select", value="cron", options=TIPI),
                campo("hour", "Ora", value="22"),
                campo("minute", "Minuto", value="30"),
                campo("interval_minutes", "Intervallo in minuti", "number", value="60"),
            ],
            submit_label="Crea pianificazione",
            subtitle="Gli agenti delegati lavorano per dominio e devono riportare l'autoverifica.",
        ))
        sezioni.append(status(
            f"Agenti delegati disponibili ({len(agenti)} domini)",
            [{"title": a.get("name"), "summary": a.get("description"), "detail": f"Autoverifica: {_t((a.get('criteria') or [''])[0])}" if a.get("criteria") else "", "status": "info", "statusLabel": _t(a.get("family"))} for a in agenti],
            subtitle="Ogni agente deve dichiarare cosa ha controllato e perché non ha completato.",
        ))
    for famiglia in payload.get("families") or []:
        lavori = famiglia.get("jobs") or []
        sezioni.append(table(
            f"{_t(famiglia.get('name'))} ({len(lavori)} pianificazioni)",
            [("job", "Pianificazione"), ("schedule", "Frequenza"), ("state", "Stato"), ("last", "Ultimo esito")],
            [_riga_job(job) for job in lavori],
            subtitle="Modifica orari, metti in pausa o richiedi un'esecuzione senza aprire il server.",
        ))
    sezioni.append(table(
        "Esecuzioni recenti",
        [("when", "Quando"), ("job", "Pianificazione"), ("origin", "Origine"), ("result", "Esito"), ("message", "Messaggio")],
        [
            {
                "when": data_ora(r.get("started_at") or r.get("created_at") or r.get("finished_at")),
                "job": " · ".join(x for x in (_t(r.get("job_name") or r.get("job_id")), _t(r.get("job_family") or r.get("template_key"))) if x),
                "origin": r.get("origin"),
                "result": r.get("status_label"),
                "message": _t(r.get("message") or r.get("error_message")) or "Nessun dettaglio registrato",
                "_tone": TONI_BADGE.get(_t(r.get("status_class")), ""),
            }
            for r in payload.get("recent_runs") or []
        ],
        subtitle="Cosa ha fatto il worker, cosa è in coda e cosa non è riuscito.",
        empty="Nessuna esecuzione ancora registrata.",
    ))
    return {
        "title": "Pianificazioni",
        "subtitle": f"Controlli programmati, richieste manuali, esiti reali e agenti delegati governati da modelli autorizzati. Registro: {_t(payload.get('registry_db'))}",
        "links": [link("Dati della console", "/admin/pianificazioni/api", external=True), link("Osservabilità", "/admin/osservabilita")],
        "sections": sezioni,
    }


def esegui(chiave: str, params: dict[str, str], values: dict[str, str]) -> dict[str, Any]:
    from web.services.scheduler_admin_surface import (
        SchedulerConsoleError,
        cancel_legal_source_runs,
        create_scheduler_job_from_payload,
        request_scheduler_run,
        save_scheduler_job_from_payload,
    )

    job_id = params.get("job_id", "")
    try:
        if chiave == "salva":
            save_scheduler_job_from_payload(job_id, dict(values), username=_utente())
            return esito(True, "Pianificazione aggiornata. Il worker applicherà la modifica entro un minuto.")
        if chiave == "crea":
            creata = create_scheduler_job_from_payload({**values, "enabled": "1"}, username=_utente())
            return esito(True, f"Pianificazione creata: {_t(creata.get('name'))}.")
        if chiave == "esegui":
            request_scheduler_run(job_id, username=_utente())
            return esito(True, "Esecuzione richiesta. Il worker la prende in carico senza bloccare la console.")
        if chiave == "annulla-fonti":
            annullate = int(cancel_legal_source_runs(username=_utente()).get("cancelled") or 0)
            if annullate:
                return esito(True, f"Controlli delle fonti legali annullati: {annullate} esecuzioni aperte chiuse.")
            return esito(True, "Nessuna esecuzione delle fonti legali aperta da annullare.", tone="info")
    except SchedulerConsoleError as exc:
        return esito(False, str(exc), tone="warning")
    except Exception:
        current_app.logger.exception("Errore azione pianificazioni %s %s", chiave, job_id)
        return esito(False, "Operazione non completata. Il dettaglio tecnico è nei log del server.")
    return esito(False, "Azione non disponibile.")


AZIONI = {"salva", "crea", "esegui", "annulla-fonti"}
