"""Il riscontro del testo resta distinto dalla sola costruzione dell'URL."""
from types import SimpleNamespace

from pct.openga_recupero import _SCHEMI, recupera_testo

XML = b"""<GA><Provvedimento><meta><descrittori>
<fascicolo anno="2023" n="00355"/></descrittori><ricorso NRG="201900721"/>
<dataPubblicazione>24/04/2023</dataPubblicazione><tipologia>Sentenza</tipologia></meta><epigrafe>Organo sintetico</epigrafe>
<dispositivo>Testo sintetico</dispositivo></Provvedimento></GA>"""
ROW = {"tipo": "Sentenza", "sede": "020", "anno": 2023, "numero": "202300355", "ricorso": "201900721"}


class Fetcher:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.urls = []

    def fetch(self, url):
        self.urls.append(url)
        return next(self.responses)


def response(raw=XML, status="ok", http=200):
    return SimpleNamespace(content=raw, status=status, http_status=http)


def test_no_automatic_certification_without_court_check():
    fetcher = Fetcher([])
    assert recupera_testo(ROW, fetcher=fetcher, verifica_organo=None)["stato"] == "intervento_necessario"
    assert fetcher.urls == []


def test_candidate_only_becomes_text_after_identity_check():
    fetcher = Fetcher([response(http=404), response()])
    result = recupera_testo(ROW, fetcher=fetcher, verifica_organo=lambda raw, row: True)
    assert result["stato"] == "acquisito"
    assert "_20.html" in result["documento"]["provenienza"]["url"]
    assert result["documento"]["approvazione_avvocato"] is False


def test_wrong_court_never_acquired():
    fetcher = Fetcher([response(), response(), response()])
    assert recupera_testo(ROW, fetcher=fetcher,
                          verifica_organo=lambda raw, row: False)["stato"] == "non_trovato"


def test_robots_block_stops_other_candidates():
    fetcher = Fetcher([response(status="robots_blocked")])
    assert recupera_testo(ROW, fetcher=fetcher,
                          verifica_organo=lambda raw, row: True)["stato"] == "intervento_necessario"
    assert len(fetcher.urls) == 1


def test_wrong_identity_never_acquired():
    fetcher = Fetcher([response(XML.replace(b'anno="2023"', b'anno="2022"'))] * 3)
    assert recupera_testo(ROW, fetcher=fetcher,
                          verifica_organo=lambda raw, row: True)["stato"] == "non_trovato"


def test_registry_covers_catalogue_offices_without_claiming_fetch_success():
    assert len(_SCHEMI) == 31
    for office in _SCHEMI:
        assert recupera_testo({**ROW, "sede": office}, verifica_organo=None)["stato"] == "intervento_necessario"


def test_download_rejects_external_host_before_network(monkeypatch):
    import pytest

    from pct.openga_recupero import _get_limitato
    monkeypatch.setattr("requests.Session", lambda: pytest.fail("Rete non deve partire"))
    for url in ["http://mdp.giustizia-amministrativa.it/visualizza/",
                "https://example.org/visualizza/",
                "https://mdp.giustizia-amministrativa.it@127.0.0.1/visualizza/",
                "https://mdp.giustizia-amministrativa.it:8443/visualizza/"]:
        with pytest.raises(ValueError):
            _get_limitato(url, headers={})


def test_external_redirect_is_never_followed(monkeypatch):
    import pytest

    from pct.openga_recupero import _get_limitato
    class Response:
        status_code = 302
        def __init__(self):
            self.headers = {"Location": "https://example.org/steal"}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    class Session:
        def __init__(self):
            self.calls = []
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()
    session = Session()
    monkeypatch.setattr("requests.Session", lambda: session)
    with pytest.raises(ValueError):
        _get_limitato("https://mdp.giustizia-amministrativa.it/visualizza/", headers={})
    assert len(session.calls) == 1
    assert session.calls[0][1]["allow_redirects"] is False


def test_download_stops_after_byte_limit(monkeypatch):
    import pytest

    from pct.openga_recupero import _get_limitato
    class Response:
        status_code = 200
        def __init__(self):
            self.headers = {}
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def iter_content(self, size):
            yield b"x" * 1_500_000
            yield b"x" * 1_500_000
    class Session:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, *args, **kwargs):
            return Response()
    monkeypatch.setattr("requests.Session", Session)
    with pytest.raises(ValueError, match="troppo grande"):
        _get_limitato("https://mdp.giustizia-amministrativa.it/visualizza/", headers={})


def test_access_limit_stops_all_variants():
    fetcher = Fetcher([response(http=429)])
    result = recupera_testo(ROW, fetcher=fetcher, verifica_organo=lambda raw, row: True)
    assert result["stato"] == "intervento_necessario"
    assert len(fetcher.urls) == 1


def test_server_error_is_not_reported_as_missing_document():
    fetcher = Fetcher([response(status="http_error", http=503)])
    result = recupera_testo(ROW, fetcher=fetcher, verifica_organo=lambda raw, row: True)
    assert result["stato"] == "intervento_necessario"
    assert len(fetcher.urls) == 1
    assert result["diagnostica"][0]["stato_http"] == 503


def test_rejected_source_preserves_fingerprint_and_reason_without_content():
    from hashlib import sha256
    raw = b"<html>temporarily unavailable</html>"
    fetcher = Fetcher([response(raw)] * 3)
    result = recupera_testo(ROW, fetcher=fetcher, verifica_organo=lambda raw, row: True)
    assert result["stato"] == "non_trovato"
    assert len(result["diagnostica"]) == 3
    for evidence in result["diagnostica"]:
        assert evidence["sha256"] == sha256(raw).hexdigest()
        assert evidence["byte"] == len(raw)
        assert evidence["rifiuto"] == "Non è un singolo provvedimento ufficiale."
        assert "content" not in evidence
