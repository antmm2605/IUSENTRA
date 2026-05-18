from pathlib import Path


def test_critical_coverage_gate_uses_governed_config():
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "tests/test_lex_docling_parser.py" in workflow
    assert "--cov-config=config/coverage-critical.ini" in workflow
    assert "--suite coverage-critical" in workflow
    assert "coverage-critical-shards:" in workflow
    assert "name: Coverage moduli critici parte" in workflow
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
