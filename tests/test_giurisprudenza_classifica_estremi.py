"""Corpus giurisprudenziale: classifica delle ricerche testuali e ricerca per estremi."""

from __future__ import annotations

from pathlib import Path

import pytest

from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza, estremi_dalla_domanda


def _consulta(numero: int, anno: int, tipo: str, *, titoli: str, massime: list[str], dispositivo: str) -> dict:
    return {
        "fonte": {"codice": "corte_costituzionale", "nome": "Corte costituzionale", "tipo_fonte": "ufficiale"},
        "ecli": f"ECLI:IT:COST:{anno}:{numero}",
        "organo_giudicante": "Corte costituzionale",
        "numero_sentenza": str(numero),
        "anno_sentenza": anno,
        "tipo_provvedimento": tipo,
        "titolo": f"Corte costituzionale, {tipo} n. {numero}/{anno}",
        "abstract": titoli,
        "massima_ufficiale": " ".join(massime),
        "massime": [{"testo": testo, "ufficiale": True, "stato_verifica": "verificata"} for testo in massime],
        "principio_sintetico": dispositivo,
        "esito": dispositivo,
        "testo_integrale": " ".join(massime) + " " + dispositivo,
        "stato_verifica": "verificata",
        "url_pagina_ufficiale": f"https://www.cortecostituzionale.it/scheda-pronuncia/{anno}/{numero}",
    }


def _cassazione(numero: int, tipo: str, titolo: str, principio: str) -> dict:
    return {
        "fonte": {"codice": "cassazione", "nome": "Corte di Cassazione", "tipo_fonte": "ufficiale"},
        "organo_giudicante": "Corte di Cassazione",
        "numero_sentenza": str(numero),
        "anno_sentenza": 2018,
        "tipo_provvedimento": tipo,
        "titolo": titolo,
        "principio_sintetico": principio,
        "testo_integrale": principio,
        "stato_verifica": "verificata",
    }


@pytest.fixture()
def corpus(tmp_path: Path) -> GestioneCorpusGiurisprudenza:
    gestore = GestioneCorpusGiurisprudenza(str(tmp_path / "giurisprudenza_corpus.db"))
    gestore.salva_sentenze_blocco(
        [
            # Ordinanza di rinvio: parla molto di ergastolo ostativo ma decide solo il rinvio.
            _consulta(
                97, 2021, "ordinanza",
                titoli="Ordinamento penitenziario - Ergastolo ostativo - Liberazione condizionale - Rinvio",
                massime=["Ergastolo ostativo e liberazione condizionale: la trattazione delle questioni sull'ergastolo ostativo e' rinviata. " * 3],
                dispositivo="rinvia all'udienza pubblica del 10 maggio 2022 la trattazione delle questioni.",
            ),
            # Sentenza di merito sull'ergastolo ostativo.
            _consulta(
                253, 2019, "sentenza",
                titoli="Contraddittorio - Intervento | Ordinamento penitenziario - Ergastolo ostativo - Permesso premio",
                massime=[
                    "Sono inammissibili gli interventi di soggetti estranei al giudizio a quo.",
                    "E' costituzionalmente illegittima la presunzione assoluta di pericolosita' del condannato all'ergastolo ostativo che non collabora, ai fini del permesso premio.",
                ],
                dispositivo="dichiara l'illegittimita' costituzionale dell'art. 4-bis, comma 1, della legge n. 354 del 1975.",
            ),
            # Ordinanza che corregge un errore materiale: mai in testa a una domanda di merito.
            _consulta(
                6, 2020, "ordinanza",
                titoli="Correzione di errore materiale - Ergastolo ostativo",
                massime=["Correzione dell'errore materiale nella sentenza sull'ergastolo ostativo."],
                dispositivo="dispone che nella sentenza n. 253 del 2019 sia corretto il seguente errore materiale.",
            ),
            # Sentenza sul licenziamento con una massima lunga e ripetitiva su un solo termine.
            _consulta(
                194, 2018, "sentenza",
                titoli="Lavoro - Licenziamento illegittimo - Indennita' - Tutele crescenti",
                massime=["Il licenziamento illegittimo nel contratto a tutele crescenti: l'indennita' rigida e' illegittima."],
                dispositivo="dichiara l'illegittimita' costituzionale dell'art. 3, comma 1, del d.lgs. n. 23 del 2015.",
            ),
            _consulta(
                40, 2004, "sentenza",
                titoli="Lavoro - Indennita'",
                massime=["Indennita' " * 200],
                dispositivo="dichiara non fondata la questione.",
            ),
            _cassazione(194, "ordinanza", "Cass. civ., ord. n. 194/2018", "Licenziamento illegittimo: indennita' risarcitoria e tutele crescenti."),
            _cassazione(500, "sentenza", "Cass. civ., sent. n. 500/2018", "Locazione: canoni e indennita' di occupazione."),
        ],
        chiave_naturale=False,
    )
    return gestore


