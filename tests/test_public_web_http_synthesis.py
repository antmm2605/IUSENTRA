"""La risposta HTTP non confonde pagine lette e confronto completato."""

from types import SimpleNamespace

import pytest

from lex.contracts import EvidenceItem, ProviderDraft
from lex.http_bounded_bridge import _free_web_direct_payload


@pytest.mark.parametrize("accepted", [True, False])
def test_http_publishes_only_accepted_comparison(monkeypatch, accepted):
    item = EvidenceItem(source_type="web_libero", source_id="public-1", title="Fonte pubblica",
                        content="Il termine è di sei mesi.", score=1,
                        metadata={"url": "https://example.org/norma"})
    monkeypatch.setattr("lex.retrieval.sources.official_web.OfficialWebSource.search",
                        lambda *args, **kwargs: [item])
    calls = []

    def summarize(request, items):
        calls.append((request, items))
        return ProviderDraft(text="Il termine è di sei mesi [1]." if accepted else "",
                             metadata={"status": "ok" if accepted else "synthesis_incomplete"})

    monkeypatch.setattr("lex.research.service.LexResearchService.summarize_public_pages", summarize)
    result = _free_web_direct_payload(user=SimpleNamespace(username="tester"),
        studio=SimpleNamespace(slug="studio-a"), metadata={}, current_user_message="Confronta la fonte",
        resolved_effective_question="Confronta la fonte", studio_context={}, request_profile={}, workflow_hint="fonti")
    assert len(calls) == 1
    assert calls[0][0].fascicolo_id is None
    assert result["evidence_summary"]["evidence_sufficient"] is accepted
    assert bool(result["compared_sources"]) is accepted
    assert bool(result["warnings"]) is not accepted
    assert len(result["sources"]) == 1
    assert result["sources"][0]["verified_reference"] is False
    assert result["free_web_saves_to_db"] is False
    assert result["disable_exports"] is not accepted
    if not accepted:
        assert "non è stato completato" in result["answer"]


def test_unread_page_remains_visible_with_its_actual_cause(monkeypatch):
    def search(self, queries, request, context):
        request.metadata["public_web_visits"] = [{"url": "https://example.org/riservata",
                                                 "status": "robots_blocked"}]
        return []

    monkeypatch.setattr("lex.retrieval.sources.official_web.OfficialWebSource.search", search)
    result = _free_web_direct_payload(user=None, studio=None, metadata={}, current_user_message="Leggi la pagina",
        resolved_effective_question="Leggi la pagina", studio_context={}, request_profile={}, workflow_hint="fonti")
    assert result["sources"] == [] and result["compared_sources"] == []
    assert any("https://example.org/riservata" in warning and "Regole di accesso" in warning
               for warning in result["warnings"])


def test_plain_reading_error_does_not_claim_a_model_comparison(monkeypatch):
    monkeypatch.setattr("lex.retrieval.sources.official_web.OfficialWebSource.search", lambda *args: [])
    result = _free_web_direct_payload(user=None, studio=None, metadata={},
        current_user_message="Leggi la pagina", resolved_effective_question="Leggi la pagina",
        studio_context={}, request_profile={}, workflow_hint="fonti")
    assert result["compared_sources"] == []
    assert "Lettura delle fonti non completata." in result["warnings"]
    assert result["execution_policy"]["llm_role"] == "non_utilizzato_per_lettura"
    assert "confronto" not in " ".join(result["warnings"]).lower()


@pytest.mark.parametrize('status,phrase', [
    ('ambiguous_source_condition', 'condizione richiamata'),
    ('unsupported_source_quotation', 'citazione testuale'),
])
def test_source_provenance_failures_explain_the_actual_reason(monkeypatch, status, phrase):
    item = EvidenceItem(source_type='web_libero', source_id='p1', title='Fonte pubblica',
                        content='Il termine è di sei mesi.', score=1,
                        metadata={'url': 'https://example.org/norma'})
    monkeypatch.setattr('lex.retrieval.sources.official_web.OfficialWebSource.search', lambda *args: [item])
    monkeypatch.setattr('lex.research.service.LexResearchService.summarize_public_pages',
                        lambda *args: ProviderDraft(text='', metadata={'status': status}))
    result = _free_web_direct_payload(user=None, studio=None, metadata={},
        current_user_message='Confronta le pagine', resolved_effective_question='Confronta le pagine',
        studio_context={}, request_profile={}, workflow_hint='fonti')
    assert phrase in result['answer']
    assert result['disable_exports'] is True
    assert result['compared_sources'] == []
    assert len(result['sources']) == 1
