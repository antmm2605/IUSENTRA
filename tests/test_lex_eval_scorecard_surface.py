from __future__ import annotations

import json
from pathlib import Path

from web.services.lex_eval_scorecard import build_lex_eval_scorecard


def test_lex_eval_scorecard_distingue_catalogo_da_prove_reali(tmp_path: Path, monkeypatch):
    results_path = tmp_path / "missing-results.json"
    monkeypatch.setenv("IUSENTRA_LEX_EVAL_RESULTS", str(results_path))

    payload = build_lex_eval_scorecard()

    assert payload["summary"]["cases_total"] == 8
    assert payload["summary"]["measured_cases"] == 0
    assert payload["summary"]["measurement_status"] == "non_misurata"
    assert payload["cases"][0]["measured"] is False
    assert payload["kpi"][0]["value"] == "non misurato"


def test_lex_eval_scorecard_legge_risultati_reali(tmp_path: Path, monkeypatch):
    results_path = tmp_path / "results.json"
    results_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "case_id": "fascicolo-001",
                        "passed": True,
                        "duration_ms": 1200,
                        "sources_useful": True,
                    },
                    {
                        "case_id": "udienza-001",
                        "passed": False,
                        "duration_ms": 2400,
                        "warnings": ["Manca una fonte utile."],
                        "sources_useful": False,
                    },
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("IUSENTRA_LEX_EVAL_RESULTS", str(results_path))

    payload = build_lex_eval_scorecard()

    assert payload["summary"]["measured_cases"] == 2
    assert payload["summary"]["passed_cases"] == 1
    assert payload["summary"]["failed_cases"] == 1
    assert payload["summary"]["sources_useful_percent"] == 50.0
    assert payload["summary"]["avg_response_ms"] == 1800.0
    assert payload["summary"]["measurement_status"] == "parziale"
    failed = next(case for case in payload["cases"] if case["id"] == "udienza-001")
    assert failed["measured"] is True
    assert failed["passed"] is False
    assert failed["warnings"] == ["Manca una fonte utile."]
