"""Le espressioni sugli importi e sui numeri non devono degenerare su lunghe file di cifre e punti (backtracking)."""
from __future__ import annotations

import time

from lex.harness.fattispecie.schede import senza_importi, segnali_del_testo
from lex.harness.scrittura_segnaposto import _NUMERO

LUNGO = "1." * 25000   # 50.000 caratteri senza «euro»


def _durata(funzione, *argomenti) -> float:
    inizio = time.perf_counter()
    funzione(*argomenti)
    return time.perf_counter() - inizio


def test_importi_su_input_lungo_sotto_100_ms():
    assert _durata(senza_importi, LUNGO) < 0.1
    assert _durata(senza_importi, LUNGO + " euro") < 0.1


def test_numeri_dei_segnaposto_su_input_lungo_sotto_100_ms():
    assert _durata(_NUMERO.sub, "X", LUNGO) < 0.1


def test_importi_riconosciuti_come_prima():
    assert "[importo]" in senza_importi("ho pagato 1.250,50 euro alla banca")
    assert "[importo]" in senza_importi("un credito di € 12.000")
    assert "650" in senza_importi("opposizione tardiva ex art. 650 c.p.c.")


def test_testo_dei_segnali_calcolato_una_volta():
    segnali_del_testo.cache_clear()
    for _ in range(50):
        segnali_del_testo("decreto ingiuntivo di 5.000 euro")
    assert segnali_del_testo.cache_info().misses == 1
