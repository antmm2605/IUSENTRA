"""Adozione esplicita dell'archivio termini; mai da richieste web.

Il chiamante deve avere drenato i produttori e mantiene il lock sorgente.
Backup coerente, fonte e audit vengono riscontrati prima del commit del marker.
"""
from __future__ import annotations

import hashlib
import argparse
import json
import os
import shutil
import sqlite3
from contextlib import ExitStack, nullcontext
from pathlib import Path
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

from pct.termini_processuali import canonical_sha256
from pct.termini_processuali_repository import DeadlineSqlRepository, archive_records, encode
from pct.termini_transition import commit_locked, prepare_locked


def _preserved_record(conn, tenant_key, expected, stored, revisions):
    """Riscontra l'originale oppure una catena finita di rettifiche auditate."""
    if stored == expected:
        return True
    if expected[0] != "templates" or stored is None or stored[:2] != expected[:2]:
        return False
    previous = json.loads(expected[2])
    target = json.loads(stored[2])
    seen = set()
    for _ in range(len(revisions)):
        candidates = [item for item in revisions if item.get("code") == expected[1]
                      and item.get("previous") == previous]
        if len(candidates) != 1:
            return False
        change = candidates[0]
        fingerprint = canonical_sha256(change)
        if fingerprint in seen:
            return False
        seen.add(fingerprint)
        audit_id = str(uuid5(NAMESPACE_URL, encode([
            "termini.revisione", tenant_key, expected[1], change.get("revision")])) )
        audit = conn.execute("SELECT azione,risorsa_id,dettagli FROM audit_log WHERE id=?", (audit_id,)).fetchone()
        if audit is None or audit[0] != "termini.revisione" or audit[1] != expected[1] or json.loads(audit[2]) != change:
            return False
        previous = change.get("replacement")
        if previous == target:
            return stored[3] == expected[3]
    return False


def read_source(path):
    content = Path(path).read_bytes()
    payload = json.loads(content.decode("utf-8"))
    archive_records(payload)
    return payload, hashlib.sha256(content).hexdigest(), content


def initialize_missing_source(source, *, tenant_key, actor_key):
    """Provisioning esplicito sotto lock, dopo drain; non sostituisce archivi esistenti."""
    if not tenant_key or not actor_key:
        raise ValueError("Studio e attore necessari per il catalogo iniziale.")
    source = Path(source)
    if source.exists():
        raise ValueError("Archivio già presente: inizializzazione respinta.")
    from pct.termini_processuali import DEFAULT_TEMPLATES
    from scripts.import_guida_pratica_termini_processuali import collect_terms, _default_sources, _template_from_term
    rows = collect_terms(_default_sources())
    templates = {template.code: template.to_dict() for template in DEFAULT_TEMPLATES}
    for row in rows:
        template = _template_from_term(row)
        if template:
            templates[template["code"]] = template
    payload = {"templates": list(templates.values()), "guida_pratica_terms": rows,
               "initial_provision": {"tenant": tenant_key, "actor": actor_key,
                                     "source_previously_absent": True}}
    archive_records(payload)
    source.parent.mkdir(parents=True, exist_ok=True)
    with source.open("x", encoding="utf-8") as target:
        target.write(encode(payload))
        target.flush()
        os.fsync(target.fileno())
    return payload


def verify_backup(destination, result):
    manifest = json.loads((destination / "source-manifest.json").read_text(encoding="utf-8"))
    for field in ("tenant_key", "source", "source_sha256", "archive_sha256", "sql_path", "postgres"):
        if manifest.get(field) != result[field]:
            raise RuntimeError("Backup dei termini riferito a fonte o studio diversi.")
    backup = manifest.get("backup", {})
    filename = destination / ("studio-termini.dump" if result["postgres"] else "studio-termini.db")
    from deploy.hetzner.backup_structured import _sha256
    if not filename.is_file() or filename.stat().st_size == 0 or _sha256(filename) != backup.get("sha256"):
        raise RuntimeError("Backup coerente dei termini non riscontrato.")
    original = destination / "termini-original.json"
    if not original.is_file() or _sha256(original) != result["source_sha256"]:
        raise RuntimeError("Fonte originale dei termini non riscontrata nel backup.")
    return backup


