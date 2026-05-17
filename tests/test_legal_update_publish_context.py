from __future__ import annotations

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
