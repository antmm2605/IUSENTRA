"""Completa l'oggetto delle pronunce della Cassazione già scaricate con la materia della fonte ufficiale.

Le pagine originali di ItalgiureWeb conservate dall'acquisizione (``originali/<sha256>.json.gz``, registrate in
``sentenzeweb_pages``) contengono per ogni provvedimento il campo «materia» (per esempio «RESPONSABILITA' CIVILE
CUSTODIA»), che l'acquisizione fino alla 2.490 non salvava. Questo strumento lo legge dalle pagine conservate,
verifica l'impronta SHA-256 della pagina, collega il provvedimento con ``sentenzeweb_aliases`` e scrive l'oggetto
solo dove è vuoto: nessun accesso alla rete, nessun testo modificato.

Uso: python tools/sentenzeweb_materie.py <directory archivio> [--prova] [--pagine N]
Con --prova conta soltanto ciò che scriverebbe, aprendo l'archivio in sola lettura.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def materia(documento: dict) -> str:
    valore = documento.get("materia") or []
    valori = valore if isinstance(valore, list) else [valore]
    return "; ".join(" ".join(str(item).split()) for item in valori if str(item).strip())


def _pagine(connection: sqlite3.Connection, root: Path):
    for digest, percorso in connection.execute("SELECT sha256, path FROM sentenzeweb_pages ORDER BY rowid"):
        file = Path(percorso)
        if not file.is_absolute() or not file.is_file():
            file = root / "originali" / f"{digest}.json.gz"
        if not file.is_file():
            yield digest, None
            continue
        grezzo = gzip.decompress(file.read_bytes())
        if hashlib.sha256(grezzo).hexdigest() != digest:
            yield digest, None
            continue
        yield digest, json.loads(grezzo).get("response", {}).get("docs", [])


def completa(root: Path, *, prova: bool = False, blocco: int = 2000, pagine: int | None = None) -> dict[str, int]:
    database = root / "giurisprudenza_corpus.db"
    if prova:
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
    else:
        connection = sqlite3.connect(database, timeout=60)
    conteggi = {"pagine": 0, "pagine_non_verificate": 0, "documenti": 0, "con_materia": 0, "da_scrivere": 0, "scritti": 0}
    try:
        alias = dict(connection.execute("SELECT source_id, native_uuid FROM sentenzeweb_aliases"))
        attesa: list[tuple[str, str]] = []

        def scrivi():
            if prova or not attesa:
                attesa.clear()
                return
            with connection:
                cursore = connection.executemany(
                    "UPDATE sentenze SET oggetto=? WHERE uuid_interno=? AND COALESCE(oggetto,'')=''", attesa)
                conteggi["scritti"] += cursore.rowcount if cursore.rowcount and cursore.rowcount > 0 else 0
            attesa.clear()

        visti: set[str] = set()
        for indice, (_digest, documenti) in enumerate(_pagine(connection, root)):
            if pagine is not None and indice >= pagine:
                break
            if documenti is None:
                conteggi["pagine_non_verificate"] += 1
                continue
            conteggi["pagine"] += 1
            for documento in documenti:
                conteggi["documenti"] += 1
                testo = materia(documento)
                uuid = alias.get(str(documento.get("id") or ""))
                if not testo or not uuid:
                    continue
                conteggi["con_materia"] += 1
                if uuid in visti:
                    continue
                visti.add(uuid)
                attesa.append((testo, uuid))
                conteggi["da_scrivere"] += 1
                if len(attesa) >= blocco:
                    scrivi()
        scrivi()
    finally:
        connection.close()
    return conteggi


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("directory")
    parser.add_argument("--prova", action="store_true")
    parser.add_argument("--pagine", type=int, default=None, help="solo le prime N pagine (per una misura)")
    args = parser.parse_args(argv)
    root = Path(args.directory).resolve()
    if args.prova:
        print(json.dumps(completa(root, prova=True, pagine=args.pagine), ensure_ascii=False))
        return 0
    from tools.sentenzeweb_importa import FileLock

    # Stesso lucchetto dell'acquisizione notturna: le due scritture non si sovrappongono mai.
    with FileLock(str(root / "acquisizione.lock"), timeout=0):
        print(json.dumps(completa(root, pagine=args.pagine), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
