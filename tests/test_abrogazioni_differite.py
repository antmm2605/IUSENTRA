"""Articoli vigenti oggi e abrogati dal 01/01/2027 dai testi unici tributari (verifica su Normattiva del 21/11/2026)."""
import importlib.util
import sys
from datetime import date
from pathlib import Path

from lex.normativa.abrogazioni_differite import nota, nota_articolo

OGGI = date(2026, 11, 21)


def test_processo_tributario_vigente_fino_al_31_12_2026_con_la_disposizione_corrispondente():
    voce = nota("1992-12-31", "546", "2", oggi=OGGI)
    assert voce["stato"] == "vigente_fino_al" and voce["fino_al"] == "2026-12-31" and voce["dal"] == "2027-01-01"
    assert voce["testo"] == ("Vigente fino al 31/12/2026; dal 01/01/2027 abrogato dall'art. 130 del d.lgs. 14 novembre 2024, "
                             "n. 175 (Testo unico della giustizia tributaria) e sostituito dall'art. 46 dello stesso testo unico.")
    # La data viene dal rinvio del d.l. 200/2025, convertito dalla l. 26/2026: la fonte lo dice.
    assert "art. 4, comma 3, del d.l. 31 dicembre 2025, n. 200" in voce["decorrenza"]
    assert "l. 27 febbraio 2026, n. 26" in voce["decorrenza"]


def test_riscossione_iva_registro():
    assert "sostituito dall'art. 16" in nota("1973-09-29", "602", "28-quinquies", oggi=OGGI)["testo"]
    assert "d.lgs. 19 gennaio 2026, n. 10" in nota("1972-10-26", "633", "7-quinquies", oggi=OGGI)["testo"]
    assert "sostituito dall'art. 178" in nota("1978-07-27", "392", "57", oggi=OGGI)["testo"]
    # Abrogazione parziale: solo i commi indicati dal testo unico.
    parziale = nota("1972-10-26", "633", "59", oggi=OGGI)
    assert parziale["parziale"] == "commi 1, 2" and "abrogato (commi 1, 2)" in parziale["testo"]
    assert nota("1978-07-27", "392", "1", oggi=OGGI) is None
    assert nota("1942-03-16", "262", "2043", oggi=OGGI) is None


def test_dopo_la_data_l_articolo_risulta_abrogato():
    voce = nota("1992-12-31", "546", "2", oggi=date(2027, 1, 1))
    assert voce["stato"] == "abrogato" and voce["testo"].startswith("Abrogato dal 01/01/2027")


def test_scheda_e_lettore_dell_articolo():
    from lex.normativa.presentazione_articolo import arricchisci

    item = arricchisci({"number": "Art. 2.", "text": "Art. 2. Oggetto della giurisdizione tributaria 1. Appartengono...",
                        "urn": "urn:nir:stato:decreto.legislativo:1992-12-31;546"})
    assert item["vigenza_nel_tempo"]["testo"].startswith("Vigente fino al 31/12/2026") or \
        item["vigenza_nel_tempo"]["testo"].startswith("Abrogato dal 01/01/2027")
    assert nota_articolo({"urn": "urn:nir:stato:legge:1978-07-27;392", "number": "57"}, oggi=OGGI)["corrispondenti"] == ["art. 178"]
    sorgente = Path("web/services/normative_article_reader.py").read_text(encoding="utf-8")
    assert "nota_articolo(item)" in sorgente and "+vigenza+" in sorgente
    pagina = Path("frontend/src/components/CodiciLeggiPage.tsx").read_text(encoding="utf-8")
    assert "selected.vigenza_nel_tempo" in pagina


def test_lettura_delle_lettere_di_abrogazione():
    spec = importlib.util.spec_from_file_location("generatore", "scripts/abrogazioni_differite_da_akn.py")
    generatore = importlib.util.module_from_spec(spec)
    sys.modules["generatore"] = generatore
    spec.loader.exec_module(generatore)
    ordine = ["1", "2", "3", "7", "7-bis", "7-ter", "8"]
    assert generatore.leggi_specifica("articoli da 2 a 7-bis , 8", ordine) == [("2", ""), ("3", ""), ("7", ""), ("7-bis", ""), ("8", "")]
    assert generatore.leggi_specifica("l' articolo 59, commi 1 e 2,", ordine) == [("59", "commi 1, 2")]
    assert generatore.leggi_specifica("articolo 9, commi quarto e quinto,", ordine) == [("9", "commi quarto, quinto")]
    assert generatore.leggi_specifica("articoli da 1 a 99", ordine) is None  # estremo non riscontrato: nessuna voce
