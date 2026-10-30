"""Un disco virtuale libero non compensa un disco Windows esaurito."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools import check_build_space as guard


def sample(device, free, required, path="/build"):
    return {"device": device, "path": path, "free_bytes": free,
            "required_bytes": required}


def test_roles_on_same_volume_require_combined_headroom():
    result = guard.assess([sample("C", 10, 6), sample("C", 10, 5, "/temp")])
    assert result["ok"] is False
    assert result["volumes"][0]["required_bytes"] == 11


def test_separate_volumes_and_exact_boundary():
    assert guard.assess([sample("C", 6, 6), sample("D", 5, 5)])["ok"]
    assert not guard.assess([sample("C", 6, 6), sample("D", 4, 5)])["ok"]


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "1e308", "invalid"])
def test_invalid_budget_cannot_disable_guard(value):
    with pytest.raises(ValueError):
        guard.positive_gib(value)


def test_large_virtual_free_does_not_hide_host_shortage(monkeypatch, capsys):
    monkeypatch.setattr(guard, "measure", lambda path, budget: sample("C", 5, 6))
    monkeypatch.setattr(guard, "engine_measure", lambda *args:
        {"ok": True, "free_bytes": 1000, "required_bytes": 6})
    assert guard.main(["--path-budget", "/build=1", "--engine-container", "iusentra-app"]) == 2
    assert '"ok": false' in capsys.readouterr().out


def test_missing_path_fails_without_creating_it(tmp_path):
    target = tmp_path / "missing"
    assert guard.main(["--path-budget", f"{target}=1"]) == 2
    assert not target.exists()


@pytest.mark.parametrize("payload", ['{}', '{"free_bytes": true}', 'invalid'])
def test_unavailable_or_invalid_engine_measurement_fails(monkeypatch, payload):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=payload)

    monkeypatch.setattr(guard.subprocess, "run", run)
    with pytest.raises((ValueError, KeyError)):
        guard.engine_measure("iusentra-app", 10)
    assert calls[0][:4] == ["docker", "exec", "iusentra-app", "python"]
    assert "run" not in calls[0]


def test_deploy_preflight_precedes_both_build_paths():
    script = (Path(__file__).parents[1] / "deploy/hetzner/deploy.sh").read_text(encoding="utf-8")
    preflight = script.index("tools/check_build_space.py")
    assert preflight < script.index('docker build --label')
    assert preflight < script.index('"${PROFILE_ARGS[@]}" build')
    assert 'check_build_capacity\n      docker build' in script
    assert 'else\n  check_build_capacity\n  docker compose' in script

def test_prebuilt_image_of_another_commit_falls_back_to_build():
    """L'archivio di .env.hetzner può riferirsi a un'altra release: si costruisce l'immagine del commit."""
    script = (Path(__file__).parents[1] / "deploy/hetzner/deploy.sh").read_text(encoding="utf-8")
    loader = script.index("load_verified_release_image.py")
    fallback = script.index('if [ "$prebuilt_loaded" != "1" ]; then')
    assert loader < fallback < script.index('docker build --label')
    assert 'if python3 deploy/hetzner/load_verified_release_image.py' in script
    assert "prebuilt_loaded=1" in script[loader:fallback]


def test_measure_resolves_link_to_physical_volume(tmp_path):
    real_disk = tmp_path / "physical"
    real_disk.mkdir()
    displayed_path = tmp_path / "displayed"
    try:
        displayed_path.symlink_to(real_disk, target_is_directory=True)
    except OSError:
        pytest.skip("Creazione collegamenti non disponibile su questa macchina")
    result = guard.measure(str(displayed_path), 10)
    assert result["path"] == str(real_disk.resolve())
    assert result["device"] == real_disk.stat().st_dev
