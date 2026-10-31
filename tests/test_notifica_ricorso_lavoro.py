"""V33: termini dell'art. 415 c.p.c. solo da fonti certe (testo reale dei decreti del lavoro, 31/10/2026)."""

from __future__ import annotations

from datetime import date

from pct.notifica_ricorso_lavoro import data_di_pronuncia, proposte_art_415

DECRETO = ("Il Giudice del Lavoro, visto l'art. 415 c.p.c., FISSA l'udienza. ORDINA che il ricorso con il pedissequo "
           "decreto sia notificato a cura dell'istante alla controparte nei termini di legge. "
           "Vicenza, 24/07/2026 Il Giudice del Lavoro Dott.")


def test_dieci_giorni_dalla_pronuncia_e_trenta_giorni_liberi_prima_dell_udienza():
    proposte = {p.code: p for p in proposte_art_415(DECRETO, udienza=date(2026, 12, 16))}
    assert proposte["LAV_415_NOTIFICA_DIECI_GIORNI"].due_date == "2026-08-03"  # lavoro: niente sospensione feriale
    assert proposte["LAV_415_NOTIFICA_DIECI_GIORNI"].perentorio is False
    assert proposte["LAV_415_NOTIFICA_TRENTA_GIORNI"].due_date == "2026-11-13"  # domenica 15/11 anticipata
    estero = proposte_art_415(DECRETO, udienza=date(2026, 12, 16), estero=True)[1]
    assert "40 giorni" in estero.title and estero.due_date < "2026-11-13"


def test_senza_fonte_certa_nessuna_data_inventata():
    assert proposte_art_415(DECRETO.replace("nei termini di legge", "entro il termine che sarà fissato"), udienza=date(2026, 12, 16)) == []
    assert proposte_art_415(DECRETO.replace("Giudice del Lavoro", "Giudice").replace("art. 415", "art. 163"), udienza=None) == []
    solo_udienza = proposte_art_415(DECRETO.replace("Vicenza, 24/07/2026 ", ""), udienza=date(2026, 12, 16))
    assert [p.code for p in solo_udienza] == ["LAV_415_NOTIFICA_TRENTA_GIORNI"]
    assert data_di_pronuncia("Vicenza, 24/07/2026 Il Giudice ... Vicenza, 25/07/2026 Il Giudice") is None
