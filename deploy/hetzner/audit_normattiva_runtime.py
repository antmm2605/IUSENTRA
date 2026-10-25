"""Read-only fingerprint and benchmark of the actual public Normattiva retrieval path."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sqlite3
import time
from pathlib import Path


def file_sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def manifest(db: Path, vectors: Path) -> dict:
    files = [db, *(vectors / name for name in ("meta.json", "vettori.i8", "scale.f32", "ids.i64", "impronte.u64"))]
    result = {"files": {str(p.relative_to(db.parent)): {"sha256": file_sha(p), "bytes": p.stat().st_size if p.is_file() else None} for p in files}}
    with sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True) as conn:
        result["counts"] = {name: conn.execute("SELECT count(*) FROM " + name).fetchone()[0] for name in ("normative_documents", "normative_articles", "normative_chunks", "normative_fts_info")}
    result["vector_meta"] = json.loads((vectors / "meta.json").read_text())
    wal = Path(str(db) + "-wal")
    result["wal_bytes"] = wal.stat().st_size if wal.exists() else 0
    result["wal_sha256"] = file_sha(wal) if result["wal_bytes"] else None
    # Supplemental library is fingerprinted, never exported or rewritten.
    library = db.with_name("codici_leggi.sqlite")
    result["library_file_sha256"] = file_sha(library)
    return result


def measure(cases: list[dict]) -> list[dict]:
    from lex.retrieval.official_sources_retriever import search_normattiva
    from lex.ricerca_giuridica.testo import articolo_normalizzato

    results = []
    for case in cases:
        diagnostics = []
        start = time.monotonic()
        rows = search_normattiva(case["domanda"], limit=10, diagnostics=diagnostics)
        elapsed = time.monotonic() - start
        matches = []
        for index, row in enumerate(rows):
            metadata = row.get("metadata") or {}
            article = str(metadata.get("article_number") or row.get("articolo_o_chunk") or "")
            date = str(metadata.get("data_atto") or row.get("data") or "")
            number = str(metadata.get("numero") or "")
            if date == case["data_atto"] and number == case["numero"] and articolo_normalizzato(article) == articolo_normalizzato(case["articolo"]):
                matches.append(index + 1)
        results.append({"id": case["id"], "seconds": elapsed, "rank": min(matches) if matches else None, "diagnostics": diagnostics, "results": rows})
    return results


def main() -> None:
    from lex.retrieval.normativa_catalog import runtime_general_path, select_runtime_catalog
    from lex.ricerca_giuridica.ibrida import motore_per_db
    from lex.ricerca_giuridica.embedding import OllamaEmbedder

    parser = argparse.ArgumentParser()
    parser.add_argument("--queries-b64", default="")
    args = parser.parse_args()
    db = runtime_general_path()
    selected, scope = select_runtime_catalog(db)
    engine = motore_per_db(selected)
    vectors = engine.cartella_vettori
    tracked = [selected, Path(str(selected) + "-wal"), *(vectors / name for name in ("meta.json", "vettori.i8", "scale.f32", "ids.i64", "impronte.u64"))]
    def signatures():
        return [(str(p), (p.stat().st_size, p.stat().st_mtime_ns) if p.exists() else None) for p in tracked]
    before = signatures()
    output = manifest(selected, vectors)
    output.update(scope=scope, runtime=engine.stato(), selected_database=str(selected), read_only=True)
    embedder = OllamaEmbedder(timeout=15, tentativi=1)
    output["embedding_runtime"] = {"model": embedder.modello, "digest": embedder.versione()}
    if args.queries_b64:
        if len(args.queries_b64) > 128 * 1024:
            raise ValueError("Campione troppo grande")
        cases = json.loads(base64.b64decode(args.queries_b64, validate=True))["casi"]
        if not isinstance(cases, list) or len(cases) > 100:
            raise ValueError("Campione non valido")
        output["results"] = measure(cases)
        output["hit10"] = sum(r["rank"] is not None for r in output["results"])
        output["questions"] = len(cases)
    if signatures() != before:
        raise RuntimeError("Archivio cambiato durante la verifica: esito non certificabile")
    output["files_stable_during_audit"] = True
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
