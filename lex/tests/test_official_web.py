from __future__ import annotations

from lex.contracts import LexRequest
from lex.retrieval.official_web import (
    resolve_official_source_ids_for_query,
    search_free_public_web,
    search_recognized_official_web,
)
from lex.retrieval.source_router import SourceRouter
from lex.retrieval.sources.official_web import OfficialWebSource


class _FakeResponse:
    def __init__(self, body: str, status_code: int = 200) -> None:
        self.status_code = status_code
        self.text = body


def test_search_recognized_official_web_filtra_domini_non_ufficiali():
    body = """
    <html>
      <body>
        <div class="result">
          <a class="result__a" href="https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2024-01-01;1">Normattiva - testo vigente</a>
          <div class="result__snippet">Versione vigente del testo normativo.</div>
        </div>
        <div class="result">
          <a class="result__a" href="https://example.com/legge-non-ufficiale">Sito non ufficiale</a>
          <div class="result__snippet">Contenuto non ammesso.</div>
        </div>
      </body>
    </html>
    """

    results = search_recognized_official_web(
        "testo vigente legge bilancio",
        source_ids=["normattiva"],
        request_get=lambda *args, **kwargs: _FakeResponse(body),
        limit_results=3,
    )

    assert len(results) == 1
    assert results[0]["domain"] == "normattiva.it"
    assert results[0]["source_id"] == "normattiva"


def test_search_free_public_web_accetta_risultati_pubblici_non_allowlist():
    body = """
    <html>
      <body>
        <div class="result">
          <a class="result__a" href="https://www.forogiuridico.it/sentenze/cassazione-penale.html">Foro giuridico - nota</a>
          <div class="result__snippet">Scheda trovata tramite ricerca libera.</div>
        </div>
        <div class="result">
          <a class="result__a" href="http://127.0.0.1/private">Risorsa locale</a>
          <div class="result__snippet">Non deve uscire.</div>
        </div>
      </body>
    </html>
    """

    results = search_free_public_web(
        "questione penale R.G. 9926/2026",
        request_get=lambda *args, **kwargs: _FakeResponse(body),
        limit_results=3,
    )

    assert len(results) == 1
    assert results[0]["domain"] == "forogiuridico.it"
    assert results[0]["source_access_label"] == "Web libero"


def test_search_free_public_web_usa_fallback_pubblico_se_duckduckgo_blocca():
    duckduckgo_challenge = "<html><body><form id='challenge-form'></form></body></html>"
    yahoo_body = """
    <html>
      <body>
        <div class="algo">
          <div class="compTitle">
            <a href="https://www.studiolegale-esempio.it/opposizione-decreto-ingiuntivo">
              Studio legale - opposizione a decreto ingiuntivo
            </a>
          </div>
          <div class="compText">
            Nota operativa per avvocati su termini, prassi e mediazione.
          </div>
        </div>
      </body>
    </html>
    """
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "duckduckgo" in url:
            return _FakeResponse(duckduckgo_challenge, status_code=202)
        if "search.yahoo.com" in url:
            return _FakeResponse(yahoo_body)
        return _FakeResponse("<html><body></body></html>")

    results = search_free_public_web(
        "opposizione decreto ingiuntivo prassi avvocati",
        request_get=fake_get,
        limit_results=3,
    )

    assert any("duckduckgo" in call for call in calls)
    assert any("search.yahoo.com" in call for call in calls)
    assert len(results) == 1
    assert results[0]["domain"] == "studiolegale-esempio.it"
    assert results[0]["search_engine"] == "yahoo"
    assert results[0]["source_priority"] == "web_libero"


