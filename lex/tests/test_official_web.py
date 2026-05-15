from __future__ import annotations

from lex.contracts import LexRequest
from lex.retrieval.official_web import resolve_official_source_ids_for_query, search_recognized_official_web
from lex.retrieval.source_router import SourceRouter
from lex.retrieval.sources.official_web import OfficialWebSource


class _FakeResponse:
    def __init__(self, body: str) -> None:
        self.status_code = 200
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
