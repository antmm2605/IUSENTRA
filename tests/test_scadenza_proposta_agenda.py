"""Aggancio agenda alla conferma di una proposta di udienza (Fase 2 sync Polisweb)."""

from __future__ import annotations

from datetime import date, timedelta

from pct.agenda import Agenda
from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
from web.services.scadenza_proposta_agenda import crea_agenda_da_udienza_confermata

FUTURO = (date.today() + timedelta(days=15)).isoformat()


def _scadenziario(tmp_path) -> GestioneScadenziario:
    return GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))


def _bozza_udienza(manager: GestioneScadenziario, **extra):
    return manager.nuova(
        titolo="Udienza di trattazione",
        tipo=TipoTermine.UDIENZA,
        data_scadenza=FUTURO,
        id_fascicolo="F1",
        stato=StatoTermine.BOZZA,
        **extra,
    )


def test_conferma_udienza_crea_appuntamento_collegato(tmp_path):
    scad = _scadenziario(tmp_path)
    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))
    bozza = _bozza_udienza(scad)
    scad.conferma_bozza(bozza.id)

    creato = crea_agenda_da_udienza_confermata(
        scad.get(bozza.id),
        gestione_agenda=agenda,
        gestione_scadenziario=scad,
    )

    assert creato is True
    appuntamenti = agenda.tutti()
    assert len(appuntamenti) == 1
    assert appuntamenti[0].data_ora.startswith(FUTURO)
    # back-link salvato sulla scadenza
    assert scad.get(bozza.id).id_appuntamento == appuntamenti[0].id


def test_conferma_udienza_e_idempotente(tmp_path):
    scad = _scadenziario(tmp_path)
    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))
    bozza = _bozza_udienza(scad)
    scad.conferma_bozza(bozza.id)

    primo = crea_agenda_da_udienza_confermata(scad.get(bozza.id), gestione_agenda=agenda, gestione_scadenziario=scad)
    secondo = crea_agenda_da_udienza_confermata(scad.get(bozza.id), gestione_agenda=agenda, gestione_scadenziario=scad)

    assert primo is True
    assert secondo is False
    assert len(agenda.tutti()) == 1


def test_orario_udienza_rispettato_se_presente(tmp_path):
    scad = _scadenziario(tmp_path)
    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))
    bozza = _bozza_udienza(scad, hearing_time="10:30")
    scad.conferma_bozza(bozza.id)

    crea_agenda_da_udienza_confermata(scad.get(bozza.id), gestione_agenda=agenda, gestione_scadenziario=scad)

    assert agenda.tutti()[0].data_ora == f"{FUTURO}T10:30:00"
