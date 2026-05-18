from __future__ import annotations

import sqlite3
from pathlib import Path

from pct.legal_update_job_queue import (
    LEGAL_UPDATE_JOB_QUEUE_SCHEMA,
    LegalUpdateJobQueue,
    build_legal_update_dedupe_key,
)
from pct.legal_update_batch_runner import LegalUpdateJobConfig, build_legal_update_source_job_queue


def test_job_queue_deduplica_per_fonte_url_hash_e_payload(tmp_path: Path):
    queue = LegalUpdateJobQueue(tmp_path / "legal_jobs.db")
    first = queue.enqueue(
        source_code="cassazione_ultime_sent_ord_questioni",
        source_name="Cassazione",
        item_url="https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
        item_title="Questione penale pendente R.G. 9926/2026",
        content="testo ufficiale",
        payload={"attachment_url": "https://www.cortedicassazione.it/resources/cms/documents/ordinanza.pdf"},
    )
    second = queue.enqueue(
        source_code="cassazione_ultime_sent_ord_questioni",
        source_name="Cassazione",
        item_url="https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
        item_title="Questione penale pendente R.G. 9926/2026",
        content="testo ufficiale",
        payload={"attachment_url": "https://www.cortedicassazione.it/resources/cms/documents/ordinanza.pdf"},
    )

    assert first.job_id == second.job_id
    assert second.deduplicated is True
    assert queue.summary()["total"] == 1
    assert queue.summary()["queued"] == 1
    assert first.to_dict()["schema"] == LEGAL_UPDATE_JOB_QUEUE_SCHEMA


def test_job_queue_retry_timeout_e_errore_leggibile(tmp_path: Path):
    queue = LegalUpdateJobQueue(tmp_path / "legal_jobs.db")
    queued = queue.enqueue(source_code="cassazione", item_url="https://example.test/doc", max_attempts=2)

    claimed = queue.claim_next(worker_id="worker-1")
    assert claimed is not None
    assert claimed.job_id == queued.job_id
    assert claimed.status == "running"
    assert claimed.attempts == 1

    retry = queue.fail(claimed.job_id, error="PDF non leggibile")
    assert retry.status == "queued"
    assert "PDF non leggibile" in retry.last_error

    claimed_again = queue.claim_next(worker_id="worker-1")
    assert claimed_again is not None
    assert claimed_again.attempts == 2
    final = queue.fail(claimed_again.job_id, error="Lettura oltre tempo massimo", timed_out=True)

    assert final.status == "timeout"
    assert "Timeout" in final.last_error
    assert queue.summary()["timeout"] == 1


def test_job_queue_recupera_job_running_dopo_crash(tmp_path: Path):
    queue = LegalUpdateJobQueue(tmp_path / "legal_jobs.db")
    queued = queue.enqueue(source_code="cassazione", item_url="https://example.test/stale", timeout_seconds=1)
    claimed = queue.claim_next(worker_id="worker-crash")
    assert claimed is not None

    with sqlite3.connect(tmp_path / "legal_jobs.db") as conn:
        conn.execute(
            "UPDATE legal_update_jobs SET started_at='2026-01-01T00:00:00Z' WHERE job_id=?",
            (queued.job_id,),
        )

    recovered = queue.recover_stale_running(older_than_seconds=0)
    requeued = queue.get(queued.job_id)

    assert recovered == 1
    assert requeued is not None
    assert requeued.status == "queued"
    assert "recuperato" in requeued.last_error.lower()
    assert queue.claim_next(worker_id="worker-2").attempts == 2


def test_dedupe_key_cambia_quando_cambia_hash_contenuto():
    base = {
        "source_code": "cassazione",
        "item_url": "https://example.test/doc",
        "item_kind": "pdf",
        "payload": {"title": "Documento"},
    }

    first = build_legal_update_dedupe_key(**base, content_hash="a" * 64)
    second = build_legal_update_dedupe_key(**base, content_hash="b" * 64)

    assert first != second
    assert first.startswith("legal-job:")


def test_batch_runner_prepara_coda_fonti_senza_eseguire_subprocess(tmp_path: Path):
    config = LegalUpdateJobConfig(intelligence_db=str(tmp_path / "motori.json"))

    report = build_legal_update_source_job_queue(
        config,
        source_codes=["cassazione_ultime_sent_ord_questioni", "cassazione_ultime_sent_ord_questioni"],
        item_timeout_seconds=90,
        max_attempts=2,
    )

    assert report["schema"] == LEGAL_UPDATE_JOB_QUEUE_SCHEMA
    assert report["summary"]["total"] == 1
    assert report["summary"]["queued"] == 1
    assert report["jobs"][1]["deduplicated"] is True
    assert report["jobs"][0]["timeout_seconds"] == 90
