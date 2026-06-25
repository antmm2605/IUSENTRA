from __future__ import annotations

import json

from click.testing import CliRunner

from lex.advanced_runtime import build_advanced_ai_capabilities
from pct.cli import cli


def test_advanced_ai_capabilities_default_sicuro(monkeypatch):
    for key in [
        "IUSENTRA_AI_SPECULATIVE_MODE",
        "LEX_AI_SPECULATIVE_MODE",
        "IUSENTRA_LLM_WIKI_ENABLED",
        "IUSENTRA_GLM_OCR_ENABLED",
        "IUSENTRA_UNLIMITED_OCR_ENABLED",
        "IUSENTRA_UNLIMITED_OCR_ENDPOINT",
        "IUSENTRA_UNLIMITED_OCR_EXTERNAL_ALLOWED",
        "IUSENTRA_EMBEDDING_PROVIDER",
        "PCT_EMBEDDING_PROVIDER",
        "LEX_EXTERNAL_ALLOWED",
        "IUSENTRA_EXTERNAL_EMBEDDINGS_ALLOWED",
        "GEMINI_API_KEY",
        "IUSENTRA_GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ]:
        monkeypatch.delenv(key, raising=False)

    payload = build_advanced_ai_capabilities()

    assert payload["ok"] is True
    assert payload["enabled"] == []
    assert payload["capabilities"]["mtp_serving"]["status"] == "disabled"
    assert payload["capabilities"]["llm_wiki"]["status"] == "disabled"
    assert payload["capabilities"]["glm_ocr"]["status"] == "disabled"
    assert payload["capabilities"]["unlimited_ocr"]["status"] == "disabled"
    assert payload["capabilities"]["gemini_embedding_2"]["status"] == "available_optional"


def test_advanced_ai_capabilities_gemini_embedding_richiede_policy(monkeypatch):
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.delenv("LEX_EXTERNAL_ALLOWED", raising=False)
    monkeypatch.delenv("IUSENTRA_EXTERNAL_EMBEDDINGS_ALLOWED", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("IUSENTRA_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    payload = build_advanced_ai_capabilities()

    gemini = payload["capabilities"]["gemini_embedding_2"]
    assert payload["ok"] is False
    assert "gemini_embedding_2" in payload["blocked"]
    assert gemini["status"] == "blocked"
    assert gemini["requires_full_reembedding"] is True


def test_advanced_ai_capabilities_mtp_su_vllm_va_misurato(monkeypatch):
    monkeypatch.setenv("IUSENTRA_AI_SERVING_ENGINE", "vllm")
    monkeypatch.setenv("IUSENTRA_AI_SPECULATIVE_MODE", "mtp")

    payload = build_advanced_ai_capabilities()

    mtp = payload["capabilities"]["mtp_serving"]
    assert mtp["status"] == "ready_to_measure"
    assert mtp["measurement_required"] is True
    assert "mtp_serving" in payload["to_measure"]


def test_cli_ai_avanzata_restituisce_payload_json(monkeypatch):
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.delenv("LEX_EXTERNAL_ALLOWED", raising=False)
    monkeypatch.delenv("IUSENTRA_EXTERNAL_EMBEDDINGS_ALLOWED", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("IUSENTRA_GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    result = CliRunner().invoke(cli, ["ai-avanzata", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["capabilities"]["gemini_embedding_2"]["status"] == "blocked"


def test_cli_ai_avanzata_fail_if_blocked(monkeypatch):
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.delenv("LEX_EXTERNAL_ALLOWED", raising=False)
    monkeypatch.delenv("IUSENTRA_EXTERNAL_EMBEDDINGS_ALLOWED", raising=False)

    result = CliRunner().invoke(cli, ["ai-avanzata", "--fail-if-blocked"])

    assert result.exit_code != 0
    assert "non sono pronte" in result.output


def test_advanced_ai_capabilities_unlimited_ocr_pronto_da_misurare(monkeypatch):
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENABLED", "1")
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENDPOINT", "http://127.0.0.1:10000")

    payload = build_advanced_ai_capabilities()

    unlimited = payload["capabilities"]["unlimited_ocr"]
    assert unlimited["status"] == "ready_to_test"
    assert unlimited["measurement_required"] is True
    assert "unlimited_ocr" in payload["to_measure"]
