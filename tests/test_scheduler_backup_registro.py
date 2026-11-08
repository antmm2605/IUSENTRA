"""Il backup giornaliero dello scheduler entra nel registro dei backup, non in /tmp."""

from __future__ import annotations

import json
from pathlib import Path

from pct.backup import GestioneBackup
from pct.scheduler_worker import start_scheduler_worker
from tests.test_web_bootstrap import _cfg_web, _write_studio_config


def test_backup_giornaliero_scrive_nel_registro_dei_backup(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("PCT_DISABLE_SCHEDULER", raising=False)
    monkeypatch.delenv("PCT_SCHEDULER_RUNNING", raising=False)
    monkeypatch.setattr(
        "web.services.archivio_letture_runtime.riprendi_eventi_lettura",
        lambda app: {"tenant": 1, "trovati": 0, "avviati": 0},
    )
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["BACKUP_DIR"] = str(tmp_path / "backup")
    cfg["IUSENTRA_DISABLE_BACKUP_JOBS"] = "0"
    monkeypatch.setenv("IUSENTRA_DISABLE_BACKUP_JOBS", "0")
    agenda = Path(cfg.get("AGENDA_DB") or tmp_path / "agenda" / "appuntamenti.json")
    agenda.parent.mkdir(parents=True, exist_ok=True)
    agenda.write_text(json.dumps([]), encoding="utf-8")
    cfg["AGENDA_DB"] = str(agenda)
    temporanee = set(Path("/tmp").glob("iusentra_sched_*"))
    app = start_scheduler_worker(cfg)
    scheduler = app.config.get("PCT_SCHEDULER")
    try:
        esito = scheduler.get_job("backup_giornaliero").func()
    finally:
        scheduler.shutdown(wait=False)
    assert esito["ok"] is True, esito
    registro = GestioneBackup(directory_backup=str(tmp_path / "backup"), percorsi_dati={}).tutti()
    assert [r.id for r in registro] == [esito["backup_id"]]
    assert set(Path("/tmp").glob("iusentra_sched_*")) == temporanee
