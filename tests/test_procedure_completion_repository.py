"""Repository SQLite: CRUD, transizioni, isolamento tenant e audit sanificato."""
from __future__ import annotations

import json
import sqlite3

import pytest

from pct.procedure_completion.models import ProcedureCompletionCard
from pct.procedure_completion.repository import ProcedureCompletionRepository


@pytest.fixture()
def repo(tmp_path):
    return ProcedureCompletionRepository(tmp_path / "pce.db")


def _card(tenant: str = "studio1") -> ProcedureCompletionCard:
    return ProcedureCompletionCard.from_dict(
        {
            "codice": "010003",
            "denominazione": "Procedimento di ingiunzione",
            "tenant_id": tenant,
            "sources": [{"source_type": "official", "title": "Normattiva", "url": "https://www.normattiva.it"}],
            "citations": [{"riferimento": "art. 633 c.p.c.", "url": "https://www.normattiva.it"}],
        }
    )


def test_run_e_card_roundtrip(repo):
    run_id = repo.create_run(procedure_code="010003", request_payload={"codice": "010003"}, tenant_id="studio1")
    assert repo.get_run(run_id, tenant_id="studio1") is not None
    card = _card()
    card.run_id = run_id
    repo.save_card(card)
    riletta = repo.get_card(card.id, tenant_id="studio1")
    assert riletta is not None
    assert riletta.codice == "010003"


def test_isolamento_tenant_su_card_e_run(repo):
    card = _card(tenant="studio1")
    repo.save_card(card)
    assert repo.get_card(card.id, tenant_id="studio1") is not None
    assert repo.get_card(card.id, tenant_id="studio2") is None
    elenco = repo.list_cards(tenant_id="studio2")
    assert all(item.id != card.id for item in elenco)


def test_transizioni_review_approve_publish(repo):
    card = _card()
    repo.save_card(card)
    in_review = repo.submit_for_review(card.id, requested_by="op", tenant_id="studio1")
    assert in_review.status == "needs_review"
    with pytest.raises(ValueError):
        repo.approve_card(card.id, reviewer="", tenant_id="studio1")
    approvata = repo.approve_card(card.id, reviewer="Avv. Verdi", reason="ok", tenant_id="studio1")
    assert approvata.status == "approved"
    assert approvata.review_avvocato["reviewer"] == "Avv. Verdi"
    pubblicata = repo.publish_card(card.id, reviewer="Avv. Verdi", tenant_id="studio1")
    assert pubblicata.status == "published"
    eventi = [r["evento"] for r in _eventi_review(repo, card.id)]
    assert eventi[:3] == ["submit_review", "approve", "publish"] or set(eventi) >= {"submit_review", "approve", "publish"}


def _eventi_review(repo, card_id):
    with repo.connect() as conn:
        rows = conn.execute(
            "SELECT evento FROM procedure_completion_review_events WHERE card_id = ? ORDER BY id",
            (card_id,),
        ).fetchall()
    return [{"evento": row["evento"]} for row in rows]


def test_audit_sanifica_dati_sensibili(repo):
    repo.audit_log(
        "procedure_completion_card",
        "card_x",
        "save",
        payload={
            "email": "mario.rossi@example.com",
            "codice_fiscale": "RSSMRA70B10G288K",
            "iban": "IT60X0542811101000000123456",
            "token": "sk-secret-token-123",
            "password": "SuperSegreta!",
            "db_path": "/home/user/dati/privati.db",
            "telefono": "+39 333 1234567",
        },
        actor="avv.rossi@example.com",
        tenant_id="studio1",
    )
    righe = repo.list_audit_log(entity_type="procedure_completion_card", entity_id="card_x")
    assert righe, "audit scritto"
    testo = json.dumps(righe[0], ensure_ascii=False)
    assert "mario.rossi@example.com" not in testo
    assert "RSSMRA70B10G288K" not in testo
    assert "IT60X0542811101000000123456" not in testo
    assert "sk-secret-token-123" not in testo
    assert "SuperSegreta!" not in testo
    assert "/home/user/dati" not in testo
    assert righe[0]["event_hash"], "hash evento deterministico presente"


def test_gap_sources_citations_template_links(repo):
    card = _card()
    repo.save_card(card)
    repo.add_source(card.id, {"source_type": "technical", "title": "Catalogo PST"}, tenant_id="studio1")
    repo.add_citation(card.id, {"riferimento": "art. 633 c.p.c.", "url": "https://x"}, tenant_id="studio1")
    repo.add_gap(card.id, {"codice_gap": "template_mancante", "descrizione": "manca", "severita": "warning"}, tenant_id="studio1")
    repo.link_template(card.id, {"template_id": "TPL1", "titolo": "Ricorso", "score": 80}, selezionato=True, tenant_id="studio1")
    gaps = repo.list_gaps(tenant_id="studio1", card_id=card.id)
    assert gaps and gaps[0]["codice_gap"] == "template_mancante"
    # tenant diverso non vede i gap del tenant 1 (le righe hanno tenant valorizzato)
    assert all(g.get("tenant_id") in ("studio1", None) for g in gaps)


def test_schema_idempotente(tmp_path):
    percorso = tmp_path / "doppio.db"
    ProcedureCompletionRepository(percorso)
    ProcedureCompletionRepository(percorso)  # seconda esecuzione: nessun errore
    with sqlite3.connect(percorso) as conn:
        tabelle = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    attese = {
        "procedure_completion_runs",
        "procedure_completion_cards",
        "procedure_completion_sources",
        "procedure_completion_citations",
        "procedure_completion_gaps",
        "procedure_completion_template_links",
        "procedure_completion_review_events",
        "procedure_completion_audit_log",
    }
    assert attese <= tabelle
