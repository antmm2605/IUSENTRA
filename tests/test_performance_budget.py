from pathlib import Path


def test_performance_smoke_exists():
    assert Path("tools/performance_smoke.py").exists()
