from __future__ import annotations

from lex.sources.polite_fetcher import PoliteFetcher, is_public_http_url


class _FakeResponse:
    def __init__(self, content: bytes = b"<html><body>testo</body></html>", status: int = 200, content_type: str = "text/html"):
        self.content = content
        self.status_code = status
        self.url = "https://www.normattiva.it/pagina"
        self.headers = {"Content-Type": content_type}


def _fetcher(http_get, **kwargs):
    defaults = {
        "sleep_fn": lambda seconds: None,
        "now_fn": lambda: 0.0,
        "iso_now": lambda: "2026-07-02T10:00:00+00:00",
    }
    defaults.update(kwargs)
    return PoliteFetcher(http_get=http_get, **defaults)


def test_guardia_url_pubbliche():
    assert is_public_http_url("https://www.normattiva.it/x") is True
    assert is_public_http_url("http://192.168.1.1/x") is False
    assert is_public_http_url("http://127.0.0.1/x") is False
    assert is_public_http_url("http://localhost/x") is False
    assert is_public_http_url("ftp://normattiva.it/x") is False
    assert is_public_http_url("http://intranet.local/x") is False


def test_robots_allow_e_deny():
    def http_get(url, headers=None, **kwargs):
        if url.endswith("/robots.txt"):
            return _FakeResponse(b"User-agent: *\nDisallow: /privato/\n", 200, "text/plain")
        return _FakeResponse()

    fetcher = _fetcher(http_get)
    assert fetcher.fetch("https://www.normattiva.it/pagina").status == "ok"
    blocked = fetcher.fetch("https://www.normattiva.it/privato/riservato")
    assert blocked.status == "robots_blocked"
    assert blocked.warnings


def test_robots_4xx_consente_ma_errore_rete_nega_fail_closed():
    def http_get_404(url, headers=None, **kwargs):
        if url.endswith("/robots.txt"):
            return _FakeResponse(b"", 404, "text/plain")
        return _FakeResponse()

    assert _fetcher(http_get_404).fetch("https://www.normattiva.it/pagina").status == "ok"

    def http_get_broken(url, headers=None, **kwargs):
        raise ConnectionError("rete non disponibile")

    result = _fetcher(http_get_broken).fetch("https://www.normattiva.it/pagina")
    assert result.status == "robots_blocked"
    assert "fail-closed" in result.warnings[0]


def test_rate_limit_per_dominio_con_clock_finto():
    def http_get(url, headers=None, **kwargs):
        if url.endswith("/robots.txt"):
            return _FakeResponse(b"", 404, "text/plain")
        return _FakeResponse()

    slept: list[float] = []
    clock = {"value": 0.0}
    fetcher = _fetcher(
        http_get,
        min_interval_seconds=2.0,
        sleep_fn=lambda seconds: slept.append(round(seconds, 3)),
        now_fn=lambda: clock["value"],
    )
    fetcher.fetch("https://www.normattiva.it/a")
    clock["value"] = 0.5
    fetcher.fetch("https://www.normattiva.it/b")
    assert slept == [1.5]  # attesa residua rispetto all'intervallo minimo


def test_max_bytes_scarta_risposte_grandi():
    def http_get(url, headers=None, **kwargs):
        if url.endswith("/robots.txt"):
            return _FakeResponse(b"", 404, "text/plain")
        return _FakeResponse(b"x" * 5000)

    result = _fetcher(http_get, max_bytes=1024).fetch("https://www.normattiva.it/big")
    assert result.status == "too_large"
    assert result.content is None


def test_url_privata_rifiutata_senza_chiamate():
    calls: list[str] = []

    def http_get(url, headers=None, **kwargs):
        calls.append(url)
        return _FakeResponse()

    result = _fetcher(http_get).fetch("http://10.0.0.1/segreto")
    assert result.status == "invalid_url"
    assert calls == []


def test_http_error_riportato_senza_eccezioni():
    class _HttpError(Exception):
        def __init__(self):
            super().__init__("404")
            self.response = _FakeResponse(b"", 404)

    def http_get(url, headers=None, **kwargs):
        if url.endswith("/robots.txt"):
            return _FakeResponse(b"", 404, "text/plain")
        raise _HttpError()

    result = _fetcher(http_get).fetch("https://www.normattiva.it/assente")
    assert result.status == "http_error"
    assert result.http_status == 404
