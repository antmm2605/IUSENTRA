from __future__ import annotations

import json

import pytest
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


@pytest.mark.parametrize(
    ("endpoint", "provider", "stato"),
    [
        ("", "self_hosted", "missing_endpoint"),
        ("https://ocr.example.invalid", "cloud", "blocked"),
        ("http://127.0.0.1:10000", "self_hosted", "ready_to_test"),
    ],
)
def test_stato_glm_ocr_rispetta_endpoint_e_policy(monkeypatch, endpoint, provider, stato):
    monkeypatch.setenv("IUSENTRA_GLM_OCR_ENABLED", "1")
    monkeypatch.setenv("IUSENTRA_GLM_OCR_PROVIDER", provider)
    monkeypatch.setenv("IUSENTRA_GLM_OCR_ENDPOINT", endpoint)
    monkeypatch.delenv("GLM_OCR_ENDPOINT", raising=False)
    monkeypatch.setenv("LEX_EXTERNAL_ALLOWED", "0")
    monkeypatch.delenv("IUSENTRA_EXTERNAL_EMBEDDINGS_ALLOWED", raising=False)

    risultato = build_advanced_ai_capabilities()
    assert risultato["capabilities"]["glm_ocr"]["status"] == stato
    assert ("glm_ocr" in risultato["to_measure"]) is (stato == "ready_to_test")
    assert ("glm_ocr" in risultato["blocked"]) is (stato != "ready_to_test")


@pytest.mark.parametrize(
    ("endpoint", "provider", "stato"),
    [
        ("", "self_hosted", "missing_endpoint"),
        ("https://ocr.example.invalid", "cloud", "blocked"),
        ("https://ocr.example.invalid", "self_hosted", "blocked"),
    ],
)
def test_stato_unlimited_ocr_blocca_un_endpoint_non_governato(monkeypatch, endpoint, provider, stato):
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENABLED", "1")
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_PROVIDER", provider)
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENDPOINT", endpoint)
    monkeypatch.delenv("UNLIMITED_OCR_ENDPOINT", raising=False)
    for nome in ("LEX_EXTERNAL_ALLOWED", "IUSENTRA_EXTERNAL_EMBEDDINGS_ALLOWED", "IUSENTRA_UNLIMITED_OCR_EXTERNAL_ALLOWED"):
        monkeypatch.delenv(nome, raising=False)

    risultato = build_advanced_ai_capabilities()
    assert risultato["capabilities"]["unlimited_ocr"]["status"] == stato
    assert "unlimited_ocr" in risultato["blocked"]
    assert "unlimited_ocr" not in risultato["to_measure"]


def test_unlimited_ocr_verifica_locale_anche_senza_adattatore(monkeypatch):
    from legal_ocr.unlimited import config

    def indisponibile(_):
        raise ImportError("Configurazione aggiuntiva non disponibile")

    monkeypatch.setattr(config, "endpoint_is_local_or_private", indisponibile)
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENABLED", "1")
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_PROVIDER", "self_hosted")
    monkeypatch.setenv("IUSENTRA_UNLIMITED_OCR_ENDPOINT", "http://127.0.0.1:10000")
    risultato = build_advanced_ai_capabilities()
    assert risultato["capabilities"]["unlimited_ocr"]["endpoint_configured"]
    assert "unlimited_ocr" in risultato["to_measure"]


def test_wiki_esige_pagine_compilate_prima_della_valutazione(monkeypatch, tmp_path):
    monkeypatch.setenv("IUSENTRA_LLM_WIKI_ENABLED", "1")
    monkeypatch.setenv("IUSENTRA_LLM_WIKI_ROOT", str(tmp_path))
    assert build_advanced_ai_capabilities()["capabilities"]["llm_wiki"]["status"] == "missing_index"

    (tmp_path / "nota.md").write_text("# Fonte di prova", encoding="utf-8")
    risultato = build_advanced_ai_capabilities()
    assert risultato["capabilities"]["llm_wiki"]["compiled_pages"] == 1
    assert risultato["capabilities"]["llm_wiki"]["status"] == "ready_to_evaluate"
    assert "llm_wiki" in risultato["to_measure"]


def test_mtp_segnala_serving_non_compatibile(monkeypatch):
    monkeypatch.setenv("IUSENTRA_AI_SERVING_ENGINE", "ollama")
    monkeypatch.setenv("IUSENTRA_AI_SPECULATIVE_MODE", "mtp")
    risultato = build_advanced_ai_capabilities()
    assert risultato["capabilities"]["mtp_serving"]["status"] == "blocked"
    assert "mtp_serving" not in risultato["to_measure"]


def test_gemini_configurazione_misurabile_senza_esporre_chiave(monkeypatch):
    monkeypatch.setenv("IUSENTRA_EMBEDDING_PROVIDER", "gemini")
    monkeypatch.setenv("LEX_EXTERNAL_ALLOWED", "1")
    monkeypatch.setenv("IUSENTRA_GEMINI_EMBEDDING_DIMENSIONS", "non valido")
    for nome in ("IUSENTRA_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(nome, raising=False)
    gemini = build_advanced_ai_capabilities()["capabilities"]["gemini_embedding_2"]
    assert gemini["status"] == "missing_credentials"
    assert gemini["output_dimensions"] == 768

    valore_di_prova = "valore-fittizio-verifica"
    monkeypatch.setenv("IUSENTRA_GEMINI_API_KEY", valore_di_prova)
    monkeypatch.setenv("IUSENTRA_GEMINI_EMBEDDING_DIMENSIONS", "4000")
    gemini = build_advanced_ai_capabilities()["capabilities"]["gemini_embedding_2"]
    assert gemini["status"] == "ready_to_measure" and gemini["api_key_present"]
    assert gemini["output_dimensions"] == 3072
    assert valore_di_prova not in json.dumps(gemini)
