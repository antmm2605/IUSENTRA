import json
import sqlite3
from pathlib import Path

from scripts.generate_lex_source_corpus import SourceCorpusOptions, generate_source_corpus


def _make_db(path: Path) -> None:
    with sqlite3.connect(str(path)) as conn:
        conn.executescript(
            """
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL DEFAULT '',
                code TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE source_documents_raw (
                id INTEGER PRIMARY KEY,
                source_id INTEGER,
                source_url TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE source_documents_normalized (
                id INTEGER PRIMARY KEY,
                raw_document_id INTEGER,
                title TEXT NOT NULL DEFAULT '',
                attachments_json TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE web_verification_evidence (
                id INTEGER PRIMARY KEY,
                evidence_key TEXT NOT NULL,
                review_id INTEGER,
                normalized_document_id INTEGER,
                source_code TEXT NOT NULL DEFAULT '',
                source_name TEXT NOT NULL DEFAULT '',
                query TEXT NOT NULL DEFAULT '',
                origin TEXT NOT NULL DEFAULT '',
                title TEXT NOT NULL DEFAULT '',
                source_url TEXT NOT NULL DEFAULT '',
                attachment_url TEXT NOT NULL DEFAULT '',
                attachment_type TEXT NOT NULL DEFAULT '',
                sha256 TEXT NOT NULL DEFAULT '',
                is_official INTEGER NOT NULL DEFAULT 0,
                context_chars INTEGER NOT NULL DEFAULT 0,
                excerpt TEXT NOT NULL DEFAULT '',
                content_text TEXT NOT NULL DEFAULT '',
                matched_terms_json TEXT NOT NULL DEFAULT '[]',
                verification_status TEXT NOT NULL DEFAULT 'verified',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.execute("INSERT INTO sources (id, name, code) VALUES (1, 'Cassazione', 'cassazione_massimario')")
        conn.execute(
            "INSERT INTO source_documents_raw (id, source_id, source_url) VALUES (10, 1, ?)",
            ("https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",),
        )
        conn.execute(
            "INSERT INTO source_documents_normalized (id, raw_document_id, title) VALUES (20, 10, ?)",
            ("Questione Penale Pendente del ricorso R.G. 9926/2026",),
        )
        conn.execute(
            """
            INSERT INTO web_verification_evidence (
                id, evidence_key, review_id, normalized_document_id, source_code, source_name,
                query, origin, title, source_url, attachment_url, attachment_type, sha256,
                is_official, context_chars, excerpt, content_text, matched_terms_json,
                verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                1,
                "ev-key-1",
                390,
                20,
                "cassazione_massimario",
                "Cassazione",
                "questione penale R.G. 9926/2026",
                "allegato_fonte_ufficiale",
                "Ordinanza di rimessione",
                "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                "https://www.cortedicassazione.it/resources/cms/documents/ordinanza.pdf",
                "pdf",
                "a" * 64,
                1,
                240,
                "R.G. 9966/2026 ordinanza di rimessione ex art. 599-bis c.p.p.",
                "Testo OCR ufficiale R.G. 9966/2026 ordinanza di rimessione ex art. 599-bis c.p.p.",
                json.dumps(["penale", "rimessione", "art. 599-bis c.p.p."]),
                "verified",
            ),
        )
        conn.commit()


