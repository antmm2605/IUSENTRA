from __future__ import annotations

import json

from PIL import Image

from legal_ocr import LegalOcrConfig, LegalOcrEvidenceStore, LegalOcrPipeline
from legal_ocr.engines import build_engine
from legal_ocr.models import PageArtifact
from legal_ocr.unlimited.client import UnlimitedOcrClient, _parse_openai_sse, build_openai_payload, extract_openai_text
from legal_ocr.unlimited.config import UnlimitedOcrSettings
from legal_ocr.unlimited.qa import answer_questions_from_text
from legal_ocr.unlimited_ocr import UnlimitedOcrEngine, split_native_and_ocr_pages


def _png(tmp_path, name="page.png"):
    path = tmp_path / name
    Image.new("RGB", (200, 120), "white").save(path)
    return path


def test_unlimited_ocr_settings_default_spento_e_fail_closed(monkeypatch):
    monkeypatch.delenv("IUSENTRA_UNLIMITED_OCR_ENABLED", raising=False)
    monkeypatch.delenv("IUSENTRA_UNLIMITED_OCR_ENDPOINT", raising=False)

    settings = UnlimitedOcrSettings.from_env()
    readiness = settings.readiness()

    assert readiness["ok"] is False
    assert "ENABLED" in str(readiness["reason"])


def test_build_engine_riconosce_unlimited_ocr():
    assert isinstance(build_engine("unlimited-ocr"), UnlimitedOcrEngine)
    assert isinstance(build_engine("baidu-unlimited-ocr"), UnlimitedOcrEngine)


def test_unlimited_ocr_hybrid_native_first_e_ai_per_pagine_scansionate(tmp_path, monkeypatch):
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENABLED", "1")
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENDPOINT", "http://127.0.0.1:10000")
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_MAX_RETRIES", "1")
    image_path = _png(tmp_path)
    native_text = (
        "Tribunale di Milano R.G. n. 12345/2026 Mario Rossi contro Beta S.r.l. "
        "Udienza del 10/10/2026. " * 3
    )
    pages = [
        PageArtifact(1, str(image_path), "a", 200, 120, text_hint=native_text),
        PageArtifact(2, str(image_path), "b", 200, 120, text_hint=""),
    ]

    def fake_post(url, payload, timeout, api_key):
        assert url.endswith("/v1/chat/completions")
        assert payload["model"] == "Unlimited-OCR"
        content = payload["messages"][0]["content"]
        assert len([item for item in content if item.get("type") == "image_url"]) == 1
        return {"choices": [{"message": {"content": "Pagina scansionata: art. 163 c.p.c. e PEC beta@example.it."}}]}

    settings = UnlimitedOcrSettings.from_env()
    engine = UnlimitedOcrEngine(client=UnlimitedOcrClient(settings, post_json=fake_post), settings=settings)
    run = engine.run(pages)

    assert run.engine == "unlimited-ocr"
    assert "native_pages=1" in run.version
    assert "ai_pages=1" in run.version
    assert "R.G. n. 12345/2026" in run.text
    assert "art. 163 c.p.c." in run.text
    assert run.tokens
    assert any("Coordinate native non disponibili" in warning for warning in run.warnings)


def test_unlimited_ocr_payload_streaming_e_parser_sse(tmp_path, monkeypatch):
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENABLED", "1")
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENDPOINT", "http://127.0.0.1:10000")
    image_path = _png(tmp_path)
    page = PageArtifact(1, str(image_path), "a", 200, 120, text_hint="")
    settings = UnlimitedOcrSettings.from_env()

    payload = build_openai_payload([page], settings=settings)
    response = _parse_openai_sse(
        'data: {"choices":[{"delta":{"content":"Tribunale "}}]}\n\n'
        'data: {"choices":[{"delta":{"content":"di Milano"}}]}\n\n'
        "data: [DONE]\n\n"
    )

    assert payload["stream"] is True
    assert extract_openai_text(response) == "Tribunale di Milano"


def test_split_native_and_ocr_pages_non_spreca_ai_su_pdf_testuale(tmp_path):
    image_path = _png(tmp_path)
    good_text = "Testo PDF nativo leggibile con molte parole e dati del fascicolo. " * 4
    pages = [
        PageArtifact(1, str(image_path), "a", 200, 120, text_hint=good_text),
        PageArtifact(2, str(image_path), "b", 200, 120, text_hint="scansione"),
    ]

    native_pages, ocr_pages, warnings = split_native_and_ocr_pages(pages, max_pages=10, max_image_bytes=1024 * 1024)

    assert [page.page for page in native_pages] == [1]
    assert [page.page for page in ocr_pages] == [2]
    assert warnings == []


