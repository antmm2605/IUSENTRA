from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pct.ocr_jobs import OCRJobStore
from pct.ocr_reconciliation import OWNER_ERROR, apply, inspect, report

TENANT = "studio-prova"


def _schema_studio(path: Path, fascicolo: str, documents: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE fascicoli (id TEXT PRIMARY KEY, documenti_json TEXT);
        CREATE TABLE fascicolo_documenti_ai_versioni (
            id TEXT PRIMARY KEY, tenant_id TEXT, fascicolo_id TEXT,
            document_id TEXT, sha256 TEXT
        );
        CREATE TABLE fascicolo_documenti_ai_testi (
            id INTEGER PRIMARY KEY, version_id TEXT, text TEXT
        );
        """
    )
    conn.execute("INSERT INTO fascicoli VALUES (?, ?)", (fascicolo, json.dumps(documents)))
    for index, document in enumerate(documents, 1):
        version_id = f"v{index}"
        conn.execute(
            "INSERT INTO fascicolo_documenti_ai_versioni VALUES (?, ?, ?, ?, ?)",
            (version_id, TENANT, fascicolo, document["id"], document["hash_sha256"]),
        )
        conn.execute(
            "INSERT INTO fascicolo_documenti_ai_testi(version_id, text) VALUES (?, ?)",
            (version_id, f"testo centrale corrente {document['id']}"),
        )
    conn.commit()
    conn.close()


def _schema_registry(path: Path, fascicolo: str, documents: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE letture_oggetti (
            tenant_id TEXT, fascicolo_id TEXT, tipo TEXT, oggetto_id TEXT,
            sha256 TEXT, sha256_archivio TEXT, presente INTEGER
        );
        CREATE TABLE letture (
            tenant_id TEXT, fascicolo_id TEXT, tipo TEXT, oggetto_id TEXT,
            sha256 TEXT, lettore TEXT, stato TEXT
        );
        """
    )
    for document in documents:
        doc_id = str(document["id"])
        content_sha = f"plain-{doc_id.lower()}"
        conn.execute(
            "INSERT INTO letture_oggetti VALUES (?, ?, 'documento', ?, ?, ?, 1)",
            (TENANT, fascicolo, doc_id, content_sha, document["hash_sha256"]),
        )
        readers = ["motore_documenti"]
        if doc_id == "D1":
            readers += ["ocr", "indice_documentale"]
        for reader in readers:
            conn.execute(
                "INSERT INTO letture VALUES (?, ?, 'documento', ?, ?, ?, 'letto')",
                (TENANT, fascicolo, doc_id, content_sha, reader),
            )
    conn.commit()
    conn.close()


