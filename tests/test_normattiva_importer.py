from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from zipfile import ZipFile

from lex.normativa.normattiva_importer import ensure_schema, import_raw_dir
from lex.retrieval.official_sources_retriever import search_normattiva


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

NIR_CODE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<NIR xmlns="http://www.normeinrete.it/nir/2.2/" xmlns:h="http://www.w3.org/HTML/1998/html4">
  <meta>
    <descrittori>
      <urn valore="urn:"/>
      <pubblicazione norm="19420404"/>
    </descrittori>
  </meta>
  <atto>
    <intestazione>
      <tipoDoc>monovigente</tipoDoc>
      <dataDoc norm="19420316">16 marzo 1942</dataDoc>
      <numDoc>262</numDoc>
      <titoloDoc>Approvazione del testo del Codice civile. (042U0262)</titoloDoc>
    </intestazione>
    <articolato>
      <articolo>
        <num>Art. 1.</num>
        <comma><h:p>Approvazione del testo del Codice civile.</h:p></comma>
      </articolo>
    </articolato>
    <annessi>
      <annesso>
        <h:p>Art. 2042.</h:p>
        <h:p>Carattere sussidiario dell'azione.</h:p>
        <h:p>L'azione di arricchimento non e' proponibile quando il danneggiato puo' esercitare un'altra azione.</h:p>
        <h:p>Art. 2043.</h:p>
        <h:p>Risarcimento per fatto illecito.</h:p>
        <h:p>Qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, obbliga chi ha commesso il fatto a risarcire il danno.</h:p>
        <h:p>Art. 2044.</h:p>
        <h:p>Legittima difesa.</h:p>
      </annesso>
    </annessi>
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


def test_normattiva_import_indicizza_articoli_codice_in_paragrafi_html(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    zip_path = raw_dir / "Codici_XML_ORIGINALE_2026-05-17.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "REGIO DECRETO_19420316_262/1942-04-04_042U0262_VIGENZA_2026-04-29_V0.xml",
            NIR_CODE_XML.encode("utf-8"),
        )

    db_path = tmp_path / "normattiva.sqlite"
    jsonl_path = tmp_path / "index" / "normattiva_chunks.jsonl"

    stats = import_raw_dir(raw_dir=raw_dir, db_path=db_path, jsonl_path=jsonl_path, min_score=0, limit=10)
    rows = search_normattiva("codice civile art. 2043", db_path=db_path, jsonl_path=jsonl_path, limit=5)

    assert stats.articles_imported >= 4
    assert rows
    assert rows[0]["fonte"] == "Normattiva"
    assert "Codice civile" in rows[0]["titolo"]
    assert "Risarcimento per fatto illecito" in rows[0]["testo"]
    assert not str(rows[0]["url_origine"]).startswith("https://www.normattiva.it/")


def test_normattiva_retrieval_usa_raw_codici_senza_reimport_massivo(tmp_path: Path):
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    zip_path = raw_dir / "Codici_XML_ORIGINALE_2026-05-17.zip"
    with ZipFile(zip_path, "w") as archive:
        archive.writestr(
            "REGIO DECRETO_19420316_262/1942-04-04_042U0262_VIGENZA_2026-04-29_V0.xml",
            NIR_CODE_XML.encode("utf-8"),
        )
    db_path = tmp_path / "normattiva.sqlite"
    with sqlite3.connect(db_path) as conn:
        ensure_schema(conn)

    rows = search_normattiva("codice civile articolo 2043", db_path=db_path, jsonl_path=tmp_path / "missing.jsonl", limit=3)

    assert len(rows) == 1
    assert rows[0]["metadata"]["source"] == "Normattiva Open Data"
    assert rows[0]["metadata"]["no_invented_link"] is True
    assert rows[0]["path_origine"].endswith("Codici_XML_ORIGINALE_2026-05-17.zip")
    assert "danno ingiusto" in rows[0]["testo"]
