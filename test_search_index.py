"""Test per lo scadenziario legale intelligente."""

import pytest
from datetime import date, timedelta

from pct.scadenziario import (
    GestioneScadenziario,
    Scadenza,
    TipoTermine,
    PrioritaTermine,
    StatoTermine,
    PRESET_TERMINI,
    calcola_termine,
    festività_italiane,
    è_giorno_lavorativo,
    prossimo_giorno_lavorativo,
    _calcola_pasqua,
)


@pytest.fixture
def gs(tmp_path):
    return GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))


# ------------------------------------------------------------------ Festività e giorni lavorativi

def test_pasqua_2024():
    p = _calcola_pasqua(2024)
    assert p == date(2024, 3, 31)


def test_pasqua_2025():
    p = _calcola_pasqua(2025)
    assert p == date(2025, 4, 20)


def test_festività_fisse_2024():
    feste = festività_italiane(2024)
    assert date(2024, 1, 1) in feste   # Capodanno
    assert date(2024, 4, 25) in feste  # Liberazione
    assert date(2024, 6, 2) in feste   # Repubblica
    assert date(2024, 8, 15) in feste  # Ferragosto
    assert date(2024, 12, 25) in feste # Natale


def test_pasquetta_2024():
    feste = festività_italiane(2024)
    assert date(2024, 4, 1) in feste  # Lunedì dell'Angelo


def test_sabato_non_lavorativo():
    sabato = date(2024, 1, 6)  # Sabato (e anche Epifania)
    assert not è_giorno_lavorativo(sabato)


def test_domenica_non_lavorativa():
    domenica = date(2024, 1, 7)
    assert not è_giorno_lavorativo(domenica)


def test_capodanno_non_lavorativo():
    assert not è_giorno_lavorativo(date(2024, 1, 1))


def test_agosto_non_lavorativo_con_feriale():
    """Agosto è non-lavorativo quando sospensione_feriale=True."""
    assert not è_giorno_lavorativo(date(2024, 8, 5))  # Lunedì normale
    assert not è_giorno_lavorativo(date(2024, 8, 20))


def test_agosto_lavorativo_senza_feriale():
    """Agosto è lavorativo quando sospensione_feriale=False."""
    lunedi_agosto = date(2024, 8, 5)
    assert è_giorno_lavorativo(lunedi_agosto, sospensione_feriale=False)


def test_giorno_lavorativo_normale():
    """Un giovedì normale è lavorativo."""
    assert è_giorno_lavorativo(date(2024, 1, 11))


def test_prossimo_giorno_lavorativo_da_domenica():
    domenica = date(2024, 1, 7)
    lun = prossimo_giorno_lavorativo(domenica)
    assert lun == date(2024, 1, 8)


def test_prossimo_giorno_lavorativo_da_sabato():
    sabato = date(2024, 1, 6)
    lun = prossimo_giorno_lavorativo(sabato)
    assert lun == date(2024, 1, 8)


# ------------------------------------------------------------------ Calcolo termini

def test_calcola_termine_liberi():
    """30 giorni liberi (lavorativi), escludendo agosto."""
    d = date(2024, 1, 15)  # Lunedì
    scad = calcola_termine(d, 30, tipo="liberi", sospensione_feriale=True)
    # Il risultato deve essere >= d + 30 giorni lavorativi
    assert scad > d
    assert è_giorno_lavorativo(scad)


def test_calcola_termine_continui():
    """30 giorni continui."""
    d = date(2024, 1, 15)
    scad = calcola_termine(d, 30, tipo="continui", sospensione_feriale=False)
    # Almeno 30 giorni dopo (può essere prorogata se cade in weekend)
    assert scad >= d + timedelta(days=30)


