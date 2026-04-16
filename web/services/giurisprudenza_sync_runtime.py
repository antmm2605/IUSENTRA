from __future__ import annotations

from threading import Lock, Thread
from typing import Any

from pct.giurisprudenza import GestioneGiurisprudenza

_SYNC_LOCK = Lock()
_RUNNING_BY_DB: dict[str, Thread] = {}


def resolve_giurisprudenza_db_path(app_config: dict[str, Any], data_paths: dict[str, str] | None = None) -> str:
    paths = dict(data_paths or {})
    return str(paths.get("GIURISPRUDENZA_DB") or app_config.get("GIURISPRUDENZA_DB") or "").strip()


def start_giurisprudenza_sync_job(
    app,
    *,
    giurisprudenza_db_path: str,
    source_ids: list[str] | None = None,
) -> dict[str, Any]:
    db_path = str(giurisprudenza_db_path or "").strip()
    if not db_path:
        raise ValueError("Percorso archivio giurisprudenza non configurato.")
    normalized_source_ids = [str(item).strip() for item in (source_ids or []) if str(item).strip()]

    with _SYNC_LOCK:
        running = _RUNNING_BY_DB.get(db_path)
        if running and running.is_alive():
            return {
                "started": False,
                "already_running": True,
                "source_ids": normalized_source_ids,
            }
        worker = Thread(
            target=_run_giurisprudenza_sync_job,
            args=(app, db_path, normalized_source_ids),
            daemon=True,
            name=f"giurisprudenza-sync:{db_path}",
        )
        _RUNNING_BY_DB[db_path] = worker
        worker.start()
        return {
            "started": True,
            "already_running": False,
            "source_ids": normalized_source_ids,
        }


def _run_giurisprudenza_sync_job(app, db_path: str, source_ids: list[str]) -> None:
    try:
        with app.app_context():
            GestioneGiurisprudenza(db_path=db_path).sync_sources(source_ids=source_ids or None)
    except Exception as exc:  # pragma: no cover - difesa runtime
        app.logger.exception("Errore sync giurisprudenza in background: %s", exc)
    finally:
        with _SYNC_LOCK:
            current = _RUNNING_BY_DB.get(db_path)
            if current and current.name == f"giurisprudenza-sync:{db_path}":
                _RUNNING_BY_DB.pop(db_path, None)


__all__ = [
    "resolve_giurisprudenza_db_path",
    "start_giurisprudenza_sync_job",
]
