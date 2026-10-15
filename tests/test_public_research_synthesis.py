"""Il confronto usa le fonti lette e non pubblica generazioni incomplete."""

import pytest

from lex.contracts import EvidenceItem, LexRequest, ProviderDraft
from lex.research.service import LexResearchService


def sources():
    return [EvidenceItem(source_type='web_libero', source_id=str(i), title=f'Fonte {i}',
                         content='Il termine è di sei mesi. La disposizione prevede una specifica eccezione.',
                         score=0, metadata={'url': f'https://example.org/fonte-{i}'}) for i in (1, 2)]


class Provider:
    def __init__(self, text, *, reason='stop', status='ok'):
        self.text, self.reason, self.status = text, reason, status
        self.calls = []

    def generate(self, request, context, evidence, workflow):
        self.calls.append((request, context, evidence, workflow))
        return ProviderDraft(text=self.text, metadata={'status': self.status, 'model': 'accepted-model',
                             'generation_result': {'done': True, 'done_reason': self.reason}})


def request():
    return LexRequest(tenant_id='studio-a', user_id='u1', session_id='s1', query='Confronta le fonti pubbliche',
                      fascicolo_id='private-case', document_id='private-document',
                      metadata={'studio_context_seed': {'private': 'dato riservato'}})


def test_local_provider_receives_only_read_sources_and_no_case_context():
    provider = Provider('Il termine è di sei mesi [1]. La seconda fonte distingue una specifica eccezione [2].')
    result = LexResearchService.summarize_public_pages(request(), sources(), provider=provider)
    assert result.metadata['status'] == 'ok'
    assert '[1](https://example.org/fonte-1)' in result.text
    assert '[2](https://example.org/fonte-2)' in result.text
    isolated, context, evidence, workflow = provider.calls[0]
    assert isolated.fascicolo_id is None and isolated.document_id is None
    assert 'studio_context_seed' not in isolated.metadata
    assert context == {}
    assert workflow == 'research'
    assert len(evidence['items']) == 2


@pytest.mark.parametrize('reason,status', [('length', 'ok'), ('stop', 'fallback_runtime_unavailable')])
def test_partial_or_fallback_generation_cannot_be_reported_as_a_comparison(reason, status):
    result = LexResearchService.summarize_public_pages(request(), sources(),
             provider=Provider('Il termine è di sei mesi [1][2].', reason=reason, status=status))
    assert result.text == ''
    assert result.metadata['status'] == 'synthesis_incomplete'


def test_a_single_citation_does_not_demonstrate_two_source_comparison():
    result = LexResearchService.summarize_public_pages(request(), sources(),
             provider=Provider('La fonte indica il termine di sei mesi [1].'))
    assert result.text == ''
    assert result.metadata['status'] == 'source_comparison_incomplete'


@pytest.mark.parametrize('link', ['https://unread.example/norma', 'javascript:alert(1)'])
def test_unread_links_are_not_published_as_evidence(link):
    result = LexResearchService.summarize_public_pages(request(), sources(),
             provider=Provider(f'La fonte indica sei mesi [1][2]. [Testo]({link})'))
    assert result.text == ''
    assert result.metadata['status'] == 'unread_source_cited'


def test_no_model_call_when_no_page_was_read():
    provider = Provider('Non deve essere usato')
    result = LexResearchService.summarize_public_pages(request(), [], provider=provider)
    assert result.metadata['status'] == 'no_read_sources'
    assert provider.calls == []
