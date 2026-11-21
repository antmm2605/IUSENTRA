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


def test_sentenze_dell_articolo_dall_indice_o_dagli_archivi(monkeypatch):
    import lex.harness.giurisprudenza as giur
    from web.services import normativa_sentenze

    chiamate = []
    monkeypatch.setattr(giur, "per_norme", lambda chiavi: chiamate.append(chiavi) or None)
    monkeypatch.setattr(giur, "cerca", lambda domanda, **kw: chiamate.append(kw.get("utente")) or EsitoGiurisprudenza(
        "consultata", [Pronuncia("Cassazione (SentenzeWeb)", "Cassazione civile", "3", "12714", "2024")], ["Cassazione"]))
    esito = normativa_sentenze.sentenze_per_articolo({"number": "2043", "urn": "urn:nir:stato:regio.decreto:1942-03-16;262"}, utente="studio:7")
    assert chiamate == [["cc:2043"], "studio:7"]
    assert esito["citazione"] == "art. 2043 c.c." and esito["fonte"] == "ricerca negli archivi"
    assert esito["pronunce"][0]["estremi"].startswith("Cassazione civile, sez. 3, n. 12714/2024")
