from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from pct.scheduler import start_scheduler


def test_local_ai_maintenance_salta_su_runtime_cloud_hosted(monkeypatch):
    monkeypatch.setenv("RAILWAY_PROJECT_ID", "proj-test")
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
    )

    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job("local_ai_maintenance")
        assert job is not None

        import pct.local_ai as local_ai_module

        class ForbiddenLocalAIService:
            def __init__(self, *args, **kwargs):
                raise AssertionError("LocalAIService non deve partire su runtime cloud-hosted")

        monkeypatch.setattr(local_ai_module, "LocalAIService", ForbiddenLocalAIService)
        job.func()
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
        monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)


def test_local_ai_maintenance_disabilitata_di_default_su_server(monkeypatch):
    monkeypatch.delenv("RAILWAY_PROJECT_ID", raising=False)
    monkeypatch.delenv("IUSENTRA_LOCAL_AI_MAINTENANCE_ENABLED", raising=False)
    monkeypatch.delenv("PCT_LOCAL_AI_MAINTENANCE_ENABLED", raising=False)
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
    )

    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job("local_ai_maintenance")
        assert job is not None

        import pct.local_ai as local_ai_module

        class ForbiddenLocalAIService:
            def __init__(self, *args, **kwargs):
                raise AssertionError("LocalAIService non deve partire senza opt-in esplicito")

        monkeypatch.setattr(local_ai_module, "LocalAIService", ForbiddenLocalAIService)
        result = job.func()

        assert result["ok"] is True
        assert result["status"] == "disabled_by_default"
        assert result["totals"]["targets"] == 0
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_mailbox_sync_runtime_job_usa_limite_automatico(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    calls: list[dict[str, object]] = []

    import web.services.mailbox_sync_runtime as mailbox_runtime

    def fake_sync_mailboxes_for_paths(
        paths,
        *,
        tenant_label: str,
        cooldown_seconds: float,
        limite: int,
        incremental_only: bool,
    ):
        calls.append(
            {
                "tenant_label": tenant_label,
                "cooldown_seconds": cooldown_seconds,
                "limite": limite,
                "incremental_only": incremental_only,
                "paths": paths,
            }
        )
        return {
            "ok": True,
            "pec": {"ok": True, "skipped": False, "reason": "", "result": {"nuove": 1}},
            "ordinary": {"ok": True, "skipped": False, "reason": "", "result": {"nuove": 2}},
        }

    monkeypatch.setattr(mailbox_runtime, "sync_mailboxes_for_paths", fake_sync_mailboxes_for_paths)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        IUSENTRA_MAILBOX_SYNC_AUTOMATIC_LIMIT=250,
        EMAIL_CASELLA_DB=str(tmp_path / "email" / "casella.json"),
        EMAIL_ORDINARIA_DB=str(tmp_path / "email" / "ordinaria.json"),
        FASCICOLI_DB=str(tmp_path / "fascicoli" / "fascicoli.json"),
        FASCICOLI_DOCS=str(tmp_path / "fascicoli" / "documenti"),
        FASCICOLI_ARCH=str(tmp_path / "fascicoli" / "archivio"),
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
    )

    scheduler = start_scheduler(app)
    try:
        result = scheduler.get_job("mailbox_sync_runtime").func()

        assert result["ok"] is True
        assert result["automatic_limit"] == 100
        assert result["incremental_only"] is True
        assert calls
        assert calls[0]["limite"] == 100
        assert calls[0]["incremental_only"] is True
        assert calls[0]["cooldown_seconds"] == 180.0
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_scheduler_polling_pec_cappa_finestre_automatiche(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    calls: dict[str, int] = {}

    import pct.config_studio as config_studio_module
    import pct.fascicoli as fascicoli_module
    import pct.polling_depositi as polling_module

    class FakeFascicoli:
        def __init__(self, *args, **kwargs):
            pass

    class FakeConfigStudio:
        config = SimpleNamespace(
            pec=SimpleNamespace(
                imap_host="imap.example.test",
                imap_port=993,
                indirizzo="studio@example.test",
                password="secret",
                use_ssl=True,
            )
        )

        def __init__(self, *args, **kwargs):
            pass

    def fake_esegui_polling(*, giorni_indietro: int, **_kwargs):
        calls["depositi"] = giorni_indietro
        return {"controllati": 0, "aggiornati": 0, "errori": 0}

    def fake_poll_cancelleria_pec(*, giorni_indietro: int, **_kwargs):
        calls["cancelleria"] = giorni_indietro
        return {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0}

    monkeypatch.setattr(fascicoli_module, "GestioneFascicoli", FakeFascicoli)
    monkeypatch.setattr(config_studio_module, "GestioneConfigStudio", FakeConfigStudio)
    monkeypatch.setattr(polling_module, "esegui_polling", fake_esegui_polling)
    monkeypatch.setattr(polling_module, "poll_cancelleria_pec", fake_poll_cancelleria_pec)

    fascicoli_db = tmp_path / "fascicoli" / "fascicoli.json"
    fascicoli_db.parent.mkdir(parents=True)
    fascicoli_db.write_text("[]", encoding="utf-8")
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        FASCICOLI_DB=str(fascicoli_db),
        FASCICOLI_DOCS=str(tmp_path / "fascicoli" / "documenti"),
        FASCICOLI_ARCH=str(tmp_path / "fascicoli" / "archivio"),
        STUDIO_CONFIG=str(tmp_path / "config" / "studio.json"),
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
        IUSENTRA_DEPOSIT_POLL_DAYS=30,
        IUSENTRA_PEC_CANCELLERIA_POLL_DAYS=30,
    )

    scheduler = start_scheduler(app)
    try:
        scheduler.get_job("polling_esiti_deposito").func()
        scheduler.get_job("poll_pec_cancelleria").func()

        assert calls == {"depositi": 7, "cancelleria": 7}
    finally:
        scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_start_scheduler_rispetta_flag_disable(monkeypatch):
    monkeypatch.setenv("PCT_DISABLE_SCHEDULER", "1")
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
    )

    scheduler = start_scheduler(app)

    assert scheduler is None
    assert "PCT_SCHEDULER" not in app.config
    monkeypatch.delenv("PCT_DISABLE_SCHEDULER", raising=False)