def test_generate_lex_source_corpus_da_evidenze_verificate(tmp_path: Path):
    db_path = tmp_path / "legal_updates.db"
    output_dir = tmp_path / "corpus"
    _make_db(db_path)

    result = generate_source_corpus(
        SourceCorpusOptions(
            intelligence_db=db_path,
            output_dir=output_dir,
            tenant_id="tenant-fonti",
            limit=10,
            overwrite=True,
        )
    )

    assert result["ok"] is True
    assert result["documents_count"] == 1
    assert result["chunks_count"] == 1

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    documents = [json.loads(line) for line in (output_dir / "documents.jsonl").read_text(encoding="utf-8").splitlines()]
    chunks = [json.loads(line) for line in (output_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines()]
    expected = [json.loads(line) for line in (output_dir / "expected_queries.jsonl").read_text(encoding="utf-8").splitlines()]
    document_ai = json.loads((output_dir / "documenti_ai" / "documenti_ai.json").read_text(encoding="utf-8"))
    memory_index = json.loads((output_dir / "memory_tree" / "index.json").read_text(encoding="utf-8"))
    memory_chunks = [
        json.loads(line)
        for line in (output_dir / "memory_tree" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert manifest["rag_ready"] is True
    assert manifest["memory_tree"]["schema"] == "iusentra.lex_memory_tree.v1"
    assert manifest["memory_tree"]["tokenjuice_schema"] == "iusentra.lex_tokenjuice.v1"
    assert manifest["automatic_training"] is False
    assert manifest["human_review_required_for_rag"] is False
    assert manifest["human_review_required_for_fine_tuning"] is True
    assert documents[0]["metadata"]["source_url"].endswith("QSP50194")
    assert documents[0]["metadata"]["attachment_url"].endswith("ordinanza.pdf")
    assert "art. 599-bis" in " ".join(documents[0]["metadata"]["norm_references"])
    assert "9966/2026" in documents[0]["metadata"]["rg_references"]
    assert "Testo OCR ufficiale" in chunks[0]["text"]
    assert expected[0]["query"].startswith("Quale allegato ufficiale")
    assert "art. 599-bis" in " ".join(expected[0]["expected_norm_references"])
    assert "9966/2026" in expected[0]["expected_rg_references"]
    assert len(document_ai["documents"]) == 1
    assert document_ai["texts"][0]["text"].startswith("Testo OCR ufficiale")
    assert result["memory_tree"]["chunks_count"] == 1
    assert memory_index["ready_documents_count"] == 1
    assert memory_chunks[0]["metadata"]["tokenjuice"]["metadata"]["llm_used"] is False
    assert memory_chunks[0]["provenance"]["attachment_url"].endswith("ordinanza.pdf")
    assert "R.G. 9966/2026" in memory_chunks[0]["rg_refs"]


def test_generate_lex_source_corpus_filtra_evidenze_senza_testo(tmp_path: Path):
    db_path = tmp_path / "legal_updates.db"
    output_dir = tmp_path / "corpus"
    _make_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("UPDATE web_verification_evidence SET content_text = '', context_chars = 0")
        conn.commit()

    result = generate_source_corpus(
        SourceCorpusOptions(
            intelligence_db=db_path,
            output_dir=output_dir,
            tenant_id="tenant-fonti",
            limit=10,
            overwrite=True,
        )
    )

    assert result["documents_count"] == 0
    assert result["chunks_count"] == 0


def test_generate_lex_source_corpus_cassazione_filtra_pagine_non_documentali(tmp_path: Path):
    db_path = tmp_path / "legal_updates.db"
    output_dir = tmp_path / "corpus"
    _make_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT INTO source_documents_raw (id, source_id, source_url) VALUES (11, 1, ?)",
            ("https://www.cortedicassazione.it/page/it/privacy_policy?contentId=NTZ00001",),
        )
        conn.execute(
            "INSERT INTO source_documents_normalized (id, raw_document_id, title) VALUES (21, 11, ?)",
            ("Privacy policy",),
        )
        conn.execute(
            """
            INSERT INTO web_verification_evidence (
                id, evidence_key, review_id, normalized_document_id, source_code, source_name,
                query, origin, title, source_url, attachment_url, attachment_type, sha256,
                is_official, context_chars, excerpt, content_text, matched_terms_json,
                verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "ev-key-privacy",
                391,
                21,
                "cassazione_massimario",
                "Cassazione",
                "privacy policy",
                "fonte_acquisita",
                "Privacy policy",
                "https://www.cortedicassazione.it/page/it/privacy_policy?contentId=NTZ00001",
                "",
                "",
                "",
                1,
                120,
                "Privacy policy del sito.",
                "Privacy policy del sito.",
                json.dumps(["privacy"]),
                "verified",
            ),
        )
        conn.commit()

    result = generate_source_corpus(
        SourceCorpusOptions(
            intelligence_db=db_path,
            output_dir=output_dir,
            tenant_id="tenant-fonti",
            source_codes=("cassazione_massimario",),
            limit=10,
            overwrite=True,
        )
    )

    documents = [json.loads(line) for line in (output_dir / "documents.jsonl").read_text(encoding="utf-8").splitlines()]
    expected = [json.loads(line) for line in (output_dir / "expected_queries.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result["documents_count"] == 1
    assert documents[0]["metadata"]["source_url"].endswith("QSP50194")
    assert "Privacy policy" not in documents[0]["title"]
    assert [row["check"] for row in expected[0]["question_matrix"]][:3] == ["sintesi", "natura_atto", "oggetto"]
    assert manifest["source_filters"]["cassazione_massimario"].startswith("solo schede documentali")


def test_generate_lex_source_corpus_cassazione_ultime_filtra_pagine_non_documentali(tmp_path: Path):
    db_path = tmp_path / "legal_updates.db"
    output_dir = tmp_path / "corpus"
    _make_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("UPDATE sources SET code = 'cassazione_ultime_sent_ord_questioni'")
        conn.execute("UPDATE web_verification_evidence SET source_code = 'cassazione_ultime_sent_ord_questioni'")
        conn.execute(
            "INSERT INTO source_documents_raw (id, source_id, source_url) VALUES (11, 1, ?)",
            ("https://www.cortedicassazione.it/it/privacy_policy.page",),
        )
        conn.execute(
            "INSERT INTO source_documents_normalized (id, raw_document_id, title) VALUES (21, 11, ?)",
            ("Privacy policy",),
        )
        conn.execute(
            """
            INSERT INTO web_verification_evidence (
                id, evidence_key, review_id, normalized_document_id, source_code, source_name,
                query, origin, title, source_url, attachment_url, attachment_type, sha256,
                is_official, context_chars, excerpt, content_text, matched_terms_json,
                verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "ev-key-privacy-latest",
                391,
                21,
                "cassazione_ultime_sent_ord_questioni",
                "Cassazione",
                "privacy policy",
                "fonte_acquisita",
                "Privacy policy",
                "https://www.cortedicassazione.it/it/privacy_policy.page",
                "",
                "",
                "",
                1,
                120,
                "Privacy policy del sito.",
                "Privacy policy del sito.",
                json.dumps(["privacy"]),
                "verified",
            ),
        )
        conn.commit()

    result = generate_source_corpus(
        SourceCorpusOptions(
            intelligence_db=db_path,
            output_dir=output_dir,
            tenant_id="tenant-fonti",
            source_codes=("cassazione_ultime_sent_ord_questioni",),
            limit=10,
            overwrite=True,
        )
    )

    documents = [json.loads(line) for line in (output_dir / "documents.jsonl").read_text(encoding="utf-8").splitlines()]
    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))

    assert result["documents_count"] == 1
    assert documents[0]["metadata"]["source_url"].endswith("QSP50194")
    assert "Privacy policy" not in documents[0]["title"]
    assert manifest["source_filters"]["cassazione_ultime_sent_ord_questioni"].startswith(
        "solo schede documentali"
    )


