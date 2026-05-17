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
