from __future__ import annotations

import socket

import pytest

from lex.legal_sources import (
    AnswerPolicy,
    LegalAnswerDraft,
    LegalCitation,
    LegalSourceEngineSettings,
    LegalSourceTools,
    NetworkDisabledError,
    RetrievedLegalPassage,
    create_default_registry,
    run_dogfood_scenarios,
)
from lex.legal_sources.populate import activate_local_engine, populate_local_engine
from lex.legal_sources.reports import dogfood_report, source_registry_report
from lex.legal_sources.retriever import LegalSourceRetriever


def _citation(**overrides) -> LegalCitation:
    values = {
        "source_id": "normattiva",
        "source_name": "Normattiva",
        "source_category": "primary_legislation",
        "jurisdiction": "IT",
        "document_type": "legge",
        "authority": "Normattiva",
        "title": "Atto fixture non reale",
        "number": "FIX-1",
        "date": "2026-01-01",
        "version_date": "2026-01-01",
        "url": "fixture://normattiva/atto",
        "retrieved_at": "2026-05-15T00:00:00+02:00",
    }
    values.update(overrides)
    return LegalCitation(**values)


def _passage(**citation_overrides) -> RetrievedLegalPassage:
    return RetrievedLegalPassage(
        text="Passaggio fixture non reale, usato solo per policy e citazioni.",
        citation=_citation(**citation_overrides),
        score=0.8,
        retrieval_method="fixture",
        source_priority=100,
    )


def test_registry_registers_all_sources_disabled_by_default():
    registry = create_default_registry(env={})

    assert len(registry.all_sources()) == 15
    assert registry.enabled_sources() == []
    assert registry.network_allowed() is False
    assert all(source.metadata.enabled_by_default is False for source in registry.all_sources())
    assert all(source.metadata.network_allowed_by_default is False for source in registry.all_sources())
    assert registry.validate().allowed is True


def test_source_opt_in_requires_global_enable_flag():
    registry = create_default_registry(env={"IUSENTRA_SOURCE_NORMATTIVA_ENABLED": "true"})

    assert registry.enabled_sources() == []

    enabled = create_default_registry(
        env={
            "IUSENTRA_LEX_AI_LEGAL_SOURCES_ENABLED": "true",
            "IUSENTRA_SOURCE_NORMATTIVA_ENABLED": "true",
        }
    )

    assert [source.metadata.source_id for source in enabled.enabled_sources()] == ["normattiva"]


def test_source_contract_does_not_fetch_when_network_disabled(monkeypatch):
    def fail_socket(*args, **kwargs):  # pragma: no cover - called only on regression
        raise AssertionError("network access is forbidden in unit tests")

    monkeypatch.setattr(socket, "socket", fail_socket)
    source = create_default_registry(env={}).get("normattiva")

    assert source is not None
    assert source.search("articolo fixture") == []
    with pytest.raises(NetworkDisabledError):
        source.fetch("urn:nir:fixture")


def test_answer_policy_accepts_grounded_draft_with_citation():
    passage = _passage()
    draft = LegalAnswerDraft(
        question="Spiega il passaggio fixture.",
        answer="La risposta e' fondata sul passaggio fixture citato.",
        passages=[passage],
        citations=[passage.citation],
        confidence=0.8,
    )

    result = AnswerPolicy().validate(draft)

    assert result.allowed is True
    assert result.errors == []


def test_answer_policy_rejects_without_passages_or_citations():
    draft = LegalAnswerDraft(
        question="Rispondi senza fonti.",
        answer="Risposta non fondata.",
        passages=[],
        citations=[],
        confidence=0.9,
    )

    result = AnswerPolicy().validate(draft)

    assert result.allowed is False
    assert [error.code for error in result.errors] == ["missing_retrieved_passages"]


def test_answer_policy_requires_version_date_for_current_law():
    passage = _passage(version_date="")
    draft = LegalAnswerDraft(
        question="Qual e' il diritto vigente secondo la fonte fixture?",
        answer="Risposta con fonte ma senza versione.",
        passages=[passage],
        citations=[passage.citation],
        confidence=0.7,
    )

    result = AnswerPolicy().validate(draft)

    assert result.allowed is False
    assert "version_date_required" in {error.code for error in result.errors}


