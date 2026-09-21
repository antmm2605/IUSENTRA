"""Riconciliazione amministrativa dei job OCR legacy senza proprietario.

Il modulo non apre documenti e non invoca OCR o indicizzazione: usa soltanto
SQL tenant-aware, registro letture e cache correnti già persistite.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

OWNER_ERROR = "Studio proprietario della lettura non identificato univocamente."


@dataclass(frozen=True)
class Candidate:
    job_id: int
    fascicolo_id: str
    documento_id: str
    tenant_id: str
    registro_path: str
    outcome: str
    target_status: str
    archive_sha256: str
    current_archive_sha256: str
    content_sha256: str
    original_error: str
    evidence: dict[str, Any]


@dataclass(frozen=True)
class Skipped:
    job_id: int
    reason: str


def _connect_ro(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def _documents(raw: object) -> list[dict[str, Any]]:
    try:
        value = json.loads(str(raw or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _historical_hashes(document: dict[str, Any]) -> set[str]:
    versions = document.get("versioni")
    if not isinstance(versions, list):
        return set()
    return {
        str(item.get("hash_sha256") or "").strip().lower()
        for item in versions
        if isinstance(item, dict) and str(item.get("hash_sha256") or "").strip()
    }


def _owners(data_root: Path, job: sqlite3.Row) -> list[tuple[str, Path, dict[str, Any], str]]:
    result: list[tuple[str, Path, dict[str, Any], str]] = []
    wanted_hash = str(job["hash_sha256"] or "").strip().lower()
    for db_path in sorted((data_root / "tenants").glob("*/studio.db")):
        with closing(_connect_ro(db_path)) as conn:
            row = conn.execute(
                "SELECT documenti_json FROM fascicoli WHERE id = ?",
                (str(job["id_fasc"]),),
            ).fetchone()
        if row is None:
            continue
        for document in _documents(row["documenti_json"]):
            if str(document.get("id") or "") != str(job["id_doc"]):
                continue
            current_hash = str(document.get("hash_sha256") or "").strip().lower()
            if wanted_hash == current_hash and current_hash:
                relation = "current"
            elif wanted_hash in _historical_hashes(document):
                relation = "historical"
            else:
                continue
            result.append((db_path.parent.name, db_path, document, relation))
    return result


def _readers(
    conn: sqlite3.Connection,
    tenant: str,
    fascicolo_id: str,
    documento_id: str,
    content_sha256: str,
) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT lettore, stato
          FROM letture
         WHERE tenant_id = ? AND fascicolo_id = ? AND tipo = 'documento'
           AND oggetto_id = ? AND sha256 = ?
        """,
        (tenant, fascicolo_id, documento_id, content_sha256),
    ).fetchall()
    return {str(row["lettore"]): str(row["stato"]) for row in rows}


def _cached_chars(index_path: Path, content_sha256: str) -> int:
    if not index_path.is_file() or not content_sha256:
        return 0
    with closing(_connect_ro(index_path)) as conn:
        row = conn.execute(
            "SELECT length(testo) AS chars FROM ocr_cache WHERE hash_sha256 = ?",
            (content_sha256,),
        ).fetchone()
    return int(row["chars"] or 0) if row else 0


def _central_text_chars(
    studio_db: Path,
    tenant: str,
    fascicolo_id: str,
    current_archive_sha256: str,
) -> int:
    with closing(_connect_ro(studio_db)) as conn:
        row = conn.execute(
            """
            SELECT max(length(t.text)) AS chars
              FROM fascicolo_documenti_ai_versioni AS v
              JOIN fascicolo_documenti_ai_testi AS t ON t.version_id = v.id
             WHERE v.tenant_id = ? AND v.fascicolo_id = ? AND v.sha256 = ?
               AND length(trim(t.text)) > 0
            """,
            (tenant, fascicolo_id, current_archive_sha256),
        ).fetchone()
    return int(row["chars"] or 0) if row else 0


def _classify(data_root: Path, job: sqlite3.Row) -> Candidate | Skipped:
    owners = _owners(data_root, job)
    if len(owners) != 1:
        return Skipped(int(job["id"]), f"owner_count={len(owners)}")
    tenant, studio_db, document, relation = owners[0]
    tenant_root = studio_db.parent
    registry_path = tenant_root / "intelligence" / "registro_letture.db"
    if not registry_path.is_file():
        return Skipped(int(job["id"]), "registro_assente")

    fascicolo_id = str(job["id_fasc"])
    documento_id = str(job["id_doc"])
    current_archive = str(document.get("hash_sha256") or "").strip().lower()
    with closing(_connect_ro(registry_path)) as registry:
        obj = registry.execute(
            """
            SELECT sha256, sha256_archivio, presente
              FROM letture_oggetti
             WHERE tenant_id = ? AND fascicolo_id = ? AND tipo = 'documento'
               AND oggetto_id = ?
            """,
            (tenant, fascicolo_id, documento_id),
        ).fetchone()
        if obj is None or int(obj["presente"] or 0) != 1:
            return Skipped(int(job["id"]), "oggetto_registro_assente")
        content_sha = str(obj["sha256"] or "").strip().lower()
        registry_archive = str(obj["sha256_archivio"] or "").strip().lower()
        if not content_sha or registry_archive != current_archive:
            return Skipped(int(job["id"]), "registro_non_allineato_versione_corrente")
        readers = _readers(registry, tenant, fascicolo_id, documento_id, content_sha)

    central_chars = _central_text_chars(studio_db, tenant, fascicolo_id, current_archive)
    if central_chars <= 0 or readers.get("motore_documenti") != "letto":
        return Skipped(int(job["id"]), "lettura_corrente_non_verificata")
    cache_chars = _cached_chars(tenant_root / "search" / "index.db", content_sha)
    evidence = {
        "hash_relation": relation,
        "registry_archive_matches_current": True,
        "motore_documenti": readers.get("motore_documenti", "missing"),
        "ocr": readers.get("ocr", "missing"),
        "indice_documentale": readers.get("indice_documentale", "missing"),
        "cache_chars": cache_chars,
        "central_text_chars": central_chars,
    }

    if relation == "historical":
        outcome, target = "superseded_version", "superseded"
    elif (
        readers.get("ocr") == "letto"
        and readers.get("indice_documentale") == "letto"
        and cache_chars > 0
    ):
        outcome, target = "already_read", "recovered"
    elif cache_chars > 0:
        outcome, target = "current_cache", "recovered"
    else:
        return Skipped(int(job["id"]), "cache_corrente_assente")

    return Candidate(
        job_id=int(job["id"]),
        fascicolo_id=fascicolo_id,
        documento_id=documento_id,
        tenant_id=tenant,
        registro_path=str(registry_path),
        outcome=outcome,
        target_status=target,
        archive_sha256=str(job["hash_sha256"] or ""),
        current_archive_sha256=current_archive,
        content_sha256=content_sha,
        original_error=str(job["last_error"] or ""),
        evidence=evidence,
    )