def test_start_scheduler_non_parte_senza_worker_o_override(monkeypatch):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    monkeypatch.delenv("PCT_ALLOW_INLINE_SCHEDULER", raising=False)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
    )

    scheduler = start_scheduler(app)

    assert scheduler is None
    assert "PCT_SCHEDULER" not in app.config


def test_lex_sentenza_economia_job_lancia_backfill_automatico(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    registry = tmp_path / "tenants.json"
    registry.write_text("{}", encoding="utf-8")
    calls: list[dict] = []

    import scripts.backfill_sentenza_lex_economics as backfill_module

    def fake_run_backfill(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "source_of_truth": "sqlite/postgresql runtime repositories",
            "totals": {
                "documents_seen": 4,
                "sentenze_found": 1,
                "unique_fascicoli_confirmed": 1,
                "applied": 1,
                "vector_indexed": 1,
                "context_mismatch_skipped": 3,
            },
        }

    monkeypatch.setattr(backfill_module, "run_backfill", fake_run_backfill)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        PCT_DATA_ROOT=str(tmp_path),
        TENANTS_REGISTRY=str(registry),
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
    )

    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job("lex_sentenza_economia_auto")
        assert job is not None

        result = job.func()

        assert result["ok"] is True
        assert result["job"] == "lex_sentenza_economia_auto"
        assert result["totals"]["applied"] == 1
        assert calls
        call = calls[0]
        assert call["apply"] is True
        assert call["skip_lex"] is False
        assert call["data_root"] == tmp_path
        assert call["registry"] == registry
        assert call["modified_after_ns"] == 0
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_lex_sentenza_economia_job_riusa_cursore_ultimo_run(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    registry = tmp_path / "tenants.json"
    registry.write_text("{}", encoding="utf-8")
    calls: list[dict] = []

    import scripts.backfill_sentenza_lex_economics as backfill_module
    from pct.scheduler_registry import scheduler_registry_repository

    def fake_run_backfill(**kwargs):
        calls.append(kwargs)
        return {
            "ok": True,
            "source_of_truth": "sqlite/postgresql runtime repositories",
            "scan_mode": "incremental",
            "incremental": {"newest_mtime_ns": 456},
            "totals": {
                "documents_catalogued": 4,
                "documents_seen": 1,
                "skipped_by_cursor": 3,
                "sentenze_found": 0,
                "unique_fascicoli_confirmed": 0,
                "applied": 0,
                "vector_indexed": 0,
                "context_mismatch_skipped": 0,
            },
        }

    monkeypatch.setattr(backfill_module, "run_backfill", fake_run_backfill)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        PCT_DATA_ROOT=str(tmp_path),
        TENANTS_REGISTRY=str(registry),
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
    )

    scheduler = start_scheduler(app)
    try:
        repo = scheduler_registry_repository(app.config)
        repo.record_scheduler_event(
            "lex_sentenza_economia_auto",
            status="completed",
            result={
                "ok": True,
                "incremental": {"newest_mtime_ns": 123},
                "totals": {"documents_seen": 10, "errors": 0, "vector_embedding_errors": 0},
            },
        )
        result = scheduler.get_job("lex_sentenza_economia_auto").func()

        assert result["scan_mode"] == "incremental"
        assert result["incremental"]["newest_mtime_ns"] == 456
        assert calls[0]["modified_after_ns"] == 123
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_pec_audit_pipeline_job_restituisce_report_operativo(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)

    import web.services.pec_pipeline_runtime as pec_runtime

    def fake_acquire(paths, *, tenant_label: str, batch_size: int):
        return {
            "scan_mode": "incremental",
            "archive_seen": 12,
            "scanned": 1,
            "relevant": 1,
            "ingested": 0,
            "duplicates": 0,
            "skipped_presided": 1,
            "missing_mime": 0,
            "errors": 0,
            "cursor_saved": True,
            "newest_sort_key": "2026-06-25T12:00:00Z",
        }

    worker_calls: list[dict[str, int]] = []

    def fake_workers(paths, *, tenant_label: str, limit: int, document_presidio_limit: int):
        worker_calls.append({"limit": limit, "document_presidio_limit": document_presidio_limit})
        return {
            "processed": 2,
            "failed": 0,
            "jobs": [],
            "document_presidio": {"checked_fascicoli": 1, "scheduled": 0, "limit": document_presidio_limit},
            "auto_deadline_notifications": {"created": 1, "errors": 0},
        }

    monkeypatch.setattr(pec_runtime, "acquire_local_pec_for_paths", fake_acquire)
    monkeypatch.setattr(pec_runtime, "run_workers_for_paths", fake_workers)

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        EMAIL_CASELLA_DB=str(tmp_path / "email" / "casella.json"),
        EMAIL_ORDINARIA_DB=str(tmp_path / "email" / "ordinaria.json"),
        FASCICOLI_DB=str(tmp_path / "fascicoli" / "fascicoli.json"),
        FASCICOLI_DOCS=str(tmp_path / "fascicoli" / "documenti"),
        FASCICOLI_ARCH=str(tmp_path / "fascicoli" / "archivio"),
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
    )

    scheduler = start_scheduler(app)
    try:
        result = scheduler.get_job("pec_audit_pipeline_workers").func()

        assert result["ok"] is True
        assert result["job"] == "pec_audit_pipeline_workers"
        assert result["scan_mode"] == "incremental"
        assert result["totals"]["archive_seen"] == 12
        assert result["totals"]["scanned"] == 1
        assert result["totals"]["processed_jobs"] == 2
        assert result["totals"]["errors"] == 0
        assert result["document_presidio_limit"] == 10
        assert worker_calls == [{"limit": 20, "document_presidio_limit": 10}]
        assert result["tenants"][0]["acquired"]["cursor_saved"] is True
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_fascicoli_document_economic_presidio_job_salva_fuori_ui(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)

    import web.services.fascicoli_presidi_runtime as presidi_runtime

    calls: list[dict[str, object]] = []

    def fake_presidio(app, *, limit_per_tenant: int, actor: str):
        calls.append({"limit": limit_per_tenant, "actor": actor})
        return {
            "ok": True,
            "job": "fascicoli_document_economic_presidio",
            "source_of_truth": "sqlite/postgresql tenant-aware",
            "scan_mode": "incrementale_su_impronta_documentale",
            "totals": {
                "createdCount": 1,
                "existingCount": 2,
                "missingBasisCount": 0,
                "processedDefined": 3,
                "contributiCheckedCount": 25,
                "contributiUpdatedCount": 4,
                "contributiMissingCount": 0,
                "documentAnalysisUpdatedCount": 6,
                "statusDefinedUpdatedCount": 1,
                "skippedCount": 0,
            },
            "tenants": [],
        }

    monkeypatch.setattr(
        presidi_runtime,
        "run_fascicoli_document_economic_presidio_for_all_tenants",
        fake_presidio,
    )

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
        IUSENTRA_FASCICOLI_PRESIDIO_LIMIT=250,
    )

    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job("fascicoli_document_economic_presidio")
        assert job is not None

        result = job.func()

        assert result["ok"] is True
        assert result["job"] == "fascicoli_document_economic_presidio"
        assert result["source_of_truth"] == "sqlite/postgresql tenant-aware"
        assert result["scan_mode"] == "incrementale_su_impronta_documentale"
        assert result["totals"]["contributiUpdatedCount"] == 4
        assert result["totals"]["documentAnalysisUpdatedCount"] == 6
        assert calls == [{"limit": 250, "actor": "IUSENTRA scheduler"}]
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_fascicoli_document_economic_presidio_default_lotto_piccolo(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)

    import web.services.fascicoli_presidi_runtime as presidi_runtime

    calls: list[dict[str, object]] = []

    def fake_presidio(app, *, limit_per_tenant: int, actor: str):
        calls.append({"limit": limit_per_tenant, "actor": actor})
        return {
            "ok": True,
            "job": "fascicoli_document_economic_presidio",
            "source_of_truth": "sqlite/postgresql tenant-aware",
            "scan_mode": "incrementale_su_impronta_documentale",
            "totals": {},
            "tenants": [],
        }

    monkeypatch.setattr(
        presidi_runtime,
        "run_fascicoli_document_economic_presidio_for_all_tenants",
        fake_presidio,
    )

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
    )

    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job("fascicoli_document_economic_presidio")
        assert job is not None
        assert job.max_instances == 1
        assert job.coalesce is True

        result = job.func()

        assert result["ok"] is True
        assert calls == [{"limit": 25, "actor": "IUSENTRA scheduler"}]
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)


