"""Riallinea solo sorgenti già acquisiti e confrontati, dopo una copia verificata."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

SNAPSHOT_SHA256 = "04013ad3b0b50ed3e6b45f905a8b90911cd131093adc9637d5d0c367bc44c487"
EXPECTED_SERVER_HEAD = "693baa9df4212fe5e1b8ca8cd1d9f2c82208607e"


def sha256(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def reconcile(repo, target, branch, snapshot, backup):
    repo, snapshot, backup = repo.resolve(), snapshot.resolve(), backup.resolve()
    assert re.fullmatch(r"[0-9a-f]{40}", target)
    assert branch in {"Codex/legal-electronic-filing-kIxcV", "claude/legal-electronic-filing-kIxcV"}
    assert not backup.is_relative_to(repo)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args])
    status = git("status", "--porcelain")
    if not status:
        return {"already_clean": True}
    assert sha256(snapshot) == SNAPSHOT_SHA256, "Copia dei sorgenti diversa da quella confrontata"
    with tarfile.open(snapshot) as archive:
        manifest = json.load(archive.extractfile("manifest.json"))
    assert git("rev-parse", "HEAD").decode().strip() == manifest["head"] == EXPECTED_SERVER_HEAD
    assert subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", manifest["head"], target]).returncode == 0
    assert subprocess.run(["git", "-C", str(repo), "merge-base", "--is-ancestor", manifest["target"], target]).returncode == 0
    assert not git("diff", "--name-only", manifest["target"], target, "--", "frontend", "pct", "web", "lex"), "Sorgenti applicativi cambiati dopo il confronto"
    entries = {e["path"]: e for e in manifest["entries"]}
    changed = set(git("diff", "HEAD", "--name-only", "-z").decode().split("\0"))
    changed.update(git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0"))
    changed.discard("")
    assert changed <= entries.keys(), "Nuovi file da preservare e confrontare"
    for name in changed:
        path = repo / name
        assert not path.is_symlink() and path.resolve().is_relative_to(repo) and ".git" not in path.parts
        entry = entries[name]
        assert path.is_file() == entry["exists"]
        if path.is_file():
            assert sha256(path) == entry["sha256"], "Sorgente modificato dopo il confronto: " + name
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(snapshot, backup)
    assert sha256(backup) == SNAPSHOT_SHA256, "Copia di sicurezza non verificata"
    backup.chmod(0o600)
    tracked = set(git("ls-tree", "-r", "--name-only", "-z", target).decode().split("\0"))
    archived = [name for name in changed if name not in tracked]
    # Rimuove dalla sola checkout i file extra già conservati nella copia;
    # non tocca dati dello studio, volumi, container o file ignorati.
    for name in archived:
        path = repo / name
        if path.is_file():
            path.unlink()
    git("checkout", "-f", "-B", branch, target)
    assert not git("status", "--porcelain"), "Repository ancora da verificare"
    return {"head": target, "backup": str(backup), "backup_sha256": SNAPSHOT_SHA256, "preserved_files": len(changed), "extra_files_archived": len(archived)}


if __name__ == "__main__":
    result = reconcile(Path("/opt/iusentra/repo"), sys.argv[1], sys.argv[2], Path(sys.argv[3]), Path("/opt/iusentra/backups/sorgenti-prima-2.436.11-20261007.tar.gz"))
    print(json.dumps(result))
