"""Il confronto riceve contenuti reali con criterio identico tra domini."""

import pytest

from lex.research.public_page_evidence import acquire_pages, page_evidence, select_passages


@pytest.mark.parametrize('question,expected', [
    ('Appello civile https://example.org/penale-amministrativo-tributario', {'civile'}),
    ('Articolo 327 c.p.c.', {'civile'}),
    ('Articolo 2043 c.c.', {'civile'}),
    ('Articolo 10 c.p.p.', {'penale'}),
    ('Termini del c.p.a.', {'amministrativo'}),
    ('I riti tributari', {'tributario'}),
    ('Confronta le fonti pubbliche', set()),
])
def test_explicit_rites_use_native_code_aliases_and_ignore_url_words(question, expected):
    from lex.research.public_page_evidence import explicit_public_rites

    assert explicit_public_rites(question) == expected


def test_no_window_fallback_reintroduces_a_short_page_outside_requested_rite():
    page = dict(status='read', url='https://example.org/atto', text='Il processo tributario ha un proprio termine.',
                blocks=[dict(index=0, kind='p', section=['Processo tributario'],
                             text='Il processo tributario ha un proprio termine.')])
    assert select_passages(page, 'Appello civile', max_chars=6000)['passages'] == []
    assert page_evidence(page, 'Appello civile', max_chars=6000) is None
    assert page['text'] == 'Il processo tributario ha un proprio termine.'


def test_specific_chapter_overrides_multi_rite_page_title():
    page = dict(text='Testo civile. Testo amministrativo.', blocks=[
        dict(index=0, kind='p', section=['Civile, amministrativo e tributario', 'Processo civile'],
             text='Il termine civile decorre dalla notificazione della sentenza.'),
        dict(index=1, kind='p', section=['Civile, amministrativo e tributario', 'Processo amministrativo'],
             text='Il termine amministrativo segue la propria disciplina.'),
    ])
    assert [p['block_index'] for p in select_passages(page, 'Termine civile')['passages']] == [0]


def test_short_dispositive_preserves_rule_and_condition_without_a_shared_keyword():
    page = dict(text='Testo completo della disposizione.', blocks=[
        dict(index=0, kind='p', section=['Articolo 327 codice di procedura civile', 'Dispositivo'],
             text='Indipendentemente dalla notificazione, il ricorso non può proporsi dopo decorsi sei mesi.'),
        dict(index=1, kind='p', section=['Articolo 327 codice di procedura civile', 'Dispositivo'],
             text='Questa disposizione non si applica quando ricorrono tutte le condizioni indicate.'),
    ])
    result = select_passages(page, 'Qual è il termine lungo?', max_chars=6000)
    assert [p['block_index'] for p in result['passages']] == [0, 1]


def test_appello_selection_keeps_shared_article_but_not_other_remedy_paragraphs():
    blocks = [
        dict(index=0, kind='p', section=['Processo civile'],
             text='Il ricorso in appello deve essere proposto entro trenta giorni dalla notifica della sentenza.'),
        dict(index=1, kind='p', section=['Processo civile'],
             text='Il ricorso per cassazione va presentato entro sessanta giorni dalla notifica della sentenza.'),
        dict(index=2, kind='p', section=['Processo civile'],
             text='Per la revocazione il termine dipende dal motivo previsto nella disposizione.'),
        dict(index=3, kind='p', section=['Dispositivo'],
             text='L’appello, il ricorso per cassazione e la revocazione non possono proporsi dopo decorsi sei mesi.'),
        dict(index=4, kind='p', section=['Dispositivo'],
             text='Questa disposizione non si applica quando sono dimostrate tutte le condizioni indicate.'),
    ]
    result = select_passages(dict(text='Inventario. ' * 300, blocks=blocks),
                             'Confronta il termine breve e lungo per l’appello civile', max_chars=1600,
                             semantic_scores={i: .8 for i in range(5)})
    assert [p['block_index'] for p in result['passages']] == [0, 3, 4]


def test_focused_comparison_starts_with_the_requested_rule_before_tool_description():
    blocks = [
        dict(index=0, kind='p', section=['Calcolatore'],
             text='Questa applicazione calcola il termine di impugnazione del provvedimento civile.'),
        dict(index=1, kind='p', section=['Processo civile'],
             text='Il termine per l’appello decorre dalla notifica della sentenza.'),
    ]
    result = select_passages(dict(text='Inventario originale. ' * 200, blocks=blocks),
                             'Confronta il termine per l’appello civile', max_chars=1000,
                             semantic_scores={0: .8, 1: .8})
    assert result['passages'][0]['block_index'] == 1
    assert blocks[0]['index'] == 0 and blocks[1]['index'] == 1


def test_generic_reading_separates_publisher_header_from_legal_intro():
    from lex.sources.html_structure import read_html_structure

    html = ('<div id="HEADER"><a href="/"><img alt="Risorse" src="logo.png"></a>'
            '<h1>Risorse</h1><p>Venerdì 16 ottobre 2026</p></div>'
            '<div id="site_intro">Il sito in un click! '
            '<a href="/chi-siamo">Chi siamo</a><a href="/servizi">Servizi</a></div>'
            '<article><h1>Disposizione</h1><div class="intro">Premessa giuridica da conservare.</div>'
            '<p>Il termine decorre dalla pubblicazione della sentenza.</p></article>')
    page = read_html_structure(html.encode(), 'text/html; charset=utf-8', url='https://example.org/atto')
    selected = select_passages(page, 'Leggi questa pagina pubblica', max_chars=6000)
    text = ' '.join(p['text'] for p in selected['passages'])
    assert 'Venerdì' in page['full_text'] and 'Il sito in un click' in page['full_text']
    assert 'Venerdì' not in text and 'Il sito in un click' not in text
    assert 'Premessa giuridica da conservare' in text


