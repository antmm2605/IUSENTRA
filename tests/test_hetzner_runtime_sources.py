"""Protezione degli hotfix nel filesystem scrivibile del container."""

import importlib.util
import hashlib
import io
import subprocess
import tarfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "runtime_sources", Path(__file__).parents[1] / "deploy/hetzner/check_runtime_sources.py"
)
guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(guard)


@pytest.mark.parametrize("kind,candidate,live,expected", [
    ("C", b"hotfix", b"hotfix", []),
    ("C", b"old", b"hotfix", ["web/services/test.py"]),
    ("A", None, b"new", ["web/services/test.py"]),
    ("D", b"old", None, ["web/services/test.py"]),
    ("D", None, None, []),
])
def test_runtime_differences_are_preserved(monkeypatch, kind, candidate, live, expected):
    def output(command, **kwargs):
        if command[1] == "diff":
            return f"{kind} /app/web/services/test.py\nA /app/instance/cache.json\n"
        assert command[:3] == ["docker", "exec", "app"]
        return live

    monkeypatch.setattr(guard.subprocess, "check_output", output)
    monkeypatch.setattr(guard.subprocess, "run", lambda *a, **kw: subprocess.CompletedProcess(
        a[0], 0 if candidate is not None else 128, candidate or b"", b""
    ))
    assert guard.conflicts("repo", "a" * 40, "app") == expected


def test_docker_failure_never_means_clean(monkeypatch):
    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr(guard.subprocess, "check_output", fail)
    with pytest.raises(subprocess.CalledProcessError):
        guard.conflicts("repo", "a" * 40, "app")


@pytest.mark.parametrize("live_content,expected", [(b"live bundle", True), (b"hotfix", False)])
def test_modified_bundle_must_match_git_exactly(monkeypatch, live_content, expected):
    archive = io.BytesIO()
    raw = b"live bundle"
    with tarfile.open(fileobj=archive, mode="w") as out:
        member = tarfile.TarInfo("web/static/react/index.html")
        member.size = len(raw)
        out.addfile(member, io.BytesIO(raw))
    checksum = hashlib.sha256(live_content).hexdigest()
    tree = hashlib.sha256(f"index.html\0{checksum}\n".encode()).hexdigest()

    def output(command, **kwargs):
        return tree if command[0] == "docker" else archive.getvalue()

    monkeypatch.setattr(guard.subprocess, "check_output", output)
    assert guard.assets_match("repo", "a" * 40, "app") is expected
