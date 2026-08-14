"""Incarichi CTU: timeline art. 195 c.p.c., CTP, proposte scadenze in BOZZA.

Fail-closed: date solo dall'ordinanza (validate ISO), incoerenze cronologiche
segnalate, proposte idempotenti, nessuna scadenza operativa senza conferma.
"""

from __future__ import annotations

import pytest

from pct.ctu import GestioneCtu, proposte_scadenze_incarico
from pct.scadenziario import GestioneScadenziario, StatoTermine


@pytest.fixture
def gestione(tmp_path):
    return GestioneCtu(db_path=str(tmp_path / "incarichi.json"))


def _incarico(gestione, **campi):
    base = dict(
        fascicolo_id="F1",
        ruolo_studio="PARTE",
        nome_ctu="Ing. Bruni",
        quesiti="Accerti il CTU lo stato dell'immobile...",
        data_nomina="2026-09-01",
        termine_bozza="2026-11-10",
        termine_osservazioni="2026-11-25",
        termine_deposito="2026-12-10",
    )
    base.update(campi)
    return gestione.nuovo(**base)


# --- Validazioni -----------------------------------------------------------------


def test_incarico_richiede_fascicolo(gestione):
    with pytest.raises(ValueError, match="fascicolo"):
        gestione.nuovo(fascicolo_id="", nome_ctu="Ing. Bruni")


def test_date_non_iso_rifiutate(gestione):
    with pytest.raises(ValueError, match="termine_bozza"):
        _incarico(gestione, termine_bozza="10/11/2026")


def test_timeline_ordinata_e_completa(gestione):
    incarico = _incarico(gestione)
    tappe = incarico.timeline()
    assert [t["chiave"] for t in tappe] == ["nomina", "giuramento", "bozza", "osservazioni", "deposito"]
    assert incarico.termini_incoerenti() == []


def test_termini_fuori_ordine_segnalati(gestione):
    incarico = _incarico(gestione, termine_osservazioni="2026-11-05")  # prima della bozza
    avvisi = incarico.termini_incoerenti()
    assert len(avvisi) == 1
    assert "ordinanza" in avvisi[0]


def test_ctp_art_201(gestione):
    incarico = _incarico(gestione)
    aggiornato = gestione.aggiungi_ctp(incarico.id, nome="Geom. Neri", parte="Convenuto")
    assert aggiornato.consulenti_parte[0].nome == "Geom. Neri"
    riletto = GestioneCtu(db_path=str(gestione.db_path)).get(incarico.id)
    assert riletto.consulenti_parte[0].parte == "Convenuto"


# --- Proposte scadenze -----------------------------------------------------------


def test_ruolo_parte_propone_osservazioni_e_deposito(gestione):
    incarico = _incarico(gestione)
    proposte = proposte_scadenze_incarico(incarico)
    chiavi = [p["chiave"].rsplit(":", 1)[-1] for p in proposte]
    assert chiavi == ["osservazioni", "deposito"]
    assert proposte[0]["data_scadenza"] == "2026-11-25"
    assert "195" in proposte[0]["fonte"]


def test_ruolo_ausiliario_propone_bozza_e_deposito(gestione):
    incarico = _incarico(gestione, ruolo_studio="AUSILIARIO")
    chiavi = [p["chiave"].rsplit(":", 1)[-1] for p in proposte_scadenze_incarico(incarico)]
    assert chiavi == ["bozza", "deposito"]


def test_senza_date_nessuna_proposta(gestione):
    incarico = _incarico(gestione, termine_bozza="", termine_osservazioni="", termine_deposito="")
    assert proposte_scadenze_incarico(incarico) == []


def test_proposte_in_bozza_e_idempotenti(gestione, tmp_path):
    scadenziario = GestioneScadenziario(db_path=str(tmp_path / "scadenze.json"))
    incarico = _incarico(gestione)
    primo = gestione.proponi_scadenze(incarico.id, get_scadenziario=lambda: scadenziario, attore="avv.rossi")
    secondo = gestione.proponi_scadenze(incarico.id, get_scadenziario=lambda: scadenziario, attore="avv.rossi")
    assert primo == 2
    assert secondo == 0
    bozze = scadenziario.bozze()
    assert len(bozze) == 2
    assert all(b.stato == StatoTermine.BOZZA for b in bozze)
    assert not scadenziario.tutte(solo_aperte=True)  # nessuna operativa senza conferma
