"""Regressione sul caso reale: responsabilita' extracontrattuale senza fonti normative.

Prima: "Sintesi operativa / Quadro verificato / Dato certo ... attendibilita' media (72%)"
con un elenco di fonti interne (template di atti, impostazioni studio, PEC, procura alle liti).
Ora: Lex dice che le fonti non bastano e che cosa manca.
"""

from __future__ import annotations

import re

from lex.contracts import Citation, EvidenceItem, LexRequest
from lex.guards.orchestrator import GuardOrchestrator
from lex.orchestrator import LexOrchestrator
from lex.providers.registry import ProviderRegistry
from lex.retrieval.filters import RetrievalFilters
from lex.router import LexRouter
from lex.tests.unit.test_bundle_scenarios import StaticContextBuilder, StaticRetrieval

DOMANDA = "Quali sono i presupposti della responsabilita' extracontrattuale?"


def _item(tipo: str, titolo: str, testo: str, score: float = 0.9) -> EvidenceItem:
    return EvidenceItem(source_type=tipo, source_id=titolo.lower().replace(" ", "-"), title=titolo, content=testo, score=score,
                        trust_class="B", source_level=3, authority="studio")


def _fonti_interne() -> list[EvidenceItem]:
    return [
        _item("template_atto", "Atto di citazione - template", "Modello di atto di citazione per il tribunale."),
        _item("legal_intelligence", "Impostazioni studio", "Area civile; capability studio; cadence mensile."),
        _item("studio_db:pec", "Configurazione PEC", "Casella PEC dello studio configurata."),
        _item("guida_pratica", "Procura alle liti", "Guida alla procura alle liti."),
    ]


def _payload(items) -> dict:
    return {
        "queries": [DOMANDA],
        "items": list(items),
        "citations": [],
        "evidence_pack": {"queries": [DOMANDA], "official_sources": [], "trusted_sources": [], "coverage_gaps": [], "compared_sources": [], "sufficient": True},
        "official_sources": [],
        "trusted_sources": ["Atto di citazione - template", "Impostazioni studio"],
        "source_comparison": [],
        "coverage_gaps": [],
        "fallback_triggered": False,
        "evidence_sufficient": True,
    }


class _Bozza:
    def __init__(self, text: str) -> None:
        self.text = text
        self.metadata = {"provider": "prova"}


class _Registro:
    def __init__(self, testo: str) -> None:
        self.testo = testo

    def pick(self, *_, **__):
        testo = self.testo

        class Provider:
            def generate(self, **_):
                return _Bozza(testo)

        return Provider()


def _esegui(payload: dict, testo: str = "Il quadro normativo e' nelle fonti verificate allegate."):
    orchestrator = LexOrchestrator(
        router=LexRouter(),
        workflow_context_builder=StaticContextBuilder(),
        retrieval_orchestrator=StaticRetrieval(payload),
        guard_orchestrator=GuardOrchestrator(),
        provider_registry=_Registro(testo),
    )
    return orchestrator.run(LexRequest(tenant_id="t", user_id="u", session_id="s", query=DOMANDA))


def test_la_domanda_va_alla_ricerca_giuridica():
    request = LexRequest(tenant_id="t", user_id="u", session_id="s", query=DOMANDA)
    assert LexRouter().resolve_workflow(request) == "normativa"


def test_senza_fonti_pertinenti_esito_onesto():
    risposta = _esegui(_payload(_fonti_interne()))
    testo = risposta.answer
    assert "non bastano" in testo
    assert "Normattiva" in testo
    assert "Dato certo" not in testo and "Sintesi operativa" not in testo and "Quadro verificato" not in testo
    assert "Qualita della risposta" not in testo and not re.search(r"\d+\s*%", testo)
    for fonte_interna in ("template", "Impostazioni studio", "PEC", "Procura alle liti"):
        assert fonte_interna not in testo.replace("Importa", ""), fonte_interna
    assert risposta.metadata.get("esito_onesto") is True
    assert risposta.confidence == 0.0 and risposta.answer_mode == "needs_review"
    assert risposta.considered_sources == [] and risposta.citations == []


def test_bozza_bloccata_dalla_guardia_esito_onesto():
    # Il modello cita l'art. 2043 c.c. che non e' nelle evidenze: la guardia blocca.
    class Bozza:
        text = "Presupposti: fatto illecito ai sensi dell'art. 2043 c.c., danno ingiusto, nesso causale e colpa."
        metadata = {"provider": "mock"}

    class Provider:
        def generate(self, **_):
            return Bozza()

    class Registro:
        def pick(self, *_, **__):
            return Provider()

    orchestrator = LexOrchestrator(
        router=LexRouter(),
        workflow_context_builder=StaticContextBuilder(),
        retrieval_orchestrator=StaticRetrieval(_payload(_fonti_interne())),
        guard_orchestrator=GuardOrchestrator(),
        provider_registry=Registro(),
    )
    risposta = orchestrator.run(LexRequest(tenant_id="t", user_id="u", session_id="s", query=DOMANDA))
    assert risposta.metadata.get("esito_onesto") is True
    assert "2043" not in risposta.answer
    assert "Dato certo" not in risposta.answer and not re.search(r"\d+\s*%", risposta.answer)


def test_i_filtri_escludono_le_evidenze_non_giuridiche_dalle_domande_giuridiche():
    request = LexRequest(tenant_id="t", user_id="u", session_id="s", query=DOMANDA)
    norma = _item("normativa_normattiva", "Codice civile art. 2043", "Qualunque fatto doloso o colposo che cagiona ad altri un danno ingiusto...")
    tenute = RetrievalFilters().apply([*_fonti_interne(), norma], request, {}, "normativa")
    assert [i.title for i in tenute] == ["Codice civile art. 2043"]
    # Fuori dalle domande giuridiche i filtri non toccano nulla.
    assert len(RetrievalFilters().apply(_fonti_interne(), request, {}, "cabina")) == 4


def test_con_una_norma_pertinente_non_scatta_l_esito_onesto():
    testo_norma = (
        "Responsabilita extracontrattuale: qualunque fatto doloso o colposo, che cagiona ad altri un danno ingiusto, "
        "obbliga colui che ha commesso il fatto a risarcire il danno."
    )
    norma = EvidenceItem(
        source_type="normativa_normattiva", source_id="cc-2043", title="Codice civile art. 2043 - Risarcimento per fatto illecito",
        content=testo_norma, score=0.97, trust_class="A", source_level=1, verified_reference=True, official_url="https://www.normattiva.it/",
    )
    payload = _payload([norma])
    payload["official_sources"] = [norma.title]
    payload["evidence_pack"]["official_sources"] = [norma.title]
    payload["citations"] = [
        Citation(source_type="normativa_normattiva", source_id="cc-2043", title=norma.title, excerpt=testo_norma, confidence=0.97,
                 trust_class="A", source_level=1, verified_reference=True, url="https://www.normattiva.it/")
    ]
    risposta = _esegui(payload, "Presupposti della responsabilita extracontrattuale: fatto, danno ingiusto, nesso causale e colpa o dolo.")
    assert risposta.metadata.get("esito_onesto") is not True
    assert "non bastano" not in risposta.answer
