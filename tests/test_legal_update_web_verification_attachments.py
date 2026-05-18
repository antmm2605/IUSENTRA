from __future__ import annotations

import hashlib
import json
from types import SimpleNamespace
from typing import Any

from pct import legal_update_web_verification as verification


class DummyResponse:
    def __init__(self, content: bytes, *, content_type: str, status_code: int = 200) -> None:
        self.content = content
        self.text = content.decode("utf-8", errors="ignore")
        self.status_code = status_code
        self.headers = {
            "content-type": content_type,
            "content-length": str(len(content)),
        }

    def iter_content(self, chunk_size: int = 65536):
        yield self.content


HTML_FIXTURE = """
<html>
  <body>
    <article>
      <h1>Decreto legislativo n. 56 del 2026</h1>
      <a href="/resources/cms/documents/testo-ufficiale.pdf">Scarica PDF ufficiale</a>
      <a href="https://www.gazzettaufficiale.it.evil.test/falso.pdf">Scarica PDF non ufficiale</a>
    </article>
  </body>
</html>
"""


def test_helper_scarica_pdf_ufficiale_e_rifiuta_dominio_simile(monkeypatch):
    source_url = "https://www.gazzettaufficiale.it/eli/id/2026/05/11/26G00056/sg"
    attachment_url = "https://www.gazzettaufficiale.it/resources/cms/documents/testo-ufficiale.pdf"
    pdf_bytes = b"%PDF-1.4\n% test ufficiale\n"
    requested: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        assert "evil.test" not in str(url)
        assert kwargs.get("allow_redirects") is False
        return DummyResponse(pdf_bytes, content_type="application/pdf")

    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(
        verification,
        "_text_from_attachment",
        lambda url, content, content_type: "Decreto legislativo n. 56 del 2026 sulla conciliazione giudiziale.",
    )

    confirmations = verification.extract_official_attachment_confirmations(
        HTML_FIXTURE,
        source_url,
        timeout=2,
        max_bytes=1024 * 1024,
    )

    assert requested == [attachment_url]
    assert len(confirmations) == 1
    row = confirmations[0]
    assert row["official"] is True
    assert row["source_url"] == source_url
    assert row["attachment_url"] == attachment_url
    assert row["title"] == "testo-ufficiale.pdf"
    assert row["attachment_type"] == "pdf"
    assert row["sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert "conciliazione giudiziale" in row["text_excerpt"]
    assert row["context_chars"] > 20


def test_helper_non_usa_testo_generico_come_titolo_allegato(monkeypatch):
    source_url = "https://www.gazzettaufficiale.it/eli/id/2026/05/11/26G00056/sg"
    generic_url = "https://www.gazzettaufficiale.it/resources/cms/documents/notizia-generica.pdf"
    requested: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        return DummyResponse(b"%PDF-1.4\n% test ufficiale\n", content_type="application/pdf")

    monkeypatch.setenv("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_LINKS", "3")
    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(
        verification,
        "_text_from_attachment",
        lambda url, content, content_type: "Decreto legislativo n. 56 del 2026 sulla conciliazione giudiziale.",
    )

    confirmations = verification.extract_official_attachment_confirmations(
        """
        <html><body>
          <a href="/resources/cms/documents/notizia-generica.pdf">Leggi la notizia</a>
        </body></html>
        """,
        source_url,
        timeout=2,
        max_bytes=1024 * 1024,
    )

    generic = next(row for row in confirmations if row["attachment_url"] == generic_url)
    assert generic["title"] == "notizia-generica.pdf"
    assert "Leggi la notizia" not in generic["title"]
    assert "evil.test" not in " ".join(requested)


def test_helper_non_scambia_menu_html_inps_per_allegato():
    source_url = (
        "https://www.inps.it/it/it/inps-comunica/atti/circolari-messaggi-e-normativa/"
        "dettaglio.circolari-e-messaggi.2026.05.circolare-numero-53-del-07-05-2026_15256.html"
    )

    links = verification._attachment_links(
        """
        <html><body>
          <a href="/it/it/previdenza/domanda-di-pensione.html">Domanda di pensione</a>
          <a href="/content/dam/inps-site/it/scorporati/circolari-e-messaggi/2026/05/Circolare_15256/Allegati/testo.pdf">
            Scarica PDF ufficiale
          </a>
        </body></html>
        """,
        source_url,
    )

    assert links == [
        {
            "url": "https://www.inps.it/content/dam/inps-site/it/scorporati/circolari-e-messaggi/2026/05/Circolare_15256/Allegati/testo.pdf",
            "label": "Scarica PDF ufficiale",
            "attachment_type": "pdf",
        }
    ]


def test_helper_gazzetta_non_scambia_pagina_aiuto_pdf_per_allegato(monkeypatch):
    source_url = "https://www.gazzettaufficiale.it/eli/id/2026/03/27/26G00056/sg"
    issue_pdf = "https://www.gazzettaufficiale.it/eli/gu/2026/03/27/72/sg/pdf"
    help_page = "https://www.gazzettaufficiale.it/caricaHtml?nomeTiles=formatoGraficoPdf"
    requested: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        if str(url) == source_url:
            return DummyResponse(
                """
                <html><body>
                  <main>
                    <h1>DECRETO LEGISLATIVO 13 marzo 2026, n. 39</h1>
                    <p>Recepimento della direttiva UE. (26G00056)</p>
                    <a href="/eli/gu/2026/03/27/72/sg/pdf">(GU Serie Generale n.72 del 27-03-2026)</a>
                    <a href="/caricaHtml?nomeTiles=formatoGraficoPdf">Formato Grafico PDF</a>
                  </main>
                </body></html>
                """.encode("utf-8"),
                content_type="text/html; charset=utf-8",
            )
        if str(url) == issue_pdf:
            return DummyResponse(b"%PDF-1.7\n% Gazzetta ufficiale\n", content_type="application/pdf")
        if str(url) == help_page:
            raise AssertionError("La pagina di aiuto non deve essere scaricata come allegato")
        raise AssertionError(f"URL inatteso: {url}")

    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(
        verification,
        "_text_from_attachment",
        lambda url, content, content_type: "Gazzetta Ufficiale decreto legislativo 13 marzo 2026 n. 39.",
    )

    context, attachments = verification._fetch_official_web_context_with_attachments(source_url, timeout=2)

    assert requested == [source_url, issue_pdf]
    assert "DECRETO LEGISLATIVO 13 marzo 2026, n. 39" in context
    assert len(attachments) == 1
    assert attachments[0]["attachment_url"] == issue_pdf
    assert attachments[0]["source_name"] == "Gazzetta Ufficiale"


def test_helper_legge_json_inps_e_scarica_pdf_reali(monkeypatch):
    source_url = (
        "https://www.inps.it/it/it/inps-comunica/atti/circolari-messaggi-e-normativa/"
        "dettaglio.circolari-e-messaggi.2026.05.circolare-numero-53-del-07-05-2026_15256.html"
    )
    json_url = source_url.replace("dettaglio.", "dettaglio.content-fragment-detail.").replace(".html", ".json")
    main_pdf = (
        "https://www.inps.it/content/dam/inps-site/it/scorporati/circolari-e-messaggi/2026/05/"
        "Circolare_15256/Allegati/16758_Circolare-numero-53-del-07-05-2026.pdf"
    )
    allegato_pdf = (
        "https://www.inps.it/content/dam/inps-site/it/scorporati/circolari-e-messaggi/2026/05/"
        "Circolare_15256/Allegati/16759_Circolare-numero-53-del-07-05-2026_Allegato-n-1.pdf"
    )
    payload = {
        "titolo": {"value": "Circolare%20numero%2053%20del%2007-05-2026"},
        "oggetto": {
            "value": (
                "%3Cp%3EDecreto-legge%2027%20febbraio%202026%2C%20n.%2025%2C%20"
                "indennit%C3%A0%20una%20tantum%20per%20lavoratori%20autonomi.%3C%2Fp%3E"
            )
        },
        "sommario": {"value": "%3Cp%3EIstruzioni%20amministrative%20INPS.%3C%2Fp%3E"},
        "testoCompleto": {
            "value": (
                "%3Cp%3EStrumenti%20di%20tutela%3A%20in%20caso%20di%20reiezione%20"
                "l'interessato%20pu%C3%B2%20presentare%20istanza%20di%20riesame.%3C%2Fp%3E"
            )
        },
        "pdf": (
            "%2Fcontent%2Fdam%2Finps-site%2Fit%2Fscorporati%2Fcircolari-e-messaggi%2F2026%2F05%2F"
            "Circolare_15256%2FAllegati%2F16758_Circolare-numero-53-del-07-05-2026.pdf"
        ),
        "allegati": {
            "value": [
                {
                    "encodedPath": (
                        "%2Fcontent%2Fdam%2Finps-site%2Fit%2Fscorporati%2Fcircolari-e-messaggi%2F2026%2F05%2F"
                        "Circolare_15256%2FAllegati%2F16758_Circolare-numero-53-del-07-05-2026.pdf"
                    ),
                    "title": "Circolare%20numero%2053%20del%2007-05-2026.pdf",
                },
                {
                    "encodedPath": (
                        "%2Fcontent%2Fdam%2Finps-site%2Fit%2Fscorporati%2Fcircolari-e-messaggi%2F2026%2F05%2F"
                        "Circolare_15256%2FAllegati%2F16759_Circolare-numero-53-del-07-05-2026_Allegato-n-1.pdf"
                    ),
                    "title": "Circolare%20numero%2053%20del%2007-05-2026_Allegato%20n%201.pdf",
                },
            ]
        },
    }
    requested: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        if str(url) == json_url:
            return DummyResponse(json.dumps(payload).encode("utf-8"), content_type="application/json")
        if str(url) in {main_pdf, allegato_pdf}:
            return DummyResponse(b"%PDF-1.4\n% documento INPS\n", content_type="application/pdf")
        raise AssertionError(f"URL inatteso: {url}")

    monkeypatch.setenv("IUSENTRA_LEGAL_VERIFICATION_ATTACHMENT_MAX_LINKS", "2")
    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(
        verification,
        "_text_from_attachment",
        lambda url, content, content_type: (
            "Circolare numero 53 del 07-05-2026 indennità una tantum e strumenti di tutela."
        ),
    )

    context, attachments = verification._fetch_official_web_context_with_attachments(source_url, timeout=2)

    assert json_url in requested
    assert main_pdf in requested
    assert allegato_pdf in requested
    assert "Circolare numero 53 del 07-05-2026" in context
    assert "Decreto-legge 27 febbraio 2026, n. 25" in context
    assert "istanza di riesame" in context
    assert len(attachments) == 2
    assert {row["attachment_url"] for row in attachments} == {main_pdf, allegato_pdf}
    assert all(row["source_name"] == "INPS" for row in attachments)


def test_helper_cassazione_salva_allegato_anche_se_pdf_non_ha_testo(monkeypatch):
    source_url = "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50202"
    attachment_url = "https://www.cortedicassazione.it/resources/cms/documents/14740_04_2026_pen_noindex.pdf"
    pdf_bytes = b"%PDF-1.7\n% scansione\n"
    requested: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        if str(url) == source_url:
            return DummyResponse(
                """
                <html><body>
                  <main>
                    <h1>Dettaglio questione penale Pendente n. 37184/2025</h1>
                    <p>Ordinanza di rimessione: 14740/2026</p>
                    <a href="/resources/cms/documents/14740_04_2026_pen_noindex.pdf">
                      Scarica Documento Ordinanza di rimessione alle SU RG. 14740/2026
                    </a>
                  </main>
                </body></html>
                """.encode("utf-8"),
                content_type="text/html; charset=utf-8",
            )
        if str(url) == attachment_url:
            return DummyResponse(pdf_bytes, content_type="application/pdf")
        raise AssertionError(f"URL inatteso: {url}")

    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(verification, "_text_from_attachment", lambda url, content, content_type: "")

    context, attachments = verification._fetch_official_web_context_with_attachments(source_url, timeout=2)

    assert requested == [source_url, attachment_url]
    assert "Ordinanza di rimessione: 14740/2026" in context
    assert len(attachments) == 1
    row = attachments[0]
    assert row["source_name"] == "Corte Suprema di Cassazione"
    assert row["attachment_url"] == attachment_url
    assert row["sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert row["context_chars"] == 0
    assert "testo non estraibile" in row["excerpt"]


def test_helper_cassazione_qsp50194_salva_testo_ocr_allegato(monkeypatch):
    source_url = "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50194"
    attachment_url = (
        "https://www.cortedicassazione.it/resources/cms/documents/"
        "Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf"
    )
    pdf_bytes = b"%PDF-1.7\n% scansione cassazione\n"
    requested: list[str] = []

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        if str(url) == source_url:
            return DummyResponse(
                """
                <html><body>
                  <main>
                    <h1>Dettaglio questione penale Pendente n. 9926/2026</h1>
                    <p>Questione penale Pendente del ricorso R.G. n. 9926/2026 ud. 09/07/2026.</p>
                    <a href="/resources/cms/documents/Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf">
                      Ordinanza di rimessione
                    </a>
                  </main>
                </body></html>
                """.encode("utf-8"),
                content_type="text/html; charset=utf-8",
            )
        if str(url) == attachment_url:
            return DummyResponse(pdf_bytes, content_type="application/pdf")
        raise AssertionError(f"URL inatteso: {url}")

    def fake_extract_text_from_document(content: bytes, filename: str, file_type: str):
        assert content == pdf_bytes
        assert filename == "Nota_Ufficio_Spoglio_V_Sez._penale_RG_9966_2026_1.pdf"
        assert file_type == "pdf"
        return SimpleNamespace(
            ok=True,
            text="Nota Ufficio Spoglio V Sez. penale R.G. 9966/2026: ordinanza di rimessione.",
        )

    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(
        "pct.document_intelligence.extraction.extract_text_from_document",
        fake_extract_text_from_document,
    )

    context, attachments = verification._fetch_official_web_context_with_attachments(source_url, timeout=2)

    assert requested == [source_url, attachment_url]
    assert "Questione penale Pendente del ricorso R.G. n. 9926/2026" in context
    assert "ordinanza di rimessione" in context
    assert len(attachments) == 1
    row = attachments[0]
    assert row["attachment_url"] == attachment_url
    assert row["context_chars"] > 0
    assert "R.G. 9966/2026" in row["text_excerpt"]


def test_verifica_web_conserva_allegato_cassazione_se_la_pagina_e_pertinente(monkeypatch):
    source_url = "https://www.cortedicassazione.it/it/qsp_dettaglio.page?contentId=QSP50202"
    attachment_url = "https://www.cortedicassazione.it/resources/cms/documents/14740_04_2026_pen_noindex.pdf"
    review = {
        "proposed_action": "NEWS_ONLY",
        "title": "Cassazione QSP50202 ordinanza 14740/2026",
        "source_url": source_url,
        "source_name": "Cassazione",
        "source_code": "cassazione_massimario",
        "classification_type": "GIURISPRUDENZA",
        "summary_short": "Questione Cassazione su ordinanza di rimessione 14740/2026.",
    }
    source = {
        "name": "Cassazione Massimario",
        "code": "cassazione_massimario",
        "category": "giurisprudenza",
        "trust_class": "A",
        "is_official": True,
    }

    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_official_sources", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_normattiva", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_gazzetta", lambda query, limit=5: [])
    monkeypatch.setattr(
        "lex.retrieval.official_web.search_recognized_official_web",
        lambda query, source_ids=None, limit_results=5: [
            {
                "title": "QSP50202 - ordinanza 14740/2026",
                "url": source_url,
                "source_name": "Corte Suprema di Cassazione",
                "official": True,
                "excerpt": "Ordinanza di rimessione 14740/2026 alla Corte di cassazione.",
            }
        ],
    )
    monkeypatch.setattr(
        verification,
        "_fetch_official_web_context_with_attachments",
        lambda url: (
            "QSP50202 ordinanza di rimessione 14740/2026 Corte di cassazione.",
            [
                {
                    "origin": "allegato_fonte_ufficiale",
                    "source_name": "Corte Suprema di Cassazione",
                    "source_url": source_url,
                    "attachment_url": attachment_url,
                    "attachment_type": "pdf",
                    "sha256": "hash-cassazione",
                    "official": True,
                    "title": "14740_04_2026_pen_noindex.pdf",
                    "excerpt": "Allegato scaricato dalla fonte ufficiale; testo non estraibile automaticamente.",
                    "content": "Allegato scaricato dalla fonte ufficiale; testo non estraibile automaticamente.",
                    "context_chars": 0,
                    "matched_terms": [],
                }
            ],
        ),
    )

    report = verification.verify_legal_update_against_public_sources(review, source, limit=2)

    assert report["ok"] is True
    assert any(row.get("attachment_url") == attachment_url for row in report["confirmations"])


def test_verifica_web_restituisce_conferma_allegato_ufficiale(monkeypatch):
    source_url = "https://www.gazzettaufficiale.it/scheda/26G00056"
    attachment_url = "https://www.gazzettaufficiale.it/resources/cms/documents/testo-ufficiale.pdf"
    pdf_bytes = b"%PDF-1.4\n% test ufficiale\n"
    requested: list[str] = []

    review = {
        "proposed_action": "NEW_NORMATIVE",
        "title": "Decreto legislativo n. 56 del 2026 sulla conciliazione",
        "source_url": source_url,
        "source_name": "Gazzetta Ufficiale",
        "classification_type": "NORMATIVA_NUOVA",
        "norm_type": "decreto legislativo",
        "norm_number": "56",
        "norm_year": "2026",
        "summary_short": "Aggiorna la conciliazione giudiziale.",
    }
    source = {
        "name": "Gazzetta Ufficiale",
        "code": "gazzetta_ufficiale",
        "category": "normativa",
        "trust_class": "A",
        "is_official": True,
    }

    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_official_sources", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_normattiva", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_gazzetta", lambda query, limit=5: [])
    monkeypatch.setattr(
        "lex.retrieval.official_web.search_recognized_official_web",
        lambda query, source_ids=None, limit_results=5: [
            {
                "title": "Scheda Gazzetta con allegato",
                "url": source_url,
                "source_name": "Gazzetta Ufficiale",
                "excerpt": "Scheda senza testo completo.",
            }
        ],
    )

    def fake_get(url: str, **kwargs: Any) -> DummyResponse:
        requested.append(str(url))
        assert "evil.test" not in str(url)
        if str(url) == attachment_url:
            return DummyResponse(pdf_bytes, content_type="application/pdf")
        return DummyResponse(HTML_FIXTURE.encode("utf-8"), content_type="text/html; charset=utf-8")

    monkeypatch.setattr(verification.requests, "get", fake_get)
    monkeypatch.setattr(
        verification,
        "_text_from_attachment",
        lambda url, content, content_type: "Decreto legislativo n. 56 del 2026 sulla conciliazione giudiziale.",
    )

    report = verification.verify_legal_update_against_public_sources(review, source, limit=2)

    attachments = [row for row in report["confirmations"] if row.get("origin") == "allegato_fonte_ufficiale"]
    assert attachments
    assert attachments[0]["source_url"] == source_url
    assert attachments[0]["attachment_url"] == attachment_url
    assert attachments[0]["attachment_type"] == "pdf"
    assert attachments[0]["sha256"] == hashlib.sha256(pdf_bytes).hexdigest()
    assert attachments[0]["official"] is True
    assert attachments[0]["context_chars"] > 20
    assert not any("evil.test" in url for url in requested)


def test_verifica_web_cerca_inps_con_titolo_minimo_e_piano_esteso(monkeypatch):
    review = {
        "proposed_action": "NEWS_ONLY",
        "title": "Circolare numero 53 del 07-05-2026",
        "source_url": (
            "https://www.inps.it/it/it/inps-comunica/atti/circolari-messaggi-e-normativa/"
            "dettaglio.circolari-e-messaggi.2026.05.circolare-numero-53-del-07-05-2026_15256.html"
        ),
        "source_name": "INPS - circolari",
        "source_code": "inps_circolari",
        "classification_type": "COMMENTO",
        "summary_short": "Circolare INPS su indennità una tantum e strumenti di tutela.",
    }
    source = {
        "name": "INPS - circolari",
        "code": "inps_circolari",
        "category": "prassi",
        "trust_class": "A",
        "is_official": True,
    }
    calls: list[tuple[str, tuple[str, ...]]] = []

    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_official_sources", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_normattiva", lambda query, limit=5: [])
    monkeypatch.setattr("lex.retrieval.official_sources_retriever.search_gazzetta", lambda query, limit=5: [])

    def fake_web_search(query: str, source_ids=None, limit_results=5):
        calls.append((query, tuple(source_ids or ())))
        return []

    monkeypatch.setattr("lex.retrieval.official_web.search_recognized_official_web", fake_web_search)

    report = verification.verify_legal_update_against_public_sources(review, source, limit=2)

    assert report["searched"]["queries"]
    assert any(query == "Circolare numero 53 del 07-05-2026" for query, _source_ids in calls)
    assert any("inps_circolari" in source_ids for _query, source_ids in calls)
    assert any(source_ids == () for _query, source_ids in calls)
