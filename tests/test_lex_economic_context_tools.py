from __future__ import annotations

import pytest

from lex.tools import economic_context_tools as tools
from pct.sentenza_economic_repository import SentenzaEconomicRepository


@pytest.fixture
def repo_path(tmp_path):
    path = tmp_path / "se.db"
    repo = SentenzaEconomicRepository(path)
    repo.save_sentenza_audit(
        "studio-a", fascicolo_id="F1", safe_to_attach=True, human_review_required=False, status="verified",
        audit={"match": {"rg_match": True}, "sentenza": {"spese_liquidate": {"beneficiario_credito": "avvocato"}}},
    )
    repo.save_sentenza_audit(
        "studio-a", fascicolo_id="F2", safe_to_attach=False, human_review_required=True, status="needs_reconciliation",
        audit={"match": {"rg_match": False}, "sentenza": {"spese_liquidate": {"beneficiario_credito": "incerto"}}},
    )
    repo.add_economic_event(
        "studio-a", fascicolo_id="F1", event_type="apri_credito_avvocato_antistatario", amount=4200.0, status="to_review",
    )
    return str(path)


def test_tool_disabilitato_quando_flag_off(monkeypatch, repo_path):
    monkeypatch.setattr(tools, "_flag_enabled", lambda: False)
    result = tools.get_fascicolo_economic_context("F1", tenant_id="studio-a", db_path=repo_path)
    assert result["ok"] is False
    assert result["code"] == "feature_disabled"


def test_contesto_economico_quando_abilitato(monkeypatch, repo_path):
    monkeypatch.setattr(tools, "_flag_enabled", lambda: True)
    result = tools.get_fascicolo_economic_context("F1", tenant_id="studio-a", db_path=repo_path)
    assert result["ok"] is True
    assert result["totals"]["crediti_avvocato_antistatario"] == 4200.0
    # isolamento tenant
    altro = tools.get_fascicolo_economic_context("F1", tenant_id="studio-b", db_path=repo_path)
    assert altro["totals"]["sentenze_lette"] == 0


def test_astensione_su_rg_non_combaciante(monkeypatch, repo_path):
    monkeypatch.setattr(tools, "_flag_enabled", lambda: True)
    repo = SentenzaEconomicRepository(repo_path)
    audit_mismatch = repo.list_sentenza_audits("studio-a", fascicolo_id="F2")[0]
    result = tools.explain_spese_liquidate(audit_mismatch["id"], tenant_id="studio-a", db_path=repo_path)
    assert result["ok"] is False
    assert result["abstain"] is True


def test_spiegazione_credito_avvocato_art93(monkeypatch, repo_path):
    monkeypatch.setattr(tools, "_flag_enabled", lambda: True)
    repo = SentenzaEconomicRepository(repo_path)
    audit_ok = repo.list_sentenza_audits("studio-a", fascicolo_id="F1")[0]
    result = tools.explain_spese_liquidate(audit_ok["id"], tenant_id="studio-a", db_path=repo_path)
    assert result["ok"] is True
    assert result["beneficiario_credito"] == "avvocato"
    assert "art. 93" in result["spiegazione"]


def test_dispatch_sconosciuto():
    assert tools.dispatch_tool("inesistente")["code"] == "unknown_tool"
