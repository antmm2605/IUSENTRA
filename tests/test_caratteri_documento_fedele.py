"""Il riconoscimento dei caratteri: quello che l'avvocato vede cambiare.

Un carattere letto male non fa saltare niente — cambia solo l'aspetto di tutta
la pagina, e ce ne si accorge davanti alla stampa.
"""

from __future__ import annotations

import subprocess
import sys

import pytest

from pct.catalogo_caratteri import ETICHETTE_CARATTERI, TONO_CARATTERI
from pct.documento_fedele.taratura import (
    FAMIGLIE_EDITOR,
    famiglia_editor,
    pila_font,
)


def test_il_catalogo_si_carica_senza_il_driver_del_database():
    """Il catalogo stava dentro un modulo che importa PostgreSQL.

    Dove quel driver manca, l'importazione trovava tre caratteri invece di
    quarantasei e ogni atto tornava in Times New Roman o in Arial. Questo test
    importa il catalogo in un interprete separato, per essere sicuri che non si
    tiri dietro niente.
    """
    codice = (
        "import sys;"
        "sys.modules['psycopg2'] = None;"
        "from pct.catalogo_caratteri import ETICHETTE_CARATTERI;"
        "print(len(ETICHETTE_CARATTERI))"
    )
    esito = subprocess.run([sys.executable, "-c", codice], capture_output=True, text=True)
    assert esito.returncode == 0, f"il catalogo non si carica da solo: {esito.stderr[-400:]}"
    assert int(esito.stdout.strip().splitlines()[-1]) > 20


def test_la_tendina_ha_tutte_le_famiglie_del_catalogo():
    assert set(FAMIGLIE_EDITOR) == set(ETICHETTE_CARATTERI)
    assert len(FAMIGLIE_EDITOR) > 20, "il catalogo non si e' caricato"


@pytest.mark.parametrize("dichiarato, atteso", [
    ("Georgia", "Georgia"),
    ("ABCDEF+Georgia-Bold", "Georgia"),
    ("TimesNewRomanPS-BoldMT", "Times New Roman"),
    ("Book Antiqua", "Book Antiqua"),
    ("Century Schoolbook", "Century Schoolbook"),
])
def test_le_famiglie_del_catalogo_restano_se_stesse(dichiarato, atteso):
    assert famiglia_editor(dichiarato)[0] == atteso


@pytest.mark.parametrize("clone, originale", [
    ("Carlito", "Calibri"),
    ("Caladea", "Cambria"),
    ("Tinos", "Times New Roman"),
    ("Arimo", "Arial"),
    ("Cousine", "Courier New"),
    ("LiberationSerif", "Times New Roman"),
    ("LiberationSans", "Arial"),
    ("LiberationMono", "Courier New"),
    ("NimbusRomNo9L-Regu", "Times New Roman"),
    ("NimbusMonoPS-Regular", "Courier New"),
    ("Gelasio", "Georgia"),
])
def test_i_cloni_metrici_tornano_al_carattere_che_imitano(clone, originale):
    """Un PDF fatto su Linux dichiara il clone, non il carattere di Word."""
    assert famiglia_editor(clone)[0] == originale


@pytest.mark.parametrize("dichiarato, atteso", [
    ("MinionPro-Regular", "Book Antiqua"),
    ("Sabon-Roman", "Book Antiqua"),
    ("EBGaramond12-Regular", "Garamond"),
    ("PTSerif-Regular", "Source Serif 4"),
    ("NotoSerif", "Source Serif 4"),
    ("Futura-Medium", "Century Gothic"),
    ("AvenirNext-Regular", "Century Gothic"),
    ("HelveticaNeue", "Arial"),
    ("FrutigerLTStd-Roman", "Arial"),
    ("CourierPrime", "Courier New"),
    ("JetBrainsMono-Regular", "Consolas"),
])
def test_i_caratteri_fuori_catalogo_vanno_al_parente_piu_vicino(dichiarato, atteso):
    assert famiglia_editor(dichiarato)[0] == atteso


@pytest.mark.parametrize("sconosciuto, atteso", [
    ("QwertyMono", "Courier New"),
    ("QwertyCode", "Courier New"),
    ("XyzSansPro", "Arial"),
    ("XyzGrotesk", "Arial"),
    ("AcmeSlab", "Times New Roman"),
    ("AcmeAntiqua", "Times New Roman"),
])
def test_un_carattere_sconosciuto_finisce_nella_famiglia_giusta(sconosciuto, atteso):
    """Prima diventava Arial per scarto, a meno della parola «serif» nel nome."""
    assert famiglia_editor(sconosciuto)[0] == atteso


def test_un_carattere_che_non_dice_niente_di_se_prende_le_grazie():
    """Un atto scritto in un carattere sconosciuto quasi sempre ha le grazie."""
    assert famiglia_editor("Qwerty")[0] == "Times New Roman"


@pytest.mark.parametrize("famiglia, generico", [
    ("Times New Roman", "serif"),
    ("Georgia", "serif"),
    ("Arial", "sans-serif"),
    ("Century Gothic", "sans-serif"),
    ("Segoe UI", "sans-serif"),
    ("Tahoma", "sans-serif"),
    ("Trebuchet MS", "sans-serif"),
    ("Courier New", "monospace"),
    ("Consolas", "monospace"),
])
def test_il_ripiego_generico_segue_il_tono_dichiarato(famiglia, generico):
    """Un carattere senza grazie che ripiega su `serif` cambia faccia appena
    manca dal computer di chi legge."""
    assert pila_font(famiglia).endswith(generico)
    assert TONO_CARATTERI.get(famiglia) in ("serif", "sans", "mono")


def test_il_nome_intero_ha_la_precedenza_su_quello_ripulito():
    """«Times New Roman» ripulito diventa «Times New», che non esiste."""
    pila = pila_font("Times New Roman")
    assert "'Times New'," not in pila, f"nella pila c'e' un carattere inventato: {pila}"
    assert pila == "'Times New Roman', serif"


def test_il_prefisso_del_sottoinsieme_non_conta():
    """I caratteri incorporati arrivano come «ABCDEF+Nome»."""
    assert famiglia_editor("WXYZAB+Verdana")[0] == "Verdana"
    assert "Verdana" in pila_font("WXYZAB+Verdana")
