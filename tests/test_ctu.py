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


def test_archivio_corrotto_non_diventa_vuoto(tmp_path):
    import json
    path = tmp_path / "incarichi.json"
    path.write_text('{"incarico":', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        GestioneCtu(str(path))
    assert path.read_text(encoding="utf-8") == '{"incarico":'


def test_riga_invalida_non_viene_scartata(tmp_path):
    path = tmp_path / "incarichi.json"
    path.write_text('{"incarico":42}', encoding="utf-8")
    with pytest.raises(ValueError, match="Identificativo CTU"):
        GestioneCtu(str(path))
    assert path.read_text(encoding="utf-8") == '{"incarico":42}'


def test_due_processi_non_sovrascrivono_incarichi(gestione):
    from pct.ctu_repository import CtuConflict
    stale = GestioneCtu(str(gestione.db_path))
    first = _incarico(gestione)
    with pytest.raises(CtuConflict):
        _incarico(stale, nome_ctu="Altro consulente")
    persisted = GestioneCtu(str(gestione.db_path)).per_fascicolo("F1")
    assert len(persisted) == 1 and persisted[0].id == first.id
    assert stale.per_fascicolo("F1") == []


def test_scrittura_fallita_non_mantiene_operazione_in_memoria(gestione, monkeypatch):
    import pct.ctu as module
    item = _incarico(gestione)
    def fail_replace(*args):
        raise OSError("Disco non disponibile")
    monkeypatch.setattr(module.os, "replace", fail_replace)
    with pytest.raises(OSError, match="Disco non disponibile"):
        gestione.aggiungi_operazione(item.id, {"data": "2026-10-09", "minuti": 120})
    assert gestione.get(item.id).operazioni == []
    assert GestioneCtu(str(gestione.db_path)).get(item.id).operazioni == []
    assert not list(gestione.db_path.parent.glob(".ctu-*"))


@pytest.mark.parametrize("change", [
    {"minuti": "non leggibile"}, {"minuti": "NaN"}, {"minuti": "Infinity"}, {"minuti": 2.5},
    {"minuti": True}, {"minuti": []}, {"minuti": -1}, {"minuti": 1441},
    {"ora": "25:00"}, {"ora": "xx:yy"}, {"ora": "9:00"}, {"ora": "09:00:30"},
    {"presenza_giudice": "non determinata"}, {"presenza_giudice": 1},
])
def test_operazione_non_valida_non_sostituisce_i_dati_con_zero_o_orari_troncati(gestione, change):
    item = _incarico(gestione)
    before = gestione.db_path.read_bytes()
    with pytest.raises(ValueError):
        gestione.aggiungi_operazione(item.id, {"data": "2026-10-09", "minuti": 120, **change})
    assert gestione.get(item.id).operazioni == []
    assert gestione.db_path.read_bytes() == before


@pytest.mark.parametrize("presenza,expected", [(False, False), (True, True), ("false", False), ("0", False), ("off", False),
                                             ("on", True), ("true", True), ("1", True)])
def test_presenza_giudice_non_scambia_false_testuale_con_true(gestione, presenza, expected):
    item = _incarico(gestione)
    gestione.aggiungi_operazione(item.id, {"data": "2026-10-09", "ora": "09:30", "minuti": "120", "presenza_giudice": presenza})
    confirmed = GestioneCtu(str(gestione.db_path)).get(item.id).operazioni[0]
    assert confirmed["presenza_giudice"] is expected
    assert confirmed["minuti"] == 120
    assert confirmed["ora"] == "09:30"


def test_barriera_preparata_impedisce_scritture_json(gestione):
    from pct.ctu_transition import prepare_locked, source_lock
    item = _incarico(gestione)
    before = gestione.db_path.read_bytes()
    with source_lock(gestione.db_path):
        prepare_locked(gestione.db_path, tenant="studio", source_sha256="a" * 64)
    with pytest.raises(RuntimeError, match="transizione SQL"):
        gestione.aggiungi_ctp(item.id, nome="Geom. Neri", parte="Convenuto")
    assert gestione.db_path.read_bytes() == before
    assert gestione.get(item.id).consulenti_parte == []
    with pytest.raises(RuntimeError, match="transizione SQL"):
        GestioneCtu(str(gestione.db_path))
