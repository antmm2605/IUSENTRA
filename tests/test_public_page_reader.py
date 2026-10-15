"""Stessa lettura governata su siti diversi, senza rete nei guardrail."""

from lex.sources.public_page_reader import PublicPageReader


def test_credential_query_is_rejected_before_any_network_request():
    calls = []
    reader = PublicPageReader(transport=lambda *args, **kwargs: calls.append(args))
    result = reader.read('https://example.org/documento?access_token=riservato')
    assert result['status'] == 'invalid_url'
    assert calls == []


def test_real_content_and_provenance_replace_search_snippets():
    calls = []

    def transport(url, **options):
        calls.append((url, options))
        if url.endswith('/robots.txt'):
            return dict(url=url, status=404, content_type='text/plain', body=b'')
        options['before_request'](url)
        return dict(url=url, status=200, content_type='text/html; charset=utf-8',
                    body='<main><h1>Fonte</h1><p>Il testo è disponibile.</p></main>'.encode())

    reader = PublicPageReader(transport=transport)
    result = reader.read('https://example.org/norma')
    assert result['status'] == 'read'
    assert 'Il testo è disponibile.' in result['text']
    assert len(result['sha256']) == 64
    assert result['verified_reference'] is False
    assert [url for url, _ in calls] == ['https://example.org/robots.txt', 'https://example.org/norma']
    assert calls[0][1]['user_agent'] == calls[1][1]['user_agent']


def test_robots_denial_does_not_fetch_document():
    calls = []

    def transport(url, **options):
        calls.append(url)
        return dict(url=url, status=200, content_type='text/plain',
                    body=b'User-agent: *\nDisallow: /')

    result = PublicPageReader(transport=transport).read('https://example.org/atto')
    assert result['status'] == 'robots_blocked'
    assert calls == ['https://example.org/robots.txt']


def test_cross_domain_redirect_checks_destination_robots_before_content():
    calls = []

    def transport(url, **options):
        calls.append(url)
        if url == 'https://example.org/robots.txt':
            return dict(url=url, status=404, content_type='text/plain', body=b'')
        if url == 'https://other.example/robots.txt':
            return dict(url=url, status=200, content_type='text/plain', body=b'User-agent: *\nDisallow: /')
        options['before_request']('https://other.example/riservato')
        raise AssertionError('Destinazione negata non deve essere letta')

    result = PublicPageReader(transport=transport).read('https://example.org/atto')
    assert result['status'] == 'network_error'
    assert 'https://other.example/robots.txt' in calls
    assert result['text'] == ''


def test_robots_server_error_is_not_a_successful_empty_document():
    def transport(url, **options):
        assert url.endswith('/robots.txt')
        return dict(url=url, status=503, content_type='text/plain', body=b'Unavailable')

    result = PublicPageReader(transport=transport).read('https://example.org/atto')
    assert result['status'] == 'robots_blocked'
    assert result['text'] == ''


def test_http_denial_is_not_readable_evidence():
    def transport(url, **options):
        return dict(url=url, status=404 if url.endswith('/robots.txt') else 403,
                    content_type='text/html', body=b'<p>Access denied</p>')

    result = PublicPageReader(transport=transport).read('https://example.org/atto')
    assert result['status'] == 'http_error'
    assert result['text'] == ''


def test_invalid_url_does_not_reach_transport():
    def forbidden(*args, **kwargs):
        raise AssertionError('Nessuna acquisizione prevista')

    result = PublicPageReader(transport=forbidden).read('https://user:secret@example.org/')
    assert result['status'] == 'invalid_url'


def test_redirect_cannot_reuse_robots_from_another_scheme():
    calls = []

    def transport(url, **options):
        calls.append(url)
        if url == 'https://example.org/robots.txt':
            return dict(url=url, status=404, content_type='text/plain', body=b'')
        if url == 'http://example.org/robots.txt':
            return dict(url=url, status=200, content_type='text/plain', body=b'User-agent: *\nDisallow: /')
        options['before_request']('http://example.org/atto')
        raise AssertionError('La policy HTTPS non autorizza la destinazione HTTP')

    result = PublicPageReader(transport=transport).read('https://example.org/atto')
    assert result['text'] == ''
    assert 'http://example.org/robots.txt' in calls


def test_excessive_crawl_delay_is_explicit_without_waiting_or_reading_page():
    def transport(url, **options):
        if url.endswith('/robots.txt'):
            return dict(url=url, status=200, content_type='text/plain',
                        body=b'User-agent: *\nCrawl-delay: 120')
        options['before_request'](url)
        raise AssertionError('Il documento non deve essere acquisito')

    result = PublicPageReader(transport=transport).read('https://example.org/atto')
    assert result['status'] == 'network_error'
    assert 'Intervallo richiesto' in result['warnings'][0]


def test_http200_access_interstitial_is_not_read_as_a_legal_document():
    def transport(url, **options):
        return dict(url=url, status=404 if url.endswith('/robots.txt') else 200,
                    content_type='text/html', body=b'<title>Request Rejected</title><p>The requested URL was rejected.</p>')

    result = PublicPageReader(transport=transport).read('https://example.org/atto')
    assert result['status'] == 'access_interstitial'
    assert result['text'] == ''


def test_article_about_access_technology_is_not_hidden_as_a_challenge():
    def transport(url, **options):
        return dict(url=url, status=404 if url.endswith('/robots.txt') else 200,
                    content_type='text/html', body=b'<title>Privacy e captcha</title><main><p>Il trattamento dei dati mediante captcha.</p></main>')

    result = PublicPageReader(transport=transport).read('https://example.org/atto')
    assert result['status'] == 'read'
    assert 'trattamento' in result['text']
