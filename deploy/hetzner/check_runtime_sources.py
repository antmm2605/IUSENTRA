"""Blocca il deploy se perde sorgenti o asset modificati nei container."""

import argparse
import hashlib
import io
import subprocess
import tarfile
from pathlib import PurePosixPath

SOURCE_SUFFIXES = {".py", ".html", ".jinja", ".jinja2", ".tsx", ".ts", ".js", ".mjs", ".css", ".scss"}
TREE_HASH_CODE = r"""
import hashlib, pathlib
root = pathlib.Path('/app/web/static/react')
rows = [(p.relative_to(root).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
        for p in root.rglob('*') if p.is_file()]
print(hashlib.sha256(''.join(n + '\0' + h + '\n' for n, h in sorted(rows)).encode()).hexdigest())
"""


def source_path(path):
    relative = PurePosixPath(path).relative_to("/app")
    return (relative.suffix in SOURCE_SUFFIXES and "__pycache__" not in relative.parts
            and relative.parts[0] not in {"instance", "data", ".venv", "node_modules"}
            and not str(relative).startswith("web/static/react/"))


def assets_match(repo, target, container):
    live = subprocess.check_output([
        "docker", "exec", container, "python", "-c", TREE_HASH_CODE,
    ], text=True).strip()
    archive = subprocess.check_output([
        "git", "-C", str(repo), "archive", target, "web/static/react",
    ])
    rows = []
    with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
        for entry in contents:
            if entry.isfile():
                name = entry.name.removeprefix("web/static/react/")
                rows.append((name, hashlib.sha256(contents.extractfile(entry).read()).hexdigest()))
    candidate = hashlib.sha256("".join(n + "\0" + h + "\n" for n, h in sorted(rows)).encode()).hexdigest()
    return bool(rows) and live == candidate


def conflicts(repo, target, container):
    rows = subprocess.check_output(["docker", "diff", container], text=True).splitlines()
    result = []
    if any(row.partition(" ")[2].startswith("/app/web/static/react/") for row in rows):
        if not assets_match(repo, target, container):
            result.append("web/static/react (bundle diverso dal server)")
    for row in rows:
        kind, _, path = row.partition(" ")
        if not path.startswith("/app/") or not source_path(path):
            continue
        relative = path[len("/app/"):]
        candidate = subprocess.run(
            ["git", "-C", str(repo), "show", f"{target}:{relative}"],
            capture_output=True, check=False,
        )
        if kind == "D":
            if candidate.returncode == 0:
                result.append(relative)
            continue
        live = subprocess.check_output(["docker", "exec", container, "cat", path])
        if candidate.returncode != 0 or candidate.stdout != live:
            result.append(relative)
    return sorted(set(result))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--target", required=True)
    args = parser.parse_args()
    ids = subprocess.check_output([
        "docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=iusentra",
    ], text=True).split()
    blocked = False
    for container in ids:
        name = subprocess.check_output([
            "docker", "inspect", "--format", "{{.Name}}", container,
        ], text=True).strip()
        for path in conflicts(args.repo, args.target, container):
            print(f"Deploy bloccato: sorgente runtime non riallineato {name}: {path}")
            blocked = True
    if blocked:
        raise SystemExit(1)
    print("Sorgenti e asset modificati nel runtime coincidono con la release candidata.")


if __name__ == "__main__":
    main()
