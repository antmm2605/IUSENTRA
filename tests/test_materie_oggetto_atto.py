"""Materie del catalogo dall'oggetto dell'atto (revisione 21/11/2026: «Altre norme» dal 59,4% al 21,9%)."""
import pytest

from lex.normativa import materie as M


@pytest.mark.parametrize("titolo, attesa", [
    ("Decreto legislativo 222/2016 — Adozione di disposizioni integrative in materia di rifiuti", M.AMBIENTE),
    ("Legge 184/1983 — Diritto del minore ad una famiglia", M.FAMIGLIA),
    ("Regio decreto 697/1892 — Che costituisce in ente morale l'asilo infantile di Zelo Surrigone", M.AMMINISTRATIVO),
    ("Decreto legge 37/2025 — Disposizioni urgenti per il contrasto dell'immigrazione irregolare", M.IMMIGRAZIONE),
    ("Legge 87/2001 — Provvedimenti straordinari per la ricostruzione", M.ALTRO),
    ("Legge 3/2022 — Conversione in legge, con modificazioni, del decreto-legge 26 novembre 2021, n. 172, "
     "recante misure urgenti per il contenimento dell'epidemia da COVID-19", M.AMMINISTRATIVO),
    ("Legge 309/1997 — Ratifica ed esecuzione della convenzione per evitare le doppie imposizioni", M.TRIBUTARIO),
    ("Decreto legislativo 11/2010 — Attuazione della direttiva 2007/64/CE, relativa ai servizi di pagamento", M.BANCA),
    ("Decreto legislativo 135/2016 — Attuazione della direttiva 2014/56/UE", M.UE),
    ("Legge 168/2008 — Rendiconto generale dell'Amministrazione dello Stato per l'esercizio finanziario 2007", M.TRIBUTARIO),
    ("Decreto legge 21/1979 — Dilazione dell'esecuzione dei provvedimenti di rilascio degli immobili adibiti ad uso di abitazione", M.CIVILE),
    ("Decreto legislativo 112/2015 — Attuazione della direttiva 2012/34/UE del Parlamento europeo e del Consiglio", M.UE),
])
def test_materia_dall_oggetto(titolo, attesa):
    assert M.materia("cerdef_1", "urn:nir:stato:legge:2000-01-01;1", titolo) == attesa


def test_costituzione_con_urn_datato_e_leggi_costituzionali():
    assert M.materia("cerdef_9", "urn:nir:stato:costituzione:1947-12-27", "Costituzione 1947-12-27 — COSTITUZIONE") == M.COSTITUZIONE
    assert M.materia("cerdef_8", "urn:nir:stato:legge.costituzionale:2022-11-07;2", "Legge costituzionale 2/2022 — Modifica") == M.COSTITUZIONE


def test_adozione_di_disposizioni_non_e_famiglia():
    assert M.materia("x", "", "Decreto 1/2020 — Adozione di disposizioni per i minori oneri amministrativi") != M.FAMIGLIA
