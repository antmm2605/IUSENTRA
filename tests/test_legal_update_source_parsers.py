from __future__ import annotations

import json

from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS
from pct.legal_update_source_parsers import fetch_source_documents


class DummyResponse:
    def __init__(self, body: str, *, url: str, content_type: str = "text/html; charset=utf-8", status_code: int = 200) -> None:
        self.text = body
        self.content = body.encode("utf-8")
        self.url = url
        self.status_code = status_code
        self.headers = {"content-type": content_type, "content-length": str(len(self.content))}

    def iter_content(self, chunk_size: int = 65536):
        yield self.content


def _source(code: str) -> dict:
    return {str(row["code"]): dict(row) for row in DEFAULT_SOURCE_ROWS}[code]


def test_parser_html_listing_detail_estrae_testo_e_allegato_pdf():
    source = _source("corte_conti")
    listing = """
    <html><body>
      <a href="/privacy">Privacy policy</a>
      <article>
        <a href="/Home/Documenti/DettaglioSentenza?id=123">Sentenza Corte dei Conti n. 123/2026</a>
        <p>Deposito 12/05/2026, responsabilità erariale e appalti.</p>
      </article>
    </body></html>
    """
    detail = """
    <html><body><main>
      <h1>Sentenza Corte dei Conti n. 123/2026</h1>
      <p>La Sezione giurisdizionale richiama il D.Lgs. 36/2023 e la responsabilità erariale.</p>
      <a href="/documenti/sentenza-123-2026.pdf">Scarica PDF ufficiale</a>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if "DettaglioSentenza" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(listing, url=target)

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0]["title"] == "Sentenza Corte dei Conti n. 123/2026"
    assert "D.Lgs. 36/2023" in docs[0]["raw_text"]
    assert docs[0]["publication_destination"] == "giurisprudenza_or_rag_only"
    assert docs[0]["publication_destination_label"] == "Giurisprudenza o solo RAG"
    assert docs[0]["attachments_json"][0]["url"].endswith("sentenza-123-2026.pdf")


def test_parser_feed_fetch_detail_se_descrizione_povera_e_conserva_pdf():
    source = _source("curia_cgue_rss")
    feed = """
    <rss><channel>
      <item>
        <title>Sentenza della Corte di giustizia UE nella causa C-123/26</title>
        <link>https://curia.europa.eu/juris/document/document.jsf?text=&amp;docid=123</link>
        <description>Comunicato breve</description>
        <pubDate>Tue, 12 May 2026 10:00:00 GMT</pubDate>
      </item>
    </channel></rss>
    """
    detail = """
    <html><body><main>
      <p>Sentenza CGUE causa C-123/26 su Direttiva UE 2019/790 e tutela degli utenti.</p>
      <a href="/juris/document/document_print.jsf?docid=123&amp;format=PDF">Scarica PDF</a>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if "document.jsf" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(feed, url=target, content_type="application/rss+xml")

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0]["published_at"] == "2026-05-12"
    assert "Direttiva UE 2019/790" in docs[0]["raw_text"]
    assert docs[0]["attachments_json"][0]["url"].startswith("https://curia.europa.eu/juris/document/document_print.jsf")
    assert docs[0]["rag_destination"] == "official_eu_case_law_rag"


def test_parser_ckan_distingue_catalogo_e_documento_concreto():
    source = _source("openga_sentenze")
    payload = {
        "result": {
            "results": [
                {
                    "id": "pkg-catalogo",
                    "title": "Catalogo sentenze amministrative",
                    "notes": "Dataset OpenGA in formato CSV.",
                    "resources": [
                        {
                            "id": "res-csv",
                            "name": "Elenco CSV",
                            "format": "CSV",
                            "url": "https://openga.giustizia-amministrativa.it/catalogo.csv",
                        }
                    ],
                },
                {
                    "id": "pkg-sentenza",
                    "title": "Sentenza TAR Lazio n. 1234/2026",
                    "notes": "Ricorso in materia di appalti e affidamento.",
                    "resources": [
                        {
                            "id": "res-pdf",
                            "name": "Sentenza TAR Lazio n. 1234/2026",
                            "format": "PDF",
                            "url": "https://openga.giustizia-amministrativa.it/sentenza-1234-2026.pdf",
                        }
                    ],
                },
            ]
        }
    }

    docs = fetch_source_documents(
        source,
        request_get=lambda url, **_kwargs: DummyResponse(
            json.dumps(payload),
            url=str(url),
            content_type="application/json",
        ),
    )

    assert len(docs) == 2
    catalog = next(row for row in docs if "Catalogo" in row["title"])
    judgment = next(row for row in docs if "Sentenza TAR" in row["title"])
    assert "Catalogo o dataset open data" in catalog["source_exclusion_reason"]
    assert judgment["source_exclusion_reason"] == ""
    assert judgment["attachments_json"][0]["url"].endswith("sentenza-1234-2026.pdf")
    assert judgment["publication_destination"] == "giurisprudenza_if_document_else_rag_only"


def test_parser_cassazione_indice_segue_solo_dettagli_content_id():
    source = _source("cassazione_ultime_sent_ord_questioni")
    base = """
    <html><body>
      <a href="/it/privacy_policy.page">Privacy policy</a>
      <a href="/it/giurisprudenza_penale.page">Giurisprudenza Penale</a>
      <a href="/it/giurisprudenza_civile.page">Giurisprudenza Civile</a>
    </body></html>
    """
    penale = """
    <html><body><article>
      <a href="/it/qsp_dettaglio.page?contentId=QSP50194">Questione Penale Pendente R.G. 9926/2026</a>
      <a href="/it/supporto.page?contentId=NOPE">Supporto</a>
    </article></body></html>
    """
    civile = """
    <html><body><article>
      <a href="/it/civile_dettaglio.page?contentId=SZC50126">Sentenza n. 11417 del 27/04/2026</a>
    </article></body></html>
    """
    detail = """
    <html><body><main>
      <p>Dettaglio con art. 606 c.p.p. e R.G. 9926/2026.</p>
      <a href="/resources/cms/documents/qsp50194.pdf">Ordinanza di rimessione PDF</a>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if target.endswith("giurisprudenza_penale.page"):
            return DummyResponse(penale, url=target)
        if target.endswith("giurisprudenza_civile.page"):
            return DummyResponse(civile, url=target)
        if "_dettaglio.page?contentId=" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(base, url=target)

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 2
    assert all("_dettaglio.page?contentId=" in row["source_url"] for row in docs)
    assert not any("privacy" in row["source_url"].lower() or "supporto" in row["source_url"].lower() for row in docs)
    assert any("art. 606 c.p.p." in row["raw_text"] for row in docs)
    assert any(row.get("attachments_json") for row in docs)
