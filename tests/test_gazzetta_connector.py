from __future__ import annotations

from lex.sources.connectors.gazzetta_ufficiale import GazzettaUfficialeConnector
from lex.sources.models import SourceConfig


def _connector() -> GazzettaUfficialeConnector:
    return GazzettaUfficialeConnector(
        SourceConfig(
            id="gazzetta_ufficiale",
            name="Gazzetta Ufficiale",
            enabled=True,
            priority=95,
            connector="gazzetta_ufficiale",
            base_url="https://www.gazzettaufficiale.it/",
        )
    )


def test_gazzetta_download_pdf_url_from_paginato():
    connector = _connector()
    url = (
        "https://www.gazzettaufficiale.it/do/gazzetta/serie_generale/0/pdfPaginato"
        "?dataPubblicazioneGazzetta=20260424&numeroGazzetta=95&tipoSerie=SG"
        "&tipoSupplemento=GU&numeroSupplemento=0&progressivo=0&numPagina=1&home=true"
    )

    issue = connector._issue_from_url(url, "https://www.gazzettaufficiale.it/30giorni/serie_generale")

    assert issue is not None
    assert "/do/gazzetta/downloadPdf" in issue.download_url
    assert "numPagina" not in issue.download_url
    assert "dataPubblicazioneGazzetta=20260424" in issue.download_url
    assert issue.data_pubblicazione == "20260424"


def test_gazzetta_extracts_issue_links_from_html():
    connector = _connector()
    html = """
    <html><body>
      <a href="/do/gazzetta/serie_generale/0/pdfPaginato?dataPubblicazioneGazzetta=20260424&numeroGazzetta=95&tipoSerie=SG&tipoSupplemento=GU&numeroSupplemento=0&progressivo=0&numPagina=1&edizione=0">PDF</a>
    </body></html>
    """

    issues = connector._extract_issues_from_html(html, "https://www.gazzettaufficiale.it/30giorni/serie_generale")

    assert len(issues) == 1
    assert issues[0].numero_gazzetta == "95"