def _estremi(righe: list[dict]) -> list[str]:
    return [f"{riga['numero_sentenza']}/{riga['anno_sentenza']}" for riga in righe]


def test_estremi_dalla_domanda():
    assert estremi_dalla_domanda("sentenza n. 194/2018")["coppie"] == [("194", 2018)]
    corte = estremi_dalla_domanda("Corte cost. 253/2019")
    assert corte["coppie"] == [("253", 2019)] and corte["organo"] == "costituzionale"
    assert estremi_dalla_domanda("Corte cost., ord. n. 97 del 2021")["coppie"] == [("97", 2021)]
    assert estremi_dalla_domanda("ECLI:IT:COST:2019:253")["ecli"] == ["ECLI:IT:COST:2019:253"]
    assert estremi_dalla_domanda("194/2018")["coppie"] == [("194", 2018)]
    assert estremi_dalla_domanda("Cass. n. 500/2018")["organo"] == "cassazione"
    # gli estremi di atti normativi non sono pronunce
    assert estremi_dalla_domanda("legge n. 40/2004 sulla procreazione assistita")["coppie"] == []
    assert estremi_dalla_domanda("art. 3 del d.lgs. 23/2015")["coppie"] == []


@pytest.mark.parametrize(
    "domanda",
    ["sentenza n. 194/2018 Corte costituzionale", "Corte cost. 194/2018", "ECLI:IT:COST:2018:194"],
)
def test_ricerca_per_estremi_mette_prima_la_pronuncia(corpus, domanda):
    righe = corpus.cerca_sentenze(q=domanda, limit=5)
    assert righe[0]["ecli"] == "ECLI:IT:COST:2018:194"
    assert righe[0]["trovata_per_estremi"] is True
    assert len({riga["id"] for riga in righe}) == len(righe)


def test_estremi_senza_organo_trovano_tutte_le_pronunce_con_quel_numero(corpus):
    righe = corpus.cerca_sentenze(q="sentenza n. 194/2018", limit=5)
    assert {riga["organo_giudicante"] for riga in righe[:2]} == {"Corte costituzionale", "Corte di Cassazione"}


def test_estremi_rispettano_i_filtri(corpus):
    righe = corpus.cerca_sentenze(q="Cass. n. 194/2018", stato_verifica="da_verificare", limit=5)
    assert all(riga.get("trovata_per_estremi") is not True for riga in righe)


def test_sentenza_di_merito_prima_di_rinvio_e_correzione(corpus):
    righe = corpus.cerca_sentenze(q="ergastolo ostativo", limit=5)
    assert _estremi(righe)[0] == "253/2019"
    assert set(_estremi(righe)[-2:]) == {"97/2021", "6/2020"}


def test_se_la_domanda_chiede_il_rinvio_non_si_penalizza(corpus):
    righe = corpus.cerca_sentenze(q="rinvio della trattazione ergastolo ostativo", limit=5)
    assert _estremi(righe)[0] == "97/2021"


def test_massima_lunga_ripetitiva_non_vince_per_accumulo(corpus):
    righe = corpus.cerca_sentenze(q="licenziamento illegittimo indennita tutele crescenti", limit=5)
    assert _estremi(righe)[0] == "194/2018"
    assert _estremi(righe).index("40/2004") > 1


def test_cassazione_ordinanza_non_penalizzata(corpus):
    righe = corpus.cerca_sentenze(q="indennita risarcitoria licenziamento illegittimo", organo_giudicante="Corte di Cassazione", limit=5)
    assert righe[0]["tipo_provvedimento"] == "ordinanza"
    assert righe[0]["numero_sentenza"] == "194"


def test_prima_la_massima_piu_pertinente(corpus):
    righe = corpus.cerca_sentenze(q="ergastolo ostativo permesso premio", limit=5)
    sentenza = next(riga for riga in righe if riga["numero_sentenza"] == "253")
    assert sentenza["massima_ufficiale"].startswith("E' costituzionalmente illegittima la presunzione assoluta")
    assert "Sono inammissibili gli interventi" in sentenza["massima_ufficiale"]


@pytest.mark.parametrize("separator", [" ", "\t", "\n", "\t" * 20000])
def test_estremi_spazi_ripetuti_non_espandono_la_regex(separator):
    result = estremi_dalla_domanda("sentenza" + separator + "n." + separator + "253" + separator + "del" + separator + "2019")
    assert result["coppie"] == [("253", 2019)]
    assert estremi_dalla_domanda("n." + separator + "253" + separator + "/" + separator + "2019")["coppie"] == [("253", 2019)]
