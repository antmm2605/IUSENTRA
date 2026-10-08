"""Migrazione esplicita e riprendibile dai chunk SQL, senza lettura dei file fonte."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from pct import embeddinggemma2, local_embedding_index
from pct.local_ai import _bounded_text_parts, _embedding_validation_reason
from pct.rag_source_provenance import checked_rows, verify_current_sql
from pct.rag_source_reconciliation import recover_sql_proofs, record_recovered_proofs


def resolve_live_core(*, registry: Path, tenant: str, db: Path,
                      tenant_root: Path, core_db: Path | None, dsn: str):
    """Confronta i percorsi dichiarati con il profilo realmente usato dallo studio."""
    from pct.tenant import DbMode, GestioneTenant
    from pct.storage_postgres import build_postgres_dsn
    from web.services.storage_runtime import resolve_storage_runtime

    manager = GestioneTenant(str(registry.resolve(strict=True)))
    studio = manager.get(tenant)
    if studio is None or studio.slug != tenant:
        raise ValueError("Studio non presente nel registro corrente")
    paths = manager.percorsi_dati(tenant, reconcile_aliases=False, ensure_baseline=False)
    expected_db = Path(paths["LOCAL_AI_DB"]).resolve(strict=True)
    expected_root = Path(paths["STUDIO_DB"]).resolve().parent
    if db.resolve(strict=True) != expected_db or tenant_root.resolve(strict=True) != expected_root:
        raise ValueError("Repository o radice diversi dai percorsi correnti dello studio")
    profile = resolve_storage_runtime(anchor_path=paths["FASCICOLI_DB"], tenant=studio)
    if profile.uses_sqlite:
        if dsn or core_db is None or core_db.resolve(strict=True) != Path(profile.studio_db_path).resolve(strict=True):
            raise ValueError("SQL dichiarato diverso dall'archivio SQLite corrente dello studio")
        return SimpleNamespace(db_path=Path(profile.studio_db_path))
    if profile.effective_mode == DbMode.POSTGRESQL:
        config = studio.database
        expected_dsn = build_postgres_dsn(
            host=config.host, port=config.porta_effettiva or 5432,
            db_name=config.db_name, user=config.utente,
            password=config.password, ssl=config.ssl,
        )
        if core_db is not None or not dsn or dsn != expected_dsn:
            raise ValueError("Connessione diversa dal PostgreSQL corrente dello studio")
        return SimpleNamespace(backend_kind="postgresql", dsn=dsn)
    raise ValueError("Archivio SQL corrente dello studio non operativo")


def migrate(db: Path, backup: Path, tenant_root: Path, *, source_verifier,
            source_reconciler=None, limit: int = 32) -> dict:
    deadline = time.monotonic() + 60
    if not callable(source_verifier):
        raise ValueError("Riscontro delle fonti SQL obbligatorio prima della migrazione")
    db = db.resolve(strict=True)
    if not db.is_relative_to(tenant_root.resolve(strict=True)):
        raise ValueError("Il repository non appartiene allo studio dichiarato")
    if db == backup.resolve() or db.is_relative_to(backup.resolve()):
        raise ValueError("Backup separato obbligatorio")
    if not embeddinggemma2.configured():
        raise ValueError("Configurare il servizio embedding locale verificato")
    backup.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = backup.with_suffix(backup.suffix + ".json")
    if backup.exists() and not manifest_path.exists():
        raise ValueError("Backup preesistente senza provenienza verificabile")
    with closing(sqlite3.connect(db, timeout=30)) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        if not backup.exists():
            # Pubblicazione del backup soltanto dopo verifica della copia coerente.
            temporary = backup.with_suffix(backup.suffix + ".preparing")
            with closing(sqlite3.connect(temporary)) as dest:
                conn.backup(dest)
                if dest.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                    raise ValueError("Backup SQL non valido")
            temporary.replace(backup)
            with backup.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            manifest_path.write_text(json.dumps({
                "source_db": str(db), "tenant_root": str(tenant_root.resolve()),
                "sha256": digest, "model": embeddinggemma2.MODEL,
            }), encoding="utf-8")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        with backup.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if manifest != {"source_db": str(db), "tenant_root": str(tenant_root.resolve()),
                        "sha256": digest, "model": embeddinggemma2.MODEL}:
            raise ValueError("Backup non corrispondente allo studio e al repository")
        with closing(sqlite3.connect(f"file:{backup.as_posix()}?mode=ro", uri=True)) as saved:
            if saved.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Backup SQL non valido")
        conn.row_factory = sqlite3.Row
        local_embedding_index.ensure_schema(conn)
        conn.execute("""CREATE TABLE IF NOT EXISTS rag_embedding_migration_checkpoint (
            model TEXT PRIMARY KEY, last_rowid INTEGER NOT NULL,
            upper_rowid INTEGER NOT NULL, unchanged INTEGER NOT NULL DEFAULT 0,
            completed INTEGER NOT NULL DEFAULT 0)""")
        conn.execute("""INSERT OR IGNORE INTO rag_embedding_migration_checkpoint
            (model,last_rowid,upper_rowid) VALUES (?,0,(SELECT COALESCE(MAX(rowid),0) FROM rag_chunks))""",
            (embeddinggemma2.MODEL,))
        conn.commit()
        checkpoint = conn.execute("SELECT * FROM rag_embedding_migration_checkpoint WHERE model=?",
                                  (embeddinggemma2.MODEL,)).fetchone()
        totals = dict(embedded=0, invalid=0, unchanged=0, changed_source=0, provenance_excluded=0)
        proofs_recovered = 0
        vectors_prepared = local_embedding_index.prepare_binary_vectors(conn)
        examined = 0
        visited = 0
        time_budget_reached = False
        rows = conn.execute("""
            SELECT c.rowid AS migration_rowid,c.*, d.sha256 AS document_sha256,
                d.parse_state,d.source_type,d.source_id
            FROM rag_chunks c JOIN rag_documents d ON d.id=c.document_id
            WHERE c.rowid>? AND c.rowid<=? ORDER BY c.rowid LIMIT ?
        """, (checkpoint["last_rowid"], checkpoint["upper_rowid"], limit)).fetchall()
        for row in rows:
            if time.monotonic() >= deadline:
                time_budget_reached = True
                break
            visited += 1
            row = dict(row)
            if callable(source_reconciler):
                proofs_recovered += record_recovered_proofs(conn, [row], source_reconciler([row]))
                row["metadata_json"] = conn.execute("SELECT metadata_json FROM rag_chunks WHERE id=?",
                                                     (row["id"],)).fetchone()[0]
            accepted = checked_rows(conn, [row], verifier=source_verifier, model=embeddinggemma2.MODEL)
            if not accepted:
                totals["provenance_excluded"] += 1
                conn.execute("UPDATE rag_embedding_migration_checkpoint SET last_rowid=? WHERE model=?",
                             (row["migration_rowid"], embeddinggemma2.MODEL))
                conn.commit()
                continue
            previous = conn.execute(
                "SELECT text_sha256, document_sha256, status, reason, segment_chars FROM rag_embedding_generations WHERE chunk_id=? AND model=?",
                (row["id"], embeddinggemma2.MODEL),
            ).fetchone()
            expected = (local_embedding_index.fingerprint(row["text"]), row["document_sha256"])
            needs_validation = previous and previous[2] == "embedded" and (
                row["parse_state"] != "parsed" or any(
                    _embedding_validation_reason(part) for part in _bounded_text_parts(
                        row["text"], max_chars=int(previous[4]),
                    )
                )
            )
            unchanged = bool(previous and tuple(previous)[:2] == expected and previous[2] in {"embedded", "invalid"}
                    and not needs_validation
                    and not (previous[3] == "fonte_non_letta" and row["parse_state"] == "parsed"))
            if unchanged:
                totals["unchanged"] += 1
            else:
                try:
                    result = local_embedding_index.build_chunks(
                        conn, [row], split=_bounded_text_parts, validate=_embedding_validation_reason,
                        deadline=deadline,
                    )
                except TimeoutError:
                    time_budget_reached = True
                    break
                examined += 1
                for key, value in result.items():
                    totals[key] += value
                if result["changed_source"]:
                    # Riprendere questo stesso elemento dopo la variazione, non
                    # dichiarare concluso un oggetto che non è stato pubblicato.
                    break
            conn.execute("""UPDATE rag_embedding_migration_checkpoint
                SET last_rowid=?,unchanged=unchanged+? WHERE model=?""",
                (row["migration_rowid"], int(unchanged), embeddinggemma2.MODEL))
            conn.commit()
        state = conn.execute("SELECT * FROM rag_embedding_migration_checkpoint WHERE model=?",
                             (embeddinggemma2.MODEL,)).fetchone()
        more = conn.execute("SELECT 1 FROM rag_chunks WHERE rowid>? AND rowid<=? LIMIT 1",
                            (state["last_rowid"], state["upper_rowid"])).fetchone()
        if not more:
            conn.execute("UPDATE rag_embedding_migration_checkpoint SET completed=1 WHERE model=?",
                         (embeddinggemma2.MODEL,))
            conn.commit()
        vectors_pending = conn.execute("""
            SELECT COUNT(*) FROM rag_embedding_segments s JOIN rag_embedding_generations g
                ON g.chunk_id=s.chunk_id AND g.model=s.model
            WHERE s.model=? AND g.status='embedded' AND s.embedding_f32 IS NULL
        """, (embeddinggemma2.MODEL,)).fetchone()[0]
        totals.update(model=embeddinggemma2.MODEL, examined=examined,
                      vectors_prepared=vectors_prepared, vectors_pending=vectors_pending,
                      visited=visited, last_rowid=state["last_rowid"],
                      upper_rowid=state["upper_rowid"], completed=not bool(more),
                      time_budget_reached=time_budget_reached, proofs_recovered=proofs_recovered)
        return totals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--tenant-root", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=32)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--registry", type=Path, required=True,
                        help="Registro tenant dell'installazione corrente")
    parser.add_argument("--core-db", type=Path,
                        help="SQL corrente; per PostgreSQL usare IUSENTRA_STUDIO_DSN nell'ambiente")
    args = parser.parse_args()
    if not 1 <= args.limit <= 128:
        parser.error("limit deve essere tra 1 e 128")
    dsn = os.environ.get("IUSENTRA_STUDIO_DSN", "")
    if bool(args.core_db) == bool(dsn):
        parser.error("Dichiarare esattamente un SQL corrente: --core-db oppure IUSENTRA_STUDIO_DSN")
    try:
        core = resolve_live_core(registry=args.registry, tenant=args.tenant, db=args.db,
                                 tenant_root=args.tenant_root, core_db=args.core_db, dsn=dsn)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    def verifier(rows):
        return verify_current_sql(rows, tenant=args.tenant, core=core)
    def reconciler(rows):
        return recover_sql_proofs(rows, tenant=args.tenant, core=core)
    print(json.dumps(migrate(args.db, args.backup, args.tenant_root,
                             source_verifier=verifier, source_reconciler=reconciler,
                             limit=args.limit), ensure_ascii=False))


if __name__ == "__main__":
    main()
