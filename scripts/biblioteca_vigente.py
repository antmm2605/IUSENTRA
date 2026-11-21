"""La biblioteca di consultazione mostra il testo vigente? Confronto con Normattiva e aggiornamento dove serve.

Uso:
  python scripts/biblioteca_vigente.py confronta --db codici_leggi.sqlite --uscita rapporto.json FILE.xml [...]
      FILE.xml: Akoma Ntoso vigenti di Normattiva (caricaAKN). Sola lettura del database.
  python scripts/biblioteca_vigente.py aggiorna --db codici_leggi.sqlite --cartella pacchetti --vigenza 2026-11-21 \\
      --atto "546/1992=urn:nir:stato:decreto.legislativo:1992-12-31;546=2,6,9" [--atto ...]
      Usa il meccanismo della biblioteca (lex.normativa.biblioteca.acquisizione.acquisisci): scarica l'AKN vigente
      alla data, controlla identità e articoli richiesti, scrive il pacchetto datato e lo importa con
      consultazione.importa_fonti (backup del database prima di scrivere, edizioni precedenti conservate).
      La chiave è quella della collezione già presente («Lex fonti: <chiave>»), così la nuova edizione la sostituisce
      nella consultazione invece di creare un doppione.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

from lex.normativa.biblioteca.confronto_vigente import classifica  # noqa: E402
from scripts.normattiva_akn_a_jsonl import converti, numero  # noqa: E402


def confronta(db: Path, files: list[Path]) -> dict:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    documenti = conn.execute("SELECT id, collection_name, urn, data_atto, numero, "
                             "max(coalesce(redazione_id,''), CASE WHEN vigenza LIKE 'VIGENTE_AL:%' "
                             "THEN substr(vigenza, 12, 10) ELSE '' END) FROM normative_documents").fetchall()
    rapporto: dict = {"database": str(db), "atti": {}, "totali": collections.Counter()}
    for xml in files:
        try:
            righe = converti(xml, {"url": "", "data_vigenza": "", "raccolto_il": "", "titolo_pagina": xml.stem})
        except KeyError as exc:
            rapporto["atti"][xml.stem] = {"errore": f"tipo di atto non gestito dal convertitore: {exc}"}
            continue
        if not righe:
            continue
        urn, data, num = righe[0]["urn"], righe[0]["data_atto"], righe[0]["urn"].split(";")[-1]
        vigente = {r["articolo"]: r["testo"] for r in righe}
        candidati = [d for d in documenti if (d[2] or "").split("~")[0] == urn or (d[3] == data and str(d[4] or "") == num)]
        voce: dict = {"urn": urn, "articoli_vigenti": len(vigente), "conteggi": collections.Counter(), "articoli": {}}
        # Come la consultazione (``consultazione.ordine_edizione``): di ogni collezione l'edizione verificata più di recente.
        ultime: dict = {}
        for riga in sorted(candidati, key=lambda d: (str(d[5] or ""), d[0])):
            ultime[riga[1]] = riga
        migliore = None
        for doc_id, collezione, _u, _d, _n, redazione in ultime.values():
            articoli = {numero(str(a)): t for a, t in conn.execute(
                "SELECT article_number, article_text FROM normative_articles WHERE document_id=?", (doc_id,))}
            chiave = (len(set(articoli) & set(vigente)), str(redazione or ""), doc_id)
            if migliore is None or chiave > migliore[0]:
                migliore = (chiave, doc_id, collezione, redazione, articoli)
        if migliore is None:
            voce["conteggi"]["atto_assente"] = len(vigente)
        else:
            _, doc_id, collezione, redazione, articoli = migliore
            voce.update(documento=doc_id, collezione=collezione, edizione=redazione)
            for n, testo in vigente.items():
                if n not in articoli:
                    voce["conteggi"]["assente_in_biblioteca"] += 1
                    continue
                categoria, diverse = classifica(articoli[n], testo)
                voce["conteggi"][categoria] += 1
                if categoria in ("sostanza", "abrogato_ma_vigente"):
                    voce["articoli"][n] = {"categoria": categoria, "differenze": [list(x) for x in diverse[:4]]}
        voce["conteggi"] = dict(voce["conteggi"])
        rapporto["totali"].update(voce["conteggi"])
        rapporto["atti"][xml.stem] = voce
        print(xml.stem, voce["conteggi"], flush=True)
    rapporto["totali"] = dict(rapporto["totali"])
    return rapporto


def aggiorna(db: Path, cartella: Path, vigenza: str, atti: list[str]) -> dict:
    from lex.normativa.biblioteca.acquisizione import acquisisci
    from lex.normativa.biblioteca.fabbisogno import Riferimento
    from lex.normativa.biblioteca.riferimenti import FonteAtto

    giorno = dt.date.fromisoformat(vigenza)
    riferimenti, note = [], {}
    for voce in atti:
        chiave, urn, articoli = voce.split("=", 2)
        note[chiave] = FonteAtto(chiave, "normattiva", urn=urn)
        riferimenti += [Riferimento(f"vigenza_normattiva_{giorno:%Y%m%d}", chiave, a.strip(),
                                    f"testo vigente al {giorno:%d/%m/%Y} (Normattiva)", "base_normativa")
                        for a in articoli.split(",") if a.strip()]
    from lex.normativa.biblioteca.acquisizione import _righe_normattiva
    from lex.normativa.biblioteca.normattiva_akn import nuovo_opener
    from lex.normativa.consultazione import VIGENTE_AL

    opener = nuovo_opener()
    prove = Path(cartella) / giorno.strftime("%Y%m%d") / "prove"

    def scarica_vigente(chiave: str, urn: str, oggi: dt.date) -> list[dict]:
        # Testo scaricato oggi da Normattiva come vigente alla data: l'edizione lo dichiara, così la consultazione
        # la mostra al posto di edizioni datate prima (``consultazione.ordine_edizione``).
        righe = _righe_normattiva(chiave, urn, oggi, opener, versione_al=giorno, archivio_locale=None, cartella_prove=prove)
        for riga in righe:
            riga["vigenza"] = f"{VIGENTE_AL}{giorno.isoformat()}"
        return righe

    esito = acquisisci(db, cartella, oggi=giorno, riferimenti=riferimenti, versione_al=giorno, fonti_note=note,
                       scarica_normattiva=scarica_vigente)
    return esito.to_dict()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sotto = ap.add_subparsers(dest="comando", required=True)
    c = sotto.add_parser("confronta")
    c.add_argument("--db", required=True)
    c.add_argument("--uscita", required=True)
    c.add_argument("file", nargs="+")
    a = sotto.add_parser("aggiorna")
    a.add_argument("--db", required=True)
    a.add_argument("--cartella", required=True)
    a.add_argument("--vigenza", required=True)
    a.add_argument("--atto", action="append", required=True)
    args = ap.parse_args()
    if args.comando == "confronta":
        rapporto = confronta(Path(args.db), [Path(f) for f in args.file])
        Path(args.uscita).write_text(json.dumps(rapporto, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(rapporto["totali"], ensure_ascii=False))
    else:
        print(json.dumps(aggiorna(Path(args.db), Path(args.cartella), args.vigenza, args.atto), ensure_ascii=False,
                         indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
