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


@pytest.mark.parametrize('claim', [
    'La pagina non li elenca, quindi non posso indicare i termini',
    'La fonte 2 non lo menziona',
    'Il testo non contiene queste informazioni',
    'La pagina in esame non ne parla',
])
def test_partial_excerpts_cannot_demonstrate_absence_from_the_whole_page(claim):
    rows = sources()
    for row in rows:
        row.metadata['selection'] = {'complete_context': False}
    provider = Provider(claim + ' [1]. '
                        'La seconda fonte indica sei mesi [2].')
    result = LexResearchService.summarize_public_pages(request(), rows, provider=provider)
    assert result.text == ''
    assert result.metadata['status'] == 'unsupported_source_absence_claim'
    assert 'non dedurre' in provider.calls[0][0].query


def test_plain_reading_returns_literal_passages_with_sections_without_model_call():
    from dataclasses import replace
    rows = sources()
    rows[0].metadata['selection'] = {'complete_context': False, 'passages': [
        {'section': ['Processo amministrativo'], 'text': 'I termini assegnati dal giudice sono perentori.'}]}
    provider = Provider('Non deve essere chiamato')
    query = 'Leggi queste due pagine pubbliche e indica quali informazioni riesci effettivamente a recuperare, citando separatamente i due link: https://example.org/1 e https://example.org/2 . Non usare dati dello studio.'
    result = LexResearchService.summarize_public_pages(replace(request(), query=query), rows, provider=provider)
    assert result.metadata['response_mode'] == 'source_passages'
    assert result.metadata['generation_performed'] is False
    assert result.metadata['compared_source_count'] == 0
    assert provider.calls == []
    assert 'Processo amministrativo\n\n> I termini assegnati dal giudice sono perentori.' in result.text
    assert rows[1].content in result.text
    assert '[1](https://example.org/fonte-1)' in result.text
    assert '[2](https://example.org/fonte-2)' in result.text


@pytest.mark.parametrize('query', ['Confronta queste pagine', 'Leggi queste pagine e confronta i termini',
                                  'Leggi queste pagine: quale termine si applica al civile?'])
def test_questions_and_comparisons_keep_the_native_model_path(query):
    from dataclasses import replace
    provider = Provider('Il termine è di sei mesi [1][2].')
    LexResearchService.summarize_public_pages(replace(request(), query=query), sources(), provider=provider)
    assert len(provider.calls) == 1


def test_source_attribution_does_not_reject_a_supported_negative_fact_about_an_act():
    rows = sources()
    rows[0].content = "L'atto esaminato non contiene i dati richiesti."
    for row in rows:
        row.metadata['selection'] = {'complete_context': False}
    provider = Provider("La fonte 1 indica che l'atto non contiene i dati richiesti [1]. "
                        "La seconda fonte descrive una specifica eccezione [2].")
    result = LexResearchService.summarize_public_pages(request(), rows, provider=provider)
    assert result.metadata['status'] == 'ok'


@pytest.mark.parametrize('wrong_source', [False, True])
def test_literal_quotation_must_match_the_attributed_source(wrong_source):
    rows = sources()
    rows[0].content = 'La regola opera quando sono soddisfatte tutte le condizioni.'
    rows[1].content = 'Una diversa disposizione disciplina un altro procedimento.'
    quote = rows[0].content if wrong_source else 'La regola opera senza alcuna condizione.'
    provider = Provider(f'“{quote}” [2]. La prima fonte disciplina le condizioni [1].')
    result = LexResearchService.summarize_public_pages(request(), rows, provider=provider)
    assert result.metadata['status'] == 'unsupported_source_quotation'
    assert result.text == ''


def test_literal_quotation_preserves_the_sources_conditions():
    rows = sources()
    provider = Provider('“Il termine è di sei mesi.” [1]. La seconda fonte descrive una specifica eccezione [2].')
    result = LexResearchService.summarize_public_pages(request(), rows, provider=provider)
    assert result.metadata['status'] == 'ok'