def test_pst_certificati_scheduler_non_forza_refresh_remoto_di_default(monkeypatch, tmp_path):
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    monkeypatch.delenv("PCT_PST_CERTIFICATI_CIFRATURA_FORCE_REFRESH", raising=False)
    calls: list[dict] = []

    import pct.pst_cifratura as pst_cifratura

    def fake_controllo(*, force_refresh=False, max_workers=6):
        calls.append({"force_refresh": force_refresh, "max_workers": max_workers})
        return {
            "ok": True,
            "totale": 1,
            "scaricati_o_validi": 1,
            "errori": 0,
            "report_path": str(tmp_path / "audit.json"),
        }

    monkeypatch.setattr(
        pst_cifratura,
        "esegui_controllo_settimanale_certificati_cifratura",
        fake_controllo,
    )

    app = Flask(__name__)
    app.config.update(
        SECRET_KEY="test",
        BACKUP_ORA="02:00",
        WA_REMINDER_ORA="18:00",
        PCT_SCHEDULER_WORKER=True,
        SCHEDULER_REGISTRY_DB=str(tmp_path / "scheduler.sqlite"),
    )

    scheduler = start_scheduler(app)
    try:
        job = scheduler.get_job("pst_certificati_cifratura_weekly")
        assert job is not None

        result = job.func()

        assert result["ok"] is True
        assert calls == [{"force_refresh": False, "max_workers": 6}]
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
