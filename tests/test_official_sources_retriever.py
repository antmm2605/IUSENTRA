from __future__ import annotations

import sqlite3
from pathlib import Path

from lex.retrieval.normativa import search_normativa_sources
from lex.retrieval.official_sources_retriever import search_gazzetta
from lex.sources.db import init_db


def _insert_gazzetta_document(conn: sqlite3.Connection, *, title: str, url: str, digest: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO official_documents (
            source_id, source_name, original_url, title, document_type, content_type,
            filename, raw_path, text_path, hash_sha256, published_at, materia,
            text_content, index_status, license, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "gazzetta_ufficiale",
            "Gazzetta Ufficiale",
            url,
            title,
            "fascicolo",
            "application/pdf",
            "gu.pdf",
            "raw/gu.pdf",
            "text/gu.txt",
            digest,
            "2026-05-18",
            "Normativa",
            "Decreto legislativo e norme pubblicate in Gazzetta Ufficiale.",
            "indicizzato",
            "",
            "{}",
        ),
    )
    return int(cur.lastrowid)


def test_search_gazzetta_deduplica_chunk_dello_stesso_documento(tmp_path: Path):
    db_path = tmp_path / "lex_sources.sqlite"
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO official_sources (id, name, connector, enabled, priority, type, refresh, base_url)
            VALUES ('gazzetta_ufficiale', 'Gazzetta Ufficiale', 'gazzetta_ufficiale', 1, 95, 'official', 'daily', 'https://www.gazzettaufficiale.it/')
            """
        )
        first_id = _insert_gazzetta_document(
            conn,
            title="Gazzetta Ufficiale - Serie Generale n. 113",
            url="https://www.gazzettaufficiale.it/do/gazzetta/downloadPdf?numeroGazzetta=113",
            digest="a" * 64,
        )
        second_id = _insert_gazzetta_document(
            conn,
            title="Gazzetta Ufficiale - Serie Generale n. 114",
            url="https://www.gazzettaufficiale.it/do/gazzetta/downloadPdf?numeroGazzetta=114",
            digest="b" * 64,
        )
        for index in range(3):
            conn.execute(
                "INSERT INTO official_chunks (document_id, source_id, chunk_index, title, text, materia) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    first_id,
                    "gazzetta_ufficiale",
                    index,
                    "Gazzetta Ufficiale - Serie Generale n. 113",
                    f"Decreto e normativa nel chunk {index}",
                    "Normativa",
                ),
            )
        conn.execute(
            "INSERT INTO official_chunks (document_id, source_id, chunk_index, title, text, materia) VALUES (?, ?, ?, ?, ?, ?)",
            (
                second_id,
                "gazzetta_ufficiale",
                0,
                "Gazzetta Ufficiale - Serie Generale n. 114",
                "Decreto e normativa in altro fascicolo",
                "Normativa",
            ),
        )
        conn.commit()

    rows = search_gazzetta("decreto normativa", limit=5, db_path=db_path, jsonl_path=tmp_path / "missing.jsonl")

    assert [row["document_id"] for row in rows] == [first_id, second_id]


def test_lex_normativa_usa_archivi_ufficiali_come_contesto(monkeypatch):
    monkeypatch.setattr(
        "lex.retrieval.normativa.get_legal_intelligence",
        lambda: (_ for _ in ()).throw(RuntimeError("nessun contesto Flask")),
    )
    monkeypatch.setattr(
        "lex.retrieval.normativa._search_normattiva",
        lambda query, limit=4: [
            {
                "chunk_id": "normattiva:2043",
                "fonte": "Normattiva",
                "titolo": "Approvazione del testo del Codice civile",
                "testo": "Art. 2043. Risarcimento per fatto illecito.",
                "url_origine": "data/normativa/raw/Codici.zip",
                "data": "1942-03-16",
            }
        ],
    )
    monkeypatch.setattr("lex.retrieval.normativa._search_gazzetta", lambda query, limit=2: [])

    rows = search_normativa_sources("codice civile art. 2043")

    assert rows
    assert rows[0].source_type == "normativa_normattiva"
    assert rows[0].metadata["authority"] == "Normattiva"
    assert rows[0].metadata["verified_reference"] is True
    assert "Risarcimento" in rows[0].excerpt
