"""Canali ufficiali delle Notizie utili: lettura dei feed registrati l'08/11/2026 (nessuna rete nei test)."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests

from lex.normativa import materie as m
from pct.notiziario import adattatori, fonti
from pct.notiziario.classifica import atti_citati
from pct.notiziario.feed import data_della_voce, leggi_feed
from pct.notiziario.rete import DIMENSIONE_MASSIMA, ErroreFonte, scarica

FIXTURE = Path(__file__).parent / "fixtures" / "notiziario"


def _notizie(fonte_id: str, file: str) -> list[dict]:
    return adattatori.da_feed(fonti.fonte(fonte_id), leggi_feed((FIXTURE / file).read_bytes()))


def test_ogni_fonte_feed_ha_url_ufficiale_https_e_data_di_verifica():
    for fonte in fonti.FONTI:
        assert fonte.url.startswith("https://")
        assert fonte.verificato_il == "2026-11-08"
        assert fonte.tipo in fonti.ETICHETTE_TIPO
        if fonte.formato == "rss":
            assert fonte.host_ammessi and fonte.url.split("/")[2] in fonte.host_ammessi


def test_gazzetta_serie_generale_collegamento_https_codice_redazionale_e_atti_citati():
    notizie = _notizie("gu_serie_generale", "gu_serie_generale.xml")
    assert len(notizie) == 5
    prima = notizie[0]
    assert prima["url"] == "https://www.gazzettaufficiale.it/eli/id/2026/11/07/26A05807/SG"
    assert prima["data"] == "2026-11-07"
    assert prima["tipo"] == fonti.NORMA
    assert prima["riferimento_ufficiale"] == "Codice redazionale 26A05807"
    assert prima["sintesi"].startswith("Proroga dello stato di emergenza")
    assert notizie[1]["atti"] == ["legge:128:1998", "legge:526:1999"]


def test_corte_costituzionale_dalla_gazzetta_distingue_pronunce_e_atti_di_promovimento():
    notizie = _notizie("gu_corte_costituzionale", "gu_corte_costituzionale.xml")
    per_titolo = {n["titolo"]: n for n in notizie}
    assert per_titolo["n. 179 SENTENZA 21 settembre - 2 novembre 2026"]["tipo"] == fonti.PRONUNCIA
    assert per_titolo["n. 178 ORDINANZA 5 - 29 ottobre 2026"]["tipo"] == fonti.PRONUNCIA
    # pubDate «Wed, 28 Oct 2026 23:00:00 GMT» è il 29 ottobre a Roma
    assert per_titolo["n. 178 ORDINANZA 5 - 29 ottobre 2026"]["data"] == "2026-10-29"
    ricorso = next(n for n in notizie if n["titolo"].startswith("n. 22 RICORSO"))
    assert ricorso["tipo"] == fonti.NOTIZIA
    assert next(n for n in notizie if "Atto di promovimento" in n["titolo"])["tipo"] == fonti.NOTIZIA


def test_inps_data_dal_campo_pubdate_italiano_e_materia_previdenziale_certa():
    notizie = _notizie("inps_circolari", "inps_circolari.xml")
    assert notizie[0]["titolo"] == "Circolare numero 110 del 05-11-2026"
    assert notizie[0]["data"] == "2026-11-05"
    assert notizie[0]["tipo"] == fonti.PRASSI
    # «riscossione dei contributi» non la rende tributaria: l'INPS è l'ente previdenziale
    assert {n["materia"] for n in notizie} == {m.LAVORO}


def test_agenzia_entrate_prassi_tributaria_senza_sintesi_inventata():
    notizie = _notizie("entrate_prassi", "entrate_prassi.xml")
    assert all(n["materia"] == m.TRIBUTARIO and n["tipo"] == fonti.PRASSI for n in notizie)
    assert all(n["sintesi"] == "" for n in notizie)  # il feed non pubblica una descrizione
    assert notizie[0]["atti"] == ["dlgs:1:2024"]


def test_garante_scarta_il_collegamento_malformato_del_feed():
    notizie = _notizie("garante_privacy", "garante_privacy.xml")
    assert all(" " not in n["url"] for n in notizie)
    assert all(n["url"].startswith("https://www.gpdp.it/garante/doc.jsp?ID=") for n in notizie)
    assert len(notizie) == 2


def test_eurlex_toglie_il_prefisso_celex_e_conserva_il_riferimento():
    notizie = _notizie("eurlex_gu_l", "eurlex_gu_l.xml")
    regolamento = next(n for n in notizie if n["riferimento_ufficiale"] == "CELEX 32026R2496")
    assert regolamento["titolo"].startswith("Regolamento di esecuzione (UE) 2026/2496")
    assert regolamento["url"] == "https://eur-lex.europa.eu/legal-content/AUTO/?uri=CELEX:32026R2496"
    assert "regue:2496:2026" in regolamento["atti"]
    assert all(n["materia"] == m.UE for n in notizie)


def test_eurlex_scarta_le_rettifiche_che_non_riguardano_la_versione_italiana():
    contenuto = (
        b'<?xml version="1.0"?><rss version="2.0"><channel><title>EUR-Lex</title><item>'
        b"<title>CELEX:32009L0081R(04): Berichtigung</title>"
        b"<description>La rettifica non riguarda la versione italiana.</description>"
        b"<link>https://eur-lex.europa.eu/./legal-content/AUTO/?uri=CELEX:32009L0081R(04)</link>"
        b"<pubDate>Fri, 06 Nov 2026 00:00:00 +0100</pubDate></item></channel></rss>"
    )
    assert adattatori.da_feed(fonti.fonte("eurlex_gu_l"), leggi_feed(contenuto)) == []


def test_cedu_una_sola_notizia_per_ricorso_anche_se_pubblicata_in_inglese_e_francese():
    notizie = _notizie("cedu_italia", "hudoc_italia.xml")
    assert len(notizie) == 2
    assert {n["riferimento_ufficiale"] for n in notizie} == {
        "78000/16;72022/17;18213/18;46960/18 - Committee Judgment",
        "44596/18;13410/23;36375/24 - Chamber Judgment",
    }


def test_curia_pronunce_con_descrizione_ufficiale_senza_tag():
    notizie = _notizie("curia", "curia.xml")
    assert notizie[0]["titolo"].startswith("161/2026 : 5 novembre 2026 - Sentenza della Corte")
    assert "<" not in notizie[0]["sintesi"] and notizie[0]["sintesi"]
    assert notizie[0]["tipo"] == fonti.PRONUNCIA


def test_identificativo_coincide_con_quello_gia_usato_dalle_notizie_utili():
    # stesse letture e preferiti salvati prima del nuovo archivio
    assert adattatori.identificativo_notizia("cassazione", "https://www.cortedicassazione.it/x").startswith("official_")
    assert len(adattatori.identificativo_notizia("cassazione", "https://www.cortedicassazione.it/x")) == 33


def test_voci_senza_data_non_entrano():
    contenuto = (
        b'<rss version="2.0"><channel><item><title>Senza data</title>'
        b"<link>https://www.inps.it/x</link></item></channel></rss>"
    )
    assert adattatori.da_feed(fonti.fonte("inps_circolari"), leggi_feed(contenuto)) == []


def test_feed_con_entita_dichiarate_viene_rifiutato():
    contenuto = (
        b'<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]>'
        b"<rss><channel><item><title>&x;</title></item></channel></rss>"
    )
    with pytest.raises(ErroreFonte):
        leggi_feed(contenuto)


def test_pagina_html_al_posto_del_feed_e_un_errore_della_fonte():
    with pytest.raises(ErroreFonte):
        leggi_feed(b"<html><body>Radware Captcha Page</body></html>")


def test_date_dei_feed():
    assert data_della_voce("Thu, 5 Nov 2026 10:08:21 +0100") == "2026-11-05"
    assert data_della_voce("2026-11-06T00:00:00Z") == "2026-11-06"
    assert data_della_voce("05/11/2026") == "2026-11-05"
    assert data_della_voce("31/02/2026") == ""


def test_atti_citati_nelle_forme_ufficiali():
    testo = (
        "art. 1, comma 121, della legge n. 107 del 2015; decreto legislativo 30 marzo 2001, n. 165; "
        "D.Lgs. 165/2001; d.P.R. 115/2002; Regolamento (UE) 2016/679"
    )
    assert atti_citati(testo) == ["legge:107:2015", "dlgs:165:2001", "dpr:115:2002", "regue:679:2016"]


class _Risposta:
    def __init__(self, status: int = 200, corpo: bytes = b"<rss/>", location: str = ""):
        self.status_code = status
        self.headers = {"Location": location} if location else {}
        self._corpo = corpo

    def iter_content(self, chunk_size: int):
        for inizio in range(0, len(self._corpo), chunk_size):
            yield self._corpo[inizio:inizio + chunk_size]


def test_rete_rifiuta_host_non_ammessi_e_reindirizzamenti_verso_altri_siti():
    host = ("www.inps.it",)
    with pytest.raises(ErroreFonte):
        scarica("https://example.com/feed", host, request_get=lambda *a, **k: _Risposta())
    with pytest.raises(ErroreFonte):
        scarica(
            "https://www.inps.it/feed", host,
            request_get=lambda *a, **k: _Risposta(302, location="https://example.com/altro"),
        )


def test_rete_tempo_massimo_stato_e_dimensione():
    host = ("www.inps.it",)

    def _lenta(*_a, **_k):
        raise requests.Timeout("lenta")

    with pytest.raises(ErroreFonte, match="tempo massimo"):
        scarica("https://www.inps.it/feed", host, request_get=_lenta)
    with pytest.raises(ErroreFonte, match="503"):
        scarica("https://www.inps.it/feed", host, request_get=lambda *a, **k: _Risposta(503))
    with pytest.raises(ErroreFonte, match="dimensione"):
        scarica(
            "https://www.inps.it/feed", host,
            request_get=lambda *a, **k: _Risposta(corpo=b"x" * (DIMENSIONE_MASSIMA + 1)),
        )


def test_rete_passa_timeout_e_niente_reindirizzamenti_automatici():
    chiamate: list[dict] = []

    def _get(url, **kwargs):
        chiamate.append(kwargs)
        return _Risposta(corpo=b"<rss></rss>")

    assert scarica("https://www.inps.it/feed", ("www.inps.it",), request_get=_get) == b"<rss></rss>"
    assert chiamate[0]["timeout"] and chiamate[0]["allow_redirects"] is False


_GU = ("www.gazzettaufficiale.it", "gazzettaufficiale.it")


@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "https://www.gazzettaufficiale.it@evil.example/",
    "https://evil.example\\@www.gazzettaufficiale.it",
    "https://utente:segreta@www.gazzettaufficiale.it/eli/id/2026/11/07/26A05807/SG",
    "https://www.gazzettaufficiale.it:8443/eli/id/2026/11/07/26A05807/SG",
    "https://evil.example/eli/id/2026/11/07/26A05807/SG",
    "https://www.gazzettaufficiale.it.evil.example/",
    "ftp://www.gazzettaufficiale.it/file",
    "https://www.gazzettaufficiale.it/eli/\x00id",
    "//www.gazzettaufficiale.it/eli/id",
    "",
])
def test_collegamento_ufficiale_scarta_gli_indirizzi_non_dell_ente(url):
    assert adattatori.collegamento_ufficiale(url, _GU) == ""


def test_collegamento_ufficiale_mantiene_e_porta_su_https_l_indirizzo_dell_ente():
    assert adattatori.collegamento_ufficiale("http://www.gazzettaufficiale.it/eli/id/2026/11/07/26A05807/SG", _GU) == (
        "https://www.gazzettaufficiale.it/eli/id/2026/11/07/26A05807/SG"
    )
    assert adattatori.collegamento_ufficiale("https://WWW.GazzettaUfficiale.it/rss/SG?x=1#frammento", _GU) == (
        "https://www.gazzettaufficiale.it/rss/SG?x=1"
    )


def test_pagine_istituzionali_scartano_i_collegamenti_fuori_dal_dominio_della_fonte():
    righe = [
        {"id": "official_" + "1" * 24, "title": "Avviso PST", "published_at": "2026-11-03",
         "source_url": "https://pst.giustizia.it/PST/it/news.page?contentId=NEW1", "short_summary": ""},
        {"id": "official_" + "2" * 24, "title": "Avviso ingannevole", "published_at": "2026-11-03",
         "source_url": "https://www.cortedicassazione.it/it/altro.page", "short_summary": ""},
        {"id": "official_" + "3" * 24, "title": "Avviso script", "published_at": "2026-11-03",
         "source_url": "javascript:alert(1)", "short_summary": ""},
    ]
    notizie = adattatori.da_pagina_istituzionale(fonti.fonte("pst_giustizia"), righe)
    assert [n["url"] for n in notizie] == ["https://pst.giustizia.it/PST/it/news.page?contentId=NEW1"]


def test_ogni_fonte_dichiara_i_propri_host_ufficiali():
    for fonte in fonti.FONTI:
        assert fonte.host_ammessi, fonte.id
        assert fonte.url.split("/")[2] in fonte.host_ammessi, fonte.id