def test_a_conditional_paraphrase_keeps_the_actual_conjunctions_and_internal_references():
    rows = sources()
    condition = "Questa disposizione non si applica quando ricorre la condizione A [291] e la condizione B [292]."
    rows[1].content = condition
    rows[1].metadata['selection'] = {'passages': [{'text': condition, 'block_index': 12}]}
    result = LexResearchService.summarize_public_pages(request(), rows,
        provider=Provider('Il termine è di sei mesi [1]. La norma non si applica quando ricorre A oppure B [2].'))
    assert result.metadata['status'] == 'ok'
    assert 'A oppure B' not in result.text
    assert ').\n\nCondizione testuale della fonte:' in result.text
    assert condition in result.text
    assert '[291](' not in result.text and '[292](' not in result.text
    assert '[2](https://example.org/fonte-2)' in result.text
    assert result.metadata['source_conditions_preserved'][0]['block_index'] == 12


@pytest.mark.parametrize('multiple', [False, True])
def test_a_condition_cannot_be_assigned_without_one_unambiguous_source_passage(multiple):
    rows = sources()
    if multiple:
        rows[1].metadata['selection'] = {'passages': [
            {'text': 'La disposizione non si applica al caso A.'},
            {'text': 'La disposizione non si applica al caso B.'}]}
    result = LexResearchService.summarize_public_pages(request(), rows,
        provider=Provider('Il termine è di sei mesi [1]. La norma non si applica nel caso C [2].'))
    assert result.metadata['status'] == 'ambiguous_source_condition'
    assert result.text == ''


def test_an_already_literal_condition_is_preserved_without_a_new_substitution():
    rows = sources()
    condition = 'La disposizione non si applica quando ricorrono A e B.'
    rows[1].content = condition
    rows[1].metadata['selection'] = {'passages': [{'text': condition}]}
    result = LexResearchService.summarize_public_pages(request(), rows,
        provider=Provider(f'Il termine è di sei mesi [1]. “{condition}” [2].'))
    assert result.metadata['status'] == 'ok'
    assert not result.metadata.get('source_conditions_preserved')


def test_internal_numbered_notes_do_not_count_as_a_second_source_citation():
    rows = sources()
    rows[1].content = 'Il termine è di sei mesi secondo la nota [1] del documento.'
    result = LexResearchService.summarize_public_pages(request(), rows,
        provider=Provider(f'“{rows[1].content}” [2].'))
    assert result.metadata['status'] == 'source_comparison_incomplete'
    assert result.text == ''


def test_a_restored_condition_cites_only_its_actual_source():
    rows = sources()
    condition = 'La disposizione non si applica quando ricorrono A e B.'
    rows[1].content = condition
    rows[1].metadata['selection'] = {'passages': [{'text': condition}]}
    result = LexResearchService.summarize_public_pages(request(), rows,
        provider=Provider('Il termine è di sei mesi [1]. La norma non si applica nel caso A [1][2].'))
    assert result.metadata['status'] == 'ok'
    assert '” [2](https://example.org/fonte-2)' in result.text
    assert '” [1]' not in result.text


def test_a_condition_without_an_attributed_source_is_not_published():
    result = LexResearchService.summarize_public_pages(request(), sources(),
        provider=Provider('Il termine è di sei mesi [1][2]. La norma non si applica nel caso A.'))
    assert result.metadata['status'] == 'ambiguous_source_condition'
    assert result.text == ''


def test_every_source_attributed_to_a_quotation_must_contain_that_quotation():
    rows = sources()
    rows[1].content = 'Una diversa disposizione disciplina un altro procedimento.'
    result = LexResearchService.summarize_public_pages(request(), rows,
        provider=Provider('“Il termine è di sei mesi.” [1][2].'))
    assert result.metadata['status'] == 'unsupported_source_quotation'
    assert result.text == ''
