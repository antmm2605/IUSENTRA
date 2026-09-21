"""Migrazione esplicita delle revisioni PEC; nessun messaggio viene modificato.

Eseguire sul codice distribuito, prima di attivare il consumo della revisione.
Il backup SQLite conserva lo stato precedente; tabella e trigger restano SQL
versionato in pct/sql anche per PostgreSQL.
"""
from __future__ import annotations
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

INDEX_SQL = """CREATE INDEX IF NOT EXISTS idx_pec_messages_unlinked_ingested
ON pec_messages(ingested_at DESC, id)
WHERE TRIM(COALESCE(linked_fascicolo_id, '')) = ''"""


def revision_statements() -> list[str]:
    source = (Path(__file__).resolve().parents[1] / "pct/sql/20260521_pec_audit_pipeline.sql").read_text(encoding="utf-8")
    source = source[source.index("CREATE TABLE IF NOT EXISTS pec_source_revisions"):source.index("CREATE TABLE IF NOT EXISTS pec_parsed_versions")]
    statements, pending = [], ""
    for line in source.splitlines(keepends=True):
        pending += line
        if sqlite3.complete_statement(pending):
            statements.append(pending.strip())
            pending = ""
    if pending.strip():
        raise ValueError("Schema revisioni SQL incompleto")
    return statements


def migrate(path: Path, *, apply: bool, backup_dir: Path | None) -> dict:
    path = path.resolve(strict=True)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10) as check:
        tenants = [str(row[0]) for row in check.execute("SELECT tenant_id FROM pec_messages GROUP BY tenant_id")]
        plans = [str(row[3]) for row in check.execute("EXPLAIN QUERY PLAN SELECT id FROM pec_messages WHERE TRIM(COALESCE(linked_fascicolo_id, '')) = '' ORDER BY ingested_at DESC LIMIT 1")]
    report = {"database": str(path), "source_of_truth": "sqlite", "tenants": tenants, "applied": False, "query_plan_before": plans}
    if not apply:
        return report
    if backup_dir is None:
        raise ValueError("--backup-dir obbligatorio con --apply")
    backup_dir.mkdir(parents=True, exist_ok=True)
    from hashlib import sha256
    name = sha256(str(path).encode()).hexdigest()[:12]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup_path = backup_dir / f"pec-{name}-{stamp}.sqlite"
    if backup_path.exists():
        raise FileExistsError(backup_path)
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as source, sqlite3.connect(backup_path) as target:
        source.backup(target, pages=2048, sleep=0.01)
        if target.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup SQLite non valido")
    backup_path.chmod(0o600)
    with sqlite3.connect(path, timeout=30) as conn:
        conn.execute("BEGIN IMMEDIATE")
        for statement in revision_statements():
            conn.execute(statement)
        conn.execute(INDEX_SQL)
        # Il trigger ha preso in carico anche le scritture successive. La
        # revisione viene avanzata per obbligare un primo passaggio completo.
        current_tenants = [str(row[0]) for row in conn.execute("SELECT tenant_id FROM pec_messages GROUP BY tenant_id")]
        for tenant in current_tenants or ["default"]:
            conn.execute("""INSERT INTO pec_source_revisions(tenant_id,messages_revision,initialized,updated_at)
            VALUES (?,1,1,CURRENT_TIMESTAMP) ON CONFLICT(tenant_id) DO UPDATE SET
            messages_revision=pec_source_revisions.messages_revision+1, initialized=1, updated_at=CURRENT_TIMESTAMP""", (tenant,))
        conn.commit()
        report["query_plan_after"] = [str(row[3]) for row in conn.execute("EXPLAIN QUERY PLAN SELECT id FROM pec_messages WHERE TRIM(COALESCE(linked_fascicolo_id, '')) = '' ORDER BY ingested_at DESC LIMIT 1")]
        report["revisions"] = [list(row) for row in conn.execute("SELECT tenant_id,messages_revision,initialized FROM pec_source_revisions ORDER BY tenant_id")]
    report.update(applied=True, backup=str(backup_path))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sqlite-db", type=Path, action="append", required=True)
    parser.add_argument("--backup-dir", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    for path in args.sqlite_db:
        print(json.dumps(migrate(path, apply=args.apply, backup_dir=args.backup_dir), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
