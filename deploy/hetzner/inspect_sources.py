"""Snapshot in sola lettura dei sorgenti locali da preservare prima del deploy."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile

root = Path("/opt/iusentra/repo")
allowed = {"frontend", "pct", "web", "lex", "deploy", "scripts", "tools", "tests", "docs", ".github"}
suffixes = {".py", ".tsx", ".ts", ".css", ".js", ".mjs", ".json", ".html", ".md", ".yml", ".yaml", ".sh", ".txt", ".toml", ".ini", ".cfg", ".conf", ".sql"}
def git(*args):
    return subprocess.check_output(["git", "-C", str(root), *args])

git("fetch", "origin", "Codex/legal-electronic-filing-kIxcV")
target = git("rev-parse", "FETCH_HEAD").decode().strip()
paths = sorted(set(git("diff", "HEAD", "--name-only", "-z").decode().split("\0") + git("ls-files", "--others", "--exclude-standard", "-z").decode().split("\0")))
entries = []
excluded = []
root_names = {".dockerignore", ".editorconfig", ".flake8", ".gitattributes", ".gitignore", ".ruff.toml", "Dockerfile", "LICENSE"}
allowed.update({"requirements", "docker", "config", "configs", "migrations", "alembic", "resources", "packaging", "legal_ocr"})
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    for name in paths:
        p = root / name
        root_source = "/" not in name and (p.suffix in suffixes or name in root_names) and name != "tokens.json" and not name.startswith(".env")
        selected = (name.split("/")[0] in allowed and p.suffix in suffixes) or root_source
        if not name:
            continue
        if p.is_symlink() or not selected or "node_modules" in p.parts or "__pycache__" in p.parts:
            excluded.append(name)
            continue
        candidate = subprocess.run(["git", "-C", str(root), "show", target + ":" + name], capture_output=True)
        data = p.read_bytes() if p.is_file() else None
        assert data is None or len(data) < 50_000_000
        entries.append({"path": name, "exists": data is not None, "matches_candidate": candidate.returncode == 0 and candidate.stdout == data, "sha256": hashlib.sha256(data).hexdigest() if data is not None else None, "candidate_exists": candidate.returncode == 0})
        if data is not None:
            info = tarfile.TarInfo("sources/" + name)
            info.size = len(data)
            info.mode = 0o755 if p.stat().st_mode & 0o111 else 0o644
            archive.addfile(info, io.BytesIO(data))
    manifest = json.dumps({"head": git("rev-parse", "HEAD").decode().strip(), "target": target, "entries": entries, "excluded_paths": excluded}, ensure_ascii=False, indent=2).encode()
    info = tarfile.TarInfo("manifest.json")
    info.size = len(manifest)
    archive.addfile(info, io.BytesIO(manifest))
