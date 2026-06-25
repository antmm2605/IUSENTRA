from pathlib import Path
from types import SimpleNamespace

from pct import ocr
from pct.document_intelligence.extraction import ExtractionResult


def test_pct_ocr_delega_alla_pipeline_document_intelligence(monkeypatch):
    calls: list[tuple[bytes, str, str]] = []

    def fake_extract(content: bytes, filename: str, file_type: str) -> ExtractionResult:
        calls.append((bytes(content), filename, file_type))
        return ExtractionResult(
            ok=True,
            text="Testo letto con OCR integrale DocumentAI.",
            pages=[],
            extraction_engine="legal-ocr:unlimited-ocr:document-index",
        )

    monkeypatch.setattr("pct.document_intelligence.extraction.extract_text_from_document", fake_extract)

    text = ocr.estrai_testo(b"%PDF-1.7\npayload", "scansione.pdf")

    assert text == "Testo letto con OCR integrale DocumentAI."
    assert calls == [(b"%PDF-1.7\npayload", "scansione.pdf", "pdf")]


def test_pct_ocr_accetta_anche_percorso_locale(monkeypatch, tmp_path: Path):
    source = tmp_path / "scansione.pdf"
    source.write_bytes(b"%PDF-1.7\npayload")

    def fake_extract(content: bytes, filename: str, file_type: str) -> ExtractionResult:
        assert content == b"%PDF-1.7\npayload"
        assert filename == "scansione.pdf"
        assert file_type == "pdf"
        return ExtractionResult(
            ok=True,
            text="Testo letto da percorso con pipeline DocumentAI.",
            pages=[],
            extraction_engine="legal-ocr:unlimited-ocr:document-index",
        )

    monkeypatch.setattr("pct.document_intelligence.extraction.extract_text_from_document", fake_extract)

    assert ocr.estrai_testo(source) == "Testo letto da percorso con pipeline DocumentAI."


def test_document_ai_tesseract_configura_tessdata_senza_flag_quotato(tmp_path: Path, monkeypatch):
    from pct.document_intelligence import extraction

    tessdata = tmp_path / "IUSENTRA" / "tessdata"
    tessdata.mkdir(parents=True)
    (tessdata / "ita.traineddata").write_bytes(b"dummy")
    fake_pytesseract = SimpleNamespace(pytesseract=SimpleNamespace(tesseract_cmd=""))

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("TESSDATA_PREFIX", f'"{tessdata}"')
    monkeypatch.setattr(extraction, "_resolve_tesseract_command", lambda: "")

    config = extraction._configure_tesseract_runtime(fake_pytesseract)

    assert config == ""
    assert extraction.os.environ["TESSDATA_PREFIX"] == str(tessdata)


def test_legal_ocr_tesseract_configura_tessdata_senza_flag_quotato(tmp_path: Path, monkeypatch):
    from legal_ocr import engines

    tessdata = tmp_path / "IUSENTRA" / "tessdata"
    tessdata.mkdir(parents=True)
    (tessdata / "ita.traineddata").write_bytes(b"dummy")
    fake_pytesseract = SimpleNamespace(pytesseract=SimpleNamespace(tesseract_cmd=""))

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("TESSDATA_PREFIX", f'"{tessdata}"')
    monkeypatch.setattr(engines, "_resolve_tesseract_command", lambda: "")

    config = engines._configure_tesseract_runtime(fake_pytesseract)

    assert config == ""
    assert engines.os.environ["TESSDATA_PREFIX"] == str(tessdata)
