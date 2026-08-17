from __future__ import annotations

from typing import Any

import pytest

from pct.notizie_utili import (
    CASSAZIONE_URL,
    PST_GIUSTIZIA_URL,
    _cassa_candidates,
    _collect_cassazione,
    _collect_pst_giustizia,
    _date_iso,
    _response,
)


class _Response:
    def __init__(self, content: bytes, url: str):
        self.content = content
        self.url = url

    def raise_for_status(self) -> None:
        return None


def _request_from(fixtures: dict[str, bytes]):
    def _request(url: str, **_kwargs: Any) -> _Response:
        return _Response(fixtures[url], url)

    return _request


def test_date_italiane_con_anno_breve_e_esteso():
    assert _date_iso("Pubblicata il 6 ago 2026") == "2026-08-06"
    assert _date_iso("Aggiornato il 17/08/26") == "2026-08-17"


def test_pst_giustizia_legge_titolo_data_e_collegamento_ufficiale():
    html = """
    <html><body>
      <div class="card-body">
        <h3>Webinar Istanza web per i professionisti</h3>
        <p>6 ago 2026</p>
        <p>Nuove indicazioni operative per i servizi telematici.</p>
        <a href="/PST/it/news_istanza_web.wp">Leggi di più</a>
      </div>
    </body></html>
    """.encode("utf-8")
    rows = _collect_pst_giustizia(
        _request_from({PST_GIUSTIZIA_URL: html}),
        limit=5,
    )

    assert len(rows) == 1
    assert rows[0]["source_code"] == "pst_giustizia"
    assert rows[0]["published_at"] == "2026-08-06"
    assert rows[0]["source_url"] == "https://pst.giustizia.it/PST/it/news_istanza_web.wp"


def test_cassa_include_gli_aggiornamenti_della_sezione_info_cassa():
    from lxml import html as lxml_html

    tree = lxml_html.fromstring("""
      <main>
        <a href="/info-cassa/contributi-2026/">Contributi previdenziali e indicazioni operative 2026</a>
      </main>
    """)

    rows = _cassa_candidates(tree)

    assert rows == [(
        "Contributi previdenziali e indicazioni operative 2026",
        "https://www.cfnews.it/info-cassa/contributi-2026/",
    )]


def test_cassazione_legge_solo_notizie_datate_dalla_pagina_ufficiale():
    html = """
    <html><body><main>
      <article>
        <time>17/08/2026</time>
        <h3><a href="/it/ultime_decisioni.page">Ultime decisioni della Corte di Cassazione</a></h3>
        <p>Raccolta aggiornata dei provvedimenti pubblicati.</p>
      </article>
    </main></body></html>
    """.encode("utf-8")
    rows = _collect_cassazione(
        _request_from({CASSAZIONE_URL: html}),
        limit=5,
    )

    assert len(rows) == 1
    assert rows[0]["source_code"] == "cassazione"
    assert rows[0]["published_at"] == "2026-08-17"
    assert rows[0]["source_url"] == "https://www.cortedicassazione.it/it/ultime_decisioni.page"


def test_raccoglitore_rifiuta_reindirizzamenti_fuori_dalle_fonti_ammesse():
    def _request(_url: str, **_kwargs: Any) -> _Response:
        return _Response(b"<html></html>", "https://example.invalid/notizia")

    with pytest.raises(ValueError, match="reindirizzato"):
        _response(_request, PST_GIUSTIZIA_URL)


def test_raccoglitore_non_contatta_la_destinazione_di_un_redirect_non_ammesso():
    called: list[str] = []

    class _RedirectResponse(_Response):
        status_code = 302
        headers = {"Location": "http://127.0.0.1/internal"}

    def _request(url: str, **_kwargs: Any) -> _Response:
        called.append(url)
        return _RedirectResponse(b"", url)

    with pytest.raises(ValueError, match="reindirizzato"):
        _response(_request, PST_GIUSTIZIA_URL)

    assert called == [PST_GIUSTIZIA_URL]


def test_gazzetta_resta_una_fonte_diretta_e_non_un_elenco_in_cache():
    from pct.notizie_utili import (
        AGGREGATED_SOURCE_IDS,
        DIRECT_SOURCE_IDS,
        _source_collectors,
    )

    collectors = _source_collectors(lambda *_args, **_kwargs: None, limit=12)

    assert set(collectors) == set(AGGREGATED_SOURCE_IDS)
    assert "gazzetta_ufficiale" in DIRECT_SOURCE_IDS
    assert "gazzetta_ufficiale" not in collectors
