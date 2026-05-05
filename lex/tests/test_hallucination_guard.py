from __future__ import annotations

from lex.contracts import EvidenceItem, LexRequest, ProviderDraft
from lex.guards.hallucination_guard import HallucinationGuard


def _request(query: str = "test") -> LexRequest:
    return LexRequest(tenant_id="tenant", user_id="utente", session_id="sess", query=query)


def test_draft_cassazione_senza_evidenze_blocca():
    verdict = HallucinationGuard().check(
        request=_request("Cassazione n. 1234/2024"),
        workflow="giurisprudenza",
        evidence={"items": [], "citations": []},
        draft=ProviderDraft(text="La Cassazione n. 1234/2024 ha affermato il principio."),
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"


def test_draft_articolo_normativa_senza_evidenze_blocca():
    verdict = HallucinationGuard().check(
        request=_request("art. 2043 c.c."),
        workflow="normativa",
        evidence={"items": [], "citations": []},
        draft=ProviderDraft(text="Si applica l'art. 2043 c.c."),
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"


def test_draft_generico_senza_riferimenti_specifici_non_blocca():
    verdict = HallucinationGuard().check(
        request=_request(),
        workflow="normativa",
        evidence={"items": [], "citations": []},
        draft=ProviderDraft(text="Non ho elementi sufficienti per una risposta conclusiva."),
    )

    assert verdict.allowed is True


def test_draft_con_riferimento_presente_nelle_evidenze_passa():
    item = EvidenceItem(
        source_type="giurisprudenza",
        source_id="cass-1234",
        title="Cassazione n. 1234/2024",
        content="La Cassazione n. 1234/2024 riguarda il punto richiesto.",
        score=0.9,
    )

    verdict = HallucinationGuard().check(
        request=_request("Cassazione n. 1234/2024"),
        workflow="giurisprudenza",
        evidence={"items": [item], "citations": []},
        draft=ProviderDraft(text="La Cassazione n. 1234/2024 e tra le evidenze disponibili."),
    )

    assert verdict.allowed is True
