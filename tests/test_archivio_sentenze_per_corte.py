"""Archivio sentenze per corte: estremi della Cassazione, intestazione leggibile, conteggi fuori richiesta, Consulta."""
import gzip
import hashlib
import json
import sqlite3
import threading
import time

import pytest

from pct.giurisprudenza_corpus import GestioneCorpusGiurisprudenza
from web.services import conteggi_archivio_cache as cache
from web.services.sentenzeweb_estremi import estremi_cassazione, intestazione, materia_leggibile, sezione_leggibile
from web.services.sentenzeweb_runtime import search


@pytest.fixture(autouse=True)
def _cache_pulita():
    cache.svuota()
    yield
    cache.svuota()


def _cassazione(tmp_path, righe):
    path = tmp_path / "giurisprudenza_corpus.db"
    corpus = GestioneCorpusGiurisprudenza(str(path))
    for numero, anno, sezione, ramo, tipo, oggetto in righe:
        corpus.salva_sentenza({
            "uuid_interno": f"sentenzeweb:sn{ramo[:3]}{anno}{sezione}{numero}",
            "fonte_codice": "cassazione_sentenzeweb", "fonte_nome": "Corte di Cassazione — SentenzeWeb",
            "tipo_fonte": "ufficiale", "organo_giudicante": f"Corte di Cassazione — {ramo}",
            "numero_sentenza": numero, "anno_sentenza": anno, "sezione": sezione, "tipo_provvedimento": tipo,
            "data_deposito": f"{anno}-02-26", "titolo": f"Cassazione sn{ramo[:3]} {numero}/{anno}",
            "oggetto": oggetto, "testo_integrale": "Testo della pronuncia. " * 40,
        })
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sentenzeweb_progress(seen INTEGER,expected INTEGER,status TEXT,id INTEGER)")
        connection.execute("INSERT INTO sentenzeweb_progress VALUES(3,3,'complete',1)")
    return {"IUSENTRA_SENTENZEWEB_DIRECTORY": str(tmp_path)}


def test_estremi_scritti_come_li_scrive_l_avvocato():
    assert estremi_cassazione("5425 2021 sezioni unite") == {"numero": "5425", "anno": 2021, "sezione": "U", "ramo": ""}
    assert estremi_cassazione("Cass. civ., sez. II, n. 26870/2026")["sezione"] == "2"
    assert estremi_cassazione("Cass. sez. lav. 1234 del 2019") == {"numero": "1234", "anno": 2019, "sezione": "L", "ramo": ""}
    assert estremi_cassazione("cass pen sez. VII 40733/2026")["ramo"] == "penale"
    assert estremi_cassazione("", "05425", "2021")["numero"] == "5425"
    assert estremi_cassazione("responsabilità medica onere della prova") is None


def test_intestazione_senza_sigle_interne_della_fonte():
    row = {"organo_giudicante": "Corte di Cassazione — civile", "sezione": "U", "tipo_provvedimento": "sentenza",
           "numero_sentenza": "05425", "anno_sentenza": 2021}
    assert intestazione(row) == "Cass. civ., Sez. Un., sentenza n. 5425/2021"
    assert "snciv" not in intestazione(row)
    assert sezione_leggibile("U", "Corte di Cassazione — penale") == "Sezioni Unite penali"
    assert sezione_leggibile("2", "Corte di Cassazione — civile") == "Sezione II civile"
    assert sezione_leggibile("L", "Corte di Cassazione — civile") == "Sezione lavoro"
    assert materia_leggibile("RESPONSABILITA' CIVILE CUSTODIA") == "Responsabilità civile custodia"