def inspect(queue_db: Path, data_root: Path) -> tuple[list[Candidate], list[Skipped]]:
    """Classifica soltanto il sottoinsieme legacy esplicito, senza alcuna scrittura."""
    with closing(_connect_ro(queue_db)) as conn:
        jobs = conn.execute(
            """
            SELECT * FROM ocr_jobs
             WHERE status = 'failed' AND tenant_id = '' AND registro_path = ''
               AND last_error = ?
             ORDER BY id
            """,
            (OWNER_ERROR,),
        ).fetchall()
    candidates: list[Candidate] = []
    skipped: list[Skipped] = []
    for job in jobs:
        result = _classify(data_root, job)
        (candidates if isinstance(result, Candidate) else skipped).append(result)
    return candidates, skipped


def _backup_database(queue_db: Path, backup_dir: Path) -> tuple[Path, str]:
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    destination = backup_dir / f"ocr_jobs.before-reconcile-{stamp}.db"
    if destination.exists():
        raise FileExistsError(destination)
    source = sqlite3.connect(str(queue_db))
    target = sqlite3.connect(str(destination))
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return destination, digest


def apply(
    queue_db: Path,
    data_root: Path,
    backup_dir: Path,
) -> dict[str, Any]:
    """Applica la sola chiusura amministrativa dopo backup SQLite consistente."""
    candidates, skipped = inspect(queue_db, data_root)
    backup_path, backup_sha256 = _backup_database(queue_db, backup_dir)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    changed = 0
    conn = sqlite3.connect(str(queue_db), timeout=30)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ocr_job_reconciliation_audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL UNIQUE,
                outcome TEXT NOT NULL,
                original_status TEXT NOT NULL,
                original_error TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                registro_path TEXT NOT NULL,
                archive_sha256 TEXT NOT NULL,
                current_archive_sha256 TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                evidence_json TEXT NOT NULL,
                reconciled_at TEXT NOT NULL
            )
            """
        )
        for candidate in candidates:
            updated = conn.execute(
                """
                UPDATE ocr_jobs
                   SET status = ?, tenant_id = ?, registro_path = ?, updated_at = ?
                 WHERE id = ? AND status = 'failed' AND tenant_id = ''
                   AND registro_path = '' AND last_error = ?
                """,
                (
                    candidate.target_status,
                    candidate.tenant_id,
                    candidate.registro_path,
                    now,
                    candidate.job_id,
                    candidate.original_error,
                ),
            )
            if updated.rowcount != 1:
                raise RuntimeError(f"Job {candidate.job_id} cambiato durante la riconciliazione")
            conn.execute(
                """
                INSERT INTO ocr_job_reconciliation_audit (
                    job_id, outcome, original_status, original_error, tenant_id,
                    registro_path, archive_sha256, current_archive_sha256,
                    content_sha256, evidence_json, reconciled_at
                ) VALUES (?, ?, 'failed', ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.job_id,
                    candidate.outcome,
                    candidate.original_error,
                    candidate.tenant_id,
                    candidate.registro_path,
                    candidate.archive_sha256,
                    candidate.current_archive_sha256,
                    candidate.content_sha256,
                    json.dumps(candidate.evidence, ensure_ascii=False, sort_keys=True),
                    now,
                ),
            )
            changed += 1
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return report(candidates, skipped, applied=True, changed=changed, backup=(backup_path, backup_sha256))


def report(
    candidates: Iterable[Candidate],
    skipped: Iterable[Skipped],
    *,
    applied: bool = False,
    changed: int = 0,
    backup: tuple[Path, str] | None = None,
) -> dict[str, Any]:
    candidates = list(candidates)
    skipped = list(skipped)
    outcomes: dict[str, int] = {}
    for item in candidates:
        outcomes[item.outcome] = outcomes.get(item.outcome, 0) + 1
    result: dict[str, Any] = {
        "source_of_truth": "tenant_sql",
        "mode": "apply" if applied else "dry-run",
        "eligible": len(candidates),
        "changed": changed,
        "outcomes": outcomes,
        "jobs": [asdict(item) for item in candidates],
        "skipped": [asdict(item) for item in skipped],
    }
    if backup is not None:
        result["backup"] = {"path": str(backup[0]), "sha256": backup[1]}
    return result


__all__ = ["OWNER_ERROR", "Candidate", "Skipped", "inspect", "apply", "report"]
