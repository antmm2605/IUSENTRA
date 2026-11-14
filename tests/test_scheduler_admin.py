from __future__ import annotations

from pathlib import Path

from web.app import create_app

from tests.test_legal_updates_pipeline import _cfg_web, _seed_platform_superadmin, _write_studio_config



PANNELLO = "/api/v1/ui/piattaforma/pianificazioni"


def _azione(client, nome: str, params: dict | None = None, values: dict | None = None):
    """Azione della pagina React «Pianificazioni» (la stessa dei moduli storici)."""
    return client.post(f"{PANNELLO}/azioni/{nome}", json={"params": params or {}, "values": values or {}})

def test_superadmin_puo_aprire_console_pianificazioni(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    from pct.scheduler_notturno import finestra
    from pct.scheduler_notturno.registro import RegistroNotte
    from pct.scheduler_registry import scheduler_registry_repository

    ora = finestra.adesso()
    sera = finestra.sera_della_notte(ora).isoformat()
    registro = RegistroNotte(scheduler_registry_repository(app.config).db_path)
    registro.apri_notte(sera, 0, "", ora.isoformat())
    registro.scrivi_passo(sera, 0, 1, "mailbox_sync_runtime", "completato",
                          messaggio="Giro eseguito.", avvio=ora.isoformat(), fine=ora.isoformat(), avanza=True,
                          risultato={"totals": {"warnings": 2}})
    registro.scrivi_passo(sera, 1, 1, "pec_audit_pipeline_workers", "rinviato",
                          messaggio="Risorsa occupata. La sincronizzazione resta da eseguire.",
                          avvio=ora.isoformat(), fine=ora.isoformat(), avanza=True, conclusa=True)

    with app.test_client() as client:
        login = client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = client.get(PANNELLO)
        alias = client.get("/admin/cronjob", follow_redirects=False)

    assert login.status_code == 302
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Pianificazioni" in html
    assert "Agenti delegati disponibili" in html
    assert "Agenti fonte legale" in html
    assert "Fonte legale: Gazzetta Ufficiale" in html
    assert "Agente clienti e soggetti" in html
    assert "Agente email PEC" in html
    assert "Sequenza notturna" in html
    assert "Conclusa con verifiche da fare" in html
    assert "Risultati dei passi notturni" in html
    assert "2 avvisi registrati" in html
    assert "Risorsa occupata. La sincronizzazione resta da eseguire." in html
    assert alias.status_code == 302
    assert alias.headers["Location"].endswith("/admin/pianificazioni")


def test_console_distingue_il_passo_in_coda_dal_motore_attivo():
    from web.services.react_piattaforma_pagina_pianificazioni import adatta

    notte = {
        "stato": "In corso", "inizio": "21:30", "fine": "07:30",
        "prossimo": "pec_audit_pipeline_workers", "motore_prossimo": "pec_audit_pipeline_workers",
        "passo_avviato_alle": "2026-11-13T22:03:00+01:00",
    }
    semaforo = {
        "testo": "Lettura in corso", "in_corso": "Lettura del fascicolo", "da_secondi": 60,
        "motore_attivo": "letture del fascicolo", "motori_in_coda": ["pec_audit_pipeline_workers"],
    }
    payload = adatta({"sequenza_notturna": notte, "semaforo_motori": semaforo})
    fatti = next(s["items"] for s in payload["sections"] if s["title"] == "Sequenza notturna")
    assert {"label": "Stato del passo", "value": "In attesa del semaforo"} in fatti


def test_api_pianificazioni_non_espone_traceback(tmp_path: Path, monkeypatch):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    from web.blueprints import scheduler_admin as scheduler_admin_module

    monkeypatch.setattr(
        scheduler_admin_module,
        "build_scheduler_admin_surface",
        lambda: {
            "recent_runs": [
                {
                    "status": "failed",
                    "result": {
                        "error": "Traceback (most recent call last):\n  File \"C:\\Users\\studio\\app.py\"",
                        "exception": "RuntimeError: dettagli interni",
                    },
                }
            ],
            "registry_db": "C:\\Users\\studio\\scheduler.db",
        },
    )

    with app.test_client() as client:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = client.get("/admin/pianificazioni/api")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "Traceback" not in body
    assert "RuntimeError" not in body
    assert "C:\\Users" not in body
    assert "Dettaglio tecnico registrato nei log server." in body


def test_superadmin_crea_e_modifica_cronjob_agente(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        create = _azione(client, "crea", values={
                "template_key": "agent_clienti_soggetti",
                "name": "Controllo clienti serale",
                "trigger_kind": "cron",
                "hour": "22",
                "minute": "45",
                "interval_minutes": "60",
                "enabled": "1",
            })
        page = create.get_data(as_text=True) + client.get(PANNELLO).get_data(as_text=True)

    assert create.status_code == 200
    assert "Controllo clienti serale" in page
    assert "Ogni giorno alle 22:45" in page
    assert "agente delegato" in page


def test_superadmin_puo_richiedere_esecuzione_cronjob(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.test_client() as client:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = _azione(client, "esegui", params={"job_id": "legal_updates_batch"})
        html = response.get_data(as_text=True) + client.get(PANNELLO).get_data(as_text=True)

    assert response.status_code == 200
    assert "Esecuzione richiesta" in html
    assert "Richiesta" in html


def test_superadmin_annulla_fonti_legali_in_corso_senza_toccare_altri_job(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    username, password = _seed_platform_superadmin(app)

    with app.app_context():
        from pct.scheduler_registry import scheduler_registry_repository

        repo = scheduler_registry_repository(app.config)
        repo.upsert_default_jobs(app.config)
        with repo.connect() as conn:
            for run_id, job_id in (
                ("run-legal-source", "legal_source_cassazione_massimario"),
                ("run-legal-batch", "legal_updates_batch"),
                ("run-ai", "local_ai_maintenance"),
            ):
                conn.execute(
                    """
                    INSERT INTO scheduled_job_runs (
                        run_id, job_id, template_key, origin, status, scheduled_at,
                        started_at, finished_at, duration_ms, message, result_json,
                        error_message, requested_by, created_at
                    )
                    VALUES (?, ?, ?, 'scheduler', 'running',
                        '2026-05-17T13:00:00Z', '2026-05-17T13:00:00Z',
                        '', 0, 'Esecuzione in corso.', '{}', '', '', '2026-05-17T13:00:00Z')
                    """,
                    (run_id, job_id, job_id),
                )

    with app.test_client() as client:
        client.post("/login", data={"username": username, "password": password}, follow_redirects=False)
        response = _azione(client, "annulla-fonti")
        html = response.get_data(as_text=True) + client.get(PANNELLO).get_data(as_text=True)

    with app.app_context():
        repo = scheduler_registry_repository(app.config)
        with repo.connect() as conn:
            statuses = {
                row["run_id"]: row["status"]
                for row in conn.execute(
                    "SELECT run_id, status FROM scheduled_job_runs WHERE run_id IN ('run-legal-source', 'run-legal-batch', 'run-ai')"
                ).fetchall()
            }

    assert response.status_code == 200
    assert "Controlli delle fonti legali annullati: 2 esecuzioni aperte chiuse." in html
    assert "Archivio legale verificato" in html
    assert "Annullata" in html
    assert statuses == {
        "run-legal-source": "cancelled",
        "run-legal-batch": "cancelled",
        "run-ai": "running",
    }


def test_console_distingue_accodamento_dall_avvio_confermato():
    from datetime import UTC, datetime

    from web.services.scheduler_admin_surface import _job_status, _surface_run

    run = {"status": "running", "started_at": datetime.now(UTC).isoformat(),
           "result": {"event": "submitted"}}
    surfaced = _surface_run(run)
    assert _job_status({"enabled": True}, surfaced) == {
        "label": "Avvio non confermato", "class": "warning",
    }
    assert _job_status({"enabled": True}, _surface_run({**run, "result": {}}))["label"] == "In corso"
