"""Lex: competenza del lavoro nel monitorio, termini senza sospensione feriale ed espulsione (2.490.12).

Comportamenti giuridici verificati sul testo vigente (biblioteca del software, archivio Normattiva):
- art. 637 c.p.c.: è competente il giudice «che sarebbe competente per la domanda proposta in via ordinaria»; per un
  credito di lavoro o di previdenza è il tribunale in funzione di giudice del lavoro, a qualunque valore (artt. 409,
  413 e 442 c.p.c.): il giudice di pace non lo è mai;
- art. 3 l. 742/1969 e art. 92 r.d. 12/1941: niente sospensione feriale nelle controversie di lavoro e previdenza e nei
  procedimenti cautelari (reclamo ex art. 669-terdecies c.p.c., quindici giorni);
- art. 203 d.lgs. 285/1992: ricorso al Prefetto entro sessanta giorni, atto amministrativo senza sospensione feriale;
- art. 18 d.lgs. 150/2011: il decreto prefettizio di espulsione si impugna davanti al giudice di pace, non con il
  ricorso al Prefetto del codice della strada.
"""
from __future__ import annotations

import re

import pytest

from lex.harness.fattispecie.materia_civile_cautelare import RECLAMO_CAUTELARE
from lex.harness.fattispecie.materia_complementi import PREFETTO
from lex.strumenti import scelta_calcoli
from pct.calcolatori import competenza_valore, termini_scadenza
from tests.lex_materie_casi import risposta


def _calcolo(domanda: str) -> tuple[str, dict]:
    ident = scelta_calcoli.calcolatore(domanda)
    return ident, scelta_calcoli.campi(ident, domanda) if ident else {}


def _senza_rimozioni(r) -> None:
    assert not r.affermazioni_tolte, r.affermazioni_tolte
    assert not r.citazioni_non_verificate, r.citazioni_non_verificate


@pytest.mark.parametrize("domanda", [
    "Redigi un ricorso per decreto ingiuntivo per 3.000 euro di straordinari non pagati",
    "Prepara il ricorso per decreto ingiuntivo per 4.000 euro di contributi previdenziali non versati",
])
def test_ricorso_monitorio_per_credito_di_lavoro_va_al_giudice_del_lavoro(domanda):
    r = risposta(domanda)
    assert r.regola == "decreto_ingiuntivo"
    _senza_rimozioni(r)
    assert "tribunale in funzione di giudice del lavoro, a qualunque valore" in r.testo
    assert "art. 413 c.p.c." in r.testo
    # Sotto i 10.000 euro il valore porterebbe al giudice di pace (art. 7 c.p.c.): per il lavoro non vale.
    assert "Competente per valore è il giudice di pace" not in r.testo
    assert not re.search(r"decreto ingiuntivo al giudice di pace", r.testo, re.I)


def test_ricorso_monitorio_per_fattura_resta_competenza_per_valore():
    r = risposta("Redigi un ricorso per decreto ingiuntivo per una fattura di 8.000 euro")
    assert r.regola == "decreto_ingiuntivo"
    _senza_rimozioni(r)
    assert "Competente per valore è il giudice di pace" in r.testo
    assert "giudice del lavoro" not in r.testo


def test_schede_di_lex_dichiarano_l_esclusione_feriale():
    assert [s.sospensione_feriale for s in RECLAMO_CAUTELARE.scadenze] == [False]
    assert [s.sospensione_feriale for s in PREFETTO.scadenze] == [False]


def test_reclamo_cautelare_nel_periodo_feriale_scade_dopo_quindici_giorni_di_calendario():
    r = risposta("Il tribunale ha rigettato il ricorso cautelare con ordinanza comunicata il 20/07/2026: "
                 "entro quando il reclamo?")
    assert r.regola == "cau_reclamo"
    _senza_rimozioni(r)
    # 20/07 + 15 = 04/08/2026, senza il rinvio al 15/09 che la sospensione feriale darebbe.
    assert "reclamo entro martedì 04/08/2026" in r.testo
    assert "con la sospensione feriale" not in r.testo


def test_ricorso_al_prefetto_estivo_non_slitta_a_ottobre():
    r = risposta("Multa per sosta notificata il 15/07/2026: entro quando il ricorso al Prefetto?")
    assert r.regola in {"cds_prefetto", "opposizione_verbale_cds"}
    _senza_rimozioni(r)
    if r.regola == "cds_prefetto":
        # 15/07 + 60 = 13/09/2026, domenica: proroga al lunedì (art. 2963 c.c.); con la sospensione sarebbe ottobre.
        assert "14/09/2026" in r.testo
        assert "con la sospensione feriale" not in r.testo


@pytest.mark.parametrize("domanda, modello, scadenza, feriale", [
    ("Decreto ingiuntivo per TFR notificato il 20/07/2026 al datore di lavoro: entro quando l'opposizione?",
     "LAV_OPPOSIZIONE_DI", "31/08/2026", False),
    ("Decreto ingiuntivo per contributi INPS notificato il 20/07/2026: entro quando l'opposizione?",
     "LAV_OPPOSIZIONE_DI", "31/08/2026", False),
    ("Decreto ingiuntivo notificato il 20/07/2026: entro quando l'opposizione?",
     "CIV_OPPOSIZIONE_DI", "29/09/2026", True),
    ("Reclamo cautelare contro l'ordinanza comunicata il 20/07/2026: entro quando?",
     "CIV_RECLAMO_CAUTELARE_669_TERDECIES", "04/08/2026", False),
])
def test_lex_sceglie_il_termine_con_o_senza_sospensione_per_materia(domanda, modello, scadenza, feriale):
    ident, campi = _calcolo(domanda)
    assert ident == "termini_processuali"
    assert campi["term_modello"] == modello
    esito = termini_scadenza.calcola(campi)
    assert esito["scadenza"] == scadenza
    assert esito["sospensione_feriale"] is feriale


def test_espulsione_non_e_il_ricorso_al_prefetto_del_codice_della_strada():
    ident, campi = _calcolo("Ricorso contro il decreto di espulsione del prefetto notificato il 20/07/2026: "
                            "entro quando?")
    assert ident == "termini_processuali"
    assert campi["term_modello"] == "IMM_RICORSO_ESPULSIONE_18"
    esito = termini_scadenza.calcola(campi)
    assert esito["scadenza"] == "10/08/2026"  # venti giorni (art. 18, comma 3, d.lgs. 150/2011)
    ident, campi = _calcolo("Verbale notificato il 15/07/2026: entro quando il ricorso al prefetto?")
    assert campi.get("term_modello") == "CDS_RICORSO_PREFETTO_60GG"


@pytest.mark.parametrize("domanda, materia, giudice", [
    ("Il dipendente reclama stipendi arretrati per 2.500 euro: competente il giudice di pace o il tribunale?",
     "lavoro_previdenza", "Tribunale in funzione di giudice del lavoro"),
    ("Opposizione tardiva ex art. 650 c.p.c. a un decreto di 6.000 euro: va dal giudice di pace o in tribunale?",
     "opposizione_decreto_ingiuntivo", "Ufficio giudiziario del giudice che ha emesso il decreto"),
])
def test_lex_competenza_che_il_valore_non_decide(domanda, materia, giudice):
    ident, campi = _calcolo(domanda)
    assert ident == "competenza_valore"
    assert campi["comp_materia"] == materia
    assert competenza_valore.calcola(campi)["giudice_competente"] == giudice
