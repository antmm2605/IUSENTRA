"""La pagina della Guida mostra come fonte solo la giurisprudenza verificata nell'archivio."""

import web.services.guida_giurisprudenza_runtime as runtime
from pct.giurisprudenza_alimentazione import leggi_citazioni
from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza


def test_citazioni_tolte_dalle_norme_e_verificate(tmp_path, monkeypatch):
    owner = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))
    owner.salva_sentenza({"uuid_interno": "sentenzeweb:snciv2025L33700O", "fonte_codice": "cassazione_sentenzeweb", "fonte_nome": "Cassazione",
                          "tipo_fonte": "ufficiale", "organo_giudicante": "Corte di Cassazione — civile", "sezione": "L", "numero_sentenza": "33700",
                          "anno_sentenza": 2025, "titolo": "Cassazione 33700/2025", "url_pagina_ufficiale": "https://www.italgiure.giustizia.it/x",
                          "testo_integrale_presente": True, "testo_integrale": "Violazione dell'art. 7, legge n. 300/1970 e dell'art. 2087 c.c."})
    leggi_citazioni(owner)
    monkeypatch.setattr(runtime, "_archivi", lambda: (tmp_path / "giurisprudenza_corpus.db", None))
    guida = {"normativa": {"riferimenti_primari": [{"fonte": "c.c.", "articolo": "2087"}, {"fonte": "Cass. SU 14897/2021", "descrizione": "inventata"}],
                           "riferimenti_secondari": [{"fonte": "Cass. lav. 33700/2025"}]}}
    risultato = runtime.arricchisci_giurisprudenza(guida)
    assert risultato["normativa"]["riferimenti_primari"] == [{"fonte": "c.c.", "articolo": "2087"}]
    assert risultato["normativa"]["riferimenti_secondari"] == []
    sezione = risultato["giurisprudenza"]
    assert [v["citazione"] for v in sezione["verificate"]] == ["Cass. lav. 33700/2025"] and sezione["non_verificate"] == 1
    assert sezione["decisioni_per_norma"][0]["decisione"] == "Cass. lav. 33700/2025"
