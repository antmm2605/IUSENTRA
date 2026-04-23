from pathlib import Path


def test_lex_orchestrator_exists():
    assert Path("lex/orchestrator.py").exists()


def test_lex_root_exists():
    assert Path("lex").exists()
