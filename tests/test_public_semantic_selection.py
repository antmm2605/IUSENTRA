"""Un solo lotto embedding nativo, senza modelli o corpus alternativi."""

import numpy as np
import pytest

from lex.research.public_page_evidence import semantic_block_scores


def page(index=0):
    return {'blocks': [{'index': index, 'kind': 'p', 'text': 'Testo pubblico pertinente sul termine di impugnazione della sentenza. ', 'section': ['Dispositivo']}]}


def test_common_question_and_document_prefixes_use_one_batch():
    calls = []

    class Embedder:
        modello = 'embeddinggemma:300m'

        def embed(self, inputs):
            calls.append(inputs)
            return np.array([[1., 0.], [0.8, 0.6], [0., 1.]])

    result = semantic_block_scores([page(), page(3)], 'termine lungo', embedder=Embedder())
    assert len(calls) == 1
    assert calls[0][0] == 'task: search result | query: termine lungo'
    assert all(text.startswith('title: Dispositivo | text: ') for text in calls[0][1:])
    assert result['scores'][0][0] == pytest.approx(0.8)
    assert result['scores'][1][3] == 0
    assert result['limited_pool'] is False


def test_bounded_pool_keeps_sources_in_round_robin_and_declares_omissions():
    class Embedder:
        modello = 'embeddinggemma:300m'

        def embed(self, inputs):
            return np.ones((len(inputs), 2))

    many = page()
    many['blocks'] += [dict(many['blocks'][0], index=i) for i in range(1, 10)]
    result = semantic_block_scores([many, page(20)], 'termine', embedder=Embedder(), max_candidates=2)
    assert set(result['scores']) == {0, 1}
    assert result['candidate_count'] == 2
    assert result['available_count'] == 11
    assert result['limited_pool'] is True


@pytest.mark.parametrize('bad', [np.zeros((2, 2)), np.array([[1., 0.], [np.nan, 1.]]), np.ones((1, 2))])
def test_invalid_embedding_is_not_a_successful_ranking(bad):
    class Embedder:
        modello = 'embeddinggemma:300m'

        def embed(self, inputs):
            return bad

    with pytest.raises(ValueError):
        semantic_block_scores([page()], 'termine', embedder=Embedder())


def test_candidate_model_cannot_be_activated_by_this_reader():
    class Embedder:
        modello = 'another-model'

        def embed(self, inputs):
            raise AssertionError('Il modello non autorizzato non deve partire')

    with pytest.raises(ValueError, match='300M'):
        semantic_block_scores([page()], 'termine', embedder=Embedder())


def test_generic_reading_instructions_use_one_common_subject_from_all_page_titles():
    calls = []

    class Embedder:
        modello = 'embeddinggemma:300m'

        def embed(self, inputs):
            calls.append(inputs)
            return np.ones((len(inputs), 2))

    pages = [dict(page(), title='Termini impugnazioni civile amministrativo tributario'),
             dict(page(3), title='Articolo 327 codice procedura civile')]
    question = ('Leggi queste due pagine pubbliche e indica quali informazioni riesci effettivamente '
                'a recuperare, citando separatamente i due link: https://example.org/a e https://example.org/b. '
                'Non usare dati dello studio.')
    result = semantic_block_scores(pages, question, embedder=Embedder())
    assert len(calls) == 1
    assert result['query_origin'] == 'common_page_titles'
    assert len(result['query_sha256']) == 64
    assert calls[0][0] == ('task: search result | query: Contenuti delle pagine: '
                           'Termini impugnazioni civile amministrativo tributario | Articolo 327 codice procedura civile')


def test_bounded_pool_ranks_requested_rule_before_keyword_heavy_commentary():
    class Embedder:
        modello = 'embeddinggemma:300m'
        def embed(self, inputs):
            return np.ones((len(inputs), 2))
    blocks = [dict(index=i, kind='p', section=['Commento'], text='Confronta termine breve lungo civile decorrenza notifica pubblicazione. ' * 2) for i in range(20)]
    blocks.append(dict(index=30, kind='p', section=['Processo civile'], text='Il ricorso in appello deve essere proposto entro trenta giorni dalla notificazione della sentenza.'))
    result = semantic_block_scores([{'blocks': blocks}], 'Confronta termine breve lungo appello civile con decorrenze', embedder=Embedder(), max_candidates=2)
    assert 30 in result['scores'][0]