def test_search_free_public_web_usa_google_pubblico_oltre_duckduckgo():
    google_body = """
    <html>
      <body>
        <div class="g">
          <a href="/url?q=https://www.studiolegale-esempio.it/mediazione-opposizione-decreto-ingiuntivo&amp;sa=U">
            <h3>Mediazione e opposizione a decreto ingiuntivo</h3>
          </a>
          <div class="VwiC3b">Nota professionale per avvocati su opposizione e mediazione.</div>
        </div>
      </body>
    </html>
    """
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "duckduckgo" in url:
            return _FakeResponse("<html><body></body></html>", status_code=202)
        if "google.com" in url:
            return _FakeResponse(google_body)
        return _FakeResponse("<html><body></body></html>")

    results = search_free_public_web(
        "opposizione decreto ingiuntivo mediazione avvocati",
        request_get=fake_get,
        limit_results=2,
    )

    assert any("duckduckgo" in call for call in calls)
    assert any("google.com" in call for call in calls)
    assert not any("search.yahoo.com" in call for call in calls)
    assert len(results) == 1
    assert results[0]["search_engine"] == "google"
    assert results[0]["domain"] == "studiolegale-esempio.it"
    assert results[0]["title"] == "Mediazione e opposizione a decreto ingiuntivo"
    assert "Nota professionale" in results[0]["excerpt"]


def test_search_free_public_web_usa_ecosia_se_altri_motori_non_restituiscono_risultati():
    ecosia_body = """
    <html>
      <body>
        <article>
          <h2>
            <a href="https://www.studioassociatoborselli.it/opposizione-a-decreto-ingiuntivo-spetta-al-creditore-promuovere-la-mediazione/">
              Opposizione a decreto ingiuntivo: creditore e mediazione
            </a>
          </h2>
          <p>Approfondimento professionale su mediazione e giudizio di opposizione.</p>
        </article>
      </body>
    </html>
    """
    calls: list[str] = []

    def fake_get(url, **kwargs):
        calls.append(url)
        if "ecosia.org" in url:
            return _FakeResponse(ecosia_body)
        return _FakeResponse("<html><body></body></html>", status_code=202)

    results = search_free_public_web(
        "opposizione decreto ingiuntivo mediazione obbligatoria",
        request_get=fake_get,
        limit_results=2,
    )

    assert any("ecosia.org" in call for call in calls)
    assert len(results) == 1
    assert results[0]["search_engine"] == "ecosia"
    assert results[0]["domain"] == "studioassociatoborselli.it"
    assert "mediazione" in results[0]["title"].lower()


def test_official_web_source_in_modalita_libera_non_usa_allowlist_ufficiale():
    body = """
    <html>
      <body>
        <div class="result">
          <a class="result__a" href="https://www.forogiuridico.it/appunti/liberi.html">Appunto libero</a>
          <div class="result__snippet">Risultato da ricerca web libera.</div>
        </div>
      </body>
    </html>
    """
    source = OfficialWebSource(request_get=lambda *args, **kwargs: _FakeResponse(body))
    request = LexRequest(
        tenant_id="tenant-demo",
        user_id="u1",
        session_id="s1",
        query="cerca quello che voglio",
        fascicolo_id="fas-1",
        metadata={"source_mode": "free_web", "free_web_enabled": True},
        allow_external_research=False,
        require_official_sources=False,
    )

    items = source.search(["cerca quello che voglio"], request=request, context={"workflow": "fascicolo"})

    assert len(items) == 1
    assert items[0].source_type == "web_libero"
    assert items[0].verified_reference is False
    assert items[0].source_level == 3
    assert items[0].metadata["allowlist_used"] is False
    assert items[0].metadata["saved_to_db"] is False
    assert items[0].metadata["url"] == "https://www.forogiuridico.it/appunti/liberi.html"
    assert request.metadata["source_registry"]["mode"] == "web_libero"
    assert request.metadata["source_registry"]["allowlist_used"] is False


