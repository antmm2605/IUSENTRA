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


def test_coda_sql_importa_revisioni_e_preserva_approvazioni(tmp_path):
    import json

    from lex.dataset import review_sql
    from web.services.lex_dataset_review_queue import load_lex_dataset_review_queue, update_lex_dataset_review_item

    directory = tmp_path / "intelligence" / "lex_dataset" / "studio-a"
    directory.mkdir(parents=True)
    db = directory / review_sql.NOME_ARCHIVIO
    db.with_suffix(".json").write_text(json.dumps([
        {"qa_id": "a", "question": "Domanda A", "answer": "Risposta già approvata", "review_status": "approved"},
    ]))
    rows = [
        {"qa_id": "a", "question": "Domanda A", "answer": "Risposta generata"},
        {"qa_id": "b", "question": "Domanda B", "answer": "Risposta B"},
    ]

    review_sql.pubblica(db, rows)
    snapshot = load_lex_dataset_review_queue(data_root=tmp_path)
    assert snapshot["summary"] == {"total": 2, "pending": 1, "approved": 1, "rejected": 0, "files": 1}
    assert [row["id"] for row in snapshot["items"]] == ["b"]

    result = update_lex_dataset_review_item("b", action="approve", answer="Risposta rivista", data_root=tmp_path)
    assert result["updated_item"]["answer"] == "Risposta rivista"
    assert review_sql.leggi(db)[0] == {"approved": 2}
    review_sql.pubblica(db, rows)
    counts, pending = review_sql.leggi(db, limite=12)
    assert counts == {"approved": 2}
    assert pending == []
    assert review_sql.revisiona(db, "a", lambda row: row | {"reviewer_id": "studio", "reviewed_at": "2026-11-12"})[
        "answer"
    ] == "Risposta già approvata"


def test_coda_sql_ricostruisce_contatori_e_preserva_decisioni_storiche(tmp_path):
    import json
    import sqlite3

    from lex.dataset import review_sql

    db = tmp_path / review_sql.NOME_ARCHIVIO
    review_sql.riallinea_contatori(db)
    assert review_sql.leggi(db) == ({}, [])
    db.with_suffix(".json").write_text(json.dumps({"items": [
        None,
        {"id": "a", "status": "approvata"},
        {"id": "b", "status": "scartata"},
    ]}), encoding="utf-8")
    review_sql.pubblica(db, [{"qa_id": "a"}, {"qa_id": "b"}])
    with sqlite3.connect(db) as conn:
        conn.execute("DELETE FROM contatori_coda")
    atteso = {"approved": 1, "rejected": 1}
    assert review_sql.leggi(db) == (atteso, [])
    review_sql.riallinea_contatori(db)
    assert review_sql.leggi(db) == (atteso, [])
    assert review_sql.revisiona(db, "non_esiste", lambda row: row) is None
    assert review_sql.revisiona(db, "a", lambda row: None) is None
    assert review_sql.leggi(db) == (atteso, [])
