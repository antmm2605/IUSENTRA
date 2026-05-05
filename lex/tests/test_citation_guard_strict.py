from __future__ import annotations

from lex.contracts import EvidenceItem, LexRequest, ProviderDraft
from lex.guards.citation_guard import CitationGuard


def _request(**kwargs) -> LexRequest:
    return LexRequest(
        tenant_id="tenant",
        user_id="utente",
        session_id="sess",
        query="test",
        **kwargs,
    )


def test_normativa_senza_evidenze_blocca():
    verdict = CitationGuard().check(
        request=_request(),
        workflow="normativa",
        evidence={"items": [], "citations": []},
        draft=ProviderDraft(text="bozza"),
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"


def test_giurisprudenza_senza_evidenze_blocca():
    verdict = CitationGuard().check(
        request=_request(),
        workflow="giurisprudenza",
        evidence={"items": [], "citations": []},
        draft=ProviderDraft(text="bozza"),
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"


def test_economico_senza_evidenze_non_blocca_ma_degrada():
    verdict = CitationGuard().check(
        request=_request(),
        workflow="economico",
        evidence={"items": [], "citations": []},
        draft=ProviderDraft(text="bozza"),
    )

    assert verdict.allowed is True
    assert verdict.risk_level == "medium"
    assert verdict.warnings


def test_require_citations_senza_evidence_item_blocca():
    verdict = CitationGuard().check(
        request=_request(require_citations=True),
        workflow="chat",
        evidence={"items": [], "citations": ["Fonte test"]},
        draft=ProviderDraft(text="bozza"),
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"


def test_strict_con_evidenza_senza_citazione_degrada():
    verdict = CitationGuard().check(
        request=_request(),
        workflow="normativa",
        evidence={
            "items": [
                EvidenceItem(
                    source_type="normativa",
                    source_id="norm-1",
                    title="Norma",
                    content="Estratto.",
                    score=0.8,
                )
            ],
            "citations": [],
        },
        draft=ProviderDraft(text="bozza"),
    )

    assert verdict.allowed is True
    assert verdict.risk_level == "medium"