def test_pipeline_con_unlimited_non_pronto_usa_fallback_corrente(tmp_path, monkeypatch):
    monkeypatch.delenv("IUSENTRA_UNLIMITED_OCR_ENABLED", raising=False)
    source = tmp_path / "atto.txt"
    source.write_text(
        "Tribunale di Milano\nR.G. n. 12345/2026\nMario Rossi contro Beta S.r.l.\n",
        encoding="utf-8",
    )
    pipeline = LegalOcrPipeline(
        LegalOcrConfig(tenant_id="tenant-a", primary_engine="unlimited-ocr", fallback_engine="native-text-fallback"),
        LegalOcrEvidenceStore(tmp_path / "store", "tenant-a"),
    )

    evidence = pipeline.run_path(source, tenant_id="tenant-a")[0]

    assert evidence["selected_engine"] == "native-text-fallback"
    attempts = (evidence.get("qc") or {}).get("engine_attempts") or []
    assert attempts[0]["engine"] == "unlimited-ocr"
    assert attempts[0]["errors"]
    vector_manifest = evidence["vector_source_manifest"]
    assert vector_manifest["full_text_sha256"]
    assert vector_manifest["full_text_chars"] >= len("Tribunale di Milano")
    assert vector_manifest["page_count"] == 1
    assert (tmp_path / "store" / vector_manifest["path"]).exists()


def test_pipeline_non_seleziona_unlimited_non_pronto_su_scansione_vuota(tmp_path, monkeypatch):
    monkeypatch.delenv("IUSENTRA_UNLIMITED_OCR_ENABLED", raising=False)
    source = _png(tmp_path, "scansione.png")
    pipeline = LegalOcrPipeline(
        LegalOcrConfig(tenant_id="tenant-a", primary_engine="unlimited-ocr", fallback_engine="native-text-fallback"),
        LegalOcrEvidenceStore(tmp_path / "store", "tenant-a"),
    )

    evidence = pipeline.run_path(source, tenant_id="tenant-a")[0]

    assert evidence["selected_engine"] == "native-text-fallback"
    assert evidence["engine_version"]["primary"] == "unlimited-ocr:not-ready"
    assert evidence["engine_version"]["selected"].startswith("native-text-fallback:")
    assert evidence["qc"]["hil_required"] is True
    assert evidence["vector_source_manifest"]["status"] == "needs_review"


def test_qa_lex_su_testo_ocr_risponde_con_citazioni():
    text = (
        "TRIBUNALE DI MILANO\n"
        "R.G. n. 12345/2026\n"
        "Mario Rossi contro Beta S.r.l.\n"
        "Visti gli artt. 163 c.p.c. e 91 c.p.c. Udienza del 10/10/2026. PEC beta@example.it."
    )

    report = answer_questions_from_text(text)

    assert report["answered"] >= 5
    answers = {item["id"]: item for item in report["answers"]}
    assert answers["numero_ruolo"]["status"] == "answered"
    assert answers["norme"]["citations"]
    assert "R.G." in json.dumps(answers["numero_ruolo"], ensure_ascii=False)


def test_qa_lex_su_scansione_giudiziaria_rgac_parti_importi():
    text = (
        "TRIBUNALE DI VIBO VALENTIA, UFFICIO DEL CONTENZIOSO CIVILE "
        "Ufficio Recupero Spese di Giustizia. Proc. N. RGAC 139/2023 - iscritto il 3.2.2023. "
        "Parti: MONTAGNESE ELISABETTA E ARRUZZOLO FRANCESCO Dos /CHIARINI MARCO "
        "Per l'inoltro si richiede il versamento di €. 27,00 ai sensi dell'art 30 DPR 115/2002. "
        "PEC roberto.montagnese@coapalmi.legalmail.it"
    )

    report = answer_questions_from_text(text)
    answers = {item["id"]: item for item in report["answers"]}

    assert report["answered"] == report["total"]
    assert "RGAC 139/2023" in answers["numero_ruolo"]["answer"]
    assert "MONTAGNESE ELISABETTA" in answers["parti"]["answer"]
    assert "ARRUZZOLO FRANCESCO" in answers["parti"]["answer"]
    assert "CHIARINI MARCO" in answers["parti"]["answer"]
    assert "27,00" in answers["importi"]["answer"]
    assert "DPR 115/2002" in answers["norme"]["answer"]
    assert "legalmail.it" in answers["pec"]["answer"]
