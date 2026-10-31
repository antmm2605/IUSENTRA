"""Lex calcola i termini col motore unico (31/10/2026).

Prima il workflow e lo strumento di Lex sommavano i giorni al calendario: niente sospensione feriale
(L. 742/1969), niente proroga al primo giorno non festivo (art. 155 c.p.c.), «oggi» dell'ora del server,
e una tabella con norme sbagliate (art. 166 a 20 giorni, appello al Consiglio di Stato a 30 giorni
con l'art. 91, 20 giorni all'opposizione all'esecuzione) e un termine inventato di 30 giorni per i casi ignoti.
"""

from __future__ import annotations

import pytest

from lex.tools.legal_studio_tools import calculate_deadline, list_termini_disponibili
from lex.workflows.termini_processuali_workflow import _TERMINI, calcola_termine


@pytest.mark.parametrize(
    ("tipo", "decorrenza", "attesa"),
    [
        # 40 giorni dal 10/07: 21 a luglio, agosto sospeso, 19 a settembre → sabato 19/09 → lunedì 21/09.
        ("opposizione_decreto_ingiuntivo", "2026-07-10", "21/09/2026"),
        # Lavoro: nessuna sospensione feriale; domenica 09/08 → lunedì 10/08.
        ("appello_sentenza_lavoro", "2026-07-10", "10/08/2026"),
        # Art. 92 c.p.a.: 60 giorni.
        ("appello_tar", "2026-06-01", "31/07/2026"),
        # Art. 307 c.p.c.: 3 mesi, allungati dei 31 giorni di agosto.
        ("riassunzione_causa", "2026-06-15", "16/10/2026"),
        # Art. 166 c.p.c.: almeno 70 giorni prima dell'udienza.
        ("costituzione_convenuto", "2026-12-10", "01/10/2026"),
    ],
)
def test_lo_strumento_di_lex_usa_sospensione_feriale_e_art_155(tipo, decorrenza, attesa):
    esito = calculate_deadline(tipo, data_decorrenza=decorrenza)
    assert esito["ok"] is True
    assert esito["scadenza"] == attesa


def test_il_workflow_e_lo_strumento_danno_la_stessa_scadenza():
    testo = calcola_termine("opposizione_decreto_ingiuntivo", data_decorrenza_iso="2026-07-10")
    assert "21/09/2026" in testo


def test_un_termine_senza_norma_non_si_inventa():
    esito = calculate_deadline("opposizione_esecuzione", data_decorrenza="2026-01-01")
    assert esito["ok"] is False


def test_la_tabella_e_una_sola_e_ha_le_norme_giuste():
    assert {voce["key"] for voce in list_termini_disponibili()} == set(_TERMINI)
    assert _TERMINI["costituzione_convenuto"]["giorni"] == 70 and _TERMINI["costituzione_convenuto"]["direzione"] == "ritroso"
    assert _TERMINI["appello_tar"]["giorni"] == 60 and "art. 92" in _TERMINI["appello_tar"]["norma"]
    assert "617" in _TERMINI["opposizione_atti_esecutivi"]["norma"]
