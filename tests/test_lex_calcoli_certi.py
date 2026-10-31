"""Lex usa i calcolatori di Strumenti legali collaudati sulla norma (V37)."""

from __future__ import annotations

import pytest

from lex.calcoli_certi import risposta_calcolatore
from lex.calcoli_certi.estrazione import estrai
from lex.calcoli_certi.presentazione import valore_leggibile
from lex.calcoli_certi.riconoscimento import SINONIMI, scegli_strumento
from lex.risposte_certe import risposta_certa
from pct.calcolatori.collaudo import CASI, collauda
from pct.calcolatori.metodi import TOOL_METHODS
from pct.calcolatori.schema import schema_calcolatore
from pct.strumenti_legali import GestioneStrumentiLegali


def test_ogni_caso_di_collaudo_coincide_con_la_norma():
    falliti = {tool: motivi for tool, motivi in collauda(GestioneStrumentiLegali()).items() if motivi}
    assert falliti == {}


def test_i_casi_e_i_sinonimi_riguardano_strumenti_esistenti():
    assert set(CASI) <= set(TOOL_METHODS)
    assert set(SINONIMI) <= set(TOOL_METHODS)
    for tool, casi in CASI.items():
        assert schema_calcolatore(tool), tool
        for caso in casi:
            assert caso.norma and caso.verificato_il and caso.attesi, (tool, caso.descrizione)


def test_interessi_legali_dalla_domanda_con_dettaglio_e_fonti():
    esito = risposta_certa("Calcola gli interessi legali su 10.000 euro dal 01/01/2024 al 31/12/2025")
    assert esito is not None and esito.tipo == "calcolatore:interessi"
    assert "€ 450,00" in esito.testo and "2,5%" in esito.testo and "€ 250,00" in esito.testo
    assert "Regime: **legali**" not in esito.testo
    assert esito.fonti


def test_dato_mancante_si_chiede_invece_di_supporlo():
    esito = risposta_certa("quanto sono gli interessi legali su un capitale di 5.000 euro?")
    assert esito is not None and esito.tipo == "calcolatore_dati_mancanti:interessi"
    assert "€" not in esito.testo.split("mi manca")[0]


def test_strumento_non_collaudato_non_da_numeri(monkeypatch):
    import lex.calcoli_certi as calcoli

    monkeypatch.setattr(calcoli, "_collaudati", lambda gestore: frozenset())
    esito = risposta_calcolatore("calcola gli interessi legali su 10.000 euro dal 01/01/2024 al 31/12/2024", GestioneStrumentiLegali)
    assert esito is not None and esito.tipo == "calcolatore_non_collaudato:interessi"
    assert "250" not in esito.testo and "/strumenti-legali/?tool=interessi" in esito.testo


@pytest.mark.parametrize("domanda", ["cosa prevede l'art. 1284 c.c.?", "spiegami gli interessi legali", "buongiorno"])
def test_senza_richiesta_di_calcolo_non_si_sceglie_un_calcolatore(domanda):
    titoli = {voce["id"]: voce["title"] for voce in GestioneStrumentiLegali.catalogo_moduli()}
    assert scegli_strumento(domanda, titoli) == ""


def test_scelte_non_indicate_sono_dichiarate_come_ipotesi():
    campi = schema_calcolatore("interessi")["campi"]
    dati = estrai("calcola gli interessi su 1.000 euro dal 01/01/2025 al 31/12/2025", campi)
    assert dati.valori["int_tipo"] == "legali" and dati.valori["int_capitale"] == "1000"
    assert dati.valori["int_data_inizio"] == "2025-01-01" and dati.valori["int_data_fine"] == "2025-12-31"
    assert dati.ipotesi and "Regime" in dati.ipotesi[0]
    mora = estrai("calcola gli interessi di mora commerciale su 1.000 euro dal 01/01/2025 al 31/12/2025", campi)
    assert mora.valori["int_tipo"] == "mora_commerciale" and not mora.ipotesi


def test_valori_in_formato_italiano():
    assert valore_leggibile("total_interest", 1234.5) == "€ 1.234,50"
    assert valore_leggibile("rate", 2.5) == "2,5%"
    assert valore_leggibile("start_date", "2024-01-31") == "31/01/2024"
    assert valore_leggibile("days", 366) == "366"
