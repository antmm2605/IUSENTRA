from __future__ import annotations

import json
from pathlib import Path

from pct.legal_update_pipeline import build_legal_update_pipeline


def test_publish_auto_news_usa_contesto_verifica_per_news_only(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("gazzetta_ufficiale")
    assert source is not None

    raw = pipeline.repository.save_raw_document(
        {
            "source_id": source["id"],
            "external_id": "dlgs-39-2026",
            "source_url": "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
            "title": "D.Lgs. 13 marzo 2026, n. 39",
            "published_at": "2026-03-13",
            "raw_html": "",
            "raw_text": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "content_hash": "hash-dlgs-39-2026",
            "fetch_status": "fetched",
            "http_status": 200,
        }
    )
    normalized = pipeline.repository.save_normalized_document(
        int(raw["id"]),
        {
            "title": "D.Lgs. 13 marzo 2026, n. 39",
            "body_text": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "body_short": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "language": "it",
            "issuer": "Gazzetta Ufficiale",
            "document_date": "2026-03-13",
            "document_type_guess": "decreto legislativo",
            "attachments_json": [],
        },
    )
    analysis = pipeline.repository.save_analysis(
        int(normalized["id"]),
        {
            "classification_type": "COMMENTO",
            "confidence_score": 0.96,
            "impact_level": "medio",
            "summary_short": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "summary_long": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )
    review = pipeline.repository.upsert_review_item(
        {
            "normalized_document_id": int(normalized["id"]),
            "analysis_id": int(analysis["id"]),
            "proposal_type": "commento",
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
            "proposal_payload_json": {},
            "status": "approved",
            "priority": 90,
        }
    )

    monkeypatch.setattr(
        "pct.legal_update_pipeline.verify_legal_update_against_public_sources",
        lambda review, source, **kwargs: {
            "ok": True,
            "reason": "Verifica pubblica completata con fonti coerenti.",
            "confirmation_count": 3,
            "official_confirmations": 2,
            "confirmations": [
                {
                    "source_name": "Gazzetta Ufficiale",
                    "official": True,
                    "excerpt": (
                        "Il decreto legislativo 13 marzo 2026, n. 39 disciplina il conferimento "
                        "delle deleghe e i controlli sulle funzioni esercitate."
                    ),
                    "context_chars": 180,
                },
                {
                    "source_name": "Autorità di vigilanza",
                    "official": True,
                    "excerpt": (
                        "La pubblicazione richiama presidi sul rischio di liquidità e sugli "
                        "obblighi di vigilanza applicabili agli intermediari."
                    ),
                    "context_chars": 170,
                },
                {
                    "source_name": "Archivio pubblico",
                    "official": False,
                    "excerpt": "La scheda conferma numero, data e oggetto del provvedimento.",
                    "context_chars": 90,
                },
            ],
            "searched": {"web_results": 3},
        },
    )

    report = pipeline.publish_auto_news(limit=10)
    news = pipeline.repository.list_news(limit=5, include_drafts=False)[0]

    assert report["count"] == 1
    assert report["items"] == [int(review["id"])]
    assert news["title"] == "D.Lgs. 13 marzo 2026, n. 39"
    assert "Aggiornamento giuridico pubblicato in fonte ufficiale" not in news["short_summary"]
    assert "deleghe" in news["short_summary"]
    assert "Contesto ufficiale verificato" in news["content"]
    assert "deleghe" in news["content"]
    assert "rischio di liquidità" in news["content"]
    assert "vigilanza" in news["content"]


def test_publish_auto_news_salva_evidenze_web_e_le_rende_ricercabili(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("agcom_provvedimenti")
    assert source is not None

    raw = pipeline.repository.save_raw_document(
        {
            "source_id": source["id"],
            "external_id": "agcom-93-26-cons",
            "source_url": "https://www.agcom.it/provvedimenti/delibera-93-26-cons",
            "title": "Delibera 93/26/CONS",
            "published_at": "2026-05-15",
            "raw_html": "",
            "raw_text": "Delibera AGCOM sulle comunicazioni elettroniche e sui diritti degli utenti.",
            "content_hash": "hash-agcom-93-26-cons",
            "fetch_status": "fetched",
            "http_status": 200,
        }
    )
    normalized = pipeline.repository.save_normalized_document(
        int(raw["id"]),
        {
            "title": "Delibera 93/26/CONS",
            "body_text": "Delibera AGCOM sulle comunicazioni elettroniche e sui diritti degli utenti.",
            "body_short": "Delibera AGCOM sulle comunicazioni elettroniche.",
            "language": "it",
            "issuer": "AGCOM",
            "document_date": "2026-05-15",
            "document_type_guess": "delibera",
            "attachments_json": [],
        },
    )
    analysis = pipeline.repository.save_analysis(
        int(normalized["id"]),
        {
            "classification_type": "COMMENTO",
            "confidence_score": 0.55,
            "impact_level": "medio",
            "summary_short": "Aggiornamento AGCOM da completare con fonte ufficiale.",
            "summary_long": "Aggiornamento AGCOM da completare con fonte ufficiale.",
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )
    review = pipeline.repository.upsert_review_item(
        {
            "normalized_document_id": int(normalized["id"]),
            "analysis_id": int(analysis["id"]),
            "proposal_type": "commento",
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
            "proposal_payload_json": {},
            "status": "pending",
            "priority": 95,
        }
    )
    calls: list[str] = []

    def fake_verify(review_payload, source_payload, **kwargs):
        calls.append(str(review_payload["title"]))
        return {
            "ok": True,
            "reason": "Verifica pubblica completata con fonti coerenti.",
            "confirmation_count": 3,
            "official_confirmations": 2,
            "confirmations": [
                {
                    "origin": "ricerca_web_governata",
                    "source_name": "AGCOM",
                    "title": "Delibera 93/26/CONS",
                    "url": "https://www.agcom.it/provvedimenti/delibera-93-26-cons",
                    "official": True,
                    "excerpt": "La delibera conferma obblighi di trasparenza sulle comunicazioni elettroniche.",
                    "content": "La delibera conferma obblighi di trasparenza sulle comunicazioni elettroniche e tutela gli utenti finali.",
                    "context_chars": 220,
                    "matched_terms": ["delibera", "93", "cons"],
                    "query": "Delibera 93/26/CONS",
                },
                {
                    "origin": "allegato_fonte_ufficiale",
                    "source_name": "AGCOM",
                    "source_url": "https://www.agcom.it/provvedimenti/delibera-93-26-cons",
                    "attachment_url": "https://www.agcom.it/documenti/delibera-93-26-cons.pdf",
                    "attachment_type": "pdf",
                    "sha256": "abc123",
                    "official": True,
                    "title": "delibera-93-26-cons.pdf",
                    "excerpt": "Testo della delibera AGCOM con obblighi di trasparenza.",
                    "content": "Testo della delibera AGCOM con obblighi di trasparenza e tutela degli utenti finali.",
                    "context_chars": 300,
                    "matched_terms": ["delibera", "trasparenza"],
                    "query": "Delibera 93/26/CONS",
                },
            ],
            "searched": {"web_results": 4},
        }

    monkeypatch.setattr("pct.legal_update_pipeline.verify_legal_update_against_public_sources", fake_verify)

    report = pipeline.publish_auto_news(limit=1)
    with pipeline.repository._connect() as conn:
        evidence_count = int(conn.execute("SELECT COUNT(*) FROM web_verification_evidence").fetchone()[0])
        with_attachments = int(
            conn.execute(
                "SELECT COUNT(*) FROM source_documents_normalized WHERE attachments_json <> '[]'"
            ).fetchone()[0]
        )
    results = pipeline.repository.search_lex_sources("trasparenza comunicazioni elettroniche", limit=5)

    assert calls == ["Delibera 93/26/CONS"]
    assert report["count"] == 1
    assert report["web_verification_attempts"] == 1
    assert report["verification_evidence_saved"] >= 2
    assert report["verification_attachments_saved"] == 1
    assert evidence_count == 2
    assert with_attachments == 1
    assert results
    assert any(row["entity_type"] == "web_evidence" for row in results)
    assert pipeline.repository.get_review_item(int(review["id"]))["status"] == "published"


def test_process_document_salva_evidenza_web_durante_acquisizione(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("garante_privacy")
    assert source is not None

    monkeypatch.setattr(
        "pct.legal_update_pipeline.analyze_document",
        lambda normalized, source, **kwargs: {
            "classification_type": "COMMENTO",
            "confidence_score": 0.54,
            "impact_level": "medio",
            "summary_short": "Provvedimento privacy su diritti degli utenti.",
            "summary_long": "Provvedimento privacy su diritti degli utenti.",
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )
    monkeypatch.setattr(
        "pct.legal_update_pipeline.verify_legal_update_against_public_sources",
        lambda review, source, **kwargs: {
            "ok": True,
            "reason": "Verifica pubblica completata.",
            "confirmation_count": 1,
            "official_confirmations": 1,
            "confirmations": [
                {
                    "origin": "fonte_acquisita",
                    "source_name": "Garante Privacy",
                    "title": "Provvedimento privacy 2026",
                    "url": "https://www.garanteprivacy.it/provvedimento-privacy-2026",
                    "official": True,
                    "excerpt": "Provvedimento privacy su diritti degli utenti e obblighi informativi.",
                    "content": "Provvedimento privacy su diritti degli utenti e obblighi informativi.",
                    "context_chars": 72,
                    "matched_terms": ["privacy", "utenti"],
                    "query": "Provvedimento privacy 2026",
                }
            ],
            "searched": {"web_results": 1},
        },
    )

    result = pipeline.process_document(
        source,
        {
            "external_id": "garante-privacy-2026",
            "source_url": "https://www.garanteprivacy.it/provvedimento-privacy-2026",
            "title": "Provvedimento privacy 2026",
            "published_at": "2026-05-17",
            "raw_html": "",
            "raw_text": "Provvedimento privacy su diritti degli utenti e obblighi informativi.",
            "content_hash": "hash-garante-privacy-2026",
            "fetch_status": "fetched",
            "http_status": 200,
        },
    )

    with pipeline.repository._connect() as conn:
        evidence_count = int(conn.execute("SELECT COUNT(*) FROM web_verification_evidence").fetchone()[0])

    results = pipeline.repository.search_lex_sources("privacy utenti obblighi informativi", limit=5)

    assert result["verification_evidence"]["attempted"] == 1
    assert result["verification_evidence"]["saved"] == 1
    assert evidence_count == 1
    assert pipeline.repository.get_review_item(int(result["review"]["id"]))["status"] == "pending"
    assert any(row["entity_type"] == "web_evidence" for row in results)


def test_backfill_web_verification_evidence_popola_review_esistenti(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("agcom_provvedimenti")
    assert source is not None
    raw = pipeline.repository.save_raw_document(
        {
            "source_id": source["id"],
            "external_id": "agcom-backfill-2026",
            "source_url": "https://www.agcom.it/provvedimenti/backfill-2026",
            "title": "Provvedimento AGCOM backfill 2026",
            "published_at": "2026-05-17",
            "raw_html": "",
            "raw_text": "Provvedimento AGCOM da completare con prova web.",
            "content_hash": "hash-agcom-backfill-2026",
            "fetch_status": "fetched",
            "http_status": 200,
        }
    )
    normalized = pipeline.repository.save_normalized_document(
        int(raw["id"]),
        {
            "title": "Provvedimento AGCOM backfill 2026",
            "body_text": "Provvedimento AGCOM da completare con prova web.",
            "body_short": "Provvedimento AGCOM da completare con prova web.",
            "language": "it",
            "issuer": "AGCOM",
            "document_date": "2026-05-17",
            "document_type_guess": "provvedimento",
            "attachments_json": [],
        },
    )
    analysis = pipeline.repository.save_analysis(
        int(normalized["id"]),
        {
            "classification_type": "COMMENTO",
            "confidence_score": 0.52,
            "impact_level": "medio",
            "summary_short": "Provvedimento AGCOM da completare.",
            "summary_long": "Provvedimento AGCOM da completare.",
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )
    pipeline.repository.upsert_review_item(
        {
            "normalized_document_id": int(normalized["id"]),
            "analysis_id": int(analysis["id"]),
            "proposal_type": "commento",
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
            "proposal_payload_json": {},
            "status": "pending",
            "priority": 80,
        }
    )
    monkeypatch.setattr(
        "pct.legal_update_pipeline.verify_legal_update_against_public_sources",
        lambda review, source, **kwargs: {
            "ok": True,
            "reason": "Verifica pubblica completata.",
            "confirmation_count": 1,
            "official_confirmations": 1,
            "confirmations": [
                {
                    "origin": "fonte_acquisita",
                    "source_name": "AGCOM",
                    "title": "Provvedimento AGCOM backfill 2026",
                    "url": "https://www.agcom.it/provvedimenti/backfill-2026",
                    "official": True,
                    "excerpt": "Provvedimento AGCOM con prova web salvata.",
                    "content": "Provvedimento AGCOM con prova web salvata.",
                    "context_chars": 44,
                    "matched_terms": ["agcom", "backfill"],
                    "query": "Provvedimento AGCOM backfill 2026",
                }
            ],
            "searched": {"web_results": 1},
        },
    )

    report = pipeline.backfill_web_verification_evidence(limit=5)

    with pipeline.repository._connect() as conn:
        evidence_count = int(conn.execute("SELECT COUNT(*) FROM web_verification_evidence").fetchone()[0])

    assert report["checked"] == 1
    assert report["web_verification_attempts"] == 1
    assert report["verification_evidence_saved"] == 1
    assert evidence_count == 1


def test_backfill_web_verification_evidence_filtra_riferimento_esatto(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("inps_circolari")
    assert source is not None

    def _seed_review(title: str, *, external_id: str) -> int:
        raw = pipeline.repository.save_raw_document(
            {
                "source_id": source["id"],
                "external_id": external_id,
                "source_url": f"https://www.inps.it/{external_id}.html",
                "title": title,
                "published_at": "2026-05-17",
                "raw_html": "",
                "raw_text": f"{title} da completare.",
                "content_hash": f"hash-{external_id}",
                "fetch_status": "fetched",
                "http_status": 200,
            }
        )
        normalized = pipeline.repository.save_normalized_document(
            int(raw["id"]),
            {
                "title": title,
                "body_text": f"{title} da completare.",
                "body_short": f"{title} da completare.",
                "language": "it",
                "issuer": "INPS",
                "document_date": "2026-05-17",
                "document_type_guess": "circolare",
                "attachments_json": [],
            },
        )
        analysis = pipeline.repository.save_analysis(
            int(normalized["id"]),
            {
                "classification_type": "COMMENTO",
                "confidence_score": 0.52,
                "impact_level": "medio",
                "summary_short": f"{title} da completare.",
                "summary_long": f"{title} da completare.",
                "what_changes": "",
                "extracted_entities_json": {},
                "proposed_action": "NEWS_ONLY",
                "target_entity_type": "",
                "target_entity_id": None,
            },
        )
        review = pipeline.repository.upsert_review_item(
            {
                "normalized_document_id": int(normalized["id"]),
                "analysis_id": int(analysis["id"]),
                "proposal_type": "commento",
                "proposed_action": "NEWS_ONLY",
                "target_entity_type": "",
                "target_entity_id": None,
                "proposal_payload_json": {},
                "status": "approved",
                "priority": 70,
            }
        )
        return int(review["id"])

    target_review_id = _seed_review("Circolare numero 53 del 07-05-2026", external_id="circolare-numero-53")
    _seed_review("Circolare numero 25 del 05-03-2026", external_id="circolare-numero-25")
    calls: list[str] = []

    def fake_verify(review, source, **kwargs):
        calls.append(str(review["title"]))
        return {
            "ok": True,
            "reason": "Fonte diretta verificata.",
            "confirmation_count": 1,
            "official_confirmations": 1,
            "confirmations": [
                {
                    "origin": "fonte_acquisita",
                    "source_name": source["name"],
                    "title": review["title"],
                    "url": review["source_url"],
                    "official": True,
                    "excerpt": "Documento INPS verificato.",
                    "content": "Documento INPS verificato.",
                    "context_chars": 25,
                    "matched_terms": ["circolare", "53"],
                    "query": review["title"],
                }
            ],
            "searched": {"web_results": 0, "direct_only": True},
        }

    monkeypatch.setattr("pct.legal_update_pipeline.verify_legal_update_against_public_sources", fake_verify)

    report = pipeline.backfill_web_verification_evidence(
        limit=10,
        query="Circolare numero 53 del 07-05-2026",
    )

    with pipeline.repository._connect() as conn:
        evidence_rows = conn.execute("SELECT review_id, title FROM web_verification_evidence").fetchall()

    assert report["selected"] == 1
    assert report["checked"] == 1
    assert report["query"] == "Circolare numero 53 del 07-05-2026"
    assert calls == ["Circolare numero 53 del 07-05-2026"]
    assert [(row["review_id"], row["title"]) for row in evidence_rows] == [
        (target_review_id, "Circolare numero 53 del 07-05-2026")
    ]


def test_backfill_web_verification_evidence_rinfresca_allegato_ocr_vuoto(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("cassazione_massimario")
    assert source is not None
    qsp_url = "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194"
    attachment_url = (
        "https://www.cortedicassazione.it/resources/cms/documents/"
        "Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf"
    )
    stale_note = "Allegato scaricato dalla fonte ufficiale; testo non estraibile automaticamente."
    raw = pipeline.repository.save_raw_document(
        {
            "source_id": source["id"],
            "external_id": "qsp-50194",
            "source_url": qsp_url,
            "title": "Questione Penale Pendente del ricorso R.G. 9926/2026",
            "published_at": "2026-05-05",
            "raw_html": "",
            "raw_text": "Questione penale pendente da completare con allegato.",
            "content_hash": "hash-qsp-50194",
            "fetch_status": "fetched",
            "http_status": 200,
        }
    )
    normalized = pipeline.repository.save_normalized_document(
        int(raw["id"]),
        {
            "title": "Questione Penale Pendente del ricorso R.G. 9926/2026",
            "body_text": "Questione penale pendente da completare con allegato.",
            "body_short": "Questione penale pendente.",
            "language": "it",
            "issuer": "Corte Suprema di Cassazione",
            "document_date": "2026-05-05",
            "document_type_guess": "questione penale",
            "attachments_json": [
                {
                    "title": "Ordinanza di rimessione",
                    "url": attachment_url,
                    "source_url": qsp_url,
                    "attachment_type": "pdf",
                    "sha256": "sha-qsp-ocr",
                    "verified": True,
                    "text_excerpt": stale_note,
                    "context_chars": 0,
                }
            ],
        },
    )
    analysis = pipeline.repository.save_analysis(
        int(normalized["id"]),
        {
            "classification_type": "GIURISPRUDENZA",
            "confidence_score": 0.74,
            "impact_level": "medio",
            "summary_short": "Questione penale pendente da completare.",
            "summary_long": "Questione penale pendente da completare.",
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )
    review = pipeline.repository.upsert_review_item(
        {
            "normalized_document_id": int(normalized["id"]),
            "analysis_id": int(analysis["id"]),
            "proposal_type": "commento",
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
            "proposal_payload_json": {},
            "status": "approved",
            "priority": 80,
        }
    )
    pipeline.repository.record_web_verification_evidence(
        review_id=int(review["id"]),
        normalized_document_id=int(normalized["id"]),
        source=source,
        verification={
            "confirmations": [
                {
                    "origin": "allegato_fonte_ufficiale",
                    "source_name": "Corte Suprema di Cassazione",
                    "title": "Ordinanza di rimessione",
                    "source_url": qsp_url,
                    "attachment_url": attachment_url,
                    "attachment_type": "pdf",
                    "sha256": "sha-qsp-ocr",
                    "official": True,
                    "excerpt": stale_note,
                    "content": stale_note,
                    "context_chars": 0,
                    "matched_terms": [],
                }
            ]
        },
    )
    ocr_text = "Ricorso n. 9966/2026 R.G. e udienza del 9 luglio 2026 davanti alla Corte di cassazione."
    stale_quality = pipeline.repository.web_evidence_quality_for_review(
        int(review["id"]),
        review=pipeline.repository.get_review_item(int(review["id"])),
    )
    assert stale_quality["status"] == "da_ocr"
    assert stale_quality["pdf_found"] is True
    assert stale_quality["pdf_text_ready"] is False
    assert stale_quality["ocr_status"] == "da_eseguire"
    assert "PDF presente ma testo OCR mancante" in stale_quality["warnings"]

    monkeypatch.setattr(
        "pct.legal_update_pipeline.verify_legal_update_against_public_sources",
        lambda review, source, **kwargs: {
            "ok": True,
            "reason": "Allegato ufficiale letto con OCR.",
            "confirmation_count": 1,
            "official_confirmations": 1,
            "confirmations": [
                {
                    "origin": "allegato_fonte_ufficiale",
                    "source_name": source["name"],
                    "title": "Ordinanza di rimessione",
                    "source_url": qsp_url,
                    "attachment_url": attachment_url,
                    "attachment_type": "pdf",
                    "sha256": "sha-qsp-ocr",
                    "official": True,
                    "excerpt": ocr_text,
                    "content": ocr_text,
                    "context_chars": len(ocr_text),
                    "matched_terms": ["9966", "2026"],
                }
            ],
        },
    )

    report = pipeline.backfill_web_verification_evidence(limit=5, review_ids=(int(review["id"]),))

    with pipeline.repository._connect() as conn:
        evidence_rows = conn.execute(
            "SELECT attachment_url, context_chars, excerpt FROM web_verification_evidence"
        ).fetchall()
        attachments_json = conn.execute(
            "SELECT attachments_json FROM source_documents_normalized WHERE id = ?",
            (int(normalized["id"]),),
        ).fetchone()["attachments_json"]

    attachments = json.loads(attachments_json)
    assert report["selected"] == 1
    assert report["checked"] == 1
    assert report["verification_attachments_saved"] == 1
    assert len(evidence_rows) == 1
    assert evidence_rows[0]["attachment_url"] == attachment_url
    assert evidence_rows[0]["context_chars"] == len(ocr_text)
    assert "9966/2026" in evidence_rows[0]["excerpt"]
    assert attachments[0]["context_chars"] == len(ocr_text)
    assert "9966/2026" in attachments[0]["text_excerpt"]
    assert report["items"][0]["quality_status"] == "pronto_con_note"
    assert report["items"][0]["quality_ready"] is True
    assert report["quality"]["summary"]["total"] == 1
    assert report["quality"]["summary"]["ready"] == 1
    assert report["quality"]["summary"]["pdf_found"] == 1
    assert report["quality"]["summary"]["pdf_text_ready"] == 1
    assert report["quality"]["summary"]["rg_discrepancies"] == 1
    quality_item = report["quality"]["items"][0]
    assert quality_item["pdf_clickable"] is True
    assert quality_item["hash_ready"] is True
    assert quality_item["text_read"] is True
    assert quality_item["ocr_status"] == "pulito"
    assert quality_item["rg_references"] == ["9926/2026", "9966/2026"]
    assert "riferimenti R.G. discordanti" in quality_item["warnings"]
    question_checks = [row["check"] for row in quality_item["question_matrix"]]
    assert question_checks[:9] == [
        "sintesi",
        "natura_atto",
        "oggetto",
        "stato",
        "punto_diritto",
        "motivi",
        "norme",
        "effetto_pratico",
        "esito",
    ]
    assert "pdf_allegato" in question_checks
    assert "discrepanza_rg" in question_checks


def test_backfill_web_verification_evidence_query_cerca_in_evidenze_e_allegati(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("cassazione_massimario")
    assert source is not None
    qsp_url = "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194"
    attachment_url = "https://www.cortedicassazione.it/resources/cms/documents/qsp50194.pdf"
    raw = pipeline.repository.save_raw_document(
        {
            "source_id": source["id"],
            "external_id": "cassazione-query-ocr",
            "source_url": "https://www.cortedicassazione.it/it/qsp.page",
            "title": "Questione penale pendente",
            "published_at": "2026-05-05",
            "raw_html": "",
            "raw_text": "Questione penale pendente.",
            "content_hash": "hash-cassazione-query-ocr",
            "fetch_status": "fetched",
            "http_status": 200,
        }
    )
    normalized = pipeline.repository.save_normalized_document(
        int(raw["id"]),
        {
            "title": "Questione penale pendente",
            "body_text": "Questione penale pendente.",
            "body_short": "Questione penale pendente.",
            "language": "it",
            "issuer": "Corte Suprema di Cassazione",
            "document_date": "2026-05-05",
            "document_type_guess": "questione penale",
            "attachments_json": [{"title": "Allegato", "url": attachment_url, "source_url": qsp_url}],
        },
    )
    analysis = pipeline.repository.save_analysis(
        int(normalized["id"]),
        {
            "classification_type": "GIURISPRUDENZA",
            "confidence_score": 0.74,
            "impact_level": "medio",
            "summary_short": "Questione penale pendente.",
            "summary_long": "Questione penale pendente.",
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )
    review = pipeline.repository.upsert_review_item(
        {
            "normalized_document_id": int(normalized["id"]),
            "analysis_id": int(analysis["id"]),
            "proposal_type": "commento",
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
            "proposal_payload_json": {},
            "status": "approved",
            "priority": 80,
        }
    )
    pipeline.repository.record_web_verification_evidence(
        review_id=int(review["id"]),
        normalized_document_id=int(normalized["id"]),
        source=source,
        verification={
            "confirmations": [
                {
                    "origin": "allegato_fonte_ufficiale",
                    "source_name": "Corte Suprema di Cassazione",
                    "title": "Allegato",
                    "source_url": qsp_url,
                    "attachment_url": attachment_url,
                    "attachment_type": "pdf",
                    "sha256": "sha-query-qsp",
                    "official": True,
                    "excerpt": "Allegato scaricato dalla fonte ufficiale; testo non estraibile automaticamente.",
                    "content": "Allegato scaricato dalla fonte ufficiale; testo non estraibile automaticamente.",
                    "context_chars": 0,
                }
            ]
        },
    )
    calls: list[str] = []

    def fake_verify(review, source, **kwargs):
        calls.append(str(review["title"]))
        return {
            "ok": True,
            "reason": "Fonte diretta verificata.",
            "confirmation_count": 1,
            "official_confirmations": 1,
            "confirmations": [
                {
                    "origin": "fonte_acquisita",
                    "source_name": source["name"],
                    "title": "Questione penale pendente QSP50194",
                    "url": qsp_url,
                    "official": True,
                    "excerpt": "Questione QSP50194 verificata.",
                    "content": "Questione QSP50194 verificata.",
                    "context_chars": 30,
                    "matched_terms": ["qsp50194"],
                    "query": "QSP50194",
                }
            ],
        }

    monkeypatch.setattr("pct.legal_update_pipeline.verify_legal_update_against_public_sources", fake_verify)

    report = pipeline.backfill_web_verification_evidence(limit=10, query="QSP50194")

    assert report["selected"] == 1
    assert report["checked"] == 1
    assert calls == ["Questione penale pendente"]


def test_backfill_cassazione_esclude_pagine_non_documentali_dalla_tranche(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("cassazione_massimario")
    assert source is not None

    def _review_for(*, external_id: str, source_url: str, title: str) -> int:
        raw = pipeline.repository.save_raw_document(
            {
                "source_id": source["id"],
                "external_id": external_id,
                "source_url": source_url,
                "title": title,
                "published_at": "2026-05-18",
                "raw_html": "",
                "raw_text": title,
                "content_hash": f"hash-{external_id}",
                "fetch_status": "fetched",
                "http_status": 200,
            }
        )
        normalized = pipeline.repository.save_normalized_document(
            int(raw["id"]),
            {
                "title": title,
                "body_text": title,
                "body_short": title,
                "language": "it",
                "issuer": "Corte Suprema di Cassazione",
                "document_date": "2026-05-18",
                "document_type_guess": "giurisprudenza",
                "attachments_json": [],
            },
        )
        analysis = pipeline.repository.save_analysis(
            int(normalized["id"]),
            {
                "classification_type": "GIURISPRUDENZA",
                "confidence_score": 0.80,
                "impact_level": "medio",
                "summary_short": title,
                "summary_long": title,
                "what_changes": "",
                "extracted_entities_json": {},
                "proposed_action": "NEWS_ONLY",
                "target_entity_type": "",
                "target_entity_id": None,
            },
        )
        review = pipeline.repository.upsert_review_item(
            {
                "normalized_document_id": int(normalized["id"]),
                "analysis_id": int(analysis["id"]),
                "proposal_type": "commento",
                "proposed_action": "NEWS_ONLY",
                "target_entity_type": "",
                "target_entity_id": None,
                "proposal_payload_json": {},
                "status": "approved",
                "priority": 80,
            }
        )
        return int(review["id"])

    legal_id = _review_for(
        external_id="cassazione-sentenza",
        source_url="https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP50088",
        title="Sentenza n. 14882 ud. 17/03/2026",
    )
    _review_for(
        external_id="cassazione-privacy",
        source_url="https://www.cortedicassazione.it/page/it/privacy_policy?contentId=NTZ00001",
        title="Privacy policy",
    )
    calls: list[str] = []

    def fake_verify(review, source, **kwargs):
        calls.append(str(review["title"]))
        return {
            "ok": True,
            "reason": "Fonte diretta verificata.",
            "confirmation_count": 1,
            "official_confirmations": 1,
            "confirmations": [
                {
                    "origin": "fonte_acquisita",
                    "source_name": source["name"],
                    "title": review["title"],
                    "url": review["source_url"],
                    "official": True,
                    "excerpt": review["title"],
                    "content": review["title"],
                    "context_chars": len(str(review["title"])),
                }
            ],
        }

    monkeypatch.setattr("pct.legal_update_pipeline.verify_legal_update_against_public_sources", fake_verify)

    report = pipeline.backfill_web_verification_evidence(
        limit=10,
        source_codes=["cassazione_massimario"],
        statuses=("approved",),
    )

    assert report["selected"] == 1
    assert report["checked"] == 1
    assert report["items"][0]["review_id"] == legal_id
    assert calls == ["Sentenza n. 14882 ud. 17/03/2026"]


def test_backfill_web_verification_evidence_lavora_solo_record_azionabili(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    actionable_source = pipeline.repository.get_source_by_code("agcom_provvedimenti")
    open_data_source = pipeline.repository.get_source_by_code("openga_sentenze")
    assert actionable_source is not None
    assert open_data_source is not None

    def _review_for(source: dict, *, external_id: str, status: str) -> int:
        raw = pipeline.repository.save_raw_document(
            {
                "source_id": source["id"],
                "external_id": external_id,
                "source_url": f"https://example.invalid/{external_id}",
                "title": f"Documento {external_id}",
                "published_at": "2026-05-17",
                "raw_html": "",
                "raw_text": f"Documento {external_id} da verificare.",
                "content_hash": f"hash-{external_id}",
                "fetch_status": "fetched",
                "http_status": 200,
            }
        )
        normalized = pipeline.repository.save_normalized_document(
            int(raw["id"]),
            {
                "title": f"Documento {external_id}",
                "body_text": f"Documento {external_id} da verificare.",
                "body_short": f"Documento {external_id} da verificare.",
                "language": "it",
                "issuer": str(source.get("name") or ""),
                "document_date": "2026-05-17",
                "document_type_guess": "provvedimento",
                "attachments_json": [],
            },
        )
        analysis = pipeline.repository.save_analysis(
            int(normalized["id"]),
            {
                "classification_type": "COMMENTO",
                "confidence_score": 0.52,
                "impact_level": "medio",
                "summary_short": f"Documento {external_id} da verificare.",
                "summary_long": f"Documento {external_id} da verificare.",
                "what_changes": "",
                "extracted_entities_json": {},
                "proposed_action": "NEWS_ONLY",
                "target_entity_type": "",
                "target_entity_id": None,
            },
        )
        review = pipeline.repository.upsert_review_item(
            {
                "normalized_document_id": int(normalized["id"]),
                "analysis_id": int(analysis["id"]),
                "proposal_type": "commento",
                "proposed_action": "NEWS_ONLY",
                "target_entity_type": "",
                "target_entity_id": None,
                "proposal_payload_json": {},
                "status": status,
                "priority": 80,
            }
        )
        return int(review["id"])

    actionable_review_id = _review_for(actionable_source, external_id="agcom-azionabile", status="pending")
    _review_for(open_data_source, external_id="openga-chiuso", status="closed")
    calls: list[tuple[str, bool]] = []

    def fake_verify(review, source, **kwargs):
        calls.append((str(source["code"]), bool(kwargs.get("direct_only"))))
        return {
            "ok": True,
            "reason": "Fonte diretta verificata.",
            "confirmation_count": 1,
            "official_confirmations": 1,
            "confirmations": [
                {
                    "origin": "fonte_acquisita",
                    "source_name": source["name"],
                    "title": review["title"],
                    "url": review["source_url"],
                    "official": True,
                    "excerpt": "Documento azionabile verificato.",
                    "content": "Documento azionabile verificato.",
                    "context_chars": 31,
                    "matched_terms": ["documento"],
                    "query": review["title"],
                }
            ],
            "searched": {"web_results": 0, "direct_only": True},
        }

    monkeypatch.setattr("pct.legal_update_pipeline.verify_legal_update_against_public_sources", fake_verify)

    report = pipeline.backfill_web_verification_evidence(limit=10, max_seconds=30)

    with pipeline.repository._connect() as conn:
        evidence_rows = conn.execute("SELECT review_id, source_code FROM web_verification_evidence").fetchall()

    assert report["selected"] == 1
    assert report["checked"] == 1
    assert report["direct_only"] is True
    assert calls == [("agcom_provvedimenti", True)]
    assert [(row["review_id"], row["source_code"]) for row in evidence_rows] == [
        (actionable_review_id, "agcom_provvedimenti")
    ]


def test_search_lex_sources_premia_evidenza_web_con_titolo_esatto(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    with pipeline.repository._connect() as conn:
        conn.execute(
            """
            INSERT INTO web_verification_evidence (
                evidence_key, review_id, normalized_document_id, source_code, source_name,
                query, origin, title, source_url, attachment_url, attachment_type, sha256,
                is_official, context_chars, excerpt, content_text, matched_terms_json,
                verification_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "exact-685",
                None,
                None,
                "inps_messaggi",
                "INPS - messaggi",
                "Messaggio numero 685 del 26-02-2026",
                "fonte_acquisita",
                "Messaggio numero 685 del 26-02-2026",
                "https://www.inps.it/messaggio-numero-685-del-26-02-2026.html",
                "https://www.inps.it/messaggio-numero-685-del-26-02-2026.pdf",
                "pdf",
                "hash-685",
                1,
                400,
                "Messaggio INPS numero 685 del 26 febbraio 2026.",
                "Messaggio INPS numero 685 del 26 febbraio 2026.",
                '["messaggio","685"]',
                "verified",
                "2026-02-26 00:00:00",
                "2026-02-26 00:00:00",
            ),
        )
        for index in range(70):
            conn.execute(
                """
                INSERT INTO web_verification_evidence (
                    evidence_key, review_id, normalized_document_id, source_code, source_name,
                    query, origin, title, source_url, attachment_url, attachment_type, sha256,
                    is_official, context_chars, excerpt, content_text, matched_terms_json,
                    verification_status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"distractor-{index}",
                    None,
                    None,
                    "inps_circolari",
                    "INPS - circolari",
                    "Circolare numero 25 del 05-03-2026",
                    "fonte_acquisita",
                    f"Circolare numero {25 + index} del 05-03-2026",
                    f"https://www.inps.it/circolare-numero-{25 + index}-del-05-03-2026.html",
                    "",
                    "",
                    "",
                    1,
                    400,
                    "Circolare INPS del 2026.",
                    "Circolare INPS del 2026.",
                    '["circolare","2026"]',
                    "verified",
                    "2026-05-17 00:00:00",
                    "2026-05-17 00:00:00",
                ),
            )
        conn.commit()

    results = pipeline.repository.search_lex_sources("Messaggio numero 685 del 26-02-2026", limit=5)

    assert results
    assert results[0]["entity_type"] == "web_evidence"
    assert results[0]["title"] == "Messaggio numero 685 del 26-02-2026"
    assert results[0]["attachment_url"] == "https://www.inps.it/messaggio-numero-685-del-26-02-2026.pdf"


def test_search_lex_sources_include_pdf_ocr_riferimenti_e_domande(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    with pipeline.repository._connect() as conn:
        conn.execute(
            """
            INSERT INTO web_verification_evidence (
                evidence_key, review_id, normalized_document_id, source_code, source_name,
                query, origin, title, source_url, attachment_url, attachment_type, sha256,
                is_official, context_chars, excerpt, content_text, matched_terms_json,
                verification_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "cassazione-qsp-pdf-ocr",
                None,
                None,
                "cassazione_ultime_sent_ord_questioni",
                "Corte Suprema di Cassazione",
                "Questione Penale Pendente del ricorso R.G. 9926/2026",
                "allegato_fonte_ufficiale",
                "Questione Penale Pendente del ricorso R.G. 9926/2026",
                "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194",
                "https://www.cortedicassazione.it/resources/cms/documents/qsp50194.pdf",
                "pdf",
                "b" * 64,
                1,
                620,
                "PDF ufficiale collegato alla scheda Cassazione.",
                (
                    "Testo OCR ufficiale della questione penale pendente. "
                    "La scheda indica R.G. 9926/2026, il PDF riporta R.G. 9966/2026. "
                    "Sono richiamati art. 606 c.p.p., art. 599-bis c.p.p. e D.Lgs. 150/2022."
                ),
                '["QSP50194","art. 606 c.p.p.","R.G. 9926/2026"]',
                "verified",
                "2026-05-18 00:00:00",
                "2026-05-18 00:00:00",
            ),
        )
        conn.commit()

    results = pipeline.repository.search_lex_sources("PDF allegato ordinanza art. 606 c.p.p. QSP50194", limit=3)

    assert results
    first = results[0]
    assert first["entity_type"] == "web_evidence"
    assert first["attachment_url"].endswith("qsp50194.pdf")
    assert any(ref["type"] == "article" and ref["official_url"] == "" for ref in first["legal_references"])
    assert "art. 606 c.p.p." in first["norm_references"]
    assert "9926/2026" in first["rg_references"]
    assert "9966/2026" in first["rg_references"]
    assert any(row["check"] == "pdf_allegato" for row in first["contextual_questions"])
    assert any(row["check"] == "articoli" for row in first["contextual_questions"])
    assert any("Riferimenti normativi" in point for point in first["key_points"])
    assert any("Domanda per Lex" in check for check in first["operational_checks"])


def test_search_lex_sources_non_usa_cassazione_per_sentenza_corte_costituzionale(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))

    with pipeline.repository._connect() as conn:
        rows = [
            (
                "cassazione-corte-cost-noise",
                "cassazione",
                "Corte Suprema di Cassazione",
                "Sentenza della Corte Costituzionale n. 50 del 27/1/2026",
                "fonte_acquisita",
                "Sentenza n. 11513 del 28/04/2026",
                "https://www.cortedicassazione.it/it/civile_dettaglio.page?contentId=SZC50131",
                "",
                "",
                "",
                1,
                500,
                "La sentenza di Cassazione richiama Corte Costituzionale e il 2026.",
                "La sentenza di Cassazione richiama Corte Costituzionale, ma non e' la n. 50 del 27/01/2026.",
                '["sentenza","corte","costituzionale","2026"]',
                "verified",
            ),
            (
                "corte-cost-50-2026",
                "corte_costituzionale",
                "Corte Costituzionale",
                "Sentenza della Corte Costituzionale n. 50 del 27/1/2026",
                "fonte_acquisita",
                "Sentenza della Corte Costituzionale n. 50 del 27/1/2026",
                "https://www.cortecostituzionale.it/actionSchedaPronuncia.do?anno=2026&numero=50",
                "",
                "",
                "",
                1,
                1200,
                "Sentenza della Corte Costituzionale n. 50 del 27 gennaio 2026.",
                "Sentenza della Corte Costituzionale n. 50 del 27 gennaio 2026.",
                '["sentenza","50","2026"]',
                "verified",
            ),
        ]
        conn.executemany(
            """
            INSERT INTO web_verification_evidence (
                evidence_key, source_code, source_name, query, origin, title,
                source_url, attachment_url, attachment_type, sha256, is_official,
                context_chars, excerpt, content_text, matched_terms_json,
                verification_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
        conn.commit()

    results = pipeline.repository.search_lex_sources(
        "Sentenza della Corte Costituzionale n. 50 del 27/1/2026",
        limit=5,
    )

    assert results
    assert results[0]["title"] == "Sentenza della Corte Costituzionale n. 50 del 27/1/2026"
    assert results[0]["source_code"] == "corte_costituzionale"
    assert all("cortedicassazione.it" not in str(row.get("official_url")) for row in results)


def test_search_lex_sources_premia_allegato_quando_domanda_chiede_allegato(tmp_path: Path):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    qsp_url = "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194"
    attachment_url = (
        "https://www.cortedicassazione.it/resources/cms/documents/"
        "Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf"
    )

    with pipeline.repository._connect() as conn:
        conn.execute(
            """
            INSERT INTO web_verification_evidence (
                evidence_key, review_id, normalized_document_id, source_code, source_name,
                query, origin, title, source_url, attachment_url, attachment_type, sha256,
                is_official, context_chars, excerpt, content_text, matched_terms_json,
                verification_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "qsp-page",
                None,
                None,
                "cassazione_massimario",
                "Cassazione Massimario",
                "QSP50194",
                "fonte_acquisita",
                "Questione Penale Pendente del ricorso R.G. 9926/2026 ud. 09/07/2026",
                qsp_url,
                "",
                "",
                "",
                1,
                1736,
                "Questione penale pendente R.G. 9926/2026.",
                "Questione penale pendente R.G. 9926/2026.",
                '["qsp50194"]',
                "verified",
                "2026-05-18 00:00:00",
                "2026-05-18 00:00:00",
            ),
        )
        conn.execute(
            """
            INSERT INTO web_verification_evidence (
                evidence_key, review_id, normalized_document_id, source_code, source_name,
                query, origin, title, source_url, attachment_url, attachment_type, sha256,
                is_official, context_chars, excerpt, content_text, matched_terms_json,
                verification_status, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "qsp-attachment",
                None,
                None,
                "cassazione_massimario",
                "Cassazione Massimario",
                "QSP50194",
                "allegato_fonte_ufficiale",
                "Ordinanza di rimessione",
                qsp_url,
                attachment_url,
                "pdf",
                "sha-qsp",
                1,
                45814,
                "Allegato ufficiale della questione penale R.G. 9926/2026.",
                "Allegato ufficiale della questione penale R.G. 9926/2026.",
                '["qsp50194"]',
                "verified",
                "2026-05-18 00:00:00",
                "2026-05-18 00:00:00",
            ),
        )
        conn.commit()

    results = pipeline.repository.search_lex_sources(
        "Quale allegato ufficiale ha la questione penale R.G. 9926/2026?",
        limit=3,
    )

    assert results
    assert results[0]["title"] == "Ordinanza di rimessione"
    assert results[0]["attachment_url"] == attachment_url


def test_publish_auto_news_salva_diagnosi_quando_web_non_trova_conferme(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("agcom_provvedimenti")
    assert source is not None
    raw = pipeline.repository.save_raw_document(
        {
            "source_id": source["id"],
            "external_id": "agcom-15-26-dtc-cp",
            "source_url": "https://www.agcom.it/provvedimenti/determina-15-26-dtc-cp",
            "title": "Determina 15/26/DTC/CP",
            "published_at": "2026-05-15",
            "raw_html": "",
            "raw_text": "Determina AGCOM da completare con fonti ufficiali.",
            "content_hash": "hash-agcom-15-26-dtc-cp",
            "fetch_status": "fetched",
            "http_status": 200,
        }
    )
    normalized = pipeline.repository.save_normalized_document(
        int(raw["id"]),
        {
            "title": "Determina 15/26/DTC/CP",
            "body_text": "Determina AGCOM da completare con fonti ufficiali.",
            "body_short": "Determina AGCOM.",
            "language": "it",
            "issuer": "AGCOM",
            "document_date": "2026-05-15",
            "document_type_guess": "determina",
            "attachments_json": [],
        },
    )
    analysis = pipeline.repository.save_analysis(
        int(normalized["id"]),
        {
            "classification_type": "COMMENTO",
            "confidence_score": 0.56,
            "impact_level": "medio",
            "summary_short": "Determina AGCOM da verificare.",
            "summary_long": "Determina AGCOM da verificare.",
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )
    review = pipeline.repository.upsert_review_item(
        {
            "normalized_document_id": int(normalized["id"]),
            "analysis_id": int(analysis["id"]),
            "proposal_type": "commento",
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
            "proposal_payload_json": {},
            "status": "pending",
            "priority": 95,
        }
    )

    monkeypatch.setattr(
        "pct.legal_update_pipeline.verify_legal_update_against_public_sources",
        lambda review, source, **kwargs: {
            "ok": False,
            "reason": "Nessuna fonte pubblica coerente trovata per la pubblicazione automatica.",
            "confirmation_count": 0,
            "official_confirmations": 0,
            "confirmations": [],
            "warnings": ["AGCOM consultata senza riscontro utile."],
            "searched": {
                "query": "Determina 15/26/DTC/CP",
                "queries": ["Determina 15/26/DTC/CP"],
                "web_results": 0,
                "web_searches": [
                    {"query": "Determina 15/26/DTC/CP", "scope": "estesa", "source_ids": [], "results": 0}
                ],
            },
        },
    )

    report = pipeline.publish_auto_news(limit=1)
    review_after = pipeline.repository.get_review_item(int(review["id"]))
    with pipeline.repository._connect() as conn:
        evidence = conn.execute("SELECT * FROM web_verification_evidence").fetchall()

    assert report["count"] == 0
    assert report["web_verification_attempts"] == 1
    assert report["verification_evidence_saved"] == 1
    assert review_after is not None
    assert review_after["status"] == "pending"
    assert review_after["priority"] == 10
    assert "Verifica fonti insufficiente" in review_after["review_notes"]
    assert len(evidence) == 1
    assert evidence[0]["origin"] == "ricerca_web_senza_conferma"


def test_publish_review_manuale_non_pubblica_testo_povero_senza_contesto(tmp_path: Path, monkeypatch):
    pipeline = build_legal_update_pipeline(str(tmp_path / "intelligence" / "motori.json"))
    source = pipeline.repository.get_source_by_code("gazzetta_ufficiale")
    assert source is not None

    raw = pipeline.repository.save_raw_document(
        {
            "source_id": source["id"],
            "external_id": "manual-dlgs-39-2026",
            "source_url": "https://www.gazzettaufficiale.it/eli/id/2026/03/13/26G00039/sg",
            "title": "D.Lgs. 13 marzo 2026, n. 39",
            "published_at": "2026-03-13",
            "raw_html": "",
            "raw_text": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "content_hash": "hash-manual-dlgs-39-2026",
            "fetch_status": "fetched",
            "http_status": 200,
        }
    )
    normalized = pipeline.repository.save_normalized_document(
        int(raw["id"]),
        {
            "title": "D.Lgs. 13 marzo 2026, n. 39",
            "body_text": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "body_short": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "language": "it",
            "issuer": "Gazzetta Ufficiale",
            "document_date": "2026-03-13",
            "document_type_guess": "decreto legislativo",
            "attachments_json": [],
        },
    )
    analysis = pipeline.repository.save_analysis(
        int(normalized["id"]),
        {
            "classification_type": "COMMENTO",
            "confidence_score": 0.94,
            "impact_level": "medio",
            "summary_short": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "summary_long": "Aggiornamento giuridico pubblicato in fonte ufficiale.",
            "what_changes": "",
            "extracted_entities_json": {},
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
        },
    )
    review = pipeline.repository.upsert_review_item(
        {
            "normalized_document_id": int(normalized["id"]),
            "analysis_id": int(analysis["id"]),
            "proposal_type": "commento",
            "proposed_action": "NEWS_ONLY",
            "target_entity_type": "",
            "target_entity_id": None,
            "proposal_payload_json": {},
            "status": "pending",
            "priority": 90,
        }
    )
    calls: list[tuple[dict, dict]] = []

    def fake_verify(review_payload, source_payload, **kwargs):
        calls.append((review_payload, source_payload))
        return {
            "ok": True,
            "reason": "Verifica pubblica completata.",
            "confirmation_count": 2,
            "official_confirmations": 2,
            "confirmations": [
                {
                    "source_name": "Gazzetta Ufficiale",
                    "official": True,
                    "excerpt": (
                        "Il decreto legislativo 13 marzo 2026, n. 39 recepisce disposizioni "
                        "sulla gestione del rischio di liquidità e sui controlli di vigilanza."
                    ),
                    "context_chars": 190,
                },
                {
                    "source_name": "Fonte istituzionale",
                    "official": True,
                    "excerpt": "La scheda conferma numero, data e ambito del provvedimento.",
                    "context_chars": 110,
                },
            ],
            "searched": {"web_results": 2},
        }

    monkeypatch.setattr("pct.legal_update_pipeline.verify_legal_update_against_public_sources", fake_verify)

    pipeline.publish_review(int(review["id"]), reviewer="admin")
    news = pipeline.repository.list_news(limit=5, include_drafts=False)[0]

    assert calls
    assert calls[0][1]["code"] == "gazzetta_ufficiale"
    assert "Aggiornamento giuridico pubblicato in fonte ufficiale" not in news["short_summary"]
    assert "rischio di liquidità" in news["content"]
    assert "Contesto ufficiale verificato" in news["content"]
