from __future__ import annotations

import json
from pathlib import Path

from pct.legal_update_pipeline import DEFAULT_SOURCE_ROWS
from pct.legal_reference_extractor import extract_references
from pct.legal_update_source_parsers import fetch_source_documents


class DummyResponse:
    def __init__(
        self,
        body: str | bytes,
        *,
        url: str,
        content_type: str = "text/html; charset=utf-8",
        status_code: int = 200,
    ) -> None:
        if isinstance(body, bytes):
            self.content = body
            self.text = body.decode("utf-8", errors="replace")
        else:
            self.text = body
            self.content = body.encode("utf-8")
        self.url = url
        self.status_code = status_code
        self.headers = {"content-type": content_type, "content-length": str(len(self.content))}
        self.encoding = None
        self.apparent_encoding = "utf-8"

    def iter_content(self, chunk_size: int = 65536):
        yield self.content


def _source(code: str) -> dict:
    return {str(row["code"]): dict(row) for row in DEFAULT_SOURCE_ROWS}[code]


def test_parser_html_vuoto_resta_diagnostico_per_fonte_rag_only():
    source = _source("eur_lex")

    docs = fetch_source_documents(source, request_get=lambda url, **_kwargs: DummyResponse("", url=str(url)))

    assert len(docs) == 1
    assert docs[0]["source_url"] == source["base_url"]
    assert docs[0]["title"] == "EUR-Lex"
    assert docs[0]["publication_destination"] == "rag_only"


def test_parser_eur_lex_riconosce_celex_ma_resta_rag_only():
    source = _source("eur_lex")
    fixture = Path("tests/fixtures/legal_updates/eur_lex_celex.html").read_text(encoding="utf-8")

    docs = fetch_source_documents(source, request_get=lambda url, **_kwargs: DummyResponse(fixture, url=str(url)))

    assert docs
    row = next(item for item in docs if "CELEX:32024R1689" in item["raw_text"])
    assert row["publication_destination"] == "rag_only"
    assert "RAG ufficiale UE" in row["source_exclusion_reason"]
    refs = extract_references(row["raw_text"], source_url=row["source_url"])
    assert any(row["reference_type"] == "celex" and row["normalized_text"] == "CELEX:32024R1689" for row in refs)


def test_parser_eur_lex_senza_celex_non_diventa_pubblicazione_strutturata():
    source = _source("eur_lex")
    html = "<html><body><article><h1>Pagina UE senza identificativo</h1><p>Testo generico.</p></article></body></html>"

    docs = fetch_source_documents(source, request_get=lambda url, **_kwargs: DummyResponse(html, url=str(url)))

    assert len(docs) == 1
    assert docs[0]["publication_destination"] == "rag_only"
    assert extract_references(docs[0]["raw_text"], source_url=docs[0]["source_url"]) == []


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


def test_parser_corte_conti_non_prende_link_di_navigazione():
    source = _source("corte_conti")
    listing = """
    <html><body>
      <a href="/Home/Organizzazione/Intranet">INTRANET</a>
      <a href="/Home/Biblioteca">BIBLIOTECA</a>
      <a href="/Home/ChiSiamo/SediStoriche">Sedi storiche</a>
    </body></html>
    """

    docs = fetch_source_documents(source, request_get=lambda url, **_kwargs: DummyResponse(listing, url=str(url)))

    assert docs == []


