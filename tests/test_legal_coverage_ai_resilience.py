from __future__ import annotations

from pct.legal_coverage_ai import CoverageAutofillEngine


class EmptyCoverageRepository:
    def list_procedure_examples(self, subbranch_code: str, limit: int = 5):
        return []

    def list_learning_examples(self, subbranch_code: str, limit: int = 5):
        return []


def test_coverage_ai_usa_fallback_se_llm_restituisce_json_semanticamente_non_valido(monkeypatch):
    monkeypatch.setattr(
        "pct.legal_coverage_ai.query_ollama",
        lambda *args, **kwargs: {"subbranch_profile": {}, "procedure": []},
    )
    engine = CoverageAutofillEngine(
        ollama_url="http://127.0.0.1:11434",
        ollama_model="gemma3:1b",
        presets={"presets": {}, "subbranch_defaults": {}},
    )

    result = engine.generate_draft(
        EmptyCoverageRepository(),
        {
            "subbranch_code": "CIV_TEST",
            "gap_type": "missing_procedure",
            "gap_payload_json": {},
        },
    )

    assert result["spec_json"]["procedure"]["subbranch_code"] == "CIV_TEST"
    assert result["procedure_code"].startswith("PROC_AUTO_CIV_TEST")
    assert result["validation_report_json"]["score"] > 0
