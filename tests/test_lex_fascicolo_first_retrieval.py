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


def test_web_libero_lex_resta_separato_da_fonti_ufficiali_e_archivi(monkeypatch):
    calls: list[str] = []

    def _fake_free_web(query, **kwargs):
        calls.append(query)
        return [
            {
                "id": "free-1",
                "title": "Commento pubblico art. 606 c.p.p.",
                "url": "https://example.org/articolo-606-cpp",
                "domain": "example.org",
                "source_name": "Example pubblico",
                "excerpt": "Risultato pubblico non promosso nel corpus ufficiale.",
            }
        ]

    monkeypatch.setattr("lex.retrieval.sources.official_web.search_free_public_web", _fake_free_web)

    request = LexRequest(
        tenant_id="tenant-a",
        user_id="user-1",
        session_id="s-1",
        query="cerca sul web libero art. 606 c.p.p.",
        metadata={"source_mode": "web_libero", "fascicolo_context": {"cliente": "Rossi"}},
        allow_external_research=True,
        require_official_sources=False,
    )

    evidence = OfficialWebSource().search([request.query], request, {"workflow": "giurisprudenza"})

    assert calls == ["cerca sul web libero art. 606 c.p.p."]
    assert len(evidence) == 1
    assert evidence[0].source_type == "web_libero"
    assert evidence[0].verified_reference is False
    assert evidence[0].metadata["allowlist_used"] is False
    assert evidence[0].metadata["saved_to_db"] is False
    assert request.metadata["source_registry"]["selected_source_ids"] == []
    assert request.metadata["source_registry"]["saved_to_db"] is False


def test_payload_http_web_libero_restituisce_risposta_diretta(monkeypatch):
    calls: list[str] = []

    def _fake_free_web(query, **kwargs):
        calls.append(query)
        return [
            {
                "id": "free-1",
                "title": "Risultato pubblico sulla ricerca",
                "url": "https://example.org/risultato",
                "domain": "example.org",
                "source_name": "example.org",
                "excerpt": "Estratto pubblico restituito dalla ricerca libera.",
            }
        ]

    monkeypatch.setattr("lex.retrieval.sources.official_web.search_free_public_web", _fake_free_web)

    payload = build_bounded_http_payload(
        user=SimpleNamespace(id="user-1"),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"messages": [], "free_web_enabled": True, "force_free_web_search": True, "source_mode": "free_web"},
        current_user_message="cerca sul web libero riforma mediazione 2026",
        resolved_effective_question="cerca sul web libero riforma mediazione 2026",
        studio_context={
            "focus_topic": "ricerca_legale",
            "sources": [{"title": "Archivio interno", "excerpt": "Da non usare nel Web libero"}],
            "structured_context": {"legal_intelligence": {"recenti": []}},
            "request_profile": {"intent": "giurisprudenza", "source_mode": "free_web"},
        },
        attachments=[],
    )

    assert calls == ["cerca sul web libero riforma mediazione 2026"]
    assert payload is not None
    assert payload["workflow"] == "web_libero"
    assert payload["free_web_enabled"] is True
    assert payload["warnings"] == []
    assert payload["sources"][0]["source_type"] == "web_libero"
    assert payload["sources"][0]["verified_reference"] is False
    assert "Risultati pubblici trovati" in payload["answer"]
    assert "Archivio interno" not in payload["answer"]


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


def test_payload_http_documenti_caricati_usano_workflow_documento(monkeypatch):
    captured: dict[str, LexRequest] = {}

    class FakeLexService:
        def ask(self, request: LexRequest):
            captured["request"] = request
            return LexResponse(
                answer="Il documento caricato evidenzia procura e allegati da controllare.",
                metadata={"workflow": "documento", "external_sources_used": False},
                evidence_summary={"evidence_count": 1},
                answer_mode="grounded",
                confidence=0.82,
            )

    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: FakeLexService())
    payload = build_bounded_http_payload(
        user=SimpleNamespace(id="user-1"),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"messages": []},
        current_user_message="analizza il documento caricato",
        resolved_effective_question="analizza il documento caricato",
        studio_context={
            "focus_topic": "documenti",
            "sources": [],
            "structured_context": {},
            "request_profile": {"intent": "sintesi_documento"},
        },
        attachments=[
            {
                "id": "doc-1",
                "name": "memo.txt",
                "mime_type": "text/plain",
                "text_excerpt": "Promemoria per controllare procura e allegati firmati.",
                "text_chars": 58,
                "truncated": False,
            }
        ],
    )

    assert payload is not None
    assert captured["request"].intent == "analyze_document"
    assert captured["request"].workflow_hint == "documento"
    assert captured["request"].metadata["attachment_count"] == 1
    assert any("Allegato caricato: memo.txt" in citation for citation in payload["citations"])


def test_payload_http_documenti_caricati_forzano_domanda_sul_documento(monkeypatch):
    captured: dict[str, LexRequest] = {}

    class FakeLexService:
        def ask(self, request: LexRequest):
            captured["request"] = request
            return LexResponse(
                answer="Il documento caricato contiene tre punti principali.",
                metadata={"workflow": "documento", "external_sources_used": False},
                evidence_summary={"evidence_count": 1},
                answer_mode="grounded",
                confidence=0.86,
            )

    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: FakeLexService())
    payload = build_bounded_http_payload(
        user=SimpleNamespace(id="user-1"),
        studio=SimpleNamespace(slug="tenant-a"),
        data={"messages": [], "attachment_request_mode": "document_question"},
        current_user_message="spiegami quali sono i punti più importanti del documento",
        resolved_effective_question="spiegami quali sono i punti più importanti del documento",
        studio_context={
            "focus_topic": "fascicoli",
            "sources": [],
            "structured_context": {"fascicolo": {"id": "fas-1"}},
            "request_profile": {"intent": "domanda_generica"},
        },
        attachments=[
            {
                "id": "doc-2",
                "name": "contratto.pdf",
                "mime_type": "application/pdf",
                "text_excerpt": "Contratto con tre clausole essenziali: pagamento, consegna e penale.",
                "text_chars": 70,
                "truncated": False,
            }
        ],
    )

    assert payload is not None
    assert captured["request"].intent == "analyze_document"
    assert captured["request"].workflow_hint == "documento"
    assert captured["request"].metadata["request_profile"]["intent"] == "sintesi_documento"
    assert captured["request"].metadata["attachment_request_mode"] == "document_question"
    seed_sources = captured["request"].metadata["studio_context_seed"]["sources"]
    assert seed_sources[0]["metadata"]["origin"] == "user_attachment"
    assert any("Allegato caricato: contratto.pdf" in citation for citation in payload["citations"])


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
