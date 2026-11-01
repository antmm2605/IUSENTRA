"""Controllo Studio e scadenziario contano le scadute con la stessa regola (verifica a vista del 01/11/2026).

Il Controllo Studio diceva «10 termini scaduti», lo scadenziario «3 scadute da chiudere»: la differenza erano 7
udienze già tenute, di cui va registrato l'esito (regola V28, artt. 126 e 127-ter c.p.c.), non termini scaduti.
"""

from datetime import date
from types import SimpleNamespace

from pct.controllo_studio.fonti import voci_scadenze
from pct.controllo_studio.voce import ordina

OGGI = date(2026, 11, 1)


def _scadenza(ident, giorno, tipo):
    return SimpleNamespace(id=ident, stato="APERTO", data_scadenza=giorno, tipo=tipo, titolo=f"Voce {ident}",
                           perentorio=False, id_fascicolo="")


def test_udienza_passata_e_esito_da_registrare_non_termine_scaduto():
    voci = ordina(voci_scadenze([
        _scadenza("t1", "2026-10-06", "DEPOSITO"),
        _scadenza("u1", "2026-10-21", "UDIENZA"),
        _scadenza("f1", "2026-11-04", "UDIENZA"),
    ], {}, OGGI), OGGI)
    per_id = {v.id: v for v in voci}
    assert per_id["scadenza-t1"].fascia == "scaduto"
    assert per_id["scadenza-u1"].fascia == "esito_udienza"
    assert per_id["scadenza-u1"].etichetta == "Esito da registrare"
    assert per_id["scadenza-f1"].fascia == "settimana"
    assert sum(1 for v in voci if v.fascia == "scaduto") == 1
