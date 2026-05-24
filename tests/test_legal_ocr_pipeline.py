from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from legal_ocr import LegalOcrConfig, LegalOcrEvidenceStore, LegalOcrPipeline


def test_legal_ocr_pipeline_fallback_audit_lex_e_notifiche(tmp_path: Path):
    source = tmp_path / "atto.txt"
    source.write_text(
        "Tribunale di Milano\n"
        "Atto art . N . RG 1234/2026\n"
        "CF RSSMRA80A01H501U PEC studio.rossi@pec.it\n"
        "data atto 10/05/2026 importo Euro 1.234,56\n"
        "udienza fissata al 10/10/2026\n",
        encoding="utf-8",
    )
    store = LegalOcrEvidenceStore(tmp_path / "store", "tenant-a")
    pipeline = LegalOcrPipeline(
        LegalOcrConfig(tenant_id="tenant-a", primary_engine="static-low-confidence", fallback_engine="native-text-fallback"),
        store,
    )

    evidence = pipeline.run_path(source, tenant_id="tenant-a", fascicolo_id="F-1", document_id="D-1")[0]

    assert evidence["fallback_used"] is True
    assert evidence["selected_engine"] == "native-text-fallback"
    assert evidence["metrics"]["avg_confidence"] >= 0.9
    assert evidence["qc"]["hil_required"] is False
    assert evidence["correction_history"]
    assert evidence["lex_export"]["path"]
    assert evidence["notification_proposals"]
    assert (tmp_path / "store" / evidence["evidence_path"]).exists()
    assert store.load_evidence(evidence["run_id"])["run_id"] == evidence["run_id"]


def test_legal_ocr_pipeline_hil_quando_campi_obbligatori_falliscono(tmp_path: Path):
    source = tmp_path / "incerto.txt"
    source.write_text("lettura senza campi obbligatori", encoding="utf-8")
    pipeline = LegalOcrPipeline(
        LegalOcrConfig(tenant_id="tenant-a", primary_engine="static-low-confidence", fallback_engine="native-text-fallback"),
        LegalOcrEvidenceStore(tmp_path / "store", "tenant-a"),
    )

    evidence = pipeline.run_path(source, tenant_id="tenant-a", document_id="D-2")[0]

    assert evidence["fallback_used"] is True
    assert evidence["qc"]["hil_required"] is True
    assert any("Campo obbligatorio" in reason for reason in evidence["qc"]["hil_reasons"])


def test_legal_ocr_external_adapter_non_invia_cloud_e_usa_fallback(tmp_path: Path):
    source = tmp_path / "atto-cloud.txt"
    source.write_text("N. RG 1234/2026 CF RSSMRA80A01H501U PEC studio.rossi@pec.it data atto 10/05/2026 importo 100,00", encoding="utf-8")
    pipeline = LegalOcrPipeline(
        LegalOcrConfig(tenant_id="tenant-a", primary_engine="abbyy", fallback_engine="native-text-fallback", local_first_only=True),
        LegalOcrEvidenceStore(tmp_path / "store", "tenant-a"),
    )

    evidence = pipeline.run_path(source, tenant_id="tenant-a", document_id="D-cloud")[0]

    assert evidence["fallback_used"] is True
    assert evidence["selected_engine"] == "native-text-fallback"
    assert evidence["qc"]["engine_attempts"][0]["engine"] == "abbyy"
    assert evidence["qc"]["engine_attempts"][0]["errors"]


def test_legal_ocr_pipeline_zip_parent_run_id_unico(tmp_path: Path):
    archive = tmp_path / "pec.zip"
    with ZipFile(archive, "w", compression=ZIP_DEFLATED) as zf:
        zf.writestr("atto-1.txt", "N. RG 1/2026 CF RSSMRA80A01H501U PEC a@pec.it data atto 01/01/2026 importo 10,00")
        zf.writestr("atto-2.txt", "N. RG 2/2026 CF RSSMRA80A01H501U PEC b@pec.it data atto 02/01/2026 importo 20,00")
    pipeline = LegalOcrPipeline(
        LegalOcrConfig(tenant_id="tenant-a", primary_engine="native-text-fallback", fallback_engine="static-low-confidence"),
        LegalOcrEvidenceStore(tmp_path / "store", "tenant-a"),
    )

    evidences = pipeline.run_path(archive, tenant_id="tenant-a", document_id="ZIP-1")

    assert len(evidences) == 2
    parent_ids = {item["parent_run_id"] for item in evidences}
    assert len(parent_ids) == 1
    assert all(item["document_id"] == "ZIP-1" for item in evidences)


def test_legal_ocr_store_rifiuta_run_id_non_sicuri(tmp_path: Path):
    store = LegalOcrEvidenceStore(tmp_path / "store", "tenant-a")

    for unsafe in ("../altro", "/tmp/altro", "C:/tmp/altro", "run con spazi"):
        try:
            store.append_hil_correction(unsafe, {"from": "x", "to": "y"})
        except ValueError as exc:
            assert "Identificativo OCR" in str(exc)
        else:  # pragma: no cover - rende esplicita la regressione di sicurezza
            raise AssertionError(f"run_id non sicuro accettato: {unsafe}")
