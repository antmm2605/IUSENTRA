"""Routing di Lex: domande giuridiche -> ricerca giuridica, dati dello studio -> livello operativo."""

from __future__ import annotations

import json
from pathlib import Path

from lex.ricerca_giuridica.classificatore import classifica_domanda

_DATI = json.loads((Path(__file__).with_name("domande.json")).read_text(encoding="utf-8"))
_SOGLIA = 0.95


def _esiti():
    return [
        (r["d"], r["e"], classifica_domanda(r["d"], _DATI["nomi_anagrafica"]).tipo)
        for r in _DATI["domande"]
    ]


def test_set_etichettato_ha_20_giuridiche_e_20_studio():
    etichette = [r["e"] for r in _DATI["domande"]]
    assert etichette.count("giuridica") >= 20 and etichette.count("studio") >= 20


def test_accuratezza_routing_almeno_95_per_cento():
    esiti = _esiti()
    errori = [(d, atteso, dato) for d, atteso, dato in esiti if atteso != dato]
    accuratezza = 1 - len(errori) / len(esiti)
    assert accuratezza >= _SOGLIA, f"accuratezza {accuratezza:.2%}; errori: {errori}"


def test_nessuna_domanda_giuridica_va_al_livello_studio():
    errori = [(d, dato) for d, atteso, dato in _esiti() if atteso == "giuridica" and dato == "studio"]
    assert not errori, errori


def test_caso_reale_responsabilita_extracontrattuale():
    c = classifica_domanda("Quali sono i presupposti della responsabilita' extracontrattuale?")
    assert c.giuridica and c.tipo_ricerca == "normativa"
    assert classifica_domanda("Cosa dice la giurisprudenza sul danno non patrimoniale?").tipo_ricerca == "giurisprudenza"
