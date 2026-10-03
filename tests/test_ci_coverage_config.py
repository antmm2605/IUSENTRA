from pathlib import Path

import pytest
import yaml


def test_critical_coverage_gate_uses_governed_config():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "tests/test_lex_docling_parser.py" in workflow
    assert "--cov-config=config/coverage-critical.ini" in workflow
    assert "--suite coverage-critical" in workflow
    assert "coverage-critical-shards:" in workflow
    assert "name: Coverage moduli critici parte" in workflow
    assert "name: Coverage moduli critici\n" not in workflow
    assert "\n  coverage-critical:\n" not in workflow
    assert "--fail-under=71" not in workflow


def test_critical_coverage_config_excludes_optional_lex_adapters():
    config = Path("config/coverage-critical.ini").read_text(encoding="utf-8")
    expected_omits = [
        "lex/image_providers/*",
        "lex/normativa/*",
        "lex/retrieval/official_sources_retriever.py",
        "lex/sources/*",
        "lex/tools/*",
    ]

    for pattern in expected_omits:
        assert pattern in config


@pytest.mark.parametrize("job", ["tests-core-shards", "coverage-critical-shards"])
def test_shards_checkout_history_for_lex_source_benchmark(job):
    workflow = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
    checkout = next(step for step in workflow["jobs"][job]["steps"]
                    if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"].get("fetch-depth") == 0, (
        "Il banco fonti deve poter caricare il retriever storico 2.435.0 tramite git show"
    )
