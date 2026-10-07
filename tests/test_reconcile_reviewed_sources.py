"""Il riallineamento preserva gli extra e rifiuta modifiche non confrontate."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tarfile

import pytest

spec = importlib.util.spec_from_file_location("reviewed_sources", Path(__file__).resolve().parents[1] / "deploy/hetzner/reconcile_reviewed_sources.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def reviewed(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args]).decode().strip()
    git("init")
    git("config", "user.email", "test@example.test")
    git("config", "user.name", "Test")
    (repo / "frontend").mkdir()
    (repo / "frontend/source.ts").write_text("old\n")
    (repo / ".gitignore").write_text("data/\n")
    git("add", ".")
    git("commit", "-m", "base")
    base = git("rev-parse", "HEAD")
    (repo / "frontend/source.ts").write_text("reviewed\n")
    git("commit", "-am", "candidate")
    target = git("rev-parse", "HEAD")
    git("checkout", "--detach", base)
    (repo / "frontend/source.ts").write_bytes(b"reviewed\r\n")
    (repo / "tools").mkdir()
    (repo / "tools/preserved.py").write_text("print('preserve')\n")
    (repo / "data").mkdir()
    (repo / "data/studio.db").write_bytes(b"tenant-data")
    entries = []
    snapshot = tmp_path / "snapshot.tar.gz"
    with tarfile.open(snapshot, "w:gz") as archive:
        for name in ("frontend/source.ts", "tools/preserved.py"):
            data = (repo / name).read_bytes()
            entries.append({"path": name, "exists": True, "sha256": hashlib.sha256(data).hexdigest()})
            info = tarfile.TarInfo("sources/" + name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
        data = json.dumps({"head": base, "target": target, "entries": entries}).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    monkeypatch.setattr(module, "EXPECTED_SERVER_HEAD", base)
    monkeypatch.setattr(module, "SNAPSHOT_SHA256", module.sha256(snapshot))
    return repo, target, snapshot, tmp_path / "backups/snapshot.tar.gz", base


def test_reconcile_preserves_archived_sources_and_leaves_tenant_data(reviewed):
    repo, target, snapshot, backup, _ = reviewed
    result = module.reconcile(repo, target, "Codex/legal-electronic-filing-kIxcV", snapshot, backup)
    assert result["extra_files_archived"] == 1
    assert backup.read_bytes() == snapshot.read_bytes()
    with tarfile.open(backup) as archive:
        assert archive.extractfile("sources/tools/preserved.py").read() == b"print('preserve')\n"
    assert (repo / "frontend/source.ts").read_bytes() == b"reviewed\n"
    assert (repo / "data/studio.db").read_bytes() == b"tenant-data"
    assert module.reconcile(repo, target, "Codex/legal-electronic-filing-kIxcV", snapshot, backup)["already_clean"]


def test_reconcile_rejects_new_unreviewed_source(reviewed):
    repo, target, snapshot, backup, base = reviewed
    (repo / "tools/new-hotfix.py").write_text("new")
    with pytest.raises(AssertionError, match="Nuovi file"):
        module.reconcile(repo, target, "Codex/legal-electronic-filing-kIxcV", snapshot, backup)
    assert not backup.exists()
    assert subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"]).decode().strip() == base


def test_reconcile_rejects_changed_hotfix_after_snapshot(reviewed):
    repo, target, snapshot, backup, _ = reviewed
    (repo / "frontend/source.ts").write_text("unreviewed hotfix")
    with pytest.raises(AssertionError, match="modificato dopo"):
        module.reconcile(repo, target, "Codex/legal-electronic-filing-kIxcV", snapshot, backup)
    assert not backup.exists()
    assert (repo / "frontend/source.ts").read_text() == "unreviewed hotfix"


def test_reconcile_rejects_corrupted_snapshot_before_changes(reviewed):
    repo, target, snapshot, backup, _ = reviewed
    snapshot.write_bytes(snapshot.read_bytes() + b"changed")
    with pytest.raises(AssertionError, match="Copia dei sorgenti"):
        module.reconcile(repo, target, "Codex/legal-electronic-filing-kIxcV", snapshot, backup)
    assert not backup.exists()
    assert (repo / "tools/preserved.py").exists()


def test_reconcile_fetches_release_absent_from_server_objects(reviewed, tmp_path):
    repo, target, snapshot, backup, base = reviewed
    subprocess.run(["git", "-C", str(repo), "branch", "server-base", base], check=True)
    subprocess.run(["git", "-C", str(repo), "branch", "release", target], check=True)
    server = tmp_path / "server"
    subprocess.run(["git", "clone", "--no-local", "--single-branch", "--branch", "server-base", str(repo), str(server)], check=True)
    assert subprocess.run(["git", "-C", str(server), "cat-file", "-e", target + "^{commit}"], capture_output=True).returncode != 0
    (server / "frontend/source.ts").write_bytes((repo / "frontend/source.ts").read_bytes())
    (server / "tools").mkdir()
    (server / "tools/preserved.py").write_bytes((repo / "tools/preserved.py").read_bytes())
    result = module.reconcile(server, target, "Codex/legal-electronic-filing-kIxcV", snapshot, backup)
    assert result["head"] == target
    assert backup.read_bytes() == snapshot.read_bytes()
    assert subprocess.check_output(["git", "-C", str(server), "rev-parse", "HEAD"]).decode().strip() == target
