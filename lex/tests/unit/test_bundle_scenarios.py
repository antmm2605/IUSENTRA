from __future__ import annotations

from lex.contracts import Citation, EvidenceItem, LexRequest
from lex.guards.orchestrator import GuardOrchestrator
from lex.orchestrator import LexOrchestrator
from lex.providers.registry import ProviderRegistry
from lex.retrieval.orchestrator import RetrievalOrchestrator
from lex.router import LexRouter


class StaticContextBuilder:
    def __init__(self, extra: dict | None = None) -> None:
        self.extra = dict(extra or {})

    def build_request_context(self, request, workflow: str) -> dict:
        context = {
            "workflow": workflow,
            "permessi": {"can_use_lex": True},
            "studio": {"effective_question": request.query},
        }
        context.update(self.extra)
        return context


class StaticRetrieval:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def collect(self, request, context, workflow):
        return dict(self.payload)


def _orchestrator_for(payload: dict, *, context: dict | None = None) -> LexOrchestrator:
    return LexOrchestrator(
        router=LexRouter(),
        workflow_context_builder=StaticContextBuilder(context),
        retrieval_orchestrator=StaticRetrieval(payload),
        guard_orchestrator=GuardOrchestrator(),
        provider_registry=ProviderRegistry(),
        memory=None,
        telemetry=None,
    )


def test_lookup_sentenza_con_numero_pdf_degrada_senza_riferimenti_verificati():
    payload = {
        "queries": ["pdf sentenza cassazione 1234 2024"],
        "items": [
            EvidenceItem(
                source_type="giurisprudenza",
                source_id="cass-raw-1",
                title="Richiamo non verificato",
                content="Richiamo generico senza estremi verificati.",
                score=0.61,
            )
        ],
        "citations": [],
        "evidence_pack": {
            "queries": ["pdf sentenza cassazione 1234 2024"],
            "official_sources": [],
            "trusted_sources": [],
            "coverage_gaps": ["Mancano fonti ufficiali tra le evidenze selezionate."],
            "compared_sources": [],
            "sufficient": False,
        },
        "official_sources": [],
        "trusted_sources": [],
        "source_comparison": [],
        "coverage_gaps": ["Mancano fonti ufficiali tra le evidenze selezionate."],
        "fallback_triggered": False,
        "evidence_sufficient": False,
    }
    orchestrator = _orchestrator_for(payload)

    response = orchestrator.run(
        LexRequest(
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            query="Dammi il PDF della sentenza Cassazione n. 1234/2024",
            metadata={"force_provider": "mock"},
        )
    )

    assert response.metadata["workflow"] == "giurisprudenza"
    assert response.metadata["provider"] == "guardrail"
    assert response.metadata["coverage_gaps"] == ["Mancano fonti ufficiali tra le evidenze selezionate."]
    assert response.answer_mode == "needs_review"
    assert "Non posso completare una risposta legale affidabile" in response.answer


def test_domanda_normativa_senza_fonti_interne_attiva_fallback_ufficiale():
    class StaticPlanner:
        def plan(self, request, context, workflow):
            return ["articolo 16 dm 150 2023 mediazione"]

    class PassFilters:
        def apply(self, results, request, context, workflow):
            return list(results)

    class InternalNormativeSource:
        def search(self, queries, request, context):
            return []

    class OfficialWebSource:
        def search(self, queries, request, context):
            return [
                EvidenceItem(
                    source_type="web_ufficiale",
                    source_id="gu-1",
                    title="Gazzetta Ufficiale",
                    content="Decreto ministeriale pubblicato in Gazzetta Ufficiale.",
                    score=0.97,
                    authority="Gazzetta Ufficiale",
                    official_url="https://www.gazzettaufficiale.it/eli/id/2023/10/31/23G00163/sg",
                    trust_class="A",
                    source_level=1,
                    verified_reference=True,
                ),
                EvidenceItem(
                    source_type="web_ufficiale",
                    source_id="norm-1",
                    title="Normattiva",
                    content="Versione vigente disponibile su Normattiva.",
                    score=0.95,
                    authority="Normattiva",
                    official_url="https://www.normattiva.it/",
                    trust_class="A",
                    source_level=1,
                    verified_reference=True,
                ),
            ]

    class StaticRouter:
        def resolve(self, request, context, workflow):
            return [InternalNormativeSource(), OfficialWebSource()]

    orchestrator = RetrievalOrchestrator(
        query_planner=StaticPlanner(),
        source_router=StaticRouter(),
        filters=PassFilters(),
    )

    payload = orchestrator.collect(
        LexRequest(
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            query="Qual e la normativa aggiornata sulla mediazione?",
        ),
        {"studio": {"effective_question": "Qual e la normativa aggiornata sulla mediazione?"}},
        "normativa",
    )

    assert payload["fallback_triggered"] is True
    assert payload["official_sources"] == ["Gazzetta Ufficiale", "Normattiva"]
    assert payload["coverage_gaps"] == []
    assert payload["evidence_sufficient"] is True


