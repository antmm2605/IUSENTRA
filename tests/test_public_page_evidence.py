"""Il confronto riceve contenuti reali con criterio identico tra domini."""

from lex.research.public_page_evidence import acquire_pages, page_evidence, select_passages


def test_same_content_and_question_receive_same_selection_on_different_sites():
    text = ('Contenuto introduttivo. ' * 120) + 'Termine lungo di impugnazione: sei mesi. ' * 20
    first = dict(text=text, url='https://example.org/a', status='read')
    second = dict(first, url='https://other.example/norma')
    assert select_passages(first, 'termine lungo impugnazione', max_chars=1200) == select_passages(second, 'termine lungo impugnazione', max_chars=1200)
    assert 'sei mesi' in select_passages(first, 'termine lungo impugnazione', max_chars=1200)['passages'][0]['text']


def test_unreadable_pages_never_become_evidence_from_search_snippet():
    for status in ('robots_blocked', 'network_error', 'empty', 'http_error'):
        assert page_evidence(dict(status=status, text='', excerpt='Sei mesi'), 'termine') is None


def test_source_identity_and_partial_context_remain_explicit():
    page = dict(status='read', text='Fonte pubblica. ' * 1000, url='https://example.org/a',
                final_url='https://example.org/b', sha256='abc', fetched_at='2026-10-15T18:00:00Z')
    evidence = page_evidence(page, 'fonte', max_chars=1000)
    assert evidence.source_id == 'https://example.org/b'
    assert evidence.metadata['sha256'] == 'abc'
    assert evidence.metadata['selection']['complete_context'] is False
    assert evidence.metadata['selection']['total_characters'] == len(page['text'])
    assert evidence.verified_reference is False


def test_acquisition_preserves_failed_urls_without_using_discovery_snippets():
    class Reader:
        def read(self, url):
            if url.endswith('/negata'):
                return dict(url=url, status='robots_blocked', text='')
            return dict(url=url, status='read', text='Testo effettivamente letto.', sha256='a')

    result = acquire_pages([dict(url='https://example.org/atto', excerpt='Snippet estraneo'),
                            dict(url='https://example.org/negata', excerpt='Dato inventato')],
                           'domanda comune', reader=Reader())
    assert result['visited_count'] == 2
    assert result['read_count'] == 1
    assert result['visits'][1]['status'] == 'robots_blocked'
    assert result['items'][0].content == 'Testo effettivamente letto.'
    assert result['question_used'] == 'domanda comune'


def test_duplicate_url_is_read_once_and_identical_content_keeps_both_origins():
    calls = []

    class Reader:
        def read(self, url):
            calls.append(url)
            return dict(url=url, status='read', text='Stesso testo pubblico.', sha256='same')

    result = acquire_pages([dict(url='https://example.org/a'), dict(url='https://example.org/a'),
                            dict(url='https://other.example/a')], 'testo', reader=Reader())
    assert len(calls) == 2
    assert len(result['items']) == 2
    assert result['visits'][1]['same_content_as'] == 'https://example.org/a'
    assert result['saved_to_db'] is False


def test_no_unrequested_expansion_or_reads_beyond_bound():
    class Reader:
        def read(self, url):
            assert url == 'https://example.org/a'
            return dict(url=url, status='read', text='Testo.', links=[{'url': 'https://other.example/unrequested'}])

    result = acquire_pages([dict(url='https://example.org/a'), dict(url='https://other.example/b')],
                           'testo', reader=Reader(), max_sources=1)
    assert result['visited_count'] == 1


def test_article_number_in_url_is_used_but_publisher_domain_is_not_topic():
    page = dict(text=('Brocardi editore informazione. ' * 100) + ('Articolo 327: termine lungo. ' * 50))
    selected = select_passages(page, 'Leggi https://www.brocardi.it/codice/art327.html', max_chars=1200)
    assert '327' in selected['passages'][0]['text']


def test_malformed_url_in_question_does_not_discard_a_page_already_read():
    result = select_passages({'text': 'Testo della norma.'}, 'Leggi http://[ e la norma')
    assert result['passages'][0]['text'] == 'Testo della norma.'


def test_complete_article_blocks_are_not_cut_at_the_term_or_mixed_with_menu():
    text = 'Menu estraneo. ' * 150 + 'Il termine è di sei mesi dalla pubblicazione della sentenza.'
    block = dict(index=1, kind='div', text='Il termine è di sei mesi dalla pubblicazione della sentenza.', section=['Dispositivo'])
    result = select_passages(dict(text=text, blocks=[block]), 'termine mesi', max_chars=100)
    assert result['selection_method'] == 'shared_query_complete_blocks_v1'
    assert result['passages'][0]['text'] == block['text']
    assert result['passages'][0]['section'] == ['Dispositivo']
    assert result['complete_context'] is False


def test_semantic_selection_preserves_rule_and_exception_before_secondary_commentary():
    blocks = [
        dict(index=0, kind='div', text='Il termine della disposizione è di sei mesi dalla pubblicazione della sentenza.', section=['Dispositivo']),
        dict(index=1, kind='div', text='La disposizione non si applica quando è dimostrata la specifica eccezione.', section=['Dispositivo']),
        dict(index=2, kind='p', text='Commento sul termine lungo e sulle sue diverse conseguenze. ' * 5, section=['Note']),
        dict(index=3, kind='p', text='Pubblicità del sito e informazioni sul servizio commerciale.', section=['Servizi']),
    ]
    result = select_passages(dict(text='Testo integrale. ' * 300, blocks=blocks), 'termine lungo',
                             max_chars=500, semantic_scores={0: 0.6, 1: 0.3, 2: 0.8, 3: 0.1})
    assert [passage['block_index'] for passage in result['passages']][:2] == [0, 1]
    assert not any(passage['block_index'] == 3 for passage in result['passages'])


def test_unscored_blocks_do_not_override_semantic_results_with_another_scale():
    blocks = [dict(index=0, kind='p', text='Termine lungo di impugnazione. ' * 4, section=['Norma']),
              dict(index=1, kind='p', text='Termine lungo di impugnazione. ' * 20, section=['Altra sezione'])]
    result = select_passages(dict(text='Testo integrale. ' * 300, blocks=blocks), 'termine lungo impugnazione',
                             max_chars=400, semantic_scores={0: 0.7})
    assert all(passage['block_index'] == 0 for passage in result['passages'])
