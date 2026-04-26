from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile

from lex.normativa.normattiva_importer import import_raw_dir


NIR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<NIR xmlns="http://www.normeinrete.it/nir/2.2/">
  <meta>
    <descrittori>
      <urn valore="urn:nir:stato:legge:2026-01-01;1"/>
      <pubblicazione norm="20260102"/>
    </descrittori>
  </meta>
  <atto>
    <intestazione>
      <tipoDoc>legge</tipoDoc>
      <dataDoc norm="20260101">1 gennaio 2026</dataDoc>
      <numDoc>1</numDoc>
      <titoloDoc>Legge sul processo civile telematico e deposito telematico</titoloDoc>
    </intestazione>
    <articolato>
      <articolo>
        <num>Art. 1</num>
        <comma>Il processo civile telematico usa firma digitale, PEC e deposito telematico.</comma>
      </articolo>
    </articolato>
  </atto>
</NIR>
"""


def test_normattiva_import_creates_sqlite_and_jsonl(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    zip_path = raw_dir / "Codici_XML_ORIGINALE_2026-04-26.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr("legge_1.xml", NIR_XML.encode("utf-8"))

    db_path = tmp_path / "normattiva.sqlite"
    jsonl_path = tmp_path / "index" / "normattiva_chunks.jsonl"

    stats = import_raw_dir(raw_dir=raw_dir, db_path=db_path, jsonl_path=jsonl_path, limit=50)

    assert stats.documents_imported == 1
    assert stats.chunks_written >= 1
    con = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in con.execute(
                "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
            ).fetchall()
        }
    finally:
        con.close()
    assert {"normative_documents", "normative_articles", "normative_chunks", "normative_sync_runs"}.issubset(tables)

    lines = [json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()]
    assert lines
    assert lines[0]["metadata"]["source"] == "Normattiva Open Data"