def test_generate_lex_source_corpus_domande_da_titolo_scheda_e_pdf_letto(tmp_path: Path):
    db_path = tmp_path / "legal_updates.db"
    output_dir = tmp_path / "corpus"
    _make_db(db_path)
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            UPDATE web_verification_evidence
            SET title = ?,
                content_text = ?,
                context_chars = ?
            WHERE id = 1
            """,
            (
                "11417_04_2026_civ_no-index.pdf",
                (
                    "Testo PDF letto. Sentenza n. 11417 del 27/04/2026. "
                    "La parte chiede una rimessione ma la Corte decide il ricorso. "
                    "Richiamati art. 71, comma 2, d.P.R. 115/2002 e art. 2946 c.c."
                ),
                260,
            ),
        )
        conn.execute(
            "UPDATE source_documents_normalized SET title = ? WHERE id = 20",
            ("Sentenza n. 11417 del 27/04/2026",),
        )
        conn.execute(
            "UPDATE source_documents_raw SET source_url = ? WHERE id = 10",
            ("https://www.cortedicassazione.it/it/civile_dettaglio.page?contentId=SZC50126",),
        )
        conn.execute(
            "UPDATE web_verification_evidence SET source_url = ? WHERE id = 1",
            ("https://www.cortedicassazione.it/it/civile_dettaglio.page?contentId=SZC50126",),
        )
        conn.commit()

    generate_source_corpus(
        SourceCorpusOptions(
            intelligence_db=db_path,
            output_dir=output_dir,
            tenant_id="tenant-fonti",
            source_codes=("cassazione_massimario",),
            limit=10,
            overwrite=True,
        )
    )

    expected = [json.loads(line) for line in (output_dir / "expected_queries.jsonl").read_text(encoding="utf-8").splitlines()]
    checks = [row["check"] for row in expected[0]["question_matrix"]]

    assert expected[0]["expected_title"] == "Sentenza n. 11417 del 27/04/2026"
    assert "principio" in checks
    assert "decisione" in checks
    assert "articoli" in checks
    assert "natura_rimessione" not in checks
