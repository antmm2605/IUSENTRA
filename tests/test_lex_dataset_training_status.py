from __future__ import annotations

import json

from web.services.lex_dataset_training_status import build_lex_dataset_training_status


def test_lex_dataset_training_status_distingue_rag_review_export_e_job(tmp_path):
    dataset_dir = tmp_path / "intelligence" / "lex_dataset"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "pipeline.json").write_text(
        json.dumps(
            {
                "manifest": {"documents": [{"document_id": "doc-1"}]},
                "chunks": [{"chunk_id": "chunk-1"}, {"chunk_id": "chunk-2"}],
                "qa_pairs": [
                    {"qa_id": "qa-1", "review_status": "pending_human_review"},
                    {"qa_id": "qa-2", "review_status": "approved"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dataset_dir / "iusentra_lex_alpaca.jsonl").write_text('{"instruction":"Domanda","output":"Risposta"}\n', encoding="utf-8")
    (dataset_dir / "iusentra_lex_sharegpt.jsonl").write_text('{"conversations":[]}\n{"conversations":[]}\n', encoding="utf-8")
    (dataset_dir / "jobs.json").write_text(
        json.dumps(
            {
                "jobs": [
                    {
                        "status": "completed",
                        "updated_at": "2026-05-17T12:30:00Z",
                        "message": "Preparazione completata.",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (dataset_dir / "errors.json").write_text(
        json.dumps({"errors": [{"message": "Documento da rileggere."}]}, ensure_ascii=False),
        encoding="utf-8",
    )

    payload = build_lex_dataset_training_status(data_root=tmp_path, ai_enabled=True)
    cards = {card["id"]: card for card in payload["cards"]}

    assert payload["ok"] is True
    assert payload["storage_label"] == "Archivio riservato dello studio"
    assert payload["privacy"]["automatic_training"] is False
    assert payload["privacy"]["external_transfer"] is False
    assert cards["rag"]["label"] == "Contesto documenti"
    assert "non serve riaddestrare il modello" in cards["rag"]["note"]
    assert cards["rag"]["status"] == "Pronto"
    assert cards["qa_review"]["label"] == "Domande in revisione"
    assert cards["qa_review"]["status"] == "Da revisionare"
    assert cards["manual_training"]["label"] == "Modello locale"
    assert cards["alpaca"]["value"] == 1
    assert cards["sharegpt"]["value"] == 2
    assert cards["manual_training"]["status"] == "Percorso manuale"
    assert cards["latest_job"]["status"] == "Completato"
    assert cards["errors"]["status"] == "Da verificare"


def test_lex_dataset_training_status_senza_artefatti_resta_neutro(tmp_path):
    payload = build_lex_dataset_training_status(data_root=tmp_path, ai_enabled=False, auto_index_documents=False)
    cards = {card["id"]: card for card in payload["cards"]}

    assert cards["rag"]["status"] == "Da preparare"
    assert cards["qa_review"]["status"] == "Nessuna coda"
    assert cards["alpaca"]["status"] == "Non esportato"
    assert cards["sharegpt"]["status"] == "Non esportato"
    assert cards["latest_job"]["status"] == "Nessun lavoro"
    assert cards["errors"]["status"] == "Nessun errore"
