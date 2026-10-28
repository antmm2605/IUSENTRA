"""Il trasferimento non puo' pubblicare un archivio alterato o un altro commit."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


spec = importlib.util.spec_from_file_location("release_image_loader", Path(__file__).parents[1] / "deploy/hetzner/load_verified_release_image.py")
loader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(loader)
REVISION = "a" * 40


def setup_transfer(monkeypatch, tmp_path, *, label=REVISION, free=30 * 1024**3):
    calls = []
    monkeypatch.setattr(loader.shutil, "disk_usage", lambda p: SimpleNamespace(free=free))
    monkeypatch.setattr(loader, "urlopen", lambda *a, **k: io.BytesIO(b"immutable-image"))
    def output(command, **kwargs):
        if command[1] == "info":
            return str(tmp_path)
        return json.dumps([{"Id": "sha256:verified", "Config": {"Labels": {"org.opencontainers.image.revision": label}}}])
    monkeypatch.setattr(loader.subprocess, "check_output", output)
    monkeypatch.setattr(loader.subprocess, "run", lambda command, **kwargs: calls.append(command))
    return calls


def test_corrupt_archive_never_reaches_docker_load(monkeypatch, tmp_path):
    calls = setup_transfer(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="SHA dell'archivio discordante"):
        loader.load("http://100.64.0.1/release.tar", "0" * 64, REVISION, tmp_path)
    assert calls == []
    assert list(tmp_path.iterdir()) == []


def test_verified_archive_loaded_and_temporary_file_removed(monkeypatch, tmp_path):
    calls = setup_transfer(monkeypatch, tmp_path)
    report = loader.load("http://100.64.0.1/release.tar", hashlib.sha256(b"immutable-image").hexdigest(), REVISION, tmp_path)
    assert calls[0][:2] == ["docker", "load"]
    assert report["image"] == "iusentra-app:" + REVISION
    assert report["container_avviati"] is False
    assert list(tmp_path.iterdir()) == []


def test_different_revision_cannot_be_promoted(monkeypatch, tmp_path):
    setup_transfer(monkeypatch, tmp_path, label="b" * 40)
    with pytest.raises(ValueError, match="commit richiesto"):
        loader.load("http://100.64.0.1/release.tar", hashlib.sha256(b"immutable-image").hexdigest(), REVISION, tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_same_disk_budgets_are_added_before_download(monkeypatch, tmp_path):
    calls = setup_transfer(monkeypatch, tmp_path, free=9 * 1024**3)
    monkeypatch.setattr(loader, "urlopen", lambda *a, **k: pytest.fail("download con spazio insufficiente"))
    with pytest.raises(ValueError, match="Spazio insufficiente"):
        loader.load("http://100.64.0.1/release.tar", "0" * 64, REVISION, tmp_path)
    assert calls == []