def test_termine_proroga_domenica():
    """Se la scadenza cade di domenica, viene prorogata a lunedì."""
    # Trovare una data dove il +30 cade di domenica
    # Data 2024-04-28 + 30 continui = 2024-05-28 (martedì) — troviamo altro
    # 2024-01-01 + 30 = 2024-01-31 (mercoledì) - no
    # 2024-02-04 + 30 continui = 2024-03-05 (martedì)
    # Usiamo 2024-03-10 + 30 = 2024-04-09 (martedì)
    # Usiamo un approccio: cerchiamo una domenica come risultato base
    for days_offset in range(1, 60):
        d_test = date(2024, 3, 1) + timedelta(days=days_offset)
        d_raw = d_test + timedelta(days=30)
        if d_raw.weekday() == 6:  # domenica
            scad = calcola_termine(d_test, 30, tipo="continui", sospensione_feriale=False)
            assert scad.weekday() != 6  # non domenica
            assert scad == d_raw + timedelta(days=1)
            break


def test_impugnazione_30gg():
    preset = PRESET_TERMINI["impugnazione_sentenza_civile"]
    assert preset["giorni"] == 30
    assert preset["tipo"] == "liberi"


def test_appello_lungo_6mesi():
    preset = PRESET_TERMINI["appello_lungo"]
    assert preset["giorni"] == 180  # 6 * 30
    assert preset["tipo"] == "continui"


def test_opposizione_decreto_ingiuntivo():
    preset = PRESET_TERMINI["opposizione_decreto_ingiuntivo"]
    assert preset["giorni"] == 40


# ------------------------------------------------------------------ CRUD Scadenze

def test_nuova_scadenza(gs):
    domani = (date.today() + timedelta(days=10)).isoformat()
    sc = gs.nuova(
        titolo="Deposito memoria",
        tipo=TipoTermine.DEPOSITO_MEMORIA,
        data_scadenza=domani,
    )
    assert sc.id is not None
    assert sc.titolo == "Deposito memoria"
    assert sc.stato == StatoTermine.APERTO


def test_titolo_vuoto_errore(gs):
    with pytest.raises(ValueError):
        gs.nuova("  ", TipoTermine.ALTRO, date.today().isoformat())


def test_nuova_da_preset(gs):
    sc = gs.nuova_da_preset(
        preset_key="impugnazione_sentenza_civile",
        titolo="Appello avverso sentenza n. 123/2024",
        data_decorrenza=date.today().isoformat(),
    )
    assert sc.id is not None
    assert sc.data_scadenza > date.today().isoformat()
    assert è_giorno_lavorativo(date.fromisoformat(sc.data_scadenza))


def test_preset_inesistente_errore(gs):
    with pytest.raises(ValueError):
        gs.nuova_da_preset("non_esiste", "titolo", date.today().isoformat())


def test_aggiorna_scadenza(gs):
    sc = gs.nuova("Test", TipoTermine.ALTRO, (date.today() + timedelta(days=5)).isoformat())
    gs.aggiorna(sc.id, note="Aggiornamento note", perentorio=True)
    aggiornata = gs.get(sc.id)
    assert aggiornata.note == "Aggiornamento note"
    assert aggiornata.perentorio is True


def test_completa_scadenza(gs):
    sc = gs.nuova("Completare", TipoTermine.ALTRO,
                  (date.today() + timedelta(days=5)).isoformat())
    gs.completa(sc.id, note="Fatto")
    completata = gs.get(sc.id)
    assert completata.stato == StatoTermine.COMPLETATO
    assert completata.completata_il != ""


def test_elimina_scadenza(gs):
    sc = gs.nuova("Elimina", TipoTermine.ALTRO,
                  (date.today() + timedelta(days=5)).isoformat())
    gs.elimina(sc.id)
    assert gs.get(sc.id) is None


# ------------------------------------------------------------------ Priorità

def test_priorita_critica_0gg():
    sc = Scadenza(
        id="test",
        tipo=TipoTermine.ALTRO,
        stato=StatoTermine.APERTO,
        titolo="Test",
        data_scadenza=date.today().isoformat(),
    )
    sc.aggiorna_priorita()
    assert sc.priorita == PrioritaTermine.CRITICA


