from pathlib import Path


def test_performance_smoke_exists():
    assert Path("tools/performance_smoke.py").exists()


def test_performance_smoke_usa_contesto_deterministico_senza_web_esterno():
    text = Path("tools/performance_smoke.py").read_text(encoding="utf-8")

    assert "allow_external_research=False" in text
    assert '"lightweight_context": True' in text
    assert '"disable_official_web": True' in text