def test_publisher_header_marking_also_works_when_the_page_has_no_main_element():
    from lex.sources.html_structure import read_html_structure

    html = ('<div id="HEADER"><a href="/"><img alt="Risorse" src="logo.png"></a>'
            '<h1>Risorse</h1><p>Venerdì 16 ottobre 2026</p></div>'
            '<div id="site_intro">Il sito in un click! '
            '<a href="/chi-siamo">Chi siamo</a><a href="/servizi">Servizi</a></div>'
            '<h1>Disposizione</h1><div class="intro">Premessa giuridica da conservare.</div>'
            '<p>Il termine decorre dalla pubblicazione della sentenza.</p>')
    page = read_html_structure(html.encode(), 'text/html; charset=utf-8', url='https://other.example/atto')
    selected = select_passages(page, 'Leggi questa pagina pubblica', max_chars=6000)
    text = ' '.join(p['text'] for p in selected['passages'])
    assert 'Venerdì' not in text and 'Il sito in un click' not in text
    assert 'Premessa giuridica da conservare' in text


def test_native_embedding_batch_is_bounded_and_represents_both_pages(monkeypatch):
    import numpy as np

    from lex.research.public_page_evidence import _native_semantic_ranking

    calls = []

    class Embedder:
        modello = 'embeddinggemma:300m'

        def __init__(self, **kwargs):
            assert kwargs == dict(modello=self.modello, timeout=8, tentativi=1, paralleli=1)

        def embed(self, texts):
            calls.append(texts)
            return np.ones((len(texts), 3))

    monkeypatch.setattr('lex.ricerca_giuridica.embedding.OllamaEmbedder', Embedder)
    pages = [dict(blocks=[dict(index=i, kind='p', section=[title],
                              text=f'Il termine lungo della fonte {title} è descritto in questo passaggio completo numero {i}.')
                         for i in range(30)]) for title in ('prima', 'seconda')]
    result = _native_semantic_ranking(pages, 'termine lungo')
    assert result['candidate_count'] == 16
    assert len(calls) == 1 and len(calls[0]) == 17
    assert len(result['scores'][0]) == len(result['scores'][1]) == 8
    assert result['limited_pool'] is True


def test_explicit_civil_request_does_not_import_other_rites_from_url_or_sections():
    blocks = [
        dict(index=0, kind='p', section=['Le impugnazioni nel processo civile'],
             text='Il ricorso in appello deve essere proposto entro trenta giorni dalla notifica della sentenza.'),
        dict(index=1, kind='p', section=['Le impugnazioni nel processo amministrativo'],
             text='Per la revocazione nei casi indicati sono previsti sessanta giorni dalla scoperta dei vizi.'),
        dict(index=2, kind='p', section=['Le impugnazioni nel processo tributario'],
             text='Nel processo tributario si applicano i termini indicati dalla disposizione richiamata.'),
    ]
    question = 'Confronta il termine per l’appello civile: https://example.org/civile-amministrativo-tributario.php'
    result = select_passages(dict(text='Inventario completo. ' * 100, blocks=blocks), question,
                             max_chars=1200, semantic_scores={0: .8, 1: .9, 2: .9})
    assert [p['block_index'] for p in result['passages']] == [0]
    assert len(blocks) == 3  # l'inventario originale non viene riscritto


def test_explicit_multiple_rites_are_preserved_without_an_unrequested_third_rite():
    blocks = [dict(index=i, kind='p', section=[f'Processo {rite}'],
                   text=f'Il termine per il processo {rite} è indicato nel testo della disposizione.')
              for i, rite in enumerate(('civile', 'amministrativo', 'tributario'))]
    result = select_passages(dict(text='Inventario completo. ' * 100, blocks=blocks),
                             'Confronta civile e amministrativo', max_chars=1200,
                             semantic_scores={0: .8, 1: .8, 2: .9})
    assert [p['block_index'] for p in result['passages']] == [0, 1]


def test_generic_reading_does_not_start_an_unnecessary_embedding_batch():
    calls = []

    class Reader:
        def read(self, url):
            return dict(url=url, status='read', text='Testo della pagina. ' * 100,
                        blocks=[dict(index=0, kind='p', section=['Contenuto'],
                                     text='La pagina presenta il contenuto effettivamente disponibile al lettore.')])

    def ranker(*args):
        calls.append(args)
        raise AssertionError('La lettura generica non richiede una classifica semantica.')

    result = acquire_pages([dict(url='https://example.org/a'), dict(url='https://other.example/b')],
                           'Leggi queste due pagine pubbliche e indica quali informazioni riesci effettivamente a recuperare, citando separatamente i due link. Non usare dati dello studio.',
                           reader=Reader(), passage_ranker=ranker)
    assert calls == []
    assert result['read_count'] == 2


def test_short_page_selection_excludes_technical_footer_without_losing_original():
    from lex.sources.html_structure import read_html_structure

    page = read_html_structure(
        b'<main><h1>Norma</h1><p>Il termine decorre dalla pubblicazione della sentenza.</p>'
        b'<div>Pagina generata in 0.004 secondi</div></main>',
        'text/html; charset=utf-8', url='https://example.org/norma')
    result = select_passages(page, 'Leggi questa pagina pubblica', max_chars=6000)
    assert 'Pagina generata' in page['full_text']
    assert 'pubblicazione' in ' '.join(p['text'] for p in result['passages'])
    assert 'Pagina generata' not in ' '.join(p['text'] for p in result['passages'])


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
