"""Rami di Lex «calcoli certi» non toccati dai casi d'uso principali (copertura critica integrale)."""

from __future__ import annotations

import pytest

import lex.calcoli_certi as calcoli
from lex.calcoli_certi import presentazione, risposta_calcolatore
from lex.calcoli_certi.estrazione import estrai
from lex.calcoli_certi.riconoscimento import scegli_strumento
from pct.strumenti_legali import GestioneStrumentiLegali


class _GestoreRotto(GestioneStrumentiLegali):
    def __init__(self, esito):
        super().__init__()
        self._esito = esito

    def calcola_interessi(self, payload):
        if isinstance(self._esito, Exception):
            raise self._esito
        return self._esito


def test_collaudo_non_eseguibile_vale_nessuno_strumento(monkeypatch):
    class _Gestore:
        pass

    monkeypatch.setattr(calcoli, "_COLLAUDATI", {})
    monkeypatch.setattr("pct.calcolatori.collaudo.strumenti_collaudati", lambda g: (_ for _ in ()).throw(RuntimeError("x")))
    assert calcoli._collaudati(_Gestore()) == frozenset()


def test_scelte_da_sorgente_e_sorgenti_non_disponibili(monkeypatch):
    campi = calcoli._campi("contributo_unificato", {"cu_categorie": [{"value": "civile", "label": ""}]})
    assert campi and all("options_from" not in c for c in campi)
    monkeypatch.setattr("pct.calcolatori.metodi.sorgenti_opzioni", lambda g: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(calcoli, "_collaudati", lambda g: frozenset({"interessi"}))
    esito = risposta_calcolatore("calcola gli interessi legali su 1.000 euro dal 01/01/2025 al 31/12/2025", GestioneStrumentiLegali)
    assert esito is not None and esito.tipo == "calcolatore:interessi"


@pytest.mark.parametrize("esito", [RuntimeError("guasto"), ["non", "un", "dizionario"]])
def test_errore_tecnico_o_risultato_anomalo_lascia_il_percorso_ordinario(monkeypatch, esito):
    monkeypatch.setattr(calcoli, "_collaudati", lambda g: frozenset({"interessi"}))
    domanda = "calcola gli interessi legali su 1.000 euro dal 01/01/2025 al 31/12/2025"
    assert risposta_calcolatore(domanda, lambda: _GestoreRotto(esito)) is None


def test_domanda_senza_strumento_riconosciuto():
    assert risposta_calcolatore("calcola qualcosa di indefinito", GestioneStrumentiLegali) is None


def test_riconoscimento_senza_corrispondenze_o_ambiguo():
    assert scegli_strumento("calcola il nulla", {"a": "Alfa", "b": "Beta"}) == ""
    assert scegli_strumento("calcola alfa e beta", {"a": "Alfa", "b": "Beta"}) == ""


def test_presentazione_valori_tabelle_testi_e_fonti():
    assert presentazione.valore_leggibile("presente", True) == "sì"
    assert presentazione.valore_leggibile("presente", False) == "no"
    risultato = {
        "prima": [{"a": i} for i in range(8)],
        "sezione": {"seconda": [{"b": 1}], "testo": "x"},
        "terza": [{"c": 1}],
    }
    righe = presentazione.tabella_dettaglio(risultato, massimo=6, tabelle=2)
    assert any("altre 2 righe" in r for r in righe)
    assert "" in righe and not any(r.startswith("Terza") for r in righe)
    assert presentazione.testi({"notes": "non elenco"}, "notes") == []
    assert presentazione.fonti({"sources": "nessuna"}) == []


def test_estrazione_visibilita_percentuali_e_giorni():
    campi = [
        {"name": "tipo", "type": "select", "options": [{"value": "a", "label": "Alfa"}, {"value": "b", "label": "Beta"}]},
        {"name": "solo_b", "type": "select", "options": [{"value": "x", "label": "Ics"}, {"value": "y", "label": "Ipsilon"}],
         "quando": {"campo": "tipo", "valori": ["b"]}},
        {"name": "aliquota", "label": "Aliquota", "type": "number"},
        {"name": "giorni_unici", "label": "Durata in giorni", "type": "number"},
    ]
    dati = estrai("con aliquota 12% per 30 giorni", campi)
    assert dati.valori["aliquota"] == "12" and dati.valori["giorni_unici"] == "30"
    assert "solo_b" not in dati.valori
    dati_b = estrai("percorso beta", campi)
    assert dati_b.valori["solo_b"] == "x"
    # Visibilità che dipende da un campo non ancora valorizzato: vale la prima opzione.
    senza_controllo = [{"name": "dipende", "type": "number", "label": "Giorni",
                        "quando": {"campo": "manca", "valori": [""]}}]
    assert estrai("per 5 giorni", senza_controllo).valori["dipende"] == "5"
    # Più campi a giorni, uno senza qualifica leggibile: si salta.
    a_giorni = [{"name": "g1", "type": "number", "label": "Giorni"},
                {"name": "g2", "type": "number", "label": "Giorni di sospensione"}]
    assert estrai("10 giorni di sospensione", a_giorni).valori == {"g2": "10"}


def test_stima_motivata_presentata_come_tale_con_le_voci_da_completare(monkeypatch):
    monkeypatch.setattr(calcoli, "_collaudati", lambda g: frozenset({"lite_temeraria"}))
    esito = risposta_calcolatore("calcola la lite temeraria con compenso liquidato di 4.000 euro", GestioneStrumentiLegali)
    assert esito is not None and esito.tipo == "calcolatore:lite_temeraria"
    assert "stima motivata del software" in esito.testo
    assert "Da completare prima di una proposta:" in esito.testo
