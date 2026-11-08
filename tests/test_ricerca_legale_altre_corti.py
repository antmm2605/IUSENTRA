"""Corte costituzionale e giustizia amministrativa nella ricerca: righe nel formato comune, guasti dichiarati."""

from __future__ import annotations

from web.services.ricerca_legale_altre_corti import decisioni_giustizia_amministrativa, pronunce_corte_costituzionale


class _Corpus:
    def __init__(self):
        self.chiamate = []

    def cerca_sentenze(self, **kwargs):
        self.chiamate.append(kwargs)
        return [{"id": 7, "numero_sentenza": "75", "anno_sentenza": "2019", "tipo_provvedimento": "Sentenza",
                 "massima_ufficiale": "Notifica a mezzo PEC: si perfeziona per il notificante alla generazione della ricevuta di accettazione.",
                 "url_pagina_ufficiale": "https://www.cortecostituzionale.it/actionSchedaPronuncia.do?anno=2019&numero=75",
                 "oggetto": "notificazione telematica", "data_deposito": "2019-04-09"}]


def test_consulta_solo_dalla_sua_fonte_con_massima_e_link_ufficiale():
    corpus = _Corpus()
    righe = pronunce_corte_costituzionale("notifica pec orario", corpus=corpus)
    assert corpus.chiamate[0]["fonte_codice"] == "corte_costituzionale" and corpus.chiamate[0]["semantica"] is False
    assert righe[0]["title"].startswith("Corte costituzionale, sentenza n. 75/2019")
    assert righe[0]["content"].startswith("Notifica a mezzo PEC") and righe[0]["official_url"].startswith("https://www.cortecostituzionale.it/")


def test_openga_solo_estremi_ed_esito_dal_catalogo():
    risposta = {"evidence_scope": "metadata_only", "risultati": [{
        "organo_giudicante": "TAR EMILIA-ROMAGNA - BOLOGNA", "numero_sentenza": "202300173", "anno_sentenza": 2023,
        "numero_ricorso": "202300041", "oggetto": "SILENZIO DELLA PUBBLICA AMMINISTRAZIONE",
        "esito": "DICHIARA CESSATA MATERIA DEL CONTENDERE", "decisione_id": "012|SENTENZA|2023|202300173",
        "official_search_url": "https://www.giustizia-amministrativa.it/dcsnprr"}]}
    righe = decisioni_giustizia_amministrativa("silenzio", endpoint="http://openga", richiesta=lambda _e, _q: risposta)
    assert righe[0]["title"] == "TAR EMILIA-ROMAGNA - BOLOGNA, sentenza n. 173/2023 — Silenzio della pubblica amministrazione"
    assert "Esito: Dichiara cessata materia del contendere" in righe[0]["content"]


def test_openga_spento_o_risposta_fuori_perimetro_non_produce_righe():
    assert decisioni_giustizia_amministrativa("x", endpoint="") == []
    assert decisioni_giustizia_amministrativa("x", endpoint="http://openga", richiesta=lambda _e, _q: {"risultati": [{}]}) == []