def test_parser_corte_conti_sostituisce_leggi_di_piu_con_titolo_scheda():
    source = _source("corte_conti")
    listing = """
    <html><body>
      <article>
        <a href="/Home/Documenti/DettaglioDocumenti?Id=74640cec">Leggi di più</a>
        <p>Sentenza pubblicata il 27/04/2026.</p>
      </article>
    </body></html>
    """
    detail = """
    <html><body><main>
      <h1>Sentenza n. 127/2026</h1>
      <p>Responsabilità erariale e appalti pubblici.</p>
      <a href="/Download?id=3f0619f6">Sentenza n. 127/2026 [141,324 KB PDF]</a>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if "DettaglioDocumenti" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(listing, url=target)

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0]["title"] == "Sentenza n. 127/2026"
    assert "Responsabilità erariale" in docs[0]["raw_text"]
    assert docs[0]["attachments_json"][0]["url"].endswith("/Download?id=3f0619f6")


def test_parser_corte_conti_usa_titolo_allegato_se_h1_generico():
    source = _source("corte_conti")
    listing = """
    <html><body>
      <article>
        <a href="/Home/Documenti/DettaglioDocumenti?Id=74640cec">Leggi di più</a>
        <p>Sentenza pubblicata il 27/04/2026.</p>
      </article>
    </body></html>
    """
    detail = """
    <html><body><main>
      <h1>Dettaglio documenti</h1>
      <h2>menu a briciole</h2>
      <p>Responsabilità erariale e appalti pubblici.</p>
      <a href="/Download?id=3f0619f6">Sentenza n. 127/2026 [141,324 KB PDF]</a>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if "DettaglioDocumenti" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(listing, url=target)

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0]["title"] == "Sentenza n. 127/2026"


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


def test_parser_feed_non_crea_fallback_documentale_su_html_non_feed():
    source = _source("curia_cgue_rss")
    html = "<html><body><main>Pagina di servizio temporanea</main></body></html>"

    docs = fetch_source_documents(source, request_get=lambda url, **_kwargs: DummyResponse(html, url=str(url)))

    assert docs == []


def test_parser_inps_messaggi_scarta_voci_non_messaggio_dal_feed_atti():
    source = _source("inps_messaggi")
    payload = {
        "data": {
            "results": [
                {"tipo": "Gara", "numero": "6552", "selectors": "gare.6552", "oggetto": "Bando di gara."},
                {
                    "tipo": "Messaggio",
                    "numero": "1618",
                    "selectors": "circolari-e-messaggi.2026.05.messaggio-numero-1618-del-15-05-2026_15261",
                    "dataPubblicazione": "14/05/2026",
                    "oggetto": "Messaggio operativo su contributi e termini previdenziali.",
                },
            ]
        }
    }

    docs = fetch_source_documents(
        source,
        request_get=lambda url, **_kwargs: DummyResponse(json.dumps(payload), url=str(url), content_type="application/json"),
    )

    assert len(docs) == 1
    assert docs[0]["title"] == "Messaggio numero 1618 del 14/05/2026"


def test_parser_curia_ripulisce_titolo_feed_con_null_e_causa():
    source = _source("curia_cgue_rss")
    feed = """
    <rss><channel>
      <item>
        <title>72/Wed May 13 00:00:00 CEST 2026 : null - Sentenza del Tribunale nella causa T-24/25</title>
        <link>https://curia.europa.eu/site/jcms/p1_1000083638</link>
        <description>Sentenza del Tribunale nella causa T-24/25.</description>
      </item>
    </channel></rss>
    """

    docs = fetch_source_documents(
        source,
        request_get=lambda url, **_kwargs: DummyResponse(feed, url=str(url), content_type="application/rss+xml"),
    )

    assert len(docs) == 1
    assert docs[0]["title"] == "Sentenza del Tribunale nella causa T-24/25"
    assert "null" not in docs[0]["title"].lower()


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


def test_parser_gazzetta_usa_elenco_30_giorni_e_pdf_ufficiale():
    source = _source("gazzetta_ufficiale")
    listing = """
    <html><body>
      <a href="/home">Home</a>
      <a href="/do/gazzetta/serie_generale/0/pdfPaginato?dataPubblicazioneGazzetta=20260424&numeroGazzetta=95&tipoSerie=SG&tipoSupplemento=GU&numeroSupplemento=0&progressivo=0&numPagina=1&edizione=0">Consulta PDF paginato</a>
      <a href="/do/gazzetta/downloadPdf?dataPubblicazioneGazzetta=20260424&numeroGazzetta=95&tipoSerie=SG&tipoSupplemento=GU&numeroSupplemento=0&progressivo=0&estensione=pdf&edizione=0">Download PDF</a>
    </body></html>
    """
    calls: list[str] = []

    def fake_get(url, **_kwargs):
        calls.append(str(url))
        return DummyResponse(listing, url=str(url))

    docs = fetch_source_documents(source, request_get=fake_get)

    assert calls == ["https://www.gazzettaufficiale.it/30giorni/serie_generale"]
    assert len(docs) == 1
    assert docs[0]["title"] == "Gazzetta Ufficiale - Serie Generale n. 95 del 24/04/2026"
    assert docs[0]["published_at"] == "2026-04-24"
    assert docs[0]["attachments_json"][0]["url"].startswith("https://www.gazzettaufficiale.it/do/gazzetta/downloadPdf")
    assert "numPagina" not in docs[0]["attachments_json"][0]["url"]


