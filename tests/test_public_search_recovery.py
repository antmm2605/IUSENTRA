"""Un canale fallito non è una ricerca negativa da riusare in cache."""

from types import SimpleNamespace

from lex.retrieval import official_web


def test_failed_channels_do_not_freeze_next_user_request(monkeypatch):
    monkeypatch.setattr(official_web, '_SEARCH_CACHE', {})
    diagnostics = []

    def failed(*args, **kwargs):
        raise TimeoutError('tempo scaduto')

    question = 'impugnazione civile termine lungo prova recupero'
    assert official_web.search_free_public_web(question, request_get=failed, diagnostics=diagnostics) == []
    assert official_web._SEARCH_CACHE == {}
    assert all(row['status'] == 'transport_error' for row in diagnostics)
    body = '<div class="result"><a class="result__a" href="https://example.org/norma">Norma pertinente</a><div class="result__snippet">Testo della ricerca</div></div>'
    recovered = official_web.search_free_public_web(question, request_get=lambda *a, **k: SimpleNamespace(status_code=200, text=body))
    assert recovered[0]['url'] == 'https://example.org/norma'


def test_challenge_page_is_not_cached_as_absence_of_legal_sources(monkeypatch):
    monkeypatch.setattr(official_web, '_SEARCH_CACHE', {})
    diagnostics = []
    result = official_web.search_free_public_web('normativa penale prova senza risultati',
             request_get=lambda *a, **k: SimpleNamespace(status_code=200, text='<html><p>Verifica accesso</p></html>'),
             diagnostics=diagnostics)
    assert result == []
    assert official_web._SEARCH_CACHE == {}
    assert all(row['status'] == 'no_recognized_results' for row in diagnostics)
