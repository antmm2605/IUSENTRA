"""Competenze che il valore non decide (valutazione del 25/11/2026).

Testo vigente (biblioteca del software): art. 413 c.p.c. («tribunale in funzione di giudice del lavoro»); art. 645,
primo comma, c.p.c. dopo il d.lgs. 164/2024 («davanti all'ufficio giudiziario al quale appartiene il giudice che ha
emesso il decreto»); art. 18, commi 2-3, d.lgs. 150/2011 (espulsione: giudice di pace, venti giorni).
"""
from __future__ import annotations

import pytest

from lex.strumenti import scelta_calcoli
from pct.calcolatori import competenza_valore, termini_scadenza


def _lex(domanda: str) -> tuple[str, dict]:
    ident = scelta_calcoli.calcolatore(domanda)
    return ident, scelta_calcoli.campi(ident, domanda) if ident else {}


@pytest.mark.parametrize("valore", ["500", "5000", "60000"])
def test_lavoro_e_tfr_sempre_al_giudice_del_lavoro(valore):
    esito = competenza_valore.calcola({"comp_materia": "lavoro_previdenza", "comp_valore": valore})
    assert esito["giudice_competente"] == "Tribunale in funzione di giudice del lavoro"


def test_opposizione_decreto_ingiuntivo_ufficio_che_lo_ha_emesso():
    esito = competenza_valore.calcola({"comp_materia": "opposizione_decreto_ingiuntivo", "comp_valore": "6000"})
    assert esito["giudice_competente"] == "Ufficio giudiziario del giudice che ha emesso il decreto"
    assert "645" in esito["riferimento"]


def test_beni_mobili_resta_per_valore():
    esito = competenza_valore.calcola({"comp_materia": "beni_mobili", "comp_valore": "6000",
                                       "comp_data_introduzione": "2026-11-25"})
    assert esito["giudice_competente"] == "Giudice di pace"


@pytest.mark.parametrize("domanda, materia", [
    ("Lavoratore con differenze retributive di 5000 euro: giudice di pace o tribunale?", "lavoro_previdenza"),
    ("Il dipendente reclama stipendi arretrati per 2.500 euro: competente il giudice di pace o il tribunale?",
     "lavoro_previdenza"),
    ("Opposizione tardiva ex art. 650 c.p.c. a un decreto di 6.000 euro: va dal giudice di pace o in tribunale?",
     "opposizione_decreto_ingiuntivo"),
])
def test_lex_non_manda_lavoro_e_opposizione_al_giudice_di_pace(domanda, materia):
    ident, campi = _lex(domanda)
    if ident == "competenza_valore":
        assert campi.get("comp_materia") == materia
        assert competenza_valore.calcola(campi)["giudice_competente"] != "Giudice di pace"


@pytest.mark.parametrize("domanda, modello, scadenza", [
    ("Decreto ingiuntivo per TFR notificato il 20/07/2026 al datore di lavoro: entro quando l'opposizione?",
     "LAV_OPPOSIZIONE_DI", "31/08/2026"),
    ("Decreto ingiuntivo notificato il 20/07/2026: entro quando l'opposizione?", "CIV_OPPOSIZIONE_DI", "29/09/2026"),
    ("Reclamo cautelare contro l'ordinanza comunicata il 20/07/2026: entro quando?",
     "CIV_RECLAMO_CAUTELARE_669_TERDECIES", "04/08/2026"),
    ("Ricorso contro il decreto di espulsione del prefetto notificato il 20/07/2026: entro quando?",
     "IMM_RICORSO_ESPULSIONE_18", "10/08/2026"),
])
def test_lex_sceglie_il_modello_di_termine_giusto(domanda, modello, scadenza):
    ident, campi = _lex(domanda)
    assert ident == "termini_processuali"
    assert campi["term_modello"] == modello
    assert termini_scadenza.calcola(campi)["scadenza"] == scadenza


def test_espulsione_venti_giorni_con_dubbio_feriale_dichiarato():
    esito = termini_scadenza.calcola({"term_modello": "IMM_RICORSO_ESPULSIONE_18", "term_data_evento": "2026-07-25"})
    assert esito["scadenza"] == "14/08/2026"
    assert esito["richiede_verifica"] is True


def test_ricorso_decreto_ingiuntivo_per_credito_di_lavoro():
    from lex.harness.fattispecie.monitorio import _CREDITO_DI_LAVORO
    import re

    assert re.search(_CREDITO_DI_LAVORO, "recupero del tfr non pagato dal datore di lavoro")
    assert not re.search(_CREDITO_DI_LAVORO, "fattura per fornitura di merce non pagata")
