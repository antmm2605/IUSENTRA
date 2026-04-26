from __future__ import annotations

from pathlib import Path

from .connectors.factory import create_connector
from .db import finish_run, init_db, record_error, save_document, start_run, upsert_source
from .models import SourceConfig


def run_source(source: SourceConfig, db_path: str | Path, raw_dir: str | Path, text_dir: str | Path, *, dry_run: bool = False) -> tuple[int, int]:
    init_db(db_path)
    upsert_source(db_path, source)

    if not source.enabled:
        print(f"[SKIP] {source.id} disabilitata")
        return 0, 0

    connector = create_connector(source)
    run_id = start_run(db_path, source.id)
    found = 0
    saved = 0
    try:
        for doc, path in connector.fetch(Path(raw_dir)):
            found += 1
            print(f"[DOC] {source.id}: {doc.title} -> {path}")
            if dry_run:
                continue
            inserted = save_document(db_path, doc, path, Path(text_dir))
            if inserted:
                saved += 1
        finish_run(db_path, run_id, "ok", found=found, saved=saved)
        return found, saved
    except Exception as exc:
        finish_run(db_path, run_id, "error", message=str(exc), found=found, saved=saved)
        record_error(db_path, source.id, run_id, str(exc), error_type=exc.__class__.__name__)
        raise
