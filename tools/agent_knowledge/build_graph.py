"""Build the agent's local graph with official Graphify, from tracked source only.

Never imports IUSENTRA, connects to its databases or runs application code.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

GRAPHIFY_VERSION = "0.9.93"
# These contain runtime data/evidence, generated bundles or historical snapshots.
EXCLUDED_ROOTS = {"artifacts", "assets", "patches", "examples"}
EXCLUDED_PREFIXES = ("web/static/react/", "tools/metaharness/", "tools/dist/")
JSON_CONFIG_FILES = {"package.json", "tokens.json", "turbo.json", ".github/required-checks.json", ".github/codeql/eccezioni.json", "tools/agent_knowledge/domains.json"}
JSON_CONFIG_PREFIXES = ("pct/template_atti_schede/", "pct/template_atti_catalogo_data/")


def source_allowed(name: str, extensions: set[str]) -> bool:
    from graphify.detect import _is_sensitive

    path = PurePosixPath(name)
    return (
        bool(path.parts)
        and not path.is_absolute()
        and ".." not in path.parts
        and path.parts[0] not in EXCLUDED_ROOTS
        and not name.startswith(EXCLUDED_PREFIXES)
        and not any(part in {"node_modules", "__pycache__", ".venv", "venv"} for part in path.parts)
        and not path.name.startswith(".env")
        and path.suffix in extensions
        and (path.suffix != ".json" or name in JSON_CONFIG_FILES
             or name.startswith(JSON_CONFIG_PREFIXES)
             or path.name in {"package.json", "tsconfig.json"}
             or path.name.endswith(".schema.json"))
        and not _is_sensitive(Path(name))
    )


def snapshot(repo: Path, destination: Path) -> dict:
    from graphify.detect import CODE_EXTENSIONS

    repo = repo.resolve(strict=True)
    destination = destination.resolve()
    if destination == repo or repo in destination.parents or destination in repo.parents:
        raise ValueError("Il grafo dell'agente deve stare fuori dal repository applicativo.")
    destination.mkdir(parents=True, exist_ok=True)
    owner = destination / "agent-owner.json"
    manifest_path = destination / "source-manifest.json"
    identity = {"repository": str(repo), "purpose": "IUSENTRA agent source snapshot"}
    if owner.exists():
        if json.loads(owner.read_text(encoding="utf-8")) != identity:
            raise ValueError("Destinazione appartenente a un altro progetto.")
    elif manifest_path.exists():
        if json.loads(manifest_path.read_text(encoding="utf-8")).get("repository") != str(repo):
            raise ValueError("Manifesto precedente appartenente a un altro progetto.")
        owner.write_text(json.dumps(identity), encoding="utf-8")
    elif any(destination.iterdir()):
        raise ValueError("Destinazione non vuota senza attestazione di proprieta.")
    else:
        owner.write_text(json.dumps(identity), encoding="utf-8")
    source = destination / "source"
    if source.is_symlink():
        raise ValueError("Radice sorgenti simbolica non consentita.")
    source.mkdir(exist_ok=True)
    previous = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=repo).decode("utf-8").split("\0")
    entries = {}
    changed = 0
    for name in sorted(n for n in names if source_allowed(n, CODE_EXTENSIONS)):
        original = repo / name
        target = source / name
        if original.is_symlink() or not original.is_file():
            continue
        if target.is_symlink() or source.resolve() not in target.resolve().parents:
            raise ValueError(f"Destinazione fuori perimetro: {name}")
        payload = original.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        entries[name] = {"sha256": digest, "bytes": len(payload)}
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != digest:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            changed += 1
    # Only a specific previously inventoried source file may be removed. No recursive deletion.
    removed = set(previous.get("files", {})) - set(entries)
    for name in sorted(removed):
        item = PurePosixPath(name)
        if item.is_absolute() or ".." in item.parts or not item.parts:
            raise ValueError(f"Voce precedente non valida: {name}")
        target = source / name
        if target.is_symlink() or source.resolve() not in target.resolve().parents:
            raise ValueError(f"Rimozione fuori perimetro: {name}")
        if target.is_file():
            if hashlib.sha256(target.read_bytes()).hexdigest() != previous["files"][name]["sha256"]:
                raise ValueError(f"Copia locale cambiata: non rimuovere {name}")
            target.unlink()
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repository": str(repo),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip(),
        "graphify_version": GRAPHIFY_VERSION,
        "scope": "tracked code and allowlisted JSON configuration; working tree hashes; no tenant data",
        "json_config_files": sorted(JSON_CONFIG_FILES),
        "json_config_prefixes": list(JSON_CONFIG_PREFIXES),
        "excluded_roots": sorted(EXCLUDED_ROOTS),
        "excluded_prefixes": list(EXCLUDED_PREFIXES),
        "files": entries,
        "by_root": dict(Counter(PurePosixPath(n).parts[0] for n in entries)),
        "changed": changed,
        "removed": sorted(removed),
    }
    manifest_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--snapshot-only", action="store_true")
    args = parser.parse_args()
    if importlib.metadata.version("graphifyy") != GRAPHIFY_VERSION:
        raise ValueError("Verificare la nuova versione Graphify prima di cambiare il pin.")
    repo = Path(__file__).resolve().parents[2]
    result = snapshot(repo, args.out)
    print(json.dumps({"files": len(result["files"]), "changed": result["changed"], "by_root": result["by_root"]}), flush=True)
    if not args.snapshot_only:
        subprocess.run([
            sys.executable, "-m", "graphify", "extract", str(args.out.resolve() / "source"),
            "--code-only", "--max-workers", "1", "--no-cluster", "--out", str(args.out.resolve()),
        ], check=True)


if __name__ == "__main__":
    main()
