"""Adozione esplicita e riprendibile delle preparazioni, senza leggere documenti."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from contextlib import ExitStack, nullcontext
from pathlib import Path
from types import SimpleNamespace

from pct.prima_nota_transition import prima_nota_source_lock
from pct.udienze.adoption import adopt_locked, read_source, verify_references


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--backup-dir", default="")
    parser.add_argument("--data-root", default=os.environ.get("PCT_DATA_ROOT", ""))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--writers-drained", action="store_true")
    args = parser.parse_args()
    if args.apply and not (args.backup_dir and args.data_root and args.writers_drained):
        parser.error("Adozione: servono volume dati, backup coerente e drain dei produttori.")
    from web.app import create_app
    from web.helpers import _cfg
    from web.services.storage_runtime import get_request_storage_runtime, _sqlite_runtime_is_unseeded
    from web.services.preparazione_udienza_sql_runtime import open_database, close_database
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    app = create_app({"SCHEDULER_ONLY": True})
    manager, targets = _targets(app, args.tenant)
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("a", encoding="utf-8") as log:
        for slug, studio in targets.items():
            with _tenant_context(app, manager, studio, slug), ExitStack() as resources:
                source = Path(_cfg("WIZARD_PRO_DB"))
                anchor = _cfg("CLIENTI_DB")
                if not anchor:
                    raise RuntimeError("Riferimento SQL canonico delle preparazioni assente.")
                profile = get_request_storage_runtime(str(anchor))
                if profile.tenant_slug and profile.tenant_slug != slug:
                    raise RuntimeError("Profilo SQL appartenente ad altro studio.")
                if profile.uses_sqlite:
                    canonical = Path(profile.studio_db_path)
                    if not canonical.is_file() or _sqlite_runtime_is_unseeded(canonical, Path(anchor)):
                        raise RuntimeError("SQL canonico assente o non inizializzato: nessun bootstrap.")
                    if not args.apply:
                        conn = sqlite3.connect(canonical.resolve().as_uri() + "?mode=ro", uri=True)
                        resources.callback(conn.close)
                        db = SimpleNamespace(conn=conn, db_path=str(canonical))
                    else:
                        db = open_database(profile)
                        resources.callback(close_database)
                elif profile.effective_mode == "POSTGRESQL":
                    db = open_database(profile)
                    resources.callback(close_database)
                    if not args.apply:
                        db.raw_conn.set_session(readonly=True)
                else:
                    raise RuntimeError("Repository SQL delle preparazioni non configurato.")
                if args.apply:
                    source.parent.mkdir(parents=True, exist_ok=True)
                with prima_nota_source_lock(source) if args.apply else nullcontext():
                    records, fingerprint, content = read_source(source)
                    verify_references(db, records)
                    if content is None and db.conn.execute("SELECT count(*) FROM moduli_json_records WHERE modulo IN ('wizard_pro','preparazioni_udienze')").fetchone()[0]:
                        raise RuntimeError("Fonte assente con mirror non vuoto: recupero necessario.")
                    tenant = slug if studio is not None else "studio"
                    result = {"tenant": tenant, "source": str(source), "source_sha256": fingerprint,
                              "records": len(records), "phase": "verified", "apply": args.apply}
                    if args.apply:
                        result.update(adopt_locked(db, source, tenant=tenant, destination=Path(args.backup_dir) / slug,
                            data_root=args.data_root, writers_drained=args.writers_drained))
                    log.write(json.dumps(result, ensure_ascii=False) + "\n")
                    log.flush()
                    print(json.dumps({"tenant": tenant, "records": len(records), "phase": result["phase"]}), flush=True)


if __name__ == "__main__":
    main()
