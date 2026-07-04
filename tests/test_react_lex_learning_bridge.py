"""Bridge React della superficie "Apprendimento Lex" (read-only)."""

from __future__ import annotations

from lex.knowledge.knowledge_base import KnowledgeBase
from web.services.react_lex_learning_bridge import build_react_lex_learning_payload


def _prepara_memoria(tmp_path, monkeypatch):
    monkeypatch.setenv("PCT_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("IUSENTRA_DATA_DIR", raising=False)
    kb = KnowledgeBase(tmp_path / "intelligence" / "lex_memory")
    kb.append(
        "improvement_proposals",
        "prop-1",
        {
            "title": "Aggiungere 'accesso civico' all'ontologia",
            "kind": "ontologia",
            "description": "Concetto ricorrente senza voce di ontologia.",
            "target_module": "lex/knowledge/legal_ontology.py",
            "confidence": 0.7,
            "requires_human_review": True,
        },
    )
    kb.append(
        "source_readings",
        "read-1",
        {
            "title": "Cassazione — dettaglio sentenza",
            "url": "https://www.cortedicassazione.it/it/civile_dettaglio.page?contentId=SZC51228",
            "status": "ok",
            "area": "civile",
            "source_id": "semina",
            "text_characters": 3955,
            "citations_normalized": ["art. 2043 c.c."],
            "fetched_at": "2026-07-04T12:41:00+00:00",
        },
    )
    return kb


def test_payload_completo_con_memoria_e_stato_job(tmp_path, monkeypatch):
    _prepara_memoria(tmp_path, monkeypatch)
    payload = build_react_lex_learning_payload({})
    assert payload["ok"] is True
    assert payload["memoria_presente"] is True
    assert payload["conteggi"]["improvement_proposals"] == 1
    assert payload["proposte"][0]["revisione_umana"] is True
    assert payload["letture"][0]["citazioni"] == 1
    job = payload["job_notturno"]
    assert job["job_id"] == "lex_autonomous_learning_nightly"
    assert job["console"] == "/admin/pianificazioni"
    # Il template nasce disabilitato: la superficie non deve mai mostrarlo attivo di default.
    assert job["abilitato"] is False


def test_payload_onesto_senza_memoria(tmp_path, monkeypatch):
    monkeypatch.setenv("PCT_DATA_ROOT", str(tmp_path))
    monkeypatch.delenv("IUSENTRA_DATA_DIR", raising=False)
    payload = build_react_lex_learning_payload({})
    assert payload["ok"] is True
    assert payload["memoria_presente"] is False
    assert payload["proposte"] == [] and payload["letture"] == []
    assert not (tmp_path / "intelligence" / "lex_memory").exists()  # mai creata dalla superficie
