"""Adozione CTU esplicita e riprendibile; nessuna scansione documentale.

Prima dell'applicazione: produttori sostituiti/drain, backup coerente,
confronto delle fonti e prova della UI. Non eseguire da una richiesta web.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
from contextlib import ExitStack, nullcontext
from pathlib import Path
from types import SimpleNamespace

from pct.ctu_repository import CtuRepository, validate_payload


def verify_persistent_backup_destination(destination, *, data_root):
    """Nel container il backup deve restare nel volume dati persistente."""
    if not Path(destination).resolve().is_relative_to(Path(data_root).resolve()):
        raise ValueError("Il backup CTU deve essere nel volume dati persistente dello studio.")


def read_source(path):
    try:
        content = Path(path).read_bytes()
    except FileNotFoundError:
        content = None
    payload = validate_payload({} if content is None else json.loads(content.decode("utf-8")))
    fingerprint = hashlib.sha256(b"__absent_ctu_source__" if content is None else content).hexdigest()
    return payload, fingerprint, content


def verify_fascicoli(db, payload):
    """Soltanto gli incarichi da adottare, nessuna enumerazione dell'archivio."""
    for fascicolo_id in sorted({item["fascicolo_id"] for item in payload.values()}):
        row = db.conn.execute("SELECT id FROM fascicoli WHERE id=?", (fascicolo_id,)).fetchone()
        if row is None:
            raise ValueError("Incarico CTU riferito a un fascicolo non presente nel repository dello studio.")


def verify_backup(destination, result):
    from deploy.hetzner.backup_structured import _sha256
    manifest = json.loads((destination / "source-manifest.json").read_text(encoding="utf-8"))
    for field in ("tenant", "source", "source_sha256", "source_exists", "sql_path"):
        if manifest.get(field) != result[field]:
            raise RuntimeError("Backup CTU riferito a fonte, archivio o studio diversi: recupero necessario.")
    backup = manifest.get("backup", {})
    backup_file = destination / ("studio-ctu.dump" if result["postgres"] else "studio-ctu.db")
    if not backup_file.is_file() or backup_file.stat().st_size == 0 or _sha256(backup_file) != backup.get("sha256"):
        raise RuntimeError("Backup coerente CTU non riscontrato: recupero necessario.")
    original = destination / "ctu-original.json"
    if result["source_exists"] and (not original.is_file() or _sha256(original) != result["source_sha256"]):
        raise RuntimeError("Copia originale CTU non riscontrata nel backup.")
    if not result["source_exists"] and original.exists():
        raise RuntimeError("Backup CTU discordante sull'assenza della fonte.")
    return backup


