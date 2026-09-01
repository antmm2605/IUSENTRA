from __future__ import annotations

from lex.autonomy.discovery import CompositeSearchProvider, LocalArchiveSearchProvider, StaticSearchProvider
from lex.retrieval import official_sources_retriever as retriever
from lex.sources.models import SourceCandidate

_RIGA_NORMATTIVA = {
    "titolo": "LEGGE 7 agosto 1990, n. 241",
    "url_origine": "urn:nir:stato:legge:1990-08-07;241",
    "testo": "La L. 241/1990 disciplina il procedimento amministrativo e il diritto di accesso agli atti.",
    "fonte": "Normattiva",
}
_RIGA_GAZZETTA = {
    "titolo": "GU Serie Generale — decreto legislativo",
    "url_origine": "https://www.gazzettaufficiale.it/eli/id/2026/06/01/26G00112/sg",
    "testo": "Decreto legislativo 7 maggio 2026, n. 96, pubblicato in Gazzetta Ufficiale.",
    "fonte": "Gazzetta Ufficiale",
}


def _patch_retriever(monkeypatch, *, normattiva=None, gazzetta=None):
    monkeypatch.setattr(retriever, "search_normattiva", lambda query, **kw: list(normattiva or []))
    monkeypatch.setattr(retriever, "search_gazzetta", lambda query, **kw: list(gazzetta or []))


def test_urn_normattiva_diventa_url_ufficiale_e_testo_inline(monkeypatch):
    _patch_retriever(monkeypatch, normattiva=[_RIGA_NORMATTIVA])
    candidates = LocalArchiveSearchProvider().search("L. 241/1990 site:normattiva.it", limit=4)
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.url == "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241"
    assert candidate.content.startswith("La L. 241/1990")
    assert candidate.discovered_by == "archivio_locale"
    assert candidate.source_id == "archivio_locale:normattiva"


def test_gazzetta_usa_url_http_originale(monkeypatch):
    _patch_retriever(monkeypatch, gazzetta=[_RIGA_GAZZETTA])
    candidates = LocalArchiveSearchProvider().search("decreto legislativo 96", limit=4)
    assert candidates[0].url.startswith("https://www.gazzettaufficiale.it/")
    assert candidates[0].source_id == "archivio_locale:gazzetta_ufficiale"


def test_righe_senza_url_http_o_senza_testo_scartate(monkeypatch):
    _patch_retriever(
        monkeypatch,
        normattiva=[
            {"titolo": "Solo zip", "url_origine": "raw/19900807_241.zip", "testo": "testo presente"},
            {"titolo": "Senza testo", "url_origine": "urn:nir:stato:legge:1990;241", "testo": ""},
        ],
    )
    assert LocalArchiveSearchProvider().search("legge 241", limit=4) == []


def test_dedup_per_url_e_tetto(monkeypatch):
    _patch_retriever(monkeypatch, normattiva=[_RIGA_NORMATTIVA, dict(_RIGA_NORMATTIVA)], gazzetta=[_RIGA_GAZZETTA])
    candidates = LocalArchiveSearchProvider().search("legge", limit=2)
    assert len(candidates) == 2
    assert len({candidate.url for candidate in candidates}) == 2


def test_archivi_assenti_risultato_vuoto_senza_eccezioni(monkeypatch):
    _patch_retriever(monkeypatch)
    assert LocalArchiveSearchProvider().search("art. 2043 codice civile", limit=3) == []


def test_composite_ordina_archivi_prima_del_web(monkeypatch):
    _patch_retriever(monkeypatch, normattiva=[_RIGA_NORMATTIVA])
    web = StaticSearchProvider(
        {"legge 241": [{"url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:1990-08-07;241", "title": "duplicato web"},
                        {"url": "https://www.gazzettaufficiale.it/altro", "title": "dal web"}]}
    )
    composite = CompositeSearchProvider([LocalArchiveSearchProvider(), web])
    candidates = composite.search("legge 241", limit=3)
    assert candidates[0].discovered_by == "archivio_locale"  # archivio prima
    urls = [candidate.url for candidate in candidates]
    assert len(urls) == len(set(map(str.casefold, urls)))  # dedup del duplicato web
    assert any(candidate.title == "dal web" for candidate in candidates)


def test_composite_provider_guasto_non_ferma_gli_altri():
    class _Guasto:
        def search(self, query: str, *, limit: int = 5) -> list[SourceCandidate]:
            raise RuntimeError("provider rotto")

    sano = StaticSearchProvider({"q": [{"url": "https://www.normattiva.it/x", "title": "ok"}]})
    candidates = CompositeSearchProvider([_Guasto(), sano]).search("q", limit=2)
    assert [candidate.title for candidate in candidates] == ["ok"]
