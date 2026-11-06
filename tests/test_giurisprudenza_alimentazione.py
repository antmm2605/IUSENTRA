"""Alimentazione continua: riparazione dei collegamenti e lettura incrementale delle citazioni nell'archivio."""

from contextlib import closing

from pct.giurisprudenza_alimentazione import attiva, collegamento_decisione, esegui_giro, leggi_citazioni, ripara_collegamenti
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza

ELENCO = ("https://www.italgiure.giustizia.it/sncass/isapi/hc.dll/sn.solr/sn-collection/select?q=kind%3A%28snciv+OR+snpen%29"
          "&rows=2&sort=id+asc&cursorMark=%2A&wt=json")


def _archivio(tmp_path):
    owner = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))
    owner.salva_sentenza({
        "uuid_interno": "sentenzeweb:snciv2021104215O", "fonte_codice": "cassazione_sentenzeweb", "fonte_nome": "Corte di Cassazione — SentenzeWeb",
        "tipo_fonte": "ufficiale", "organo_giudicante": "Corte di Cassazione — civile", "sezione": "L", "numero_sentenza": "4215",
        "anno_sentenza": 2021, "titolo": "Cassazione snciv 4215/2021", "url_pagina_ufficiale": ELENCO, "testo_integrale_presente": True,
        "testo_integrale": "Violazione dell'art. 2087 c.c. e dell'art. 63, comma 2, del d.lgs. n. 165 del 2001 (Cass., Sez. U, n. 24418 del 2010).",
    })
    return owner


def test_si_attiva_solo_in_continua(monkeypatch):
    monkeypatch.delenv("IUSENTRA_ALIMENTAZIONE_GIURISPRUDENZA", raising=False)
    assert not attiva({}) and attiva({"IUSENTRA_ALIMENTAZIONE_GIURISPRUDENZA": "continua"})
    assert esegui_giro({})["status"] == "spenta"


def test_ripara_il_collegamento_di_elenco(tmp_path):
    owner = _archivio(tmp_path)
    with closing(owner._connect()) as connessione, connessione:
        assert ripara_collegamenti(connessione) == 1
        url = connessione.execute("SELECT url_pagina_ufficiale FROM sentenze").fetchone()[0]
        assert ripara_collegamenti(connessione) == 0
    assert url == collegamento_decisione("snciv2021104215O") and "cursorMark" not in url


def test_lettura_delle_citazioni_incrementale(tmp_path):
    owner = _archivio(tmp_path)
    primo = leggi_citazioni(owner)
    assert primo["lette"] == 1 and primo["norme"] == 2 and primo["precedenti"] == 1 and primo["da_leggere"] == 0
    assert leggi_citazioni(owner)["lette"] == 0
    with closing(owner._connect()) as connessione:
        norme = {(r[0], r[1]) for r in connessione.execute("SELECT n.sigla, n.articolo FROM norme n JOIN sentenza_norme sn ON sn.norma_id=n.id")}
        precedente = connessione.execute("SELECT sezione, numero_sentenza, anno_sentenza FROM sentenza_precedenti").fetchone()
    assert norme == {("c.c.", "2087"), ("D.Lgs. 165/2001", "63")}
    assert tuple(precedente) == ("U", "24418", 2010)
