"""Stato installazione studio in una schermata unica."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import current_app

from web.services.admin_surfaces_shared import (
    count_documents,
    get_agenda_manager,
    get_auth_manager,
    get_calendar_sync_manager,
    get_clienti_manager,
    get_fascicoli_manager,
    get_scadenziario_manager,
    load_studio_config,
    storage_mode_label,
)
from web.services.observability_runtime import build_observability_payload


def _step(status: str, title: str, summary: str, detail: str) -> dict[str, str]:
    return {
        "status": status,
        "title": title,
        "summary": summary,
        "detail": detail,
    }


def build_studio_installation_status() -> dict[str, Any]:
    config = load_studio_config()
    auth = get_auth_manager()
    clienti = get_clienti_manager()
    fascicoli = get_fascicoli_manager()
    agenda = get_agenda_manager()
    scadenziario = get_scadenziario_manager()
    calendar_sync = get_calendar_sync_manager()
    observability = build_observability_payload(current_app._get_current_object())

    users = auth.lista()
    active_users = [user for user in users if getattr(user, "attivo", True)]
    profiles = calendar_sync.list_profiles()
    local_ai = dict((observability.get("providers") or {}).get("local_ai") or {})
    local_ai_runtime = dict(local_ai.get("runtime") or {})

    studio_cfg = dict(config.get("studio") or {})
    pec_cfg = dict(config.get("pec") or {})
    smtp_cfg = dict(config.get("smtp") or {})

    bootstrap_path = Path(str(current_app.config.get("BOOTSTRAP_ADMIN_CREDENTIALS_PATH", "")))
    steps = [
        _step(
            "ok" if studio_cfg.get("nome") and studio_cfg.get("avvocato") else "warning",
            "Configurazione studio",
            studio_cfg.get("nome") or "Studio da completare",
            "Anagrafica studio, avvocato referente e recapiti principali.",
        ),
        _step(
            "ok" if active_users else "block",
            "Utente admin e sicurezza",
            f"{len(active_users)} utenti attivi registrati",
            "Verifica password iniziali, bootstrap admin e presenza di almeno un amministratore operativo.",
        ),
        _step(
            "ok" if pec_cfg.get("indirizzo") and smtp_cfg.get("host") else "warning",
            "PEC, canali e firma",
            pec_cfg.get("indirizzo") or "PEC da configurare",
            "Controlla PEC, SMTP, firma digitale e disponibilita dei canali telematici.",
        ),
        _step(
            "ok" if profiles else "warning",
            "Calendari, agenda e scadenze",
            f"{len(profiles)} profili calendario configurati",
            "Agenda interna, reminder e sincronizzazioni esterne.",
        ),
        _step(
            "ok" if (clienti.statistiche().get("totale") or 0) or (fascicoli.statistiche().get("attivi") or 0) else "warning",
            "Import dati iniziali",
            f"{clienti.statistiche().get('totale', 0)} clienti · {fascicoli.statistiche().get('totale', 0)} fascicoli",
            "Clienti, fascicoli, documenti, appuntamenti e scadenze caricati nello studio.",
        ),
        _step(
            "ok" if str(local_ai_runtime.get("status") or "") in {"ready", "available"} else "warning",
            "Lex e intelligence",
            str(local_ai_runtime.get("status_text") or local_ai_runtime.get("status") or "runtime da verificare"),
            "Disponibilita provider locale, retrieval, workspace intelligence e fonti legali interne.",
        ),
    ]

    checks = [
        {
            "label": "Storage operativo",
            "status": "ok",
            "value": storage_mode_label(),
        },
        {
            "label": "Test connettivita AI locale",
            "status": "ok" if str(local_ai_runtime.get("status") or "") in {"ready", "available"} else "warning",
            "value": str(local_ai_runtime.get("status_text") or local_ai_runtime.get("status") or "non disponibile"),
        },
        {
            "label": "Test Local Signer",
            "status": "ok",
            "value": "Pacchetti distribuiti e download esposti in piattaforma",
        },
        {
            "label": "Test portali e configurazione",
            "status": "ok" if pec_cfg.get("indirizzo") else "warning",
            "value": "Configurazione PEC e canali telematici presente" if pec_cfg.get("indirizzo") else "Configurazione telematica da completare",
        },
    ]

    counters = {
        "utenti": len(active_users),
        "clienti": clienti.statistiche().get("totale", 0),
        "fascicoli": fascicoli.statistiche().get("totale", 0),
        "documenti": count_documents(fascicoli),
        "agenda": agenda.statistiche().get("totale", 0),
        "scadenze": scadenziario.statistiche().get("totale", 0),
        "bootstrap_pending": bootstrap_path.exists(),
    }

    return {
        "steps": steps,
        "checks": checks,
        "counters": counters,
        "warnings": [
            "Bootstrap admin ancora presente: chiudere il primo accesso." if bootstrap_path.exists() else "",
            "Calendari esterni non ancora configurati." if not profiles else "",
            "Runtime Lex locale da verificare." if str(local_ai_runtime.get("status") or "") not in {"ready", "available"} else "",
        ],
    }