def test_answer_policy_marks_authority_practice_as_not_binding():
    passage = _passage(
        source_id="agenzia_entrate",
        source_name="Agenzia delle Entrate",
        source_category="tax_practice",
        document_type="interpello",
        title="Risposta fixture non reale",
        url="fixture://agenzia-entrate/interpello",
    )
    draft = LegalAnswerDraft(
        question="Questa prassi vale come legge?",
        answer="Non risulta diritto vincolante: e' prassi di autorita.",
        passages=[passage],
        citations=[passage.citation],
        confidence=0.65,
    )

    result = AnswerPolicy().validate(draft)

    assert result.allowed is True
    assert "non_binding_authority_practice" in {warning.code for warning in result.warnings}


def test_safe_retriever_and_tools_refuse_without_local_index(tmp_path):
    settings = LegalSourceEngineSettings(
        data_dir=tmp_path / "data",
        index_dir=tmp_path / "empty-index",
        artifact_dir=tmp_path / "artifacts",
        runtime_config_path=tmp_path / "data" / "runtime_config.json",
    )
    retriever = LegalSourceRetriever(settings=settings)
    tools = LegalSourceTools(retriever=retriever)

    assert retriever.combined_search("articolo fixture") == []
    result = tools.explain_with_sources("Spiega una norma senza fonti")

    assert result.ok is False
    assert result.refusal["reason"] == "insufficient_sources"


def test_auto_populate_creates_local_index_without_network(tmp_path, monkeypatch):
    def fail_socket(*args, **kwargs):  # pragma: no cover - called only on regression
        raise AssertionError("network access is forbidden during local population")

    monkeypatch.setattr(socket, "socket", fail_socket)
    settings = LegalSourceEngineSettings(
        enabled=True,
        allow_network=False,
        auto_populate=True,
        populate_on_startup=True,
        data_dir=tmp_path / "data",
        index_dir=tmp_path / "indexes",
        artifact_dir=tmp_path / "artifacts",
        enabled_source_ids=("normattiva", "gazzetta_ufficiale"),
        runtime_config_path=tmp_path / "data" / "runtime_config.json",
    )

    result = populate_local_engine(settings=settings, force=True)

    assert result.ok is True
    assert result.populated is True
    assert result.network_used is False
    assert result.passages_written == 2
    assert (tmp_path / "indexes" / "passages.jsonl").exists()
    assert (tmp_path / "artifacts" / "reports" / "auto_populate_report.json").exists()


def test_retriever_and_tools_use_populated_local_index(tmp_path):
    settings = LegalSourceEngineSettings(
        enabled=True,
        allow_network=False,
        auto_populate=True,
        populate_on_startup=True,
        data_dir=tmp_path / "data",
        index_dir=tmp_path / "indexes",
        artifact_dir=tmp_path / "artifacts",
        enabled_source_ids=("normattiva",),
        runtime_config_path=tmp_path / "data" / "runtime_config.json",
    )
    populate_local_engine(settings=settings, force=True)
    retriever = LegalSourceRetriever(settings=settings, auto_populate=False)
    tools = LegalSourceTools(retriever=retriever)

    rows = retriever.exact_lookup("source:normattiva")
    result = tools.explain_with_sources("Quali capacita ha Normattiva?")

    assert rows
    assert rows[0].has_valid_citation()
    assert result.ok is True
    assert result.data["citations"][0]["source_id"] == "normattiva"


def test_activation_writes_ignored_runtime_config_and_populates(tmp_path):
    settings = LegalSourceEngineSettings(
        data_dir=tmp_path / "data",
        index_dir=tmp_path / "indexes",
        artifact_dir=tmp_path / "artifacts",
        runtime_config_path=tmp_path / "data" / "runtime_config.json",
    )

    result = activate_local_engine(source_ids=["normattiva"], settings=settings, populate=True, force=True)

    assert result.ok is True
    assert result.activated is True
    assert result.populated is True
    assert result.runtime_config_path.endswith("runtime_config.json")
    assert (tmp_path / "data" / "runtime_config.json").exists()


def test_dogfood_scenarios_all_pass_without_network(monkeypatch):
    def fail_socket(*args, **kwargs):  # pragma: no cover - called only on regression
        raise AssertionError("network access is forbidden in dogfood")

    monkeypatch.setattr(socket, "socket", fail_socket)

    results = run_dogfood_scenarios()

    assert results
    assert all(result.passed for result in results)


def test_reports_are_structured_and_safe():
    registry = source_registry_report(create_default_registry(env={}))
    dogfood = dogfood_report()

    assert registry["legal_sources_enabled"] is False
    assert registry["network_allowed"] is False
    assert dogfood["network_used"] is False
    assert dogfood["customer_data_used"] is False
    assert dogfood["passed"] is True
