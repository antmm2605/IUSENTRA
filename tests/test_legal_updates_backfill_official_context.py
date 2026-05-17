from __future__ import annotations

import sqlite3
from pathlib import Path

from pct.legal_update_pipeline import build_legal_update_pipeline
from scripts.legal_updates_backfill_official_context import PERFORMED_BY, run_backfill


DIRTY_TEXT = """
Leggi la notizia
13/03/2026
D.Lgs. 13 marzo 2026, n. 39
Leggi la notizia
14/03/2026
Aggiornamento giuridico pubblicato in fonte ufficiale.
"""


def _official_context(url: str, query: str) -> dict[str, object]:
    assert "gazzettaufficiale.it" in url
    assert "39/2026" in query or "39" in query
    return {
        "officialTitle": "D.Lgs. 13 marzo 2026, n. 39",
        "officialContext": (
            "DECRETO LEGISLATIVO 13 marzo 2026, n. 39. "
            "Attuazione della direttiva europea in materia di obblighi organizzativi "
            "e controlli interni.\n"
            "Art. 1 Oggetto e ambito di applicazione. Il decreto disciplina gli "
            "adempimenti degli operatori, le verifiche documentali e le responsabilità "
            "connesse ai procedimenti interessati.\n"
            "Art. 2 Entrata in vigore. Le disposizioni entrano in vigore il giorno "
            "successivo alla pubblicazione nella Gazzetta Ufficiale."
        ),
        "contextSummary": (
            "Il decreto legislativo 13 marzo 2026, n. 39 disciplina obblighi "
            "organizzativi, controlli interni e decorrenza delle disposizioni."
        ),
        "keyPoints": ["Obblighi organizzativi e controlli interni confermati dalla fonte ufficiale."],
        "operationalChecks": ["Verificare la decorrenza indicata dall'art. 2 prima dell'uso in atto."],
        "contextCompleted": True,
        "warnings": [],
    }


