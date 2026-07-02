from __future__ import annotations

import json

import pytest

from lex.knowledge.knowledge_base import COLLECTIONS, KnowledgeBase


def test_append_load_dedup_su_disco(tmp_path):
    kb = KnowledgeBase(tmp_path, iso_now=lambda: "2026-07-02T10:00:00+00:00")
    assert kb.append("legal_terms", "abc123", {"normalized": "danno ingiusto"}) is True
    assert kb.append("legal_terms", "abc123", {"normalized": "danno ingiusto"}) is False
    records = kb.load("legal_terms")
    assert len(records) == 1
    assert records[0]["schema_version"] == "iusentra.lex_learning.legal_terms.v1"
    assert records[0]["record_id"] == "abc123"
    assert records[0]["created_at"] == "2026-07-02T10:00:00+00:00"
    assert records[0]["payload"]["normalized"] == "danno ingiusto"


def test_dedup_sopravvive_al_reload(tmp_path):
    KnowledgeBase(tmp_path).append("citations", "id1", {"x": 1})
    kb = KnowledgeBase(tmp_path)
    assert kb.append("citations", "id1", {"x": 1}) is False
    assert kb.known_ids("citations") == {"id1"}


def test_righe_malformate_saltate(tmp_path):
    kb = KnowledgeBase(tmp_path)
    kb.append("citations", "ok", {"x": 1})
    path = kb.path_for("citations")
    path.write_text(path.read_text(encoding="utf-8") + "non-json\n", encoding="utf-8")
    assert [record["record_id"] for record in KnowledgeBase(tmp_path).load("citations")] == ["ok"]


def test_snapshot_counts_e_summary(tmp_path):
    kb = KnowledgeBase(tmp_path)
    kb.append("legal_terms", "a", {})
    kb.append("research_questions", "b", {})
    counts = kb.snapshot_counts()
    assert set(counts) == set(COLLECTIONS)
    assert counts["legal_terms"] == 1
    assert kb.summarize()["total_records"] == 2


def test_read_only_non_scrive_ma_deduplica(tmp_path):
    kb = KnowledgeBase(tmp_path, read_only=True)
    assert kb.append("legal_terms", "dry", {"x": 1}) is True
    assert kb.append("legal_terms", "dry", {"x": 1}) is False
    assert not kb.path_for("legal_terms").exists()
    assert list(tmp_path.iterdir()) == []


def test_collezione_sconosciuta_rifiutata(tmp_path):
    kb = KnowledgeBase(tmp_path)
    with pytest.raises(ValueError):
        kb.append("collezione_inventata", "x", {})
    with pytest.raises(ValueError):
        kb.append("legal_terms", "", {})


def test_record_json_leggibile_a_mano(tmp_path):
    kb = KnowledgeBase(tmp_path)
    kb.append("improvement_proposals", "p1", {"title": "Proposta"})
    line = kb.path_for("improvement_proposals").read_text(encoding="utf-8").splitlines()[0]
    assert json.loads(line)["payload"]["title"] == "Proposta"
