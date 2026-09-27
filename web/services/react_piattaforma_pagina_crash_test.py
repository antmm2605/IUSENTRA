"""Crash test operativo e backup blindato per la shell React del pannello.

Sostituisce la pagina storica `/admin/crash-test-operativo` (blueprint
`web/blueprints/operational_resilience_admin.py`, template
`web/templates/admin/crash_test_operativo.html`) e i suoi due invii:
`/admin/crash-test-operativo/esegui` e `/admin/crash-test-operativo/backup`.

I dati restano quelli di `build_operational_crash_surface`: qui cambia solo la
forma (sezioni tipizzate); le azioni chiamano gli stessi servizi del modulo
storico con gli stessi argomenti e gli stessi esiti.
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

DOMANDE_CRITICHE = (
    "Posso rompere il DB e il sistema non fa danni?",
    "Posso spiegare ogni decisione AI?",
    "Un non tecnico capisce tutti gli errori?",
    "Posso migrare e tornare indietro senza paura?",
    "I dati sporchi NON entrano mai?",
)

STATI_SISTEMA = {
    "ok": ("success", "Regolare"),
    "degraded": ("warning", "Degradato"),
    "error": ("danger", "Errore"),
}

REGOLA_OPERATIVA = (
    "Questo pannello deve rendere il sistema impossibile da rompere e sempre spiegabile: se una fase fallisce, "
    "non si continua in silenzio; si genera il ticket, si salva il report, si pianifica il nuovo autotest e si "
    "conserva un backup completo e incrementale prima dei nuovi tentativi."
)


# ------------------------------------------------------------------ lettura


def costruisci(slug: str) -> dict[str, Any]:
    """Payload della pagina, come la rotta storica `dashboard()`."""
    from web.services.operational_resilience_surface import build_operational_crash_surface

    return build_operational_crash_surface(selected_slug=str(slug or "").strip().lower())


def _filtro_studio(contesto: dict[str, Any]) -> dict[str, Any] | None:
    scelte = contesto.get("tenant_choices") or []
    if not scelte:
        return None
    return {
        "name": "slug",
        "label": "Studio",
        "value": next((_t(s.get("slug")) for s in scelte if s.get("selected")), ""),
        "options": [{"value": _t(s.get("slug")), "label": f"{_t(s.get('nome'))} · {_t(s.get('slug'))} · {_t(s.get('selected_mode'))}"} for s in scelte],
    }


def _orari(piano: dict[str, Any]) -> str:
    autotest = ", ".join(_t(r.get("time")) for r in piano.get("crash_tests") or [] if _t(r.get("time")))
    backup = _t((piano.get("backup") or {}).get("time"))
    return f"Gli autotest di riparazione sono pianificati alle {autotest or 'n.d.'} e il backup completo e incrementale alle {backup or 'n.d.'}."


def _sezione_comandi(payload: dict[str, Any]) -> list[dict[str, Any]]:
    contesto = payload.get("context") or {}
    slug = _t(contesto.get("tenant_slug"))
    studio = [] if contesto.get("tenant_choices") else [("Studio attivo", contesto.get("studio_nome"))]
    return [
        facts("Studio e comandi operativi", studio + [
            ("Archivio strutturato", payload.get("backend_label")),
            ("Indirizzo dello studio", slug or "studio unico"),
        ]),
        actions(
            "Comandi operativi",
            [
                azione(
                    "esegui",
                    "Esegui crash test adesso",
                    tone="primary",
                    params={"slug": slug, "auto_repair": "1", "max_attempts": "3"},
                    confirm="Avviare ora il crash test operativo con riparazione automatica (fino a 3 tentativi)? L'esecuzione può richiedere alcuni minuti.",
                ),
                azione(
                    "backup",
                    "Esegui backup blindato",
                    params={"slug": slug},
                    confirm="Eseguire ora il backup blindato completo e incrementale dello studio?",
                ),
            ],
            subtitle=_orari(payload.get("schedule_plan") or {}),
        ),
    ]


def _sezione_pianificazione(piano: dict[str, Any]) -> dict[str, Any]:
    righe = [{"kind": "Autotest di riparazione", "label": r.get("label"), "time": r.get("time")} for r in piano.get("crash_tests") or []]
    backup = piano.get("backup") or {}
    righe.append({"kind": "Backup blindato", "label": backup.get("label"), "time": backup.get("time"), "_tone": "success"})
    return table("Pianificazione automatica", [("kind", "Tipo"), ("label", "Esecuzione"), ("time", "Orario")], righe)


def _esito_ultimo(ultimo: dict[str, Any]) -> tuple[str, str]:
    if not ultimo:
        return "Non eseguito", "neutral"
    return ("Operativo", "success") if ultimo.get("overall_ok") else ("Da correggere", "warning")


def _sezioni_ultimo_report(payload: dict[str, Any]) -> list[dict[str, Any]]:
    ultimo = payload.get("latest_report") or {}
    sommario = ultimo.get("summary") or {}
    etichetta, tono = _esito_ultimo(ultimo)
    return [
        metrics(
            [
                {"label": "Esito", "value": etichetta, "tone": tono, "note": "Esito persistito, ticket generati e verifica finale sì/no."},
                {"label": "Fasi presidiate", "value": sommario.get("phase_total") or 0, "note": "Fasi del crash test operativo"},
                {"label": "Fasi passate", "value": sommario.get("passed_phases") or 0, "note": f"Tentativi: {sommario.get('attempts') or 0}"},
                {"label": "Ticket di riparazione", "value": len(payload.get("repair_tickets") or []), "note": "Azioni operative ancora aperte"},
                {"label": "Ultimo report", "value": data_ora(ultimo.get("generated_at")) or "n.d.", "note": _t(ultimo.get("report_path")) or "Nessun report salvato"},
            ],
            title="Ultimo crash test reale",
        ),
        _sezione_domande(ultimo),
    ]


def _sezione_domande(ultimo: dict[str, Any]) -> dict[str, Any]:
    verifiche = ultimo.get("quick_checks") or [{"question": d, "ok": None} for d in DOMANDE_CRITICHE]
    voci = []
    for v in verifiche:
        esito = v.get("ok")
        stato, etichetta = ("success", "Sì") if esito is True else ("danger", "No") if esito is False else ("", "In attesa")
        voci.append({"title": v.get("question"), "status": stato, "statusLabel": etichetta})
    sottotitolo = "" if ultimo.get("quick_checks") else "Esegui il crash test per ottenere il risultato finale sì/no su tutte le domande critiche."
    return status("Domande critiche", voci, subtitle=sottotitolo)


def _sezione_fasi(ultimo: dict[str, Any]) -> dict[str, Any]:
    righe = [
        {
            "phase": f"{_t(f.get('label'))} — {_t(f.get('description'))}" if _t(f.get("description")) else f.get("label"),
            "state": "OK" if f.get("status") == "passed" else "Errore",
            "duration": f"{_t(f.get('duration_seconds'))} s",
            "output": _t(f.get("output_excerpt")) or "Nessun dettaglio disponibile.",
            "_tone": "success" if f.get("status") == "passed" else "danger",
        }
        for f in ultimo.get("phases") or []
    ]
    return table(
        "Fasi del crash test operativo",
        [("phase", "Fase"), ("state", "Stato"), ("duration", "Durata"), ("output", "Estratto operativo")],
        righe,
        empty="Nessuna esecuzione reale disponibile.",
    )


def _sezione_salute(salute: dict[str, Any]) -> dict[str, Any]:
    voci = []
    for chiave, titolo in (("scheduler", "Pianificatore"), ("ocr", "OCR"), ("ai", "AI locale"), ("db", "Database")):
        valore = _t(salute.get(chiave)).lower()
        tono, etichetta = STATI_SISTEMA.get(valore, ("", valore or "n.d."))
        voci.append({"title": titolo, "status": tono, "statusLabel": etichetta})
    return status("Stato del sistema in tempo reale", voci)


def _sezione_ticket(tickets: list[dict[str, Any]]) -> dict[str, Any]:
    if not tickets:
        return notes("Ticket di riparazione", ["Nessun ticket di riparazione aperto."], tone="success")
    voci = []
    for t in tickets:
        estratto = _t((t.get("payload_json") or {}).get("output_excerpt"))
        dettagli = [f"Codice intervento: {_t(t.get('action_code'))}", f"Estratto tecnico: {estratto}" if estratto else ""]
        grave = t.get("severity") == "danger"
        voci.append({
            "title": t.get("title"),
            "summary": t.get("remediation"),
            "detail": " · ".join(d for d in dettagli if d),
            "status": "danger" if grave else "warning",
            "statusLabel": "Critico" if grave else "Attenzione",
        })
    return status("Ticket di riparazione", voci)


def _sezioni_backup(payload: dict[str, Any]) -> list[dict[str, Any]]:
    esecuzioni = payload.get("backup_runs") or []
    if not esecuzioni:
        return [notes("Backup blindato e destinazioni", ["Nessun backup blindato registrato."], tone="info")]
    destinazioni = (payload.get("latest_backup_report") or {}).get("backup_targets") or {}
    ultimo = payload.get("latest_backup_payload") or {}
    locale = _t(destinazioni.get("local_target")) or (_t(ultimo.get("local_copy_path")) if ultimo else "") or "non configurata"
    righe = [
        {
            "type": r.get("backup_type"),
            "state": r.get("status"),
            "when": data_ora(r.get("executed_at")) or "n.d.",
            "copies": f"Locale: {'sì' if r.get('local_copy_path') else 'no'} · Esterna: {'sì' if r.get('secondary_copy_path') else 'no'}",
            "_tone": "success" if r.get("status") == "OK" else "danger",
        }
        for r in esecuzioni
    ]
    return [
        facts("Backup blindato e destinazioni", [
            ("Copia locale dello studio", locale),
            ("Destinazione secondaria", _t(destinazioni.get("secondary_target")) or "da stabilire (es. cartella sincronizzata Google Drive)"),
        ]),
        table("Backup blindati eseguiti", [("type", "Tipo"), ("state", "Stato"), ("when", "Eseguito"), ("copies", "Copie")], righe),
    ]


def adatta(payload: dict[str, Any]) -> dict[str, Any]:
    ultimo = payload.get("latest_report") or {}
    return {
        "title": "Crash test operativo",
        "subtitle": (
            "Simula una giornata reale di studio: dati sporchi, pubblicazione SQL, revisione AI, migrazione, ripristino, "
            "osservabilità e backup blindato, con report persistiti e ticket di riparazione."
        ),
        "links": [link("Salute del sistema in formato JSON", "/admin/system-health", external=True)],
        "filter": _filtro_studio(payload.get("context") or {}),
        "sections": [
            *_sezione_comandi(payload),
            _sezione_pianificazione(payload.get("schedule_plan") or {}),
            *_sezioni_ultimo_report(payload),
            _sezione_fasi(ultimo),
            _sezione_salute(payload.get("system_health") or {}),
            _sezione_ticket(list(payload.get("repair_tickets") or [])),
            *_sezioni_backup(payload),
            notes("Regola operativa", [REGOLA_OPERATIVA], tone="info"),
        ],
    }


# ------------------------------------------------------------------ azioni


def _valore(dati: dict[str, Any], nome: str, predefinito: str) -> str:
    """Come `request.form.get(nome, predefinito)`, con i tipi JSON riportati a testo."""
    valore = dati.get(nome)
    if valore is None:
        return predefinito
    if isinstance(valore, bool):
        return "1" if valore else "0"
    if isinstance(valore, float) and valore.is_integer():
        return str(int(valore))
    return str(valore)


def _nota_report(etichetta: str, report: dict[str, Any]) -> list[dict[str, Any]]:
    percorso = _t(report.get("report_path"))
    return [notes("Report", [f"{etichetta}: {percorso}"], tone="info")] if percorso else []


def _esegui_crash_test(dati: dict[str, Any]) -> dict[str, Any]:
    from flask import current_app

    from web.services.operational_resilience_surface import execute_operational_crash_surface

    slug = _valore(dati, "slug", "").strip().lower()
    auto_repair = str(_valore(dati, "auto_repair", "1") or "1").strip().lower() not in {"0", "false", "off", "no"}
    try:
        max_attempts = int(str(_valore(dati, "max_attempts", "3") or "3").strip() or 3)
    except ValueError:
        return {"ok": False, "message": "Numero massimo di tentativi non valido.", "tone": "danger", "sections": []}
    try:
        report = execute_operational_crash_surface(
            selected_slug=slug,
            trigger_source="manual",
            schedule_code="manual",
            auto_repair=auto_repair,
            max_attempts=max_attempts,
        )
    except Exception:
        current_app.logger.exception("Errore crash test operativo")
        return {"ok": False, "message": "Errore durante il crash test operativo.", "tone": "danger", "sections": []}
    if report.get("overall_ok"):
        esito = {"ok": True, "message": "Crash test operativo completato con esito verde.", "tone": "success"}
    else:
        esito = {"ok": True, "message": "Crash test operativo completato con criticità tracciate e ticket di riparazione.", "tone": "warning"}
    return {**esito, "sections": _nota_report("Report generato", report)}


def _esegui_backup(dati: dict[str, Any]) -> dict[str, Any]:
    from flask import current_app

    from web.services.operational_resilience_surface import execute_operational_backup_surface

    slug = _valore(dati, "slug", "").strip().lower()
    try:
        report = execute_operational_backup_surface(selected_slug=slug, trigger_source="manual", schedule_code="manual")
    except Exception:
        current_app.logger.exception("Errore backup blindato")
        return {"ok": False, "message": "Errore durante il backup blindato.", "tone": "danger", "sections": []}
    if report.get("skipped"):
        esito = {"ok": True, "message": "Archivi e copie sono disattivati dalla politica operativa dello studio.", "tone": "info"}
    elif report.get("success"):
        esito = {"ok": True, "message": "Backup blindato completo e incrementale eseguito correttamente.", "tone": "success"}
    else:
        esito = {"ok": True, "message": "Backup blindato eseguito con errori: controlla il report operativo.", "tone": "warning"}
    return {**esito, "sections": _nota_report("Report del backup", report)}


AZIONI = {"esegui": _esegui_crash_test, "backup": _esegui_backup}


def esegui(azione: str, params: dict[str, Any], values: dict[str, Any]) -> dict[str, Any]:
    gestore = AZIONI.get(str(azione or "").strip())
    if gestore is None:
        return {"ok": False, "message": "Azione non disponibile in questa pagina.", "tone": "danger", "sections": []}
    return gestore({**(values or {}), **(params or {})})


__all__ = ["adatta", "costruisci", "esegui"]