def test_errore_telematico_restituisce_risposta_deterministica_con_metadati():
    payload = {
        "queries": ["errore telematico busta rifiutata"],
        "items": [
            EvidenceItem(
                source_type="telematico",
                source_id="tel-1",
                title="Esito deposito PST",
                content="Busta rifiutata per allegato obbligatorio mancante.",
                score=0.92,
            )
        ],
        "citations": [],
        "evidence_pack": {
            "queries": ["errore telematico busta rifiutata"],
            "official_sources": [],
            "trusted_sources": [],
            "coverage_gaps": [],
            "compared_sources": [],
            "sufficient": True,
        },
        "official_sources": [],
        "trusted_sources": [],
        "source_comparison": [],
        "coverage_gaps": [],
        "fallback_triggered": False,
        "evidence_sufficient": True,
    }
    orchestrator = _orchestrator_for(payload)

    response = orchestrator.run(
        LexRequest(
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            query="Spiegami l'errore telematico della busta",
            intent="explain_telematico_error",
        )
    )

    assert response.metadata["workflow"] == "telematico_status"
    assert response.metadata["provider"] == "deterministic"
    assert "Esito operativo governato" in response.answer
    assert "coverage_gaps" in response.metadata
    assert "fallback_triggered" in response.metadata


def test_riassunto_fascicolo_conserva_fonti_e_metadati_nella_risposta():
    payload = {
        "queries": ["riepilogo fascicolo rg 1025 2024"],
        "items": [
            EvidenceItem(
                source_type="fascicolo",
                source_id="fas-1",
                title="RG 1025/2024",
                content="Pratica definita con 16 documenti e 1 scadenza da riallineare.",
                score=0.88,
                authority="Fascicolo interno",
            )
        ],
        "citations": [
            Citation(
                source_type="fascicolo",
                source_id="fas-1",
                title="RG 1025/2024",
                excerpt="Pratica definita con 16 documenti.",
                confidence=0.88,
                authority="Fascicolo interno",
            )
        ],
        "evidence_pack": {
            "queries": ["riepilogo fascicolo rg 1025 2024"],
            "official_sources": [],
            "trusted_sources": ["RG 1025/2024"],
            "coverage_gaps": [],
            "compared_sources": [{"title": "RG 1025/2024", "trust_class": ""}],
            "sufficient": True,
        },
        "official_sources": [],
        "trusted_sources": ["RG 1025/2024"],
        "source_comparison": [{"title": "RG 1025/2024", "trust_class": ""}],
        "coverage_gaps": [],
        "fallback_triggered": False,
        "evidence_sufficient": True,
    }
    orchestrator = _orchestrator_for(payload, context={"fascicolo": {"id": "FAS-1", "stato": "definito"}})

    response = orchestrator.run(
        LexRequest(
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            query="Riepiloga il fascicolo",
            intent="summarize_fascicolo",
            fascicolo_id="FAS-1",
            metadata={"force_provider": "mock"},
        )
    )

    assert response.metadata["workflow"] == "fascicolo"
    assert response.metadata["provider"] == "mock"
    assert response.considered_sources == ["RG 1025/2024"]
    assert response.evidence_summary["evidence_count"] == 1


def test_caso_economico_preventivo_tariffario_fattura_usa_fast_path_deterministico():
    payload = {
        "queries": ["verifica preventivo parcella fattura"],
        "items": [
            EvidenceItem(
                source_type="preventivi",
                source_id="prev-1",
                title="Preventivo civile RG 1025/2024",
                content="Compenso principale, anticipazioni, fattura e saldo coerenti.",
                score=0.91,
            )
        ],
        "citations": [],
        "evidence_pack": {
            "queries": ["verifica preventivo parcella fattura"],
            "official_sources": [],
            "trusted_sources": [],
            "coverage_gaps": [],
            "compared_sources": [],
            "sufficient": True,
        },
        "official_sources": [],
        "trusted_sources": [],
        "source_comparison": [],
        "coverage_gaps": [],
        "fallback_triggered": False,
        "evidence_sufficient": True,
    }
    orchestrator = _orchestrator_for(payload)

    response = orchestrator.run(
        LexRequest(
            tenant_id="tenant-1",
            user_id="user-1",
            session_id="session-1",
            query="Valuta preventivo, tariffario e fattura della pratica",
            intent="evaluate_preventivo",
        )
    )

    assert response.metadata["workflow"] == "economico"
    assert response.metadata["provider"] == "deterministic"
    assert "preventivo guidato" in response.answer.lower()
    assert response.evidence_summary["fallback_triggered"] is False
