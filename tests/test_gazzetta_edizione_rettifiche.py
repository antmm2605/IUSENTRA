"""La vista HTML originario non prova la prima pubblicazione PDF."""
from datetime import date
from html import escape
from io import BytesIO
from urllib.parse import urlencode

import pytest

from lex.normativa.biblioteca.gazzetta_originale import BASE, acquisisci_originale


@pytest.mark.parametrize("nota,edizione", [
    ("", "HTML_GU_ORIGINARIO"),
    ("L'atto e' integrato con le correzioni apportate dall'avviso di rettifica pubblicato in GU 13/11/2001.", "HTML_GU_ORIGINARIO_CON_RETTIFICHE"),
    ("Errata-corrige pubblicata successivamente.", "HTML_GU_ORIGINARIO_CON_RETTIFICHE"),
])
def test_html_con_rettifiche_non_diventa_prima_pubblicazione(nota, edizione):
    title = "DECRETO DEL PRESIDENTE DELLA REPUBBLICA 6 giugno 2001, n. 379"
    menu = BASE + "/atto/vediMenuHTML?" + urlencode({
        "atto.dataPubblicazioneGazzetta": "2001-10-20",
        "atto.codiceRedazionale": "001G0428", "tipoVigenza": "originario",
    })
    article = BASE + "/atto/serie_generale/caricaArticolo?" + urlencode({
        "art.dataPubblicazioneGazzetta": "2001-10-20",
        "art.codiceRedazionale": "001G0428", "art.versione": "1",
        "art.idArticolo": "1", "art.flagTipoArticolo": "0",
    })
    first = BASE + "/eli/id/2001/10/20/001G0428/sg"
    documents = {
        first: (f'<div id="titolo_atto">{escape(title)} {escape(nota)}</div>'
                f'<a href="{escape(menu)}">Testo originario</a>').encode(),
        menu: f'<a href="{escape(article)}">Articolo 1</a>'.encode(),
        article: b'<div class="dettaglio_atto_testo"><pre>Art. 1\nTesto pubblicato nella vista ufficiale.</pre></div>',
    }

    class Response(BytesIO):
        def __init__(self, url):
            super().__init__(documents[url])
            self.url = url

        def geturl(self):
            return self.url

    class Opener:
        def open(self, url, timeout):
            return Response(url)

    result = acquisisci_originale(data_gu=date(2001, 10, 20),
        codice_redazionale="001G0428", intestazione_attesa=title, opener=Opener())
    assert result.vista_edizione == edizione
    assert nota in result.annotazioni_edizione
    assert result.articoli[0]["edizione"] == edizione
    assert result.articoli[0]["prima_pubblicazione_pdf_verificata"] is False
    assert result.articoli[0]["applicabilita_verificata"] is False
    assert result.articoli[0]["testo"] == "Art. 1\nTesto pubblicato nella vista ufficiale."
    assert len(result.documenti) == 3