def _schema_index(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ocr_cache (hash_sha256 TEXT PRIMARY KEY, testo TEXT)")
    conn.executemany(
        "INSERT INTO ocr_cache VALUES (?, ?)",
        [("plain-d1", "ocr già eseguito"), ("plain-d2", "cache corrente recuperabile")],
    )
    conn.commit()
    conn.close()


def _job(queue: Path, job_id: int, fascicolo: str, doc_id: str, archive_sha: str, *, error: str = OWNER_ERROR) -> None:
    conn = sqlite3.connect(queue)
    conn.execute(
        """
        INSERT INTO ocr_jobs (
            id, status, percorso, hash_sha256, id_fasc, id_doc, nome_doc,
            tipo_doc, index_path, worker_id, attempts, created_at, updated_at,
            last_error, tenant_id, registro_path
        ) VALUES (?, 'failed', '/non-usato', ?, ?, ?, 'documento.pdf', 'ALLEGATO',
                  '/non-usato', '', 1, '2026-09-10', '2026-09-10', ?, '', '')
        """,
        (job_id, archive_sha, fascicolo, doc_id, error),
    )
    conn.commit()
    conn.close()


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    data_root = tmp_path / "data"
    queue = data_root / "search" / "ocr_jobs.db"
    OCRJobStore(str(queue))
    fascicolo = "F1"
    documents = [
        {"id": "D1", "hash_sha256": "archive-d1", "versioni": []},
        {"id": "D2", "hash_sha256": "archive-d2", "versioni": []},
        {
            "id": "D3",
            "hash_sha256": "archive-d3-current",
            "versioni": [{"hash_sha256": "archive-d3-old"}],
        },
    ]
    tenant_root = data_root / "tenants" / TENANT
    _schema_studio(tenant_root / "studio.db", fascicolo, documents)
    _schema_registry(tenant_root / "intelligence" / "registro_letture.db", fascicolo, documents)
    _schema_index(tenant_root / "search" / "index.db")
    _job(queue, 1, fascicolo, "D1", "archive-d1")
    _job(queue, 2, fascicolo, "D2", "archive-d2")
    _job(queue, 3, fascicolo, "D3", "archive-d3-old")
    _job(queue, 4, fascicolo, "D1", "archive-d1", error="errore diverso")
    return data_root, queue


def test_dry_run_classifica_senza_scrivere(tmp_path: Path):
    data_root, queue = _fixture(tmp_path)

    candidates, skipped = inspect(queue, data_root)
    result = report(candidates, skipped)

    assert result["mode"] == "dry-run"
    assert result["source_of_truth"] == "tenant_sql"
    assert result["outcomes"] == {
        "already_read": 1,
        "current_cache": 1,
        "superseded_version": 1,
    }
    conn = sqlite3.connect(queue)
    assert conn.execute("SELECT count(*) FROM ocr_jobs WHERE status = 'failed'").fetchone()[0] == 4
    assert conn.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='ocr_job_reconciliation_audit'"
    ).fetchone()[0] == 0
    conn.close()


def test_apply_fa_backup_preserva_errore_e_resta_idempotente(tmp_path: Path):
    data_root, queue = _fixture(tmp_path)
    backup_dir = tmp_path / "backup"

    result = apply(queue, data_root, backup_dir)

    assert result["changed"] == 3
    backup = Path(result["backup"]["path"])
    assert backup.is_file()
    assert len(result["backup"]["sha256"]) == 64
    conn = sqlite3.connect(queue)
    rows = conn.execute(
        "SELECT id, status, tenant_id, registro_path, last_error FROM ocr_jobs ORDER BY id"
    ).fetchall()
    assert [row[1] for row in rows] == ["recovered", "recovered", "superseded", "failed"]
    assert all(row[2] == TENANT and row[3].endswith("registro_letture.db") for row in rows[:3])
    assert all(row[4] == OWNER_ERROR for row in rows[:3])
    audit = conn.execute(
        "SELECT job_id, outcome, original_error FROM ocr_job_reconciliation_audit ORDER BY job_id"
    ).fetchall()
    assert [row[1] for row in audit] == ["already_read", "current_cache", "superseded_version"]
    assert all(row[2] == OWNER_ERROR for row in audit)
    conn.close()

    again = apply(queue, data_root, backup_dir)
    assert again["changed"] == 0
    conn = sqlite3.connect(queue)
    assert conn.execute("SELECT count(*) FROM ocr_job_reconciliation_audit").fetchone()[0] == 3
    conn.close()

    snapshot = OCRJobStore(str(queue)).status_snapshot()
    assert snapshot["riconciliati"] == 2
    assert snapshot["superati"] == 1
    assert snapshot["completati"] == 0
    assert snapshot["throughput_ultima_ora"] == 0


def test_owner_ambiguo_non_viene_toccato(tmp_path: Path):
    data_root, queue = _fixture(tmp_path)
    source = data_root / "tenants" / TENANT / "studio.db"
    duplicate = data_root / "tenants" / "secondo-studio" / "studio.db"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes(source.read_bytes())

    candidates, skipped = inspect(queue, data_root)

    assert candidates == []
    assert {item.reason for item in skipped} == {"owner_count=2"}
