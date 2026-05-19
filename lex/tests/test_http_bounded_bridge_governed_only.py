from __future__ import annotations

from types import SimpleNamespace

from lex.context.builder import LexContextBuilder
from lex.context.studio_context import build_studio_context
from lex.contracts import LexRequest, LexResponse
from lex.http_bounded_bridge import build_bounded_http_payload
from lex.retrieval.source_router import SourceRouter
from lex.retrieval.sources.official_web import OfficialWebSource


class DummyLexService:
    def __init__(self) -> None:
        self.last_request = None

    def ask(self, request):
        self.last_request = request
        return LexResponse(
            answer="Risposta governata.",
            confidence=0.62,
            answer_mode="needs_review",
            metadata={"workflow": request.workflow_hint or "question_answering", "provider": "deterministic"},
            warnings=["Risposta prudenziale."],
            next_actions=["Aggancia evidenze aggiuntive."],
            evidence_summary={"evidence_count": 1, "evidence_sufficient": False},
        )


def _base_context(**overrides):
    payload = {
        "sources": [],
        "structured_context": {},
        "focus_label": "",
        "focus_topic": "",
        "request_profile": {"intent": "", "source_mode": "balanced", "drafting_mode": False},
        "execution_policy": {},
        "source_policy_summary": {},
        "source_mode": "balanced",
        "web_fallback_used": False,
        "web_execution_requested": False,
    }
    payload.update(overrides)
    return payload


def _call(studio_context, monkeypatch, *, question="Che cosa devo fare oggi?", attachments=None):
    service = DummyLexService()
    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: service)
    payload = build_bounded_http_payload(
        user=SimpleNamespace(username="utente"),
        studio=SimpleNamespace(slug="studio"),
        data={"session_id": "sess"},
        current_user_message=question,
        resolved_effective_question=question,
        studio_context=studio_context,
        attachments=attachments,
    )
    return payload, service


def test_governed_only_instrada_richiesta_operativa_generica(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")

    payload, service = _call(_base_context(), monkeypatch)

    assert payload is not None
    assert service.last_request is not None
    assert service.last_request.intent == "ask_lex"


def test_governed_only_instrada_normativa_senza_focus_esplicito(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")
    context = _base_context(
        request_profile={"intent": "normativa", "source_mode": "strict", "drafting_mode": False},
        source_mode="strict",
    )

    payload, service = _call(context, monkeypatch, question="Qual e la norma applicabile?")

    assert payload is not None
    assert service.last_request.workflow_hint == "normativa"
    assert service.last_request.require_official_sources is True


def test_governed_only_instrada_giurisprudenza_strict(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")
    context = _base_context(
        request_profile={"intent": "giurisprudenza", "source_mode": "strict", "drafting_mode": False},
        source_mode="strict",
    )

    payload, service = _call(context, monkeypatch, question="Cassazione n. 1234/2024")

    assert payload is not None
    assert service.last_request.workflow_hint == "giurisprudenza"
    assert service.last_request.intent == "research_giurisprudenza"


def test_opzione_web_libero_e_manuale_non_passa_da_job(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")
    monkeypatch.setattr(
        "lex.retrieval.sources.official_web.search_free_public_web",
        lambda query, **kwargs: [
            {
                "id": "free-1",
                "title": "Risultato libero",
                "url": "https://example.org/libero",
                "domain": "example.org",
                "excerpt": "Estratto pubblico non salvato.",
            }
        ],
    )
    context = _base_context(
        sources=[{"title": "Fonte del contesto pagina", "excerpt": "Non deve entrare nel web libero."}],
        structured_context={"fascicolo": {"id": "fas-1"}},
        request_profile={"intent": "", "source_mode": "balanced", "drafting_mode": False},
        source_mode="balanced",
    )
    service = DummyLexService()
    monkeypatch.setattr("lex.http_bounded_bridge._application_lex_service", lambda: service)

    payload = build_bounded_http_payload(
        user=SimpleNamespace(username="utente"),
        studio=SimpleNamespace(slug="studio"),
        data={"session_id": "sess", "free_web_enabled": True},
        current_user_message="Cerca sul web libero questione penale R.G. 9926/2026",
        resolved_effective_question="Cerca sul web libero questione penale R.G. 9926/2026",
        studio_context=context,
    )

    assert payload is not None
    assert service.last_request is None
    assert payload["workflow"] == "web_libero"
    assert payload["source_mode"] == "free_web"
    assert payload["web_execution_requested"] is True
    assert payload["free_web_enabled"] is True
    assert payload["force_free_web_search"] is True
    assert payload["public_web_forced"] is True
    assert payload["sources"][0]["source_type"] == "web_libero"
    assert payload["sources"][0]["verified_reference"] is False
    assert "Risultati pubblici trovati" in payload["answer"]
    assert "Fonte del contesto pagina" not in payload["answer"]
    assert payload["warnings"] == []
    assert payload["next_actions"] == []
    assert payload["disable_exports"] is False
    assert payload["legal_reference_guard_active"] is False
    assert payload["free_web_saves_to_db"] is False
    assert payload["free_web_responsibility"] == "controllo_avvocato"
    assert payload["execution_policy"]["responsibility_scope"] == "controllo_avvocato"


def test_web_libero_stringa_isola_contesto_studio(monkeypatch):
    monkeypatch.setattr(
        "lex.context.studio_context._build_lex_studio_context",
        lambda *args, **kwargs: {
            "sources": [{"title": "Impostazioni studio", "text": "Dato interno da non usare."}],
            "structured_context": {"fascicolo": {"id": "fas-1"}},
            "prompt_block": "Contesto interno da non usare.",
        },
    )
    request = LexRequest(
        tenant_id="tenant-demo",
        user_id="u1",
        session_id="s1",
        query="atto legale",
        metadata={"source_mode": "web libero", "free_web_enabled": True},
    )

    studio_context = build_studio_context(request)
    full_context = LexContextBuilder().build_request_context(request, "atto")

    assert studio_context["sources"] == []
    assert studio_context["structured_context"] == {}
    assert studio_context["prompt_block"] == ""
    assert full_context["studio"]["sources"] == []
    assert "studio_operativo" not in full_context
    assert full_context["free_web"]["enabled"] is True


def test_source_router_web_libero_stringa_usa_solo_web():
    router = SourceRouter()
    request = LexRequest(
        tenant_id="tenant-demo",
        user_id="u1",
        session_id="s1",
        query="atto legale",
        fascicolo_id="fas-1",
        metadata={"source_mode": "web libero"},
    )

    sources = router.resolve(request, {}, "atto")

    assert len(sources) == 1
    assert isinstance(sources[0], OfficialWebSource)


def test_attachments_non_diventano_prompt_libero(monkeypatch):
    monkeypatch.setenv("LEX_GOVERNED_ONLY", "1")
    attachment = {
        "id": "att-1",
        "name": "atto.txt",
        "mime_type": "text/plain",
        "text_excerpt": "Testo dell'atto caricato.",
        "size_bytes": 32,
    }

    payload, service = _call(_base_context(), monkeypatch, attachments=[attachment])

    assert payload is not None
    assert service.last_request is not None
    seed_sources = service.last_request.metadata["studio_context_seed"]["sources"]
    assert seed_sources
    assert seed_sources[0]["metadata"]["origin"] == "user_attachment"
    assert "Testo dell'atto caricato" in seed_sources[0]["excerpt"]
