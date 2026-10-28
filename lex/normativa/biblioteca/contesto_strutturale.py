"""Contesto XML dei soli candidati già scelti dalla ricerca.

Non espande l'elenco, non decide applicabilità e non altera i punteggi. Consente
un confronto controllato sugli stessi 50 candidati del banco congelato.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from pathlib import Path


def contesto_candidati(righe: list[dict], *, archivio_generale: Path, biblioteca: Path) -> list[dict]:
    if len(righe)>100:
        raise ValueError("Troppi candidati per il contesto strutturale")
    result=[dict(row,struttura_xml=[]) for row in righe]
    for catalog,path in [("archivio_generale",archivio_generale),("biblioteca_codici_leggi",biblioteca)]:
        positions=[i for i,row in enumerate(result) if row.get("archive_catalog")==catalog
                   and type(row.get("normative_article_id")) is int]
        if not positions:
            continue
        with closing(sqlite3.connect(Path(path).resolve().as_uri()+"?mode=ro",uri=True,timeout=2)) as conn:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='normative_structure' AND type='table'").fetchone():
                continue
            for pos in positions:
                row=result[pos]
                nodes=conn.execute("SELECT node_json FROM normative_structure WHERE document_id=? AND article_id=? ORDER BY depth",
                                   (row["document_id"],row["normative_article_id"])).fetchall()
                for value, in nodes:
                    node=json.loads(value)
                    if (node.get("tipo") not in {"libro","parte","titolo","capo","sezione","sottosezione"}
                            or not (node.get("numero") or node.get("rubrica"))):
                        continue
                    result[pos]["struttura_xml"].append(node)
    return result