def apply_adoption(db, source, result, *, destination, payload, content):
    """Il chiamante mantiene il lock della fonte per backup e commit."""
    from pct.ctu_transition import commit_locked, prepare_locked
    from deploy.hetzner.backup_structured import _backup_sqlite
    from scripts.postgres_backup import backup_postgres

    resume = destination.exists()
    if resume:
        result["backup"] = verify_backup(destination, result)
    else:
        destination.mkdir(parents=True, exist_ok=False)
        if result["postgres"]:
            result["backup"] = backup_postgres(db.dsn, destination / "studio-ctu.dump")
        else:
            source_db = Path(db.db_path)
            if shutil.disk_usage(destination).free < source_db.stat().st_size + 1024**3:
                raise RuntimeError("Spazio insufficiente per il backup coerente CTU.")
            result["backup"] = _backup_sqlite(source_db, destination / "studio-ctu.db")
        if content is not None:
            (destination / "ctu-original.json").write_bytes(content)
        (destination / "source-manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        verify_backup(destination, result)
    current, fingerprint, _ = read_source(source)
    if fingerprint != result["source_sha256"] or current != payload:
        raise RuntimeError("Fonte CTU cambiata durante il backup: adozione sospesa.")
    verify_fascicoli(db, payload)
    prepare_locked(source, tenant=result["tenant_key"], source_sha256=fingerprint)
    repo = CtuRepository(db, result["tenant_key"], actor_key="migrazione-ctu")
    repo.ensure_schema()
    # Installazione esplicita dei segnali: nessun DDL al caricamento della UI.
    from pct.operational_live import ensure_live_schema
    ensure_live_schema(db.conn, postgres=result["postgres"])
    adopted = repo.initialize(payload, source_sha256=fingerprint, backup_reference=str(destination.resolve()))
    state = db.conn.execute("SELECT source_sha256,backup_reference FROM ctu_state WHERE tenant_key=?", (result["tenant_key"],)).fetchone()
    if state is None or tuple(state[i] for i in range(2)) != (fingerprint, str(destination.resolve())):
        raise RuntimeError("Conferma SQL CTU non riscontrata: barriera conservata.")
    adoption = db.conn.execute("SELECT actor_key,action,before_json,after_json,created_at FROM ctu_audit "
                               "WHERE tenant_key=? AND revision=0 AND record_key='__adoption'", (result["tenant_key"],)).fetchone()
    expected = repo._audit_values(0, "__adoption", adoption[0], adoption[1], adoption[2], adoption[3], adoption[4]) if adoption else None
    general = db.conn.execute("SELECT id,timestamp,id_utente,username,azione,risorsa_tipo,risorsa_id,dettagli,ip,esito "
                              "FROM audit_log WHERE id=?", (expected[0],)).fetchone() if expected else None
    if general is None or tuple(general[i] for i in range(10)) != expected:
        raise RuntimeError("Audit dell'adozione CTU non confermato: barriera conservata.")
    commit_locked(source, tenant=result["tenant_key"], source_sha256=fingerprint)
    result["sql_records"] = len(adopted)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--backup-dir", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--writers-drained", action="store_true")
    args = parser.parse_args()
    if args.apply and (not args.backup_dir or not args.writers_drained):
        parser.error("Servono backup coerente e drain dei produttori precedenti.")
    if args.apply and Path("/.dockerenv").exists() and os.environ.get("PCT_DATA_ROOT"):
        try:
            verify_persistent_backup_destination(args.backup_dir, data_root=os.environ["PCT_DATA_ROOT"])
        except ValueError as error:
            parser.error(str(error))
    from web.app import create_app
    from web.helpers import _cfg
    from web.services.storage_runtime import get_request_storage_runtime, _sqlite_runtime_is_unseeded
    from web.services.ctu_runtime import open_database
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    from pct.ctu_transition import source_lock
    app = create_app({"SCHEDULER_ONLY": True})
    manager, targets = _targets(app, args.tenant)
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("a", encoding="utf-8") as log:
        for slug, studio in targets.items():
            with _tenant_context(app, manager, studio, slug), ExitStack() as resources:
                source = Path(_cfg("CTU_DB"))
                anchor = _cfg("CLIENTI_DB")
                if not anchor:
                    raise RuntimeError("Riferimento SQL canonico CTU assente.")
                profile = get_request_storage_runtime(str(anchor))
                if profile.uses_sqlite:
                    canonical = Path(profile.studio_db_path)
                    if not canonical.is_file() or _sqlite_runtime_is_unseeded(canonical, Path(anchor)):
                        raise RuntimeError("SQL canonico CTU assente o non inizializzato: nessun bootstrap.")
                    if not args.apply:
                        conn = sqlite3.connect(canonical.resolve().as_uri() + "?mode=ro", uri=True)
                        resources.callback(conn.close)
                        db = SimpleNamespace(conn=conn, db_path=str(canonical))
                    else:
                        db = open_database(profile)
                        resources.callback(db.chiudi)
                else:
                    db = open_database(profile)
                    resources.callback(db.chiudi)
                    if not args.apply:
                        db.raw_conn.set_session(readonly=True)
                if args.apply:
                    source.parent.mkdir(parents=True, exist_ok=True)
                with source_lock(source) if args.apply else nullcontext():
                    payload, fingerprint, content = read_source(source)
                    verify_fascicoli(db, payload)
                    if content is None:
                        count = db.conn.execute("SELECT COUNT(*) FROM moduli_json_records WHERE modulo IN ('ctu','ctu_incarichi')").fetchone()
                        if count and int(count[0]):
                            raise RuntimeError("Fonte CTU assente e mirror non vuoto: recupero necessario.")
                    result = {"tenant": slug, "tenant_key": slug if studio is not None else "studio",
                              "source": str(source.resolve()), "source_sha256": fingerprint,
                              "source_exists": content is not None, "records": len(payload), "apply": args.apply,
                              "postgres": getattr(db, "backend_kind", "") == "postgresql",
                              "sql_path": str(getattr(db, "db_path", "postgresql"))}
                    if args.apply:
                        apply_adoption(db, source, result, destination=Path(args.backup_dir) / slug, payload=payload, content=content)
                    log.write(json.dumps(result, ensure_ascii=False) + "\n")
                    log.flush()
                    print(json.dumps({"tenant": slug, "apply": args.apply, "records": len(payload)}), flush=True)


if __name__ == "__main__":
    main()