def apply_adoption(db, source, *, destination, tenant_key, actor_key):
    """Chiamare soltanto sotto source_lock, dopo drain e verifica del tenant SQL."""
    if not tenant_key or not actor_key:
        raise ValueError("Studio e attore della migrazione dei termini necessari.")
    destination = Path(destination)
    payload, fingerprint, content = read_source(source)
    result = {"tenant_key": tenant_key, "source": str(Path(source).resolve()),
              "source_sha256": fingerprint, "archive_sha256": canonical_sha256(payload),
              "postgres": getattr(db, "backend_kind", "") == "postgresql",
              "sql_path": str(getattr(db, "db_path", "postgresql"))}
    if destination.exists():
        result["backup"] = verify_backup(destination, result)
    else:
        destination.mkdir(parents=True, exist_ok=False)
        if result["postgres"]:
            from scripts.postgres_backup import backup_postgres
            result["backup"] = backup_postgres(db.dsn, destination / "studio-termini.dump")
        else:
            from deploy.hetzner.backup_structured import _backup_sqlite
            database_path = Path(db.db_path)
            if shutil.disk_usage(destination).free < database_path.stat().st_size + 1024**3:
                raise RuntimeError("Spazio insufficiente per il backup coerente dei termini.")
            result["backup"] = _backup_sqlite(database_path, destination / "studio-termini.db")
        (destination / "termini-original.json").write_bytes(content)
        (destination / "source-manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        verify_backup(destination, result)
    current, current_hash, _ = read_source(source)
    if current_hash != fingerprint or current != payload:
        raise RuntimeError("Fonte dei termini cambiata durante il backup: adozione sospesa.")
    prepare_locked(source, tenant=tenant_key, source_sha256=fingerprint)
    adoption = (fingerprint, str(destination.resolve()))
    repo = DeadlineSqlRepository(db, tenant_key, source=source, actor_key=actor_key, expected_adoption=adoption)
    repo.ensure_schema()
    from pct.operational_live import ensure_live_schema
    ensure_live_schema(db.conn, postgres=result["postgres"])
    receipt = repo.initialize(payload, source_sha256=fingerprint, backup_reference=adoption[1])
    rows = db.conn.execute(
        "SELECT kind,record_key,payload_json,order_key FROM termini_records WHERE tenant_key=? ORDER BY kind,record_key",
        (tenant_key,),
    ).fetchall()
    expected = sorted(archive_records(payload), key=lambda row: (row[0], row[1]))
    # Al primo passaggio tutte le righe devono coincidere con la fonte;
    # un replay successivo può conservare ulteriori calcoli, mai sovrascriverli.
    stored = {(row[0], row[1]): tuple(row[i] for i in range(4)) for row in rows}
    revisions = [json.loads(row[2]) for row in rows if row[0] == "template_revisions"]
    if any(not _preserved_record(db.conn, tenant_key, row, stored.get((row[0], row[1])), revisions)
           for row in expected):
        raise RuntimeError("Archivio SQL dei termini non concordante con la fonte: barriera conservata.")
    audit_id = str(uuid5(NAMESPACE_URL, encode(["termini.adoption", tenant_key, fingerprint])))
    audit = db.conn.execute("SELECT azione,risorsa_id,dettagli FROM audit_log WHERE id=?", (audit_id,)).fetchone()
    details = json.loads(audit[2]) if audit else {}
    if audit is None or audit[0] != "termini.adozione" or audit[1] != tenant_key or details != {
        "source_sha256": fingerprint, "backup_reference": adoption[1],
        "archive_sha256": canonical_sha256(payload), "records": len(expected),
    }:
        raise RuntimeError("Audit dell'adozione dei termini non confermato: barriera conservata.")
    commit_locked(source, tenant=tenant_key, source_sha256=fingerprint)
    from pct.termini_rule_revisions import rectify_native_caution
    revision = rectify_native_caution(repo)
    from pct.termini_guide_rule_revisions import rectify_imported_reclami
    guide_revisions = rectify_imported_reclami(repo)
    return {**result, "receipt": receipt, "sql_records": len(rows), "native_rule_revision": revision, "guide_rule_revisions": guide_revisions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--backup-dir", default="")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--writers-drained", action="store_true")
    parser.add_argument("--initialize-missing", action="store_true")
    args = parser.parse_args()
    if args.apply and (not args.backup_dir or not args.writers_drained):
        parser.error("Servono backup coerente e drain dei produttori precedenti.")
    if args.apply and Path("/.dockerenv").exists() and os.environ.get("PCT_DATA_ROOT"):
        if not Path(args.backup_dir).resolve().is_relative_to(Path(os.environ["PCT_DATA_ROOT"]).resolve()):
            parser.error("Il backup dei termini deve restare nel volume dati persistente.")
    from web.app import create_app
    from web.helpers import _cfg
    from web.services.storage_runtime import get_request_storage_runtime, _sqlite_runtime_is_unseeded
    from web.services.termini_runtime import open_database
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    from pct.termini_transition import source_lock
    app = create_app({"SCHEDULER_ONLY": True})
    manager, targets = _targets(app, "" if args.tenant == "all" else args.tenant)
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open("a", encoding="utf-8") as log:
        for slug, studio in targets.items():
            with _tenant_context(app, manager, studio, slug), ExitStack() as resources:
                source = Path(_cfg("TERMINI_PROCESSUALI_DB"))
                anchor = _cfg("CLIENTI_DB")
                if not anchor:
                    raise RuntimeError("Riferimento SQL canonico dei termini assente.")
                profile = get_request_storage_runtime(str(anchor))
                if profile.tenant_slug and profile.tenant_slug != slug:
                    raise RuntimeError("Profilo SQL dei termini riferito ad altro studio.")
                if profile.uses_sqlite:
                    canonical = Path(profile.studio_db_path)
                    if not canonical.is_file() or _sqlite_runtime_is_unseeded(canonical, Path(anchor)):
                        raise RuntimeError("SQL canonico dei termini assente o non inizializzato: nessun bootstrap.")
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
                with source_lock(source) if args.apply else nullcontext():
                    key = slug if studio is not None else "studio"
                    if not source.exists():
                        if not args.apply:
                            result = {"tenant_key": key, "apply": False, "source_missing": True,
                                      "requires_initial_provision": True}
                            log.write(json.dumps(result, ensure_ascii=False) + "\n")
                            log.flush()
                            print(json.dumps(result))
                            continue
                        if not args.initialize_missing:
                            raise RuntimeError("Archivio dei termini assente: serve il provisioning esplicito, nessun bootstrap dalla GET.")
                        initialize_missing_source(source, tenant_key=key, actor_key="migrazione-termini")
                    payload, fingerprint, _ = read_source(source)
                    result = {"tenant_key": key, "source_sha256": fingerprint,
                              "records": len(archive_records(payload)), "apply": args.apply}
                    if args.apply:
                        result.update(apply_adoption(db, source, destination=Path(args.backup_dir) / slug,
                                                     tenant_key=key, actor_key="migrazione-termini"))
                    log.write(json.dumps(result, ensure_ascii=False) + "\n")
                    log.flush()
                    print(json.dumps({"tenant": slug, "apply": args.apply, "records": result["records"]}))


if __name__ == "__main__":
    main()