def test_ricerca_per_numero_e_anno_dall_indice_con_sezione_e_oggetto(tmp_path, monkeypatch):
    config = _cassazione(tmp_path, [
        ("05425", 2021, "U", "civile", "sentenza", "PROCEDIMENTO CIVILE"),
        ("05425", 2021, "3", "penale", "sentenza", ""),
        ("09006", 2021, "U", "civile", "sentenza", ""),
    ])

    def nessuna_ricerca_nei_testi(*args, **kwargs):
        raise AssertionError("Gli estremi si cercano sull'indice (anno, numero), non con la ricerca nei testi")

    monkeypatch.setattr(GestioneCorpusGiurisprudenza, "cerca_sentenze", nessuna_ricerca_nei_testi)
    risultato = search(config, "5425 2021 sezioni unite")
    assert risultato["searchedBy"] == "estremi"
    assert [r["title"] for r in risultato["records"]] == ["Cass. civ., Sez. Un., sentenza n. 5425/2021"]
    scheda = risultato["records"][0]
    assert scheda["sectionLabel"] == "Sezioni Unite civili" and scheda["number"] == "5425" and scheda["year"] == 2021
    assert scheda["date"] == "2021-02-26" and scheda["subject"] == "Procedimento civile"
    assert len(search(config, "", "5425", "2021")["records"]) == 2
    assert len(search(config, "", "5425", "2021", ramo="penale")["records"]) == 1
    vuota = search(config, "", "5425", "2020")
    assert vuota["records"] == [] and "5425/2020" in vuota["message"]
    assert "anno" in search(config, "", "5425", "")["message"]


def test_conteggio_lento_non_blocca_la_pagina_e_poi_arriva(tmp_path):
    rilascio = threading.Event()

    def lento():
        rilascio.wait(5)
        return {"conteggio": 426399}

    inizio = time.monotonic()
    assert cache.conteggio_memorizzato("prova", tmp_path / "x.db", lento, attesa=0.2) is None
    assert time.monotonic() - inizio < 1
    rilascio.set()
    time.sleep(0.2)
    assert cache.conteggio_memorizzato("prova", tmp_path / "x.db", lento, attesa=0.2) == {"conteggio": 426399}


def test_conteggio_ricalcolato_quando_l_archivio_cambia_ed_errore_non_nascosto(tmp_path):
    file = tmp_path / "a.db"
    file.write_text("1")
    valori = iter([1, 2])
    assert cache.conteggio_memorizzato("c", file, lambda: next(valori)) == 1
    assert cache.conteggio_memorizzato("c", file, lambda: next(valori)) == 1
    file.write_text("22")
    assert cache.conteggio_memorizzato("c", file, lambda: next(valori)) == 2

    def rotto():
        raise sqlite3.DatabaseError("file is not a database")

    with pytest.raises(sqlite3.DatabaseError):
        cache.conteggio_memorizzato("rotto", file, rotto)


def test_inventario_cassazione_in_aggiornamento_non_e_zero(tmp_path, monkeypatch):
    from web.services import sentenzeweb_runtime

    config = _cassazione(tmp_path, [("00001", 2020, "1", "civile", "sentenza", "")])
    monkeypatch.setattr(sentenzeweb_runtime, "_inventory_counts", lambda corpus: time.sleep(3) or {})
    monkeypatch.setattr(cache, "ATTESA_SECONDI", 0.1)
    stato = sentenzeweb_runtime.inventory(config)
    assert stato["available"] and stato["caseCount"] is None and stato["status"] == "counting"


