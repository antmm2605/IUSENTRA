"""Tool Lex del Procedure Completion: registry governato, niente raw chat, niente rete."""
from __future__ import annotations

import pytest

from lex.tools.registry import LexToolRegistry
from pct.procedure_completion.repository import ProcedureCompletionRepository
from pct.procedure_completion.service import ProcedureCompletionService

PERMESSI = [
    "procedure_completion.leggi",
    "procedure_completion.esegui",
    "procedure_completion.approva",
    "procedure_completion.pubblica",
]


@pytest.fixture()
def registry():
    return LexToolRegistry()


@pytest.fixture()
def service(tmp_path):
    # Service in-memory su SQLite temporaneo: nessuna rete, nessun LLM.
    return ProcedureCompletionService(ProcedureCompletionRepository(tmp_path / "pce.db"))


def _kwargs(service):
    return {
        "service": service,
        "tenant_id": "studio1",
        "user_id": "avv.verdi",
        "user_permissions": PERMESSI,
    }


def test_tool_registrati_con_descrittori_governati(registry):
    attesi = {
        "procedure_completion_preview",
        "procedure_completion_search",
        "procedure_completion_explain_article",
        "procedure_completion_suggest_template",
        "procedure_completion_list_gaps",
    }
    assert attesi <= set(registry.tools)
    for nome in attesi:
        descrittore = registry.descriptor(nome)
        assert descrittore is not None
        assert descrittore.transport == "in_process", "nessuna chat raw, solo tool in-process"
        assert descrittore.allowed_in_free_web is False
        assert descrittore.mutates_state is False


def test_validate_tool_call_rispetta_rbac(registry):
    negato = registry.validate_tool_call("procedure_completion_preview", user_permissions=["fascicoli.leggi"])
    assert negato["allowed"] is False
    concesso = registry.validate_tool_call(
        "procedure_completion_preview", user_permissions=["procedure_completion.esegui"]
    )
    assert concesso["allowed"] is True


def test_preview_tool_restituisce_contratto_governato(registry, service):
    esito = registry.tools["procedure_completion_preview"].run(
        codice="010003",
        denominazione="Procedimento di ingiunzione ante causam",
        **_kwargs(service),
    )
    assert esito["ok"] is True
    for chiave in ("official_sources", "citations", "compared_sources", "coverage_gaps", "confidence", "answer_mode", "needs_review", "next_actions"):
        assert chiave in esito, chiave
    assert esito["needs_review"] is True
    assert esito["citations"], "nessuna risposta giuridica senza citazioni"
    assert esito["answer_mode"] == "needs_review"


def test_preview_tool_512075_needs_review_con_next_actions(registry, service):
    esito = registry.tools["procedure_completion_preview"].run(
        codice="512075",
        denominazione="Accordo di ristrutturazione dei debiti (artt. 57-64 D.Lgs. 14/2019 CCII)",
        **_kwargs(service),
    )
    assert esito["ok"] is True
    assert esito["needs_review"] is True
    assert any("catalogo" in gap.lower() for gap in esito["coverage_gaps"])
    assert esito["next_actions"], "fonti insufficienti: il tool propone azioni, non inventa"


def test_explain_article_non_risponde_senza_citazioni(registry, service):
    card = service.preview_completion(
        {"codice": "010003", "denominazione": "Procedimento di ingiunzione"},
        {"tenant_id": "studio1", "user_id": "avv", "permissions": set(PERMESSI)},
    )["card"]
    fuori_scheda = registry.tools["procedure_completion_explain_article"].run(
        card_id=card["id"], article_ref="art. 2043 c.c.", **_kwargs(service)
    )
    assert fuori_scheda["ok"] is False
    assert fuori_scheda["needs_review"] is True
    assert fuori_scheda["next_actions"]
    in_scheda = registry.tools["procedure_completion_explain_article"].run(
        card_id=card["id"], article_ref="art. 633 c.p.c.", **_kwargs(service)
    )
    assert in_scheda["ok"] is True
    assert in_scheda["citations"]


def test_search_e_list_gaps_tool(registry, service):
    service.preview_completion(
        {"codice": "010003", "denominazione": "Procedimento di ingiunzione"},
        {"tenant_id": "studio1", "user_id": "avv", "permissions": set(PERMESSI)},
    )
    ricerca = registry.tools["procedure_completion_search"].run(query="ingiunzione", **_kwargs(service))
    assert ricerca["ok"] is True
    assert ricerca["cards"]
    gap_queue = registry.tools["procedure_completion_list_gaps"].run(**_kwargs(service))
    assert gap_queue["ok"] is True
    assert "coverage_gaps" in gap_queue


def test_feature_flag_spento_disattiva_i_tool(registry, service, monkeypatch):
    monkeypatch.setenv("IUSENTRA_FF_LEX_PROCEDURECOMPLETION_ENABLED", "0")
    esito = registry.tools["procedure_completion_preview"].run(codice="010003", denominazione="Test procedura", **_kwargs(service))
    assert esito["ok"] is False
    assert esito["reason"] == "feature_flag_disabled"
