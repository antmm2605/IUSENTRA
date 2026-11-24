"""Rito dell'accesso ai documenti: termine di trenta giorni letto dal testo vigente dell'art. 116 c.p.a. (biblioteca di
consultazione, edizione vigente al 23/11/2026). Frasi nuove, scritte per questo controllo (24/11/2026)."""
from __future__ import annotations

from datetime import date

import pytest

from lex.harness import rispondi
from lex.harness.norme import ISTANTANEA, contiene
from lex.harness.norme import testo_norma as leggi_testo

pytestmark = pytest.mark.skipif(not ISTANTANEA.is_file(), reason="istantanea delle norme non generata")

OGGI = "\n\nOggi è il 24/11/2026."


def test_art_116_cpa_ha_il_testo_completo():
    t = leggi_testo("cpa:116")
    assert t is not None and len(t.testo) > 1000
    assert contiene("cpa:116", "il ricorso e' proposto entro trenta giorni dalla conoscenza della determinazione impugnata")


def test_diniego_di_accesso_trenta_giorni_dalla_conoscenza():
    r = rispondi("Il Comune di Ancona ha respinto con provvedimento notificato il 04/11/2026 l'istanza di accesso agli atti "
                 "del permesso di costruire del vicino che il mio cliente aveva presentato il 01/10/2026. Entro quando "
                 "ricorriamo al TAR?" + OGGI, oggi=date(2026, 11, 24))
    assert r.regola == "accesso_atti"
    assert "04/12/2026" in r.testo and "art. 116 c.p.a." in r.testo
    assert "senza testo" not in r.testo and not r.affermazioni_tolte


def test_silenzio_sull_accesso_termine_scaduto_detto_chiaramente():
    r = rispondi("Il mio cliente ha chiesto il 10/09/2026 all'ASL di Pescara l'accesso alla propria cartella del concorso e "
                 "non ha avuto risposta. Come procediamo?" + OGGI, oggi=date(2026, 11, 24))
    assert r.regola == "accesso_atti"
    assert "10/10/2026" in r.testo and "09/11/2026" in r.testo and "già scaduto" in r.testo
