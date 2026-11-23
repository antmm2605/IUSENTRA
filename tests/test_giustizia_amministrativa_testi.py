"""Testo integrale delle sentenze del Consiglio di Stato e del CGA dal sito ufficiale (estremi da OpenGA)."""
from types import SimpleNamespace

from pct.giustizia_amministrativa_testi import ArchivioTestiGA, leggi

PAGINA = ("<html><body><p>Pubblicato il 11/03/2020</p><p>REPUBBLICA ITALIANA</p><p>IN NOME DEL POPOLO ITALIANO</p>"
          "<p>Il Consiglio di Stato in sede giurisdizionale (Sezione Sesta) ha pronunciato la presente SENTENZA sul ricorso "
          "numero di registro generale 4232 del 2019, proposto da ... per l'esecuzione del giudicato ... annullamento del "
          "titolo edilizio e dell'assenso paesistico ... " + "motivazione " * 40 + "</p><script>x()</script></body></html>")


def _righe():
    return [
        {"sede": "002", "nome_sede": "CdS GIURISDIZIONALE - ROMA", "tipo": "SENTENZA", "numero": "202001731", "anno": 2020,
         "ricorso": "201904232", "oggetto": "ESECUZIONE SENTENZA - ASSENSO PAESISTICO", "esito": "RESPINGE"},
        {"sede": "002", "nome_sede": "CdS GIURISDIZIONALE - ROMA", "tipo": "SENTENZA", "numero": "202607168", "anno": 2026,
         "ricorso": "202603768", "oggetto": "APPALTI", "esito": ""},
        {"sede": "032", "nome_sede": "CGA GIURISDIZIONALE - PALERMO", "tipo": "SENTENZA BREVE", "numero": "202600659",
         "anno": 2026, "ricorso": "202600141", "oggetto": "EDILIZIA", "esito": ""},
        {"sede": "027", "nome_sede": "TAR TRENTINO ALTO ADIGE - TRENTO", "tipo": "SENTENZA", "numero": "202400191",
         "anno": 2024, "ricorso": "202400095", "oggetto": "VIGILI DEL FUOCO", "esito": ""},
    ]


def test_coda_testo_ricerca_e_404(tmp_path):
    archivio = ArchivioTestiGA(tmp_path / "ga.sqlite")
    assert archivio.carica_estremi(_righe()) == 4
    assert archivio.carica_estremi(_righe()) == 0
    coda = archivio.da_leggere()
    # Consiglio di Stato prima, poi CGA, poi TAR; dai più recenti.
    assert [c["id"].split("|")[-1] for c in coda] == ["202607168", "202001731", "202600659", "202400191"]
    assert coda[3]["url"] == ("https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&schema=tar_tn&nrg=202400095"
                              "&nomeFile=202400191_01.html&subDir=Provvedimenti")
    assert coda[1]["url"] == ("https://mdp.giustizia-amministrativa.it/visualizza/?nodeRef=&schema=cds&nrg=201904232"
                              "&nomeFile=202001731_11.html&subDir=Provvedimenti")

    def scarica(url):
        if "202001731" in url or "202600659" in url:
            return SimpleNamespace(status_code=200, url=url, content=PAGINA.encode())
        return SimpleNamespace(status_code=200, url="https://mdp.giustizia-amministrativa.it/visualizza/404.html", content=b"")

    esito = leggi(archivio, scarica=scarica, tempo_massimo=60, pausa=0)
    assert esito == {"letti": 2, "errori": 2}
    assert archivio.conteggi() == {"letto": 2, "non_disponibile": 2}
    trovati = archivio.cerca("assenso paesistico")
    assert [t["numero"] for t in trovati] and trovati[0]["pubblicato_il"] == "11/03/2020"
    assert archivio.da_leggere() == []
