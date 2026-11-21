"""Lettura dell'articolo in «Codici e leggi»: segni di Normattiva, accenti, note, saggio legale e sentenze."""
from datetime import date

from lex.harness.giurisprudenza import EsitoGiurisprudenza, Pronuncia
from lex.normativa.presentazione_articolo import arricchisci, presenta, saggio_legale_vigente

TESTO_1284 = ("Art. 1284. (Saggio degli interessi). Il saggio degli interessi legali e' determinato in misura pari al "
              "5 per cento in ragione d'anno. Il Ministro del tesoro puo' modificarne annualmente la misura. (129a) "
              "(260a)(276) ((348)) Allo stesso saggio si computano gli interessi convenzionali. ----------------- "
              "AGGIORNAMENTO (276) Il D.M. ha disposto che \"La misura del saggio e' fissata al 3,5 per cento\".")


def test_segni_grezzi_tolti_e_note_a_parte():
    lettura = presenta(TESTO_1284)
    for segno in ("(129a)", "(260a)", "(276)", "((348))", "AGGIORNAMENTO"):
        assert segno not in lettura["testo"], segno
    assert "è determinato" in lettura["testo"] and "può modificarne" in lettura["testo"]
    assert lettura["note"].startswith("AGGIORNAMENTO (276)")
    assert "e' fissata" in lettura["note"]  # le note riportano testi altrui: nessuna correzione


def test_accenti_solo_dove_certi():
    testo = presenta("Se il giorno e' festivo; altresi' perche' un po' di attivita' «e' citata» E' vero. Il (1) resta.")["testo"]
    assert testo.startswith("Se il giorno è festivo; altresì perché un po' di attività «e' citata» È vero.")
    assert "(1)" in testo  # nessuna nota (1): il numero tra parentesi resta


def test_saggio_legale_vigente_nell_art_1284():
    saggio = saggio_legale_vigente(date(2026, 11, 21))
    assert saggio["misura"] == "1,60%" and saggio["decreto"] == "D.M. MEF 10 dicembre 2025"
    item = arricchisci({"number": "1284", "urn": "urn:nir:stato:regio.decreto:1942-03-16;262", "text": TESTO_1284})
    assert item["saggio_legale_vigente"]["misura"] == "1,60%"
    assert item["text"] == TESTO_1284  # il testo della fonte resta intatto
    assert "saggio_legale_vigente" not in arricchisci({"number": "2043", "urn": "urn:nir:stato:regio.decreto:1942-03-16;262", "text": "x"})


def _corpus(tmp_path):
    import sqlite3

    db = tmp_path / "corpus.sqlite"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sentenze(id INTEGER PRIMARY KEY, organo_giudicante, sezione, numero_sentenza, anno_sentenza, "
                 "data_deposito, testo_integrale)")
    conn.execute("CREATE VIRTUAL TABLE sentenze_fts USING fts5(testo_integrale, content='', tokenize='unicode61')")
    righe = [(1, "Corte di Cassazione — civile", "3", "012714", 2024, "2024-05-08", "ai sensi dell'art. 2043 c.c. il danno"),
             (2, "Corte di Cassazione — civile", "1", "000100", 2023, "2023-01-02", "art. 2043 cod. civ. e art. 1218"),
             (3, "Corte di Cassazione — civile", "2", "000200", 2025, "2025-03-01", "art. 2044 c.c. legittima difesa")]
    for r in righe:
        conn.execute("INSERT INTO sentenze VALUES (?,?,?,?,?,?,?)", r)
        conn.execute("INSERT INTO sentenze_fts(rowid, testo_integrale) VALUES (?,?)", (r[0], r[6]))
    conn.commit()
    conn.close()

    class Corpus:
        def _connect(self):
            from pct.giurisprudenza_corpus import connessione_sola_lettura
            return connessione_sola_lettura(str(db))

    return Corpus()


def test_sentenze_dell_articolo_dall_indice_o_dalla_citazione(monkeypatch, tmp_path):
    import lex.harness.giurisprudenza as giur
    from web.services import normativa_sentenze

    chiamate = []
    monkeypatch.setattr(giur, "per_norme", lambda chiavi: chiamate.append(chiavi) or None)
    corpus = _corpus(tmp_path)
    monkeypatch.setattr(normativa_sentenze, "_archivi", lambda: [("Cassazione (SentenzeWeb)", corpus)])
    esito = normativa_sentenze.sentenze_per_articolo(
        {"number": "2043", "urn": "urn:nir:stato:regio.decreto:1942-03-16;262"}, utente="studio:7")
    assert chiamate == [["cc:2043"]]
    assert esito["citazione"] == "art. 2043 c.c." and esito["fonte"] == "ricerca della citazione negli archivi"
    assert [p["numero"] for p in esito["pronunce"]] == ["12714", "100"]  # la 2044 non cita l'art. 2043
    assert esito["pronunce"][0]["estremi"].startswith("Corte di Cassazione — civile, sez. 3, n. 12714/2024")


def test_sentenze_dall_indice_precalcolato(monkeypatch):
    import lex.harness.giurisprudenza as giur
    from web.services import normativa_sentenze

    monkeypatch.setattr(giur, "per_norme", lambda chiavi: EsitoGiurisprudenza(
        "indice precalcolato", [Pronuncia("Cassazione (SentenzeWeb)", "Cassazione civile", "3", "12714", "2024")], ["Cassazione"]))
    esito = normativa_sentenze.sentenze_per_articolo({"number": "13", "urn": "urn:nir:stato:decreto.del.presidente.della.repubblica:2002-05-30;115",
                                                      "data_atto": "2002-05-30", "numero": "115"})
    assert esito["citazione"] == "art. 13 d.P.R. 115/2002" and esito["pronunce"][0]["numero"] == "12714"
