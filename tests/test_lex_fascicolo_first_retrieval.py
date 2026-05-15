from types import SimpleNamespace

from lex.contracts import LexRequest, LexResponse
from lex.http_bounded_bridge import build_bounded_http_payload
from lex.retrieval.source_router import SourceRouter
from lex.retrieval.sources.official_web import OfficialWebSource


def _source_names(request: LexRequest, workflow: str = "fascicolo") -> list[str]:
    return [source.__class__.__name__ for source in SourceRouter().resolve(request, {}, workflow)]


def test_fascicolo_first_non_usa_fonti_esterne_se_non_servono():
    request = LexRequest(
        tenant_id="tenant-a",
        user_id="user-1",
        session_id="s-1",
        query="riassumi il fascicolo",
        fascicolo_id="fas-1",
        workflow_hint="fascicolo",
        metadata={"fascicolo_first": True},
        allow_external_research=False,
        require_official_sources=False,
    )

    names = _source_names(request)

    assert "FascicoliSource" in names
    assert "DocumentiSource" in names
    assert "OfficialWebSource" not in names
    assert "NormativeSource" not in names
    assert "GiurisprudenzaSource" not in names


def test_fascicolo_first_usa_fonti_esterne_solo_con_ragione_pertinente():
    request = LexRequest(
        tenant_id="tenant-a",
        user_id="user-1",
        session_id="s-1",
        query="verifica art. 1453 codice civile per questo fascicolo",
        fascicolo_id="fas-1",
        workflow_hint="fascicolo",
        metadata={
            "fascicolo_first": True,
            "external_sources_reason": "La domanda richiede verifica normativa su art. 1453 c.c.",
        },
        allow_external_research=True,
        require_official_sources=True,
    )

    names = _source_names(request)

    assert "NormativeSource" in names
    assert "GiurisprudenzaSource" in names
    assert OfficialWebSource.should_include(request, "fascicolo") is True


def test_payload_http_fascicolo_first_flags_senza_fonti_esterne(monkeypatch):
    captured: dict[str, LexRequest] = {}

    class FakeLexService:
        def ask(self, request: LexRequest):
            captured["request"] = request
            return LexResponse(
                answer="Non risulta dai documenti disponibili nel fascicolo.",
                metadata={
                    "workflow": "fascicolo",
                    "fascicolo_first": request.metadata.get("fascicolo_first"),
                    "external_sources_used": False,
                    "external_sources_reason": None,
                },
                evidence_summary={"evidence_count": 1},
                answer_mode="grounded",
                confidence=0.8,
            )

    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: FakeLexService())
    payload = build_bounded_http_payload(
        user=SimpleNamespace(id="user-1"),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"fascicolo_id": "fas-1", "messages": []},
        current_user_message="riassumi il fascicolo",
        resolved_effective_question="riassumi il fascicolo",
        studio_context={
            "focus_topic": "fascicoli",
            "sources": [{"title": "Documento indicizzato", "excerpt": "Testo fascicolo"}],
            "structured_context": {"fascicolo": {"id": "fas-1"}},
            "request_profile": {"intent": "sintesi_fascicolo"},
        },
        attachments=[],
    )

    assert payload is not None
    assert payload["fascicolo_first"] is True
    assert payload["external_sources_used"] is False
    assert payload["external_sources_reason"] is None
    assert captured["request"].allow_external_research is False


def test_payload_http_fonti_esterne_hanno_ragione(monkeypatch):
    class FakeLexService:
        def ask(self, request: LexRequest):
            return LexResponse(
                answer="Serve verificare l'art. 1453 c.c. sul caso.",
                metadata={
                    "workflow": "fascicolo",
                    "fascicolo_first": True,
                    "external_sources_used": True,
                    "external_sources_reason": request.metadata.get("external_sources_reason"),
                },
                evidence_summary={"evidence_count": 2},
                answer_mode="grounded",
                confidence=0.82,
            )

    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: FakeLexService())
    payload = build_bounded_http_payload(
        user=SimpleNamespace(id="user-1"),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"fascicolo_id": "fas-1", "messages": []},
        current_user_message="verifica art. 1453 codice civile per questo fascicolo",
        resolved_effective_question="verifica art. 1453 codice civile per questo fascicolo",
        studio_context={
            "focus_topic": "fascicoli",
            "sources": [{"title": "Documento indicizzato", "excerpt": "Testo fascicolo"}],
            "structured_context": {"fascicolo": {"id": "fas-1"}},
            "request_profile": {"intent": "sintesi_fascicolo"},
        },
        attachments=[],
    )

    assert payload is not None
    assert payload["fascicolo_first"] is True
    assert payload["external_sources_used"] is True
    assert payload["external_sources_reason"]
    assert "normativa" in payload["external_sources_reason"]


def test_payload_http_ricerca_legale_auto_web_anche_con_contesto_interno(monkeypatch):
    captured: dict[str, LexRequest] = {}

    class FakeLexService:
        def ask(self, request: LexRequest):
            captured["request"] = request
            return LexResponse(
                answer="Verifica giurisprudenziale avviata.",
                metadata={
                    "workflow": "giurisprudenza",
                    "external_sources_used": True,
                    "external_sources_reason": request.metadata.get("external_sources_reason"),
                },
                evidence_summary={"evidence_count": 0},
                answer_mode="needs_review",
                confidence=0.45,
            )

    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: FakeLexService())
    payload = build_bounded_http_payload(
        user=SimpleNamespace(id="user-1"),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"messages": []},
        current_user_message="Cerca giurisprudenza aggiornata sul licenziamento disciplinare",
        resolved_effective_question="Cerca giurisprudenza aggiornata sul licenziamento disciplinare",
        studio_context={
            "focus_topic": "ricerca_legale",
            "sources": [{"title": "Archivio interno", "excerpt": "Voce non sufficiente"}],
            "structured_context": {"legal_intelligence": {"recenti": []}},
            "request_profile": {"intent": "giurisprudenza", "source_mode": "balanced"},
        },
        attachments=[],
    )

    assert payload is not None
    assert captured["request"].allow_external_research is True
    assert captured["request"].require_official_sources is True
    assert captured["request"].metadata["external_sources_reason"]
