from __future__ import annotations

from lex.contracts import LexRequest
from lex.providers.deterministic_provider import DeterministicProvider
from lex.retrieval.cache import clear_retrieval_cache
from lex.retrieval.orchestrator import RetrievalOrchestrator
from lex.retrieval.source_router import SourceRouter
from lex.retrieval.sources.guida_pratica import GuidaPraticaSource
from lex.router import LexRouter


def _request(query: str, **kwargs) -> LexRequest:
    return LexRequest(
        tenant_id="tenant-guida",
        user_id="utente-test",
        session_id="sessione-guida",
        query=query,
        metadata={"disable_studio_database_source": True, **dict(kwargs.pop("metadata", {}) or {})},
        **kwargs,
    )


def test_guida_pratica_source_legge_scheda_completa_da_codice_ufficiale():
    source = GuidaPraticaSource()
    request = _request("Guida pratica licenziamento gmo codice 220101")

    results = source.search([request.query], request, {})

    assert results
    item = results[0]
    assert item.source_type == "guida_pratica"
    assert item.source_id == "220101"
    assert "Licenziamento individuale" in item.title
    assert "Guida pratica interna facoltativa" in item.content
    assert "Normativa letta dalla scheda" in item.content
    assert "Allegati obbligatori" in item.content
    assert item.metadata["deposit_code_official"] is True
    assert item.metadata["depositable"] is True
    assert item.metadata["full_guidance_available"] is True
    assert item.metadata["linguistic_profile"] == "conversazionale_avvocato"
    assert isinstance(item.metadata["guidance_payload"], dict)
    assert item.metadata["document_plan"]["enabled"] is True
    assert item.metadata["document_plan"]["import"]["enabled"] is True
    assert "Piano documento della guida" in item.content
    assert "import PDF/Word disponibile" in item.content


def test_guida_pratica_source_lex_legge_contesto_fascicolo_e_piano_documento():
    source = GuidaPraticaSource()
    request = _request(
        "Lex, aiutami con la guida pratica del fascicolo",
        metadata={
            "fascicolo": {
                "cliente": "Cliente Studio",
                "ufficio": "Tribunale di Palmi",
                "oggetto": "Licenziamento individuale per giustificato motivo oggettivo",
                "codice_oggetto_pst": "220101",
                "documenti_count": 3,
                "attivita_count": 2,
            }
        },
    )

    item = source.search([request.query], request, {})[0]

    assert item.source_id == "220101"
    assert "Contesto fascicolo letto dalla guida" in item.content
    assert "cliente: Cliente Studio" in item.content
    assert "codice ufficiale fascicolo: 220101" in item.content
    assert item.metadata["document_plan"]["enabled"] is True
    assert item.metadata["document_plan"]["import"]["formats"] == ["PDF", "Word"]


def test_guida_pratica_source_espone_voci_curate_utente_quando_presenti():
    source = GuidaPraticaSource()
    request = _request("Guida pratica codice GUIDA_ADS_MODIFICA_REVOCA_413062")

    item = source.search([request.query], request, {})[0]

    assert item.source_id == "GUIDA_ADS_MODIFICA_REVOCA_413062"
    assert "Tipologie di intervento" in item.content
    assert "Legittimati attivi" in item.content
    assert "Obbligo mediazione o negoziazione" in item.content
    assert "Avvertimenti redazionali obbligatori" in item.content
    assert "Esiti processuali tipici" in item.content
    assert item.metadata["tipologie_intervento_count"] > 0
    assert item.metadata["legittimati_attivi_count"] > 0
    assert item.metadata["has_obbligo_mediazione"] is True


def test_guida_pratica_source_non_forza_alias_su_codice_ministeriale_differente():
    source = GuidaPraticaSource()
    request = _request("Mi serve la guida pratica per apertura tutela minori")

    results = source.search([request.query], request, {})
    aliases = [item for item in results if item.source_id == "GUIDA_TUTELA_MINORI_ORDINARIA"]

    assert aliases
    alias = aliases[0]
    assert alias.metadata["deposit_code_official"] is False
    assert alias.metadata["depositable"] is False
    assert alias.metadata["codice_originale_ricevuto"] == "413011"
    assert "guida interna non depositabile" in alias.content
    assert "413010" in alias.content or "B02041" in alias.content


def test_source_router_espone_guida_pratica_a_lex_senza_fonti_esterne():
    router = SourceRouter()
    request = _request("guida pratica licenziamento gmo")

    sources = router.resolve(request, {"studio": {}}, "question_answering")
    source_names = [source.__class__.__name__ for source in sources]

    assert "GuidaPraticaSource" in source_names
    assert "OfficialWebSource" not in source_names


def test_router_non_scambia_la_guida_pratica_generale_per_fascicolo():
    workflow = LexRouter().resolve_workflow(_request("guida pratica per licenziamento gmo"))

    assert workflow == "question_answering"


def test_retrieval_orchestrator_recupera_guida_pratica_come_evidenza_conversazionale():
    clear_retrieval_cache()
    request = _request("guida pratica licenziamento gmo codice 220101", metadata={"disable_retrieval_cache": True})
    orchestrator = RetrievalOrchestrator()

    payload = orchestrator.collect(request, {"studio": {"effective_question": request.query}}, "question_answering")

    assert payload["evidence_sufficient"] is True
    assert any(item.source_type == "guida_pratica" and item.source_id == "220101" for item in payload["items"])
    assert "GuidaPraticaSource" in payload["used_sources"]
    assert "OfficialWebSource" not in payload["used_sources"]


def test_provider_risponde_in_modo_conversazionale_sulla_guida_pratica():
    source = GuidaPraticaSource()
    request = _request("mi spieghi operativamente la guida pratica 220101")
    item = source.search([request.query], request, {})[0]

    draft = DeterministicProvider().generate(
        request,
        {},
        {"items": [item]},
        "question_answering",
    )

    assert "Ho letto la guida pratica collegata" in draft.text
    assert "supporto operativo per l'avvocato" in draft.text
    assert "non blocca il lavoro sul fascicolo" in draft.text
    assert "codice risulta presente nel catalogo PST/XSD ufficiale" in draft.text