def test_parser_agcom_prende_provvedimenti_non_navigazione():
    source = _source("agcom_provvedimenti")
    listing = """
    <html><body>
      <nav><a href="https://agcom.portaleamministrazionetrasparente.it/">Autorità trasparente</a></nav>
      <article>
        <a href="/provvedimenti/delibera-93-26-cons">Delibera 93/26/CONS</a>
        <p>Provvedimento su tutela utenti e controversie.</p>
      </article>
    </body></html>
    """
    detail = """
    <html><body><main>
      <h1>Delibera 93/26/CONS</h1>
      <p>Sanzione e tutela utenti ai sensi del Regolamento UE 2022/2065.</p>
      <a href="/documents/delibera-93-26-cons.pdf">Scarica PDF</a>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if "delibera-93-26-cons" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(listing, url=target)

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0]["title"] == "Delibera 93/26/CONS"
    assert "Autorità trasparente" not in docs[0]["title"]
    assert "Regolamento UE 2022/2065" in docs[0]["raw_text"]
    assert docs[0]["attachments_json"][0]["url"].endswith("delibera-93-26-cons.pdf")


def test_parser_anac_prende_documenti_operativi_non_servizi():
    source = _source("anac_documenti")
    listing = """
    <html><body>
      <a href="/it/contattaci">Contattaci</a>
      <article>
        <a href="/-/parere-di-precontenzioso-n.-161-del-6-maggio-2026">Parere di precontenzioso n. 161 del 6 maggio 2026</a>
        <p>Appalto pubblico e affidamento.</p>
      </article>
    </body></html>
    """
    detail = """
    <html><body><main>
      <p>Parere ANAC su gara, affidamento e art. 120 c.p.a.</p>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if "/-/" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(listing, url=target)

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0]["title"].startswith("Parere di precontenzioso")
    assert "Contattaci" not in docs[0]["title"]
    assert "art. 120 c.p.a." in docs[0]["raw_text"]
    assert docs[0].get("attachments_json") in (None, [])


def test_parser_corte_costituzionale_prende_solo_schede_pronuncia():
    source = _source("corte_costituzionale")
    listing = """
    <html><body>
      <a href="/contenuti/link/decisioni-del-mese">Decisioni del mese</a>
      <article>
        <a href="/scheda-pronuncia/2026/76">Sentenza n. 76/2026</a>
        <p>Deposito del 12/05/2026, questione di legittimità costituzionale.</p>
      </article>
    </body></html>
    """
    detail = """
    <html><body><main>
      <h1>Sentenza n. 76/2026</h1>
      <p>La Corte costituzionale decide su art. 24 Cost. e processo amministrativo.</p>
      <a href="/stampa-pdf-pronuncia/2026/76">Versione Pdf</a>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if "/scheda-pronuncia/" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(listing, url=target)

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0]["title"] == "Sentenza n. 76/2026"
    assert "art. 24 Cost." in docs[0]["raw_text"]
    assert docs[0]["source_url"].endswith("/scheda-pronuncia/2026/76")
    assert docs[0]["attachments_json"][0]["url"].endswith("/stampa-pdf-pronuncia/2026/76")


def test_parser_corte_costituzionale_non_crea_fallback_su_captcha():
    source = _source("corte_costituzionale")
    html = "<html><head><title>Radware Captcha Page</title></head><body>validate.perfdrive.com</body></html>"

    docs = fetch_source_documents(source, request_get=lambda url, **_kwargs: DummyResponse(html, url=str(url)))

    assert docs == []


def test_parser_garante_prende_newsletter_docweb_non_social():
    source = _source("garante_privacy")
    listing = """
    <html><body>
      <a href="https://www.linkedin.com/company/autorit-garante-per-la-protezione-dei-dati-personali">linkedin</a>
      <article>
        <a href="/home/docweb/-/docweb-display/docweb/10239073">NEWSLETTER del 15 aprile 2026 - Il Garante privacy sanziona Eni</a>
        <p>Privacy, sanzione e trattamento dati.</p>
      </article>
    </body></html>
    """
    detail = """
    <html><body><main>
      <p>Provvedimento del Garante privacy su sanzione e Regolamento UE 2016/679.</p>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if "docweb-display" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(listing, url=target)

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0]["title"].startswith("NEWSLETTER del 15 aprile 2026")
    assert "linkedin" not in docs[0]["title"].lower()
    assert "Regolamento UE 2016/679" in docs[0]["raw_text"]


