from __future__ import annotations

from typing import Any

from lex.retrieval.official_web import search_recognized_official_web


class DummyResponse:
    def __init__(self, text: str, *, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


GAZZETTA_ARCHIVE_HTML = """
<html><body>
  <span class="notizie_singola">
    <span class="subtitolo_grid">27 marzo 2026</span>
    <h6>ACCORDI DI DELEGA, GESTIONE RISCHIO DI LIQUIDITA' E VIGILANZA - RECEPIMENTO DIRETTIVA (UE)</h6>
    <p>(<a href="http://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00056/sg" target="_blank">D.Lgs. 13 marzo 2026, n. 39</a>)</p>
    <a href="/showNewsDetail?id=8217&backTo=archivio&anno=2026&provenienza=archivio">Leggi la notizia</a>
  </span>
  <span class="notizie_singola">
    <span class="subtitolo_grid">25 marzo 2026</span>
    <h6>LEGGE DI DELEGAZIONE EUROPEA 2025</h6>
    <p>(<a href="http://www.gazzettaufficiale.it/eli/id/2026/03/25/26G00053/sg">L. 17 marzo 2026, n. 36</a>)</p>
  </span>
</body></html>
"""


def test_gazzetta_resolver_usa_archivio_ufficiale_per_codice_redazionale():
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        calls.append((str(url), dict(kwargs.get("params") or {})))
        assert "duckduckgo" not in str(url).lower()
        return DummyResponse(GAZZETTA_ARCHIVE_HTML)

    results = search_recognized_official_web(
        "26G00056",
        source_ids=["gazzetta_ufficiale"],
        request_get=fake_get,
        limit_results=3,
    )

    assert calls == [("https://www.gazzettaufficiale.it/showArchivioNews", {"anno": "2026"})]
    assert len(results) == 1
    assert results[0]["url"] == "https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00056/sg"
    assert results[0]["source_name"] == "Gazzetta Ufficiale"
    assert "ACCORDI DI DELEGA" in results[0]["title"]


def test_gazzetta_resolver_usa_archivio_ufficiale_per_riferimento_normativo():
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        calls.append((str(url), dict(kwargs.get("params") or {})))
        assert "duckduckgo" not in str(url).lower()
        return DummyResponse(GAZZETTA_ARCHIVE_HTML)

    results = search_recognized_official_web(
        "D.Lgs. 13 marzo 2026, n. 39 Gazzetta Ufficiale",
        source_ids=["gazzetta_ufficiale"],
        request_get=fake_get,
        limit_results=3,
    )

    assert calls == [("https://www.gazzettaufficiale.it/showArchivioNews", {"anno": "2026"})]
    assert len(results) == 1
    assert results[0]["url"].endswith("/26G00056/sg")
    assert "D.Lgs. 13 marzo 2026, n. 39" in results[0]["excerpt"]


def test_gazzetta_resolver_accetta_riferimento_numero_anno():
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        calls.append((str(url), dict(kwargs.get("params") or {})))
        assert "duckduckgo" not in str(url).lower()
        return DummyResponse(GAZZETTA_ARCHIVE_HTML)

    results = search_recognized_official_web(
        "D.Lgs. 39/2026",
        source_ids=["gazzetta_ufficiale"],
        request_get=fake_get,
        limit_results=3,
    )

    assert calls == [("https://www.gazzettaufficiale.it/showArchivioNews", {"anno": "2026"})]
    assert len(results) == 1
    assert results[0]["url"].endswith("/26G00056/sg")


def test_gazzetta_ignora_risultati_senza_testo_ufficiale_e_non_ripete_la_lettura():
    valid = GAZZETTA_ARCHIVE_HTML.replace("26G00056", "26G00981")
    duplicate_card = valid.split("<body>", 1)[1].split("</body>", 1)[0]
    almost_matching = """
      <div class="notizie_singola">
        <a href="/showNewsDetail?id=981">Indice della notizia 26G00981</a>
      </div>
      <div class="notizie_singola">
        <a href="https://example.test/eli/id/26G00981">Riproduzione non ufficiale</a>
      </div>
    """
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs["params"]))
        return DummyResponse(f"<html>{almost_matching}{duplicate_card}{duplicate_card}</html>")

    results = search_recognized_official_web(
        "26G00981",
        source_ids=["gazzetta_ufficiale"],
        request_get=fake_get,
        limit_results=3,
    )
    assert len(results) == 1
    assert results[0]["official_url"].endswith("/26G00981/sg")
    results[0]["title"] = "modifica del chiamante"

    repeated = search_recognized_official_web(
        "26G00981",
        source_ids=["gazzetta_ufficiale"],
        request_get=fake_get,
        limit_results=3,
    )
    assert "ACCORDI DI DELEGA" in repeated[0]["title"]
    assert calls == [("https://www.gazzettaufficiale.it/showArchivioNews", {"anno": "2026"})]


def test_gazzetta_archivio_non_disponibile_usa_la_ricerca_sulla_fonte_ufficiale():
    calls = []

    def fake_get(url, **kwargs):
        calls.append((url, kwargs["params"]))
        if url.endswith("showArchivioNews"):
            return DummyResponse("Archivio non disponibile", status_code=503)
        if "site:gazzettaufficiale.it" in kwargs["params"]["q"]:
            return DummyResponse(
                '<article><h2><a href="https://www.gazzettaufficiale.it/eli/id/2026/10/19/26G00982/sg">'
                "Decreto legislativo n. 982/2026</a></h2></article>"
            )
        return DummyResponse("")

    results = search_recognized_official_web(
        "26G00982",
        source_ids=["gazzetta_ufficiale"],
        request_get=fake_get,
        limit_results=1,
    )
    assert len(results) == 1
    assert results[0]["source_id"] == "gazzetta_ufficiale"
    assert results[0]["url"].endswith("/26G00982/sg")
    assert calls[0][1] == {"anno": "2026"}
    assert calls[1][1] == {"q": "site:gazzettaufficiale.it 26G00982"}
