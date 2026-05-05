from __future__ import annotations

from lex.contracts import EvidenceItem, LexRequest, ProviderDraft
from lex.guards.legal_reference_guard import LegalReferenceGuard


def _request(query: str) -> LexRequest:
    return LexRequest(tenant_id="tenant", user_id="utente", session_id="sess", query=query)


def test_domanda_su_sentenza_senza_fonte_verificata_blocca():
    verdict = LegalReferenceGuard().check(
        request=_request("Trova la sentenza Cassazione n. 1234/2024"),
        workflow="giurisprudenza",
        evidence={"items": [], "citations": []},
        draft=ProviderDraft(text="La Cassazione n. 1234/2024 dice questo."),
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"


def test_domanda_su_pdf_sentenza_senza_pdf_verificato_blocca():
    item = EvidenceItem(
        source_type="giurisprudenza",
        source_id="cass-1234",
        title="Cassazione n. 1234/2024",
        content="Estratto verificato senza PDF.",
        score=0.8,
        metadata={"numero_sentenza": "1234", "anno": "2024"},
        verified_reference=True,
        official_url="https://www.cortedicassazione.it/",
    )

    verdict = LegalReferenceGuard().check(
        request=_request("Scarica il PDF della sentenza Cassazione n. 1234/2024"),
        workflow="giurisprudenza",
        evidence={"items": [item], "citations": []},
        draft=ProviderDraft(text="Non prometto il download."),
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"


def test_domanda_normativa_strict_senza_fonte_ufficiale_blocca():
    item = EvidenceItem(
        source_type="normativa",
        source_id="memo",
        title="Nota interna non verificata",
        content="Richiamo generico all'art. 2043 c.c.",
        score=0.7,
    )

    verdict = LegalReferenceGuard().check(
        request=_request("Qual e la norma applicabile?"),
        workflow="normativa",
        evidence={"items": [item], "citations": []},
        draft=ProviderDraft(text="Si applica l'art. 2043 c.c."),
    )

    assert verdict.allowed is False
    assert verdict.risk_level == "high"


def test_domanda_con_fonte_verificata_passa():
    item = EvidenceItem(
        source_type="normativa",
        source_id="cc-2043",
        title="Codice civile - art. 2043",
        content="Qualunque fatto doloso o colposo...",
        score=0.95,
        trust_class="A",
        source_level=1,
        verified_reference=True,
        official_url="https://www.normattiva.it/",
    )

    verdict = LegalReferenceGuard().check(
        request=_request("Qual e la norma applicabile?"),
        workflow="normativa",
        evidence={"items": [item], "citations": []},
        draft=ProviderDraft(text="La fonte verificata e disponibile."),
    )

    assert verdict.allowed is True
