"""Importazione governata della biblioteca pubblica 2.440.0, senza dati degli studi."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from lex.normativa.consultazione import importa_fonti, catalogo


def importa_biblioteca(source: Path, db: Path) -> dict:
    if not db.is_file():
        raise RuntimeError("Archivio di consultazione assente: preparare la base prima di importare, senza nascondere gli atti esistenti.")
    files = sorted((source / "atti").glob("*.jsonl"))
    rows = [[json.loads(line) for line in f.read_text(encoding="utf-8").splitlines() if line.strip()] for f in files]
    if len(files) != 84 or sum(map(len, rows)) != 2954 or any(not r for r in rows):
        raise ValueError("Pacchetto biblioteca 2.440.0 incompleto: nessuna scrittura eseguita.")
    keys = {r[0]["chiave"] for r in rows}
    if len(keys) != 84:
        raise ValueError("Identità degli atti non univoche: nessuna scrittura eseguita.")
    report = importa_fonti(source, db, "2026-10-19")
    acts = catalogo(db)
    if not keys <= {a["key"] for a in acts}:
        raise RuntimeError("Importazione non completamente visibile nel catalogo.")
    return dict(report, atti_release_visibili=len(keys), atti_catalogo=len(acts))


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa con backup la biblioteca pubblica della release 2.440.0")
    parser.add_argument("--source", type=Path, default=Path("/app/lex/normativa/integrazioni/biblioteca_20261019"))
    parser.add_argument("--db", type=Path, default=Path(os.getenv("PCT_NORMATTIVA_DB", "/data/normativa/normattiva.sqlite")).with_name("codici_leggi.sqlite"))
    args = parser.parse_args()
    print(json.dumps(importa_biblioteca(args.source, args.db), ensure_ascii=False))


if __name__ == "__main__":
    main()