def _seed_dirty_dlgs_39(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    repo = pipeline.repository
    source = repo.get_source_by_code("gazzetta_ufficiale")
    assert source is not None

    raw = repo.save_raw_document(
        {
            "source_id": source["id"],
            "external_id": "dlgs-39-2026",
            "source_url": "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
            "title": "Leggi la notizia",
            "published_at": "2026-03-13",
            "raw_html": f"<article>{DIRTY_TEXT}</article>",
            "raw_text": DIRTY_TEXT,
            "content_hash": "dirty-dlgs-39-2026",
            "fetch_status": "fetched",
            "http_status": 200,
        }
    )
    normalized = repo.save_normalized_document(
        int(raw["id"]),
        {
            "title": "Leggi la notizia",
            "body_text": DIRTY_TEXT,
            "body_short": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "language": "it",
            "issuer": "Gazzetta Ufficiale",
            "document_date": "2026-03-13",
            "document_type_guess": "decreto legislativo",
            "attachments_json": [],
        },
    )
    analysis = repo.save_analysis(
        int(normalized["id"]),
        {
            "classification_type": "NORMATIVA_NUOVA",
            "confidence_score": 0.94,
            "impact_level": "medio",
            "summary_short": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "summary_long": DIRTY_TEXT,
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEW_NORMATIVE",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )
    review = repo.upsert_review_item(
        {
            "normalized_document_id": int(normalized["id"]),
            "analysis_id": int(analysis["id"]),
            "proposal_type": "normativa",
            "proposed_action": "NEW_NORMATIVE",
            "target_entity_type": "",
            "target_entity_id": None,
            "proposal_payload_json": {"title": "Leggi la notizia", "body": DIRTY_TEXT},
            "status": "approved",
            "priority": 90,
        }
    )

    db_path = Path(repo.db_path)
    with sqlite3.connect(db_path) as conn:
        news_id = conn.execute(
            """
            INSERT INTO news (
                title, slug, short_summary, content, news_type, source_url,
                source_document_id, is_auto_generated, publication_status,
                published_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'published', '2026-03-13', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "Leggi la notizia",
                "leggi-la-notizia",
                "Aggiornamento giuridico pubblicato in fonte ufficiale.",
                DIRTY_TEXT,
                "normativa",
                "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
                int(normalized["id"]),
            ),
        ).lastrowid
        normative_id = conn.execute(
            """
            INSERT INTO normative (
                title, slug, norm_type, norm_number, norm_year, issuer,
                publication_date, effective_date, status, source_url,
                source_document_id, text_official, text_current, summary,
                notes, version_group_id, created_at, updated_at
            )
            VALUES (?, ?, 'decreto legislativo', '39', '2026', 'Gazzetta Ufficiale',
                    '2026-03-13', '2026-03-14', 'vigente', ?, ?, ?, ?, ?,
                    '', 'decreto-legislativo-39-2026-gazzetta-ufficiale',
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "Leggi la notizia",
                "leggi-la-notizia-normativa",
                "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
                int(normalized["id"]),
                DIRTY_TEXT,
                DIRTY_TEXT,
                "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            ),
        ).lastrowid
        conn.commit()

    return db_path, {
        "raw_id": int(raw["id"]),
        "normalized_id": int(normalized["id"]),
        "review_id": int(review["id"]),
        "news_id": int(news_id),
        "normative_id": int(normative_id),
    }


def _read_rows(db_path: Path, ids: dict[str, int]) -> dict[str, dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return {
            "raw": dict(conn.execute("SELECT * FROM source_documents_raw WHERE id = ?", (ids["raw_id"],)).fetchone()),
            "news": dict(conn.execute("SELECT * FROM news WHERE id = ?", (ids["news_id"],)).fetchone()),
            "normative": dict(conn.execute("SELECT * FROM normative WHERE id = ?", (ids["normative_id"],)).fetchone()),
        }


def test_backfill_dlgs_39_dry_run_non_scrive_e_preserva_raw(tmp_path: Path):
    db_path, ids = _seed_dirty_dlgs_39(tmp_path)
    before = _read_rows(db_path, ids)

    plan = run_backfill(db_path, context_helper=_official_context)

    assert plan["dry_run"] is True
    assert plan["mode"] == "dry-run"
    assert plan["stats"]["applyable_ready"] == 2
    assert {"news", "normative", "review", "raw"}.issubset(
        {item["entity_type"] for item in plan["items"]}
    )
    assert any(item["old"].get("title") == "Leggi la notizia" for item in plan["items"])
    assert any(
        item["entity_type"] == "news"
        and item["new"]["title"] == "D.Lgs. 13 marzo 2026, n. 39"
        and item["hashes"]["old_sha256"] != item["hashes"]["new_sha256"]
        for item in plan["items"]
    )
    assert _read_rows(db_path, ids) == before


def test_backfill_dlgs_39_apply_scrive_news_normative_con_audit_versione_e_raw_intatto(tmp_path: Path):
    db_path, ids = _seed_dirty_dlgs_39(tmp_path)
    before = _read_rows(db_path, ids)

    plan = run_backfill(db_path, apply_changes=True, context_helper=_official_context)

    assert plan["dry_run"] is False
    assert plan["apply"]["errors"] == 0
    assert plan["apply"]["applied"] == 2

    after = _read_rows(db_path, ids)
    assert after["raw"]["title"] == before["raw"]["title"] == "Leggi la notizia"
    assert after["raw"]["raw_text"] == before["raw"]["raw_text"] == DIRTY_TEXT
    assert after["news"]["title"] == "D.Lgs. 13 marzo 2026, n. 39"
    assert "obblighi organizzativi" in after["news"]["short_summary"]
    assert "responsabilità connesse" in after["news"]["content"]
    assert after["normative"]["title"] == "D.Lgs. 13 marzo 2026, n. 39"
    assert "Art. 1 Oggetto" in after["normative"]["text_official"]
    assert "raw originale conservato" in after["normative"]["notes"]

    with sqlite3.connect(db_path) as conn:
        audit_rows = conn.execute(
            "SELECT entity_type, action FROM audit_log WHERE performed_by = ? ORDER BY id",
            (PERFORMED_BY,),
        ).fetchall()
        versions = conn.execute(
            "SELECT text_version FROM normative_versions WHERE normative_id = ?",
            (ids["normative_id"],),
        ).fetchall()

    assert ("news", "update") in audit_rows
    assert ("normative", "update") in audit_rows
    assert any("controlli interni" in row[0] for row in versions)
