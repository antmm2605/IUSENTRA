from __future__ import annotations

import json
from pathlib import Path

from lex.dataset.nightly import (
    build_lex_dataset_for_document_ai_json,
    infer_document_ai_tenant_ids,
    run_lex_dataset_nightly,
)
from pct.tenant import GestioneTenant


def _write_document_ai_json(
    path: Path,
    *,
    tenant_id: str = "tenant-a",
    text: str | None = None,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "documents": [
            {
                "id": "docai-1",
                "tenant_id": tenant_id,
                "fascicolo_id": "fas-1",
                "original_filename": "memoria.pdf",
                "safe_filename": "memoria.pdf",
                "mime_type": "application/pdf",
                "sha256": "abc123",
                "status": "ready",
            }
        ],
        "texts": [
            {
                "tenant_id": tenant_id,
                "fascicolo_id": "fas-1",
                "document_id": "docai-1",
                "version_id": "v1",
                "text": text
                or (
                    "Il documento contiene una memoria difensiva con domanda, "
                    "eccezioni processuali e richiesta istruttoria dello studio."
                ),
                "pages": [
                    {
                        "page_number": 1,
                        "text": text
                        or "Memoria difensiva con domanda, eccezioni processuali e richiesta istruttoria.",
                    }
                ],
            }
        ],
        "audit_events": [],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_dataset_notturno_prepara_artefatti_senza_addestramento(tmp_path: Path):
    source = _write_document_ai_json(tmp_path / "fascicoli" / "documenti_ai" / "documenti_ai.json")

    result = build_lex_dataset_for_document_ai_json(
        tenant_id="tenant-a",
        document_ai_json_path=source,
        output_root=tmp_path / "intelligence" / "lex_dataset",
        include_pending_review_export=True,
    )

    output = tmp_path / "intelligence" / "lex_dataset" / "tenant-a"
    assert result["status"] == "completed"
    assert result["documents_count"] == 1
    assert result["automatic_training"] is False
    assert result["external_training"] is False
    assert result["human_review_required"] is True
    assert (output / "manifest.json").exists()
    assert (output / "chunks.jsonl").exists()
    assert (output / "qa_review_queue.json").exists()
    assert (tmp_path / "intelligence" / "lex_dataset" / "latest_job.json").exists()


def test_run_lex_dataset_nightly_compare_console_superadmin(tmp_path: Path):
    studio_root = tmp_path / "studio"
    source = studio_root / "fascicoli" / "documenti_ai" / "documenti_ai.json"
    _write_document_ai_json(source, tenant_id="studio-rossi")

    report = run_lex_dataset_nightly(
        config={
            "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
            "FASCICOLI_DB": str(studio_root / "fascicoli" / "fascicoli.json"),
            "IUSENTRA_LEX_DATASET_EXPORT_PENDING_REVIEW": "1",
        }
    )

    assert report["ok"] is True
    assert report["tenants_processed"] == 1
    assert report["documents_count"] == 1
    assert report["automatic_training"] is False
    assert "Nessun addestramento automatico avviato" in report["summary"]
    assert infer_document_ai_tenant_ids(source) == ("studio-rossi",)
    assert (studio_root / "intelligence" / "lex_dataset" / "studio-rossi" / "manifest.json").exists()


def test_run_lex_dataset_nightly_salva_fingerprint_e_salta_sorgente_invariata(tmp_path: Path, monkeypatch):
    studio_root = tmp_path / "studio"
    source = studio_root / "fascicoli" / "documenti_ai" / "documenti_ai.json"
    _write_document_ai_json(source, tenant_id="studio-rossi")
    cfg = {
        "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
        "FASCICOLI_DB": str(studio_root / "fascicoli" / "fascicoli.json"),
        "IUSENTRA_LEX_DATASET_EXPORT_PENDING_REVIEW": "1",
    }

    first = run_lex_dataset_nightly(config=cfg)
    assert first["completed"] == 1
    assert (studio_root / "intelligence" / "lex_dataset" / "source_index.json").exists()

    def fail_load(*_args, **_kwargs):
        raise AssertionError("documenti_ai.json invariato non deve essere riletto dal job notturno")

    monkeypatch.setattr("lex.dataset.nightly.load_document_ai_json_documents", fail_load)

    second = run_lex_dataset_nightly(config=cfg)

    assert second["ok"] is True
    assert second["completed"] == 0
    assert second["skipped_unchanged"] == 1
    assert second["jobs"][0]["status"] == "skipped_unchanged"
    assert second["jobs"][0]["scan_mode"] == "source_unchanged_skip"
    assert second["documents_count"] == 1


def test_run_lex_dataset_nightly_scrive_chunk_sensibili_solo_in_locale(tmp_path: Path):
    studio_root = tmp_path / "studio"
    _write_document_ai_json(
        studio_root / "fascicoli" / "documenti_ai" / "documenti_ai.json",
        tenant_id="studio-verdi",
        text=(
            "Il cliente RSSMRA80A01H501U ha inviato mario.rossi@example.com e "
            "chiede una memoria riservata con dati personali da tenere nello studio."
        ),
    )

    report = run_lex_dataset_nightly(
        config={
            "TENANTS_REGISTRY": str(tmp_path / "tenants.json"),
            "FASCICOLI_DB": str(studio_root / "fascicoli" / "fascicoli.json"),
        }
    )

    output = studio_root / "intelligence" / "lex_dataset" / "studio-verdi"
    assert report["ok"] is True
    assert report["jobs"][0]["sensitive_chunks_count"] >= 1
    assert report["jobs"][0]["external_training"] is False
    assert report["jobs"][0]["automatic_training"] is False
    assert (output / "chunks.jsonl").exists()
    assert (output / "qa_review_queue.json").exists()


def test_run_lex_dataset_nightly_usa_documenti_ai_condivisi_ma_scrive_nel_tenant(tmp_path: Path):
    registry = tmp_path / "tenants.json"
    manager = GestioneTenant(str(registry))
    studio = manager.crea("Studio Rossi", "studio-rossi", db_config={"mode": "SQLITE"})
    shared_source = tmp_path / "fascicoli" / "documenti_ai" / "documenti_ai.json"
    _write_document_ai_json(shared_source, tenant_id=studio.slug)

    report = run_lex_dataset_nightly(
        config={
            "TENANTS_REGISTRY": str(registry),
            "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        }
    )

    tenant_output = tmp_path / "tenants" / studio.storage_key / "intelligence" / "lex_dataset" / studio.slug
    assert report["ok"] is True
    assert report["tenants_processed"] == 1
    assert report["documents_count"] == 1
    assert (tenant_output / "qa_review_queue.json").exists()
    assert not (tmp_path / "intelligence" / "lex_dataset" / studio.slug / "qa_review_queue.json").exists()