def test_parser_garante_non_tratta_link_gdpr_come_allegato_documento():
    source = _source("garante_privacy")
    listing = """
    <html><body>
      <article>
        <a href="/home/docweb/-/docweb-display/docweb/10239073">NEWSLETTER privacy</a>
        <p>Privacy, sanzione e trattamento dati.</p>
      </article>
    </body></html>
    """
    detail = """
    <html><body><main>
      <p>Provvedimento del Garante privacy su sanzione e Regolamento UE 2016/679.</p>
      <a href="/il-testo-del-regolamento">GDPR</a>
    </main></body></html>
    """

    def fake_get(url, **_kwargs):
        target = str(url)
        if "docweb-display" in target:
            return DummyResponse(detail, url=target)
        return DummyResponse(listing, url=target)

    docs = fetch_source_documents(source, request_get=fake_get)

    assert len(docs) == 1
    assert docs[0].get("attachments_json") in (None, [])


def test_parser_pst_tiene_solo_download_tecnici_documentali():
    source = _source("pst_giustizia_download")
    listing = """
    <html><body><main>
      <article><a href="/PST/it/schede_pratiche.page">Schede pratiche</a></article>
      <article><a href="/PST/it/documentation.page">Documentazione</a></article>
      <article>
        <a href="/PST/resources/cms/documents/specifiche_deposito_telematico_2026.pdf">Specifiche deposito telematico 2026</a>
        <p>Download tecnico PST utile a deposito telematico, schemi e manuali operativi.</p>
      </article>
    </main></body></html>
    """

    docs = fetch_source_documents(source, request_get=lambda url, **_kwargs: DummyResponse(listing, url=str(url)))

    assert len(docs) == 1
    assert docs[0]["title"] == "Specifiche deposito telematico 2026"
    assert docs[0]["source_url"].endswith("specifiche_deposito_telematico_2026.pdf")
    assert docs[0]["publication_destination"] == "rag_only"


def test_parser_decodifica_windows_1252_senza_caratteri_sostitutivi():
    source = _source("agcom_provvedimenti")
    listing = """
    <html><body>
      <article>
        <a href="/provvedimenti/delibera-94-26-cons">Delibera 94/26/CONS - Illegittimità</a>
        <p>Provvedimento e sanzione.</p>
      </article>
    </body></html>
    """.encode("windows-1252")

    docs = fetch_source_documents(
        source,
        request_get=lambda url, **_kwargs: DummyResponse(
            listing,
            url=str(url),
            content_type="text/html; charset=utf-8",
        ),
    )

    assert len(docs) == 1
    assert "Illegittimità" in docs[0]["title"]
    assert "\ufffd" not in docs[0]["title"]


def test_parser_ripara_mojibake_gia_presente_nel_testo_html():
    source = _source("agcom_provvedimenti")
    title = "Delibera 95/26/CONS - Illegittimit\u00c3\u00a0 dell\u00e2\u20ac\u2122atto"
    listing = f"""
    <html><body>
      <article>
        <a href="/provvedimenti/delibera-95-26-cons">{title}</a>
        <p>Provvedimento e sanzione.</p>
      </article>
    </body></html>
    """

    docs = fetch_source_documents(source, request_get=lambda url, **_kwargs: DummyResponse(listing, url=str(url)))

    assert len(docs) == 1
    assert "Illegittimità dell’atto" in docs[0]["title"]
    assert "\u00c3" not in docs[0]["title"]
