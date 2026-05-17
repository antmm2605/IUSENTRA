import json
from pathlib import Path

from web.services.lex_dataset_review_queue import (
    load_lex_dataset_review_queue,
    update_lex_dataset_review_item,
)


def _write_queue(root: Path) -> Path:
    queue = root / "intelligence" / "lex_dataset" / "tenant-a" / "qa_review_queue.json"
    queue.parent.mkdir(parents=True, exist_ok=True)
    queue.write_text(
        json.dumps(
            [
                {
                    "qa_id": "qa-1",
                    "question": "Quale informazione risulta?",
                    "answer": "Testo @@@db.fascicolo.nome@@@ da controllare.",
                    "tenant_id": "tenant-a",
                    "document_id": "doc-1",
                    "source": {
                        "title": "memoria.pdf",
                        "fascicolo_id": "FAS-1",
                        "page_start": 2,
                        "page_end": 2,
                    },
                    "review_status": "pending_human_review",
                    "requires_human_review": True,
                    "privacy_classification": "sensitive",
                },
                {
                    "qa_id": "qa-2",
                    "question": "Domanda gia approvata?",
                    "answer": "Risposta gia approvata.",
                    "tenant_id": "tenant-a",
                    "document_id": "doc-2",
                    "source": {"title": "contratto.pdf"},
                    "review_status": "approved",
                    "requires_human_review": False,
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return queue


def test_lex_dataset_review_queue_legge_domande_candidate_senza_training(tmp_path):
    _write_queue(tmp_path)

    payload = load_lex_dataset_review_queue(data_root=tmp_path)

    assert payload["ok"] is True
    assert payload["automatic_training"] is False
    assert payload["external_transfer"] is False
    assert payload["summary"]["total"] == 2
    assert payload["summary"]["pending"] == 1
    assert payload["summary"]["approved"] == 1
    assert payload["items"][0]["id"] == "qa-1"
    assert payload["items"][0]["sourceTitle"] == "memoria.pdf"
    assert "@@@db" not in payload["items"][0]["answer"]


def test_lex_dataset_review_queue_approva_e_persiste_modifiche(tmp_path):
    queue = _write_queue(tmp_path)

    payload = update_lex_dataset_review_item(
        "qa-1",
        action="approve",
        question="Quale fatto operativo va ricordato?",
        answer="Va ricordato il fatto verificato nel documento.",
        note="Controllata dallo studio.",
        reviewer_id="avv-1",
        data_root=tmp_path,
    )

    rows = json.loads(queue.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["automatic_training"] is False
    assert rows[0]["review_status"] == "approved"
    assert rows[0]["requires_human_review"] is False
    assert rows[0]["question"] == "Quale fatto operativo va ricordato?"
    assert rows[0]["answer"] == "Va ricordato il fatto verificato nel documento."
    assert rows[0]["reviewer_id"] == "avv-1"
    assert (queue.parent / "review_events.jsonl").exists()


def test_lex_dataset_review_queue_scarto_non_crea_export_training(tmp_path):
    queue = _write_queue(tmp_path)

    payload = update_lex_dataset_review_item(
        "qa-1",
        action="reject",
        note="Risposta non utile.",
        reviewer_id="avv-1",
        data_root=tmp_path,
    )

    rows = json.loads(queue.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert rows[0]["review_status"] == "rejected"
    assert rows[0]["requires_human_review"] is True
    assert not (queue.parent / "alpaca.jsonl").exists()
