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


def test_estremi_consulta_ordinanza_e_forme_abbreviate():
    from lex.guards.hallucination_guard import extract_legal_references

    def chiavi(testo: str) -> set[str]:
        return {ref.key for ref in extract_legal_references(testo)}

    assert "ordinanza:45:2019" in chiavi("Con l'ordinanza n. 45/2019 la questione e' stata restituita.")
    assert {"corte costituzionale:12:2020", "ordinanza:12:2020"} <= chiavi("Corte cost., ord. n. 12/2020")
    assert {"corte costituzionale:242:2019", "sentenza:242:2019"} <= chiavi("C. cost., sent. n. 242/2019")
    assert "sentenza:194:2018" in chiavi("Corte Cost. sent. n. 194 del 2018")


def test_ordinanza_della_consulta_supportata_dalla_fonte_passa():
    evidenza = EvidenceItem(
        source_type="giurisprudenza",
        source_id="cc-2021-97",
        title="Corte costituzionale, ordinanza n. 97/2021",
        content="Massima: e' rinviata la trattazione delle questioni sull'ergastolo ostativo.",
        score=0.9,
        metadata={"numero_sentenza": "97", "anno_sentenza": "2021", "ecli": "ECLI:IT:COST:2021:97"},
    )
    verdict = HallucinationGuard().check(
        request=_request("ergastolo ostativo"),
        workflow="giurisprudenza",
        evidence={"items": [evidenza], "citations": []},
        draft=ProviderDraft(text="Con Corte cost., ord. n. 97/2021 la Consulta ha rinviato la decisione [1]."),
    )
    assert verdict.allowed is True


def test_ordinanza_inventata_blocca_nel_workflow_strict():
    evidenza = EvidenceItem(
        source_type="giurisprudenza",
        source_id="cc-2021-97",
        title="Corte costituzionale, ordinanza n. 97/2021",
        content="Rinvio della trattazione.",
        score=0.9,
    )
    verdict = HallucinationGuard().check(
        request=_request("ergastolo ostativo"),
        workflow="giurisprudenza",
        evidence={"items": [evidenza], "citations": []},
        draft=ProviderDraft(text="Si veda anche l'ordinanza n. 33/2022 [1]."),
    )
    assert verdict.allowed is False
    assert "ordinanza n. 33/2022" in verdict.warnings[0]
