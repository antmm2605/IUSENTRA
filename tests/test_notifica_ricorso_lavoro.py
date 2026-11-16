"""V33: termini dell'art. 415 c.p.c. solo da fonti certe (testo reale dei decreti del lavoro, 31/10/2026)."""

from __future__ import annotations

from datetime import date

from pct.notifica_ricorso_lavoro import data_di_pronuncia, proposte_art_415

DECRETO = ("Il Giudice del Lavoro, visto l'art. 415 c.p.c., FISSA l'udienza. ORDINA che il ricorso con il pedissequo "
           "decreto sia notificato a cura dell'istante alla controparte nei termini di legge. "
           "Vicenza, 24/07/2026 Il Giudice del Lavoro Dott.")


def test_dieci_giorni_dalla_pronuncia_e_trenta_giorni_liberi_prima_dell_udienza():
    proposte = {p.code: p for p in proposte_art_415(DECRETO, udienza=date(2026, 12, 16), estero=False)}
    assert proposte["LAV_415_NOTIFICA_DIECI_GIORNI"].due_date == "2026-08-03"  # lavoro: niente sospensione feriale
    assert proposte["LAV_415_NOTIFICA_DIECI_GIORNI"].perentorio is False
    assert proposte["LAV_415_NOTIFICA_TRENTA_GIORNI"].due_date == "2026-11-13"  # domenica 15/11 anticipata
    estero = proposte_art_415(DECRETO, udienza=date(2026, 12, 16), estero=True)[1]
    assert "40 giorni" in estero.title and estero.due_date < "2026-11-13"


def test_senza_fonte_certa_nessuna_data_inventata():
    assert proposte_art_415(DECRETO.replace("nei termini di legge", "entro il termine che sarà fissato"), udienza=date(2026, 12, 16)) == []
    assert proposte_art_415(DECRETO.replace("Giudice del Lavoro", "Giudice").replace("art. 415", "art. 163"), udienza=None) == []
    solo_udienza = proposte_art_415(DECRETO.replace("Vicenza, 24/07/2026 ", ""), udienza=date(2026, 12, 16), estero=False)
    assert [p.code for p in solo_udienza] == ["LAV_415_NOTIFICA_TRENTA_GIORNI"]
    assert data_di_pronuncia("Vicenza, 24/07/2026 Il Giudice ... Vicenza, 25/07/2026 Il Giudice") is None


def test_destinazione_ignota_non_equivale_a_notifica_in_italia():
    assert [p.code for p in proposte_art_415(DECRETO, udienza=date(2026, 12, 16))] == [
        "LAV_415_NOTIFICA_DIECI_GIORNI",
    ]


def test_due_vincoli_un_solo_adempimento_di_notifica():
    from pct.notifica_ricorso_lavoro import unifica_notifica_art_415

    vincoli = proposte_art_415(DECRETO, udienza=date(2026, 12, 16), estero=False)
    proposta, = unifica_notifica_art_415(vincoli, oggi="2026-08-04")
    assert proposta.code == "LAV_415_NOTIFICA_TRENTA_GIORNI"
    assert proposta.due_date == vincoli[1].due_date
    assert proposta.altri_codici == ("LAV_415_NOTIFICA_DIECI_GIORNI",)
    assert "03/08/2026" in proposta.summary()
    assert "comma 4" in proposta.summary() and "comma 5" in proposta.summary()
    assert unifica_notifica_art_415(vincoli[:1], oggi="2026-08-04") == vincoli[:1]


def test_unifica_solo_vincoli_dello_stesso_appuntamento():
    from dataclasses import replace

    from pct.notifica_ricorso_lavoro import unifica_notifica_art_415

    primo, secondo = proposte_art_415(DECRETO, udienza=date(2026, 12, 16), estero=False)
    primo = replace(primo, campi_scadenza={"id_appuntamento": "UD1"})
    secondo = replace(secondo, campi_scadenza={"id_appuntamento": "UD1"})
    proposta, = unifica_notifica_art_415([primo, secondo], oggi="2026-08-01")
    assert proposta.campi_scadenza == {"id_appuntamento": "UD1"}
    altro = replace(secondo, campi_scadenza={"id_appuntamento": "UD2"})
    assert unifica_notifica_art_415([primo, altro], oggi="2026-08-01") == [primo, altro]
