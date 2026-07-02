"""Provider web governato del ciclo autonomo: nessuna rete reale, request_get finto."""

from __future__ import annotations

from lex.autonomy.discovery import ConfigurableWebSearchProvider

_FAKE_DDG_HTML = """
<html><body>
<div class="result">
  <a class="result__a" href="https://www.normattiva.it/uri-res/N2Ls?urn:test-art-9876">
    Art. 9876 — disposizione di prova
  </a>
  <a class="result__snippet">Estratto della disposizione di prova su Normattiva.</a>
</div>
<div class="result">
  <a class="result__a" href="https://blog-non-ufficiale.example.com/commento">Commento non ufficiale</a>
</div>
</body></html>
"""


class _FakeResponse:
    status_code = 200
    text = _FAKE_DDG_HTML


def test_provider_web_filtra_su_domini_governati_e_non_tocca_la_rete():
    calls: list[str] = []

    def fake_get(url, params=None, headers=None, timeout=None, **kwargs):
        calls.append(str((params or {}).get("q", "")))
        return _FakeResponse()

    provider = ConfigurableWebSearchProvider(source_ids=["normattiva"], request_get=fake_get, limit_results=4)
    candidates = provider.search("art. 9876 disposizione di prova unica xzq", limit=4)

    assert calls, "il provider deve usare il request_get iniettato"
    urls = [candidate.url for candidate in candidates]
    assert "https://www.normattiva.it/uri-res/N2Ls?urn:test-art-9876" in urls
    # Il dominio fuori allowlist non passa mai il filtro governato.
    assert all("blog-non-ufficiale" not in url for url in urls)
    assert all(candidate.discovered_by == "official_web" for candidate in candidates)


def test_provider_web_rimuove_i_token_site_dalle_query():
    captured: list[str] = []

    def fake_get(url, params=None, headers=None, timeout=None, **kwargs):
        captured.append(str((params or {}).get("q", "")))
        return _FakeResponse()

    provider = ConfigurableWebSearchProvider(source_ids=["normattiva"], request_get=fake_get, limit_results=2)
    provider.search("art. 5432 prova doppione qqz site:normattiva.it", limit=2)
    # official_web antepone il proprio site:<dominio>: il token del query_builder
    # non deve comparire una seconda volta dentro la query inoltrata.
    assert captured
    assert all(query.count("site:") == 1 for query in captured)


def test_provider_web_degrada_a_lista_vuota_su_errori():
    def broken_get(url, params=None, headers=None, timeout=None, **kwargs):
        raise ConnectionError("rete non disponibile")

    provider = ConfigurableWebSearchProvider(source_ids=["normattiva"], request_get=broken_get, limit_results=2)
    assert provider.search("art. 1111 prova errore rete kkj", limit=2) == []
