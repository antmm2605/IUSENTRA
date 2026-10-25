"""Snapshot dei soli dati pubblici Normattiva; nessuna modifica all'archivio sorgente.

Eseguito sul server dal workflow di audit. Esclude segreti e dati degli studi.
Lo snapshot non certifica ancora la copertura dei vettori: questa va misurata sul testo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
from urllib.parse import urlsplit, urlunsplit

FILES = ("meta.json", "vettori.i8", "scale.f32", "ids.i64", "impronte.u64")
TABLES = {"normative_documents", "normative_articles", "normative_chunks", "normative_sync_runs",
          "normative_fts", "normative_fts_info", "normative_indici_meta"}
SAFE_ENV = {"PCT_NORMATTIVA_DB", "PCT_NORMATTIVA_JSONL", "LEX_NORMATTIVA_VETTORI_DIR",
            "LEX_RICERCA_SEMANTICA", "LEX_EMBED_MODEL", "LEX_EMBED_URL", "LEX_EMBED_URLS",
            "PCT_LOCAL_AI_EMBED_MODEL", "PCT_LOCAL_AI_BASE_URL", "OLLAMA_BASE_URL",
            "LEX_EMBED_TIMEOUT_S", "LEX_EMBED_KEEP_ALIVE", "LEX_EMBED_PARALLELI"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def public_config(env: list[str]) -> dict[str, str]:
    out = {}
    for item in env:
        key, sep, value = item.partition("=")
        if not sep or key not in SAFE_ENV:
            continue
        if "URL" in key:
            clean = []
            for url in value.split(","):
                u = urlsplit(url)
                # Non esportare userinfo, query string o frammenti di URL configurati.
                host = u.hostname or ""
                if ":" in host:
                    host = "[" + host + "]"
                authority = host + (":" + str(u.port) if u.port else "")
                clean.append(urlunsplit((u.scheme, authority, u.path, "", "")))
            value = ",".join(clean)
        out[key] = value
    return out


def snapshot(db: Path, vectors: Path, target: Path, config: dict) -> dict:
    if not db.is_file() or db.is_symlink():
        raise ValueError("Database pubblico assente o percorso non ammesso")
    source = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        names = {row[0] for row in source.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        allowed = TABLES | {"normative_fts_" + n for n in ("data", "idx", "docsize", "config", "content")}
        unknown = {n for n in names - allowed if not n.startswith("sqlite_")}
        if unknown or not {"normative_documents", "normative_articles", "normative_chunks"} <= names:
            raise ValueError("Schema diverso dall'archivio pubblico Normattiva: esportazione bloccata")
        before_db = source.execute("PRAGMA data_version").fetchone()[0]
        before_vectors = {}
        for name in FILES:
            p = vectors / name
            if not p.is_file() or p.is_symlink():
                raise ValueError("Indice assente, incompleto o percorso non ammesso: " + name)
            st = p.stat()
            before_vectors[name] = (st.st_size, st.st_mtime_ns)
        needed = 2 * (db.stat().st_size + sum(v[0] for v in before_vectors.values())) + 2 * 1024**3
        if shutil.disk_usage(target.parent).free < needed:
            raise ValueError("Spazio insufficiente per snapshot e pacchetto; sorgenti invariati")
        target.mkdir(exist_ok=False)
        dest_db = target / "normativa" / "normattiva.sqlite"
        dest_db.parent.mkdir()
        dest = sqlite3.connect(dest_db)
        try:
            source.backup(dest, pages=4096, sleep=0.05)
            if dest.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise ValueError("Snapshot SQLite non integro")
            counts = {name: dest.execute("SELECT COUNT(*) FROM " + name).fetchone()[0]
                      for name in sorted(TABLES & names) if name != "normative_fts"}
        finally:
            dest.close()
        dest_vectors = dest_db.parent / "vettori_normattiva"
        dest_vectors.mkdir()
        hashes = {"normativa/normattiva.sqlite": sha256(dest_db)}
        for name in FILES:
            src = vectors / name
            dst = dest_vectors / name
            shutil.copyfile(src, dst)
            digest = sha256(dst)
            if digest != sha256(src):
                raise ValueError("Indice cambiato durante la copia: snapshot non utilizzabile")
            hashes["normativa/vettori_normattiva/" + name] = digest
        for name, before in before_vectors.items():
            st = (vectors / name).stat()
            if (st.st_size, st.st_mtime_ns) != before:
                raise ValueError("Indice in scrittura: snapshot non utilizzabile")
        if source.execute("PRAGMA data_version").fetchone()[0] != before_db:
            raise ValueError("Database cambiato durante la copia: snapshot non utilizzabile")
        manifest = {"scope": "public_normattiva_only", "source_untouched": True,
                    "database": str(db), "vectors": str(vectors), "counts": counts,
                    "vector_meta": json.loads((dest_vectors / "meta.json").read_text()),
                    "sha256": hashes, "configuration": config,
                    "index_text_coverage_certified": False}
        (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        return manifest
    finally:
        source.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    args = parser.parse_args()
    if not args.run.replace("-", "").isdigit():
        raise ValueError("Identificativo di audit non valido")
    info = json.loads(subprocess.check_output(["docker", "inspect", "iusentra-app"], text=True))[0]
    mounts = [Path(m["Source"]) for m in info["Mounts"] if m["Destination"] == "/data"]
    if len(mounts) != 1:
        raise ValueError("Volume applicativo non univoco")
    config = public_config(info["Config"]["Env"])
    if config.get("PCT_NORMATTIVA_DB", "/data/normativa/normattiva.sqlite") != "/data/normativa/normattiva.sqlite":
        raise ValueError("Database non standard: verificare prima il percorso pubblico")
    if config.get("LEX_NORMATTIVA_VETTORI_DIR", "") not in ("", "/data/normativa/vettori_normattiva"):
        raise ValueError("Indice personalizzato: verificare prima il percorso pubblico")
    base = Path("/opt/iusentra/normattiva-parity/exports")
    base.mkdir(parents=True, exist_ok=True)
    target = base / args.run
    manifest = snapshot(mounts[0] / "normativa/normattiva.sqlite",
                        mounts[0] / "normativa/vettori_normattiva", target, config)
    manifest["runtime_image"] = info["Config"]["Image"]
    runtime_probe = ("import json; from lex.ricerca_giuridica.embedding import OllamaEmbedder; "
                     "e=OllamaEmbedder(timeout=10); "
                     "print(json.dumps({'modello':e.modello,'versione':e.versione()}))")
    probe = subprocess.run(["docker", "exec", "iusentra-app", "python", "-c", runtime_probe],
                           capture_output=True, text=True, timeout=45, check=False)
    manifest["embedding_runtime"] = (json.loads(probe.stdout.splitlines()[-1])
                                     if probe.returncode == 0 and probe.stdout.strip()
                                     else {"verified": False, "exit": probe.returncode})
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    package = base / (args.run + ".tar.gz")
    if package.exists():
        raise ValueError("Pacchetto già esistente: non sovrascrivere una prova")
    with tarfile.open(package, "w:gz", compresslevel=1) as archive:
        archive.add(target, arcname="snapshot", recursive=True)
    digest = sha256(package)
    package.with_suffix(package.suffix + ".sha256").write_text(digest + "  " + package.name + "\n")
    print(json.dumps({"archive": str(package), "sha256": digest, "bytes": package.stat().st_size,
                      "counts": manifest["counts"], "source_untouched": True}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