def test_priorita_alta_5gg():
    sc = Scadenza(
        id="test",
        tipo=TipoTermine.ALTRO,
        stato=StatoTermine.APERTO,
        titolo="Test",
        data_scadenza=(date.today() + timedelta(days=5)).isoformat(),
    )
    sc.aggiorna_priorita()
    assert sc.priorita == PrioritaTermine.ALTA


def test_priorita_bassa_60gg():
    sc = Scadenza(
        id="test",
        tipo=TipoTermine.ALTRO,
        stato=StatoTermine.APERTO,
        titolo="Test",
        data_scadenza=(date.today() + timedelta(days=60)).isoformat(),
    )
    sc.aggiorna_priorita()
    assert sc.priorita == PrioritaTermine.BASSA


# ------------------------------------------------------------------ Query

def test_imminenti(gs):
    domani = (date.today() + timedelta(days=1)).isoformat()
    tra_30 = (date.today() + timedelta(days=30)).isoformat()
    gs.nuova("Vicina", TipoTermine.ALTRO, domani)
    gs.nuova("Lontana", TipoTermine.ALTRO, tra_30)
    imm = gs.imminenti(entro_giorni=7)
    assert len(imm) == 1
    assert imm[0].titolo == "Vicina"


def test_scadute_rilevate(gs):
    ieri = (date.today() - timedelta(days=1)).isoformat()
    gs.nuova("Scaduta", TipoTermine.ALTRO, ieri)
    sc = gs.scadute()
    assert len(sc) == 1
    assert sc[0].stato == StatoTermine.SCADUTO


def test_filtra_per_fascicolo(gs):
    gs.nuova("F1", TipoTermine.ALTRO,
             (date.today() + timedelta(days=10)).isoformat(),
             id_fascicolo="FASC001")
    gs.nuova("F2", TipoTermine.ALTRO,
             (date.today() + timedelta(days=10)).isoformat(),
             id_fascicolo="FASC002")
    risultati = gs.tutte(id_fascicolo="FASC001")
    assert all(s.id_fascicolo == "FASC001" for s in risultati)


def test_avvisi_da_notificare(gs):
    """Una scadenza tra 7 giorni deve generare un avviso."""
    tra_7 = (date.today() + timedelta(days=7)).isoformat()
    gs.nuova("Avviso test", TipoTermine.ALTRO, tra_7,
             giorni_preavviso=[7, 3, 1])
    da_notif = gs.scadenze_da_notificare()
    assert len(da_notif) == 1
    assert da_notif[0][1] == 7


def test_segna_avviso_inviato(gs):
    tra_7 = (date.today() + timedelta(days=7)).isoformat()
    sc = gs.nuova("Avviso test 2", TipoTermine.ALTRO, tra_7,
                  giorni_preavviso=[7, 3, 1])
    gs.segna_avviso_inviato(sc.id, 7)
    da_notif = gs.scadenze_da_notificare()
    ids = [s.id for s, _ in da_notif]
    assert sc.id not in ids


# ------------------------------------------------------------------ Persistenza

def test_persistenza(tmp_path):
    db = str(tmp_path / "sc.json")
    gs1 = GestioneScadenziario(db_path=db)
    gs1.nuova("Persistenza", TipoTermine.ALTRO,
              (date.today() + timedelta(days=10)).isoformat())
    gs2 = GestioneScadenziario(db_path=db)
    assert len(gs2.tutte()) == 1
    assert gs2.tutte()[0].titolo == "Persistenza"


# ------------------------------------------------------------------ Statistiche

def test_statistiche(gs):
    domani = (date.today() + timedelta(days=1)).isoformat()
    tra_30 = (date.today() + timedelta(days=30)).isoformat()
    sc1 = gs.nuova("SC1", TipoTermine.ALTRO, domani)
    gs.nuova("SC2", TipoTermine.ALTRO, tra_30)
    gs.completa(sc1.id)
    stats = gs.statistiche()
    assert stats["totale"] == 2
    assert stats["completate"] == 1
    assert stats["aperte"] == 1