def test_official_web_source_restituisce_evidenze_quando_la_query_lo_richiede():
    body = """
    <html>
      <body>
        <div class="result">
          <a class="result__a" href="https://www.cortedicassazione.it/cassazione-resources/resources/cms/documents/sentenza.pdf">Cassazione - sentenza recente</a>
          <div class="result__snippet">Pronuncia ufficiale recente in PDF.</div>
        </div>
      </body>
    </html>
    """
    source = OfficialWebSource(request_get=lambda *args, **kwargs: _FakeResponse(body))
    request = LexRequest(
        tenant_id="tenant-demo",
        user_id="u1",
        session_id="s1",
        query="Puoi controllare sul web l'ultima sentenza civile?",
        metadata={"source_ids": ["cassazione"]},
    )

    items = source.search(["ultima sentenza civile cassazione"], request=request, context={"workflow": "chat"})

    assert len(items) == 1
    assert items[0].source_type == "web_ufficiale"
    assert items[0].metadata["authority"] == "official_web"
    assert items[0].metadata["url"].endswith(".pdf")
    assert items[0].official_url.endswith(".pdf")


def test_search_recognized_official_web_fallback_cassazione_lista_pubblica():
    empty_search = "<html><body></body></html>"
    cassazione_page = """
    <html>
      <body>
        <div class="card-news">
          <h3>
            <a href="https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP50042">
              Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026
            </a>
          </h3>
          <p>
            <span>Estradizione per l'estero</span>:
            Estradizione cautelare passiva - Requisitoria del Procuratore generale.
          </p>
        </div>
      </body>
    </html>
    """

    def fake_get(url, **kwargs):
        if "duckduckgo" in url:
            return _FakeResponse(empty_search)
        if kwargs.get("params", {}).get("frame3_item") == 2:
            return _FakeResponse(cassazione_page)
        return _FakeResponse("<html><body></body></html>")

    results = search_recognized_official_web(
        "Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026",
        source_ids=["cassazione"],
        request_get=fake_get,
        limit_results=3,
    )

    assert len(results) == 1
    assert results[0]["source_id"] == "cassazione"
    assert results[0]["official_url"].endswith("contentId=SZP50042")
    assert "14575" in results[0]["title"]


def test_resolve_official_source_ids_prioritizza_cassazione_per_sentenza_esatta():
    source_ids = resolve_official_source_ids_for_query(
        "Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026",
        limit=4,
    )

    assert source_ids[0] == "cassazione"


def test_source_router_aggiunge_official_web_source_su_richiesta_web():
    router = SourceRouter()
    request = LexRequest(
        tenant_id="tenant-demo",
        user_id="u1",
        session_id="s1",
        query="Puoi verificare sul web la normativa aggiornata sul deposito telematico?",
    )

    sources = router.resolve(request, {}, "chat")

    assert any(isinstance(source, OfficialWebSource) for source in sources)


def test_source_router_web_libero_non_trascina_fonti_db_o_fascicolo():
    router = SourceRouter()
    request = LexRequest(
        tenant_id="tenant-demo",
        user_id="u1",
        session_id="s1",
        query="cerca liberamente un tema non censito",
        fascicolo_id="fas-1",
        metadata={"source_mode": "free_web", "free_web_enabled": True},
    )

    sources = router.resolve(request, {}, "fascicolo")

    assert [source.__class__.__name__ for source in sources] == ["OfficialWebSource"]


def test_official_web_source_traccia_fonti_partner_quando_non_esiste_fallback_pubblico():
    source = OfficialWebSource(request_get=lambda *args, **kwargs: _FakeResponse("<html><body></body></html>"))
    request = LexRequest(
        tenant_id="tenant-demo",
        user_id="u1",
        session_id="s1",
        query="Vorrei una visura dal registro imprese",
        metadata={"source_ids": ["registro_imprese_api"]},
    )

    items = source.search(["visura registro imprese"], request=request, context={"workflow": "chat"})

    registry_context = request.metadata.get("source_registry") or {}
    assert items == []
    assert registry_context["partner_sources"][0]["key"] == "registro_imprese_api"
    assert registry_context["credentialed_sources"][0]["key"] == "registro_imprese_api"
