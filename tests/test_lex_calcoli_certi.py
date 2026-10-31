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


def test_date_eta_punti_e_giorni_nominati_vanno_al_campo_giusto():
    campi = schema_calcolatore("danno_biologico")["campi"]
    dati = estrai(
        "calcola il danno biologico: 10 punti, eta 30 anni, liquidazione 31/10/2026, sinistro del 05/03/2025, "
        "20 giorni di inabilita totale e 40 giorni di inabilita parziale",
        campi,
    )
    assert dati.valori["db_data_sinistro"] == "2025-03-05" and dati.valori["db_data_liquidazione"] == "2026-10-31"
    assert dati.valori["db_eta"] == "30" and dati.valori["db_perc_ip"] == "10"
    assert dati.valori["db_giorni_itt"] == "20" and dati.valori["db_giorni_itp"] == "40"


def test_numero_ambiguo_resta_al_calcolatore():
    campi = schema_calcolatore("danno_biologico")["campi"]
    dati = estrai("calcola il danno biologico, eta 30 o eta 40, 10 punti, 15 giorni", campi)
    assert "db_eta" not in dati.valori
    assert "db_giorni_itt" not in dati.valori and "db_giorni_itp" not in dati.valori


def test_lex_calcola_il_danno_biologico_con_la_tavola_vigente():
    esito = risposta_calcolatore(
        "calcola il danno biologico: persona di 7 anni di eta, 10 punti, sinistro 01/06/2026, liquidazione al 31/10/2026",
        GestioneStrumentiLegali,
    )
    assert esito is not None and esito.tipo == "calcolatore:danno_biologico"
    # cella dell'allegato II del D.M. 28/09/2026 (10 punti, 7 anni) e tabella 2.A
    assert "€ 26.468,00" in esito.testo and "Totale: **€ 32.026,00**" in esito.testo
    assert esito.testo.index("Totale") < esito.testo.index("Età")


def test_mesi_iniziale_e_finale_dalla_domanda():
    campi = schema_calcolatore("rivalutazione_istat")["campi"]
    dati = estrai("rivaluta 1.000 euro da gennaio 2020 a 01/2025", campi)
    assert (dati.valori["riv_anno_base"], dati.valori["riv_mese_base"]) == ("2020", "1")
    assert (dati.valori["riv_anno_fine"], dati.valori["riv_mese_fine"]) == ("2025", "1")
    assert "riv_mese_base" not in estrai("rivaluta 1.000 euro da gennaio 2020", campi).valori


def test_lex_calcola_il_credito_di_valore_con_gli_interessi_compensativi():
    esito = risposta_calcolatore(
        "calcola rivalutazione e interessi compensativi sul credito di valore di 10.000 euro "
        "da gennaio 2024 a gennaio 2025",
        GestioneStrumentiLegali,
    )
    assert esito is not None and esito.tipo == "calcolatore:maggior_danno"
    assert "€ 10.130,00" in esito.testo and "1224" in esito.testo