def test_materie_dalle_pagine_originali_conservate(tmp_path):
    from tools.sentenzeweb_materie import completa

    config = _cassazione(tmp_path, [("02557", 2025, "3", "civile", "decreto", "")])
    pagina = json.dumps({"response": {"docs": [{"id": "snciv2025302557D", "materia": ["RESPONSABILITA' CIVILE CUSTODIA"]}]}}).encode()
    digest = hashlib.sha256(pagina).hexdigest()
    (tmp_path / "originali").mkdir()
    (tmp_path / "originali" / f"{digest}.json.gz").write_bytes(gzip.compress(pagina))
    db = tmp_path / "giurisprudenza_corpus.db"
    with sqlite3.connect(db) as connection:
        connection.executescript(
            "CREATE TABLE sentenzeweb_pages(sha256 TEXT PRIMARY KEY,path TEXT NOT NULL,records INTEGER NOT NULL,acquired_at TEXT NOT NULL);"
            "CREATE TABLE sentenzeweb_aliases(source_id TEXT PRIMARY KEY,native_uuid TEXT NOT NULL,proof_text_sha256 TEXT NOT NULL,acquired_at TEXT NOT NULL);")
        connection.execute("INSERT INTO sentenzeweb_pages VALUES(?,?,1,'2026-11-21')", (digest, str(tmp_path / "originali" / f"{digest}.json.gz")))
        uuid = connection.execute("SELECT uuid_interno FROM sentenze").fetchone()[0]
        connection.execute("INSERT INTO sentenzeweb_aliases VALUES('snciv2025302557D',?,'x','2026-11-21')", (uuid,))
    prima = db.read_bytes()
    assert completa(tmp_path, prova=True)["da_scrivere"] == 1
    assert db.read_bytes() == prima
    assert completa(tmp_path)["scritti"] == 1
    scheda = search(config, "2557/2025")["records"][0]
    assert scheda["subject"] == "Responsabilità civile custodia"
    assert completa(tmp_path)["scritti"] == 0


def test_consulta_estremi_senza_barra_cercati_come_numero_e_anno(tmp_path):
    from web.services.giurisprudenza_native_runtime import search as cerca_corpus

    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "corpus.db"))
    corpus.salva_sentenza({"uuid_interno": "cost-194-2018", "fonte_codice": "corte_costituzionale",
                           "fonte_nome": "Corte costituzionale", "tipo_fonte": "ufficiale",
                           "organo_giudicante": "Corte costituzionale", "numero_sentenza": "194", "anno_sentenza": 2018,
                           "tipo_provvedimento": "sentenza", "data_deposito": "2018-11-08",
                           "titolo": "Sentenza 194/2018", "oggetto": "Giudizio di legittimità costituzionale in via incidentale",
                           "abstract": "Lavoro - Licenziamento illegittimo - Indennità predeterminata - Illegittimità costituzionale.",
                           "principio_sintetico": "dichiara l'illegittimità costituzionale dell'art. 3, comma 1, del d.lgs. 4 marzo 2015, n. 23",
                           "testo_integrale": "Testo della sentenza. " * 30})
    risultato = cerca_corpus(corpus, source="corte_costituzionale", query="194 2018")
    scheda = risultato["records"][0]
    assert (scheda["number"], scheda["year"], scheda["kind"]) == ("194", 2018, "sentenza")
    assert scheda["subject"].startswith("Lavoro - Licenziamento illegittimo")
    assert scheda["judgment"] == "Giudizio di legittimità costituzionale in via incidentale"
    assert scheda["ruling"].startswith("dichiara l'illegittimità costituzionale dell'art. 3")


def test_consulta_elenco_iniziale_per_data_di_deposito_senza_ordinare_tutto_il_corpus(tmp_path, monkeypatch):
    from web.services.giurisprudenza_native_runtime import search as cerca_corpus

    corpus = GestioneCorpusGiurisprudenza(str(tmp_path / "corpus.db"))
    for numero, data in (("10", "2025-03-01"), ("206", "2026-11-13"), ("1", "2024-01-10")):
        corpus.salva_sentenza({"uuid_interno": f"cost-{numero}", "fonte_codice": "corte_costituzionale",
                               "fonte_nome": "Corte costituzionale", "tipo_fonte": "ufficiale",
                               "organo_giudicante": "Corte costituzionale", "numero_sentenza": numero,
                               "anno_sentenza": int(data[:4]), "tipo_provvedimento": "sentenza", "data_deposito": data,
                               "titolo": f"Sentenza {numero}", "testo_integrale": "Testo. " * 30})

    def vietata(*args, **kwargs):
        raise AssertionError("L'elenco iniziale non ordina l'intero corpus")

    monkeypatch.setattr(GestioneCorpusGiurisprudenza, "cerca_sentenze", vietata)
    risultato = cerca_corpus(corpus, source="corte_costituzionale", query="")
    assert [r["number"] for r in risultato["records"]] == ["206", "10", "1"]
