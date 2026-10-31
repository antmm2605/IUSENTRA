"""Memorie 171-ter proposte dalla prima udienza e ricalcolate al rinvio (31/10/2026)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from pct.scadenze_da_udienza import allinea_scadenze_udienza, e_prima_udienza_di_cognizione
from pct.scadenziario import GestioneScadenziario, StatoTermine

OGGI = date(2026, 9, 1)


def _udienza(data: str, titolo: str = "Prima udienza di comparizione e trattazione", **altro):
    return SimpleNamespace(id="APP-1", tipo="UDIENZA", stato="PROGRAMMATO", data_ora=f"{data}T09:30:00",
                           titolo=titolo, note="", procedimento="", **altro)


FASCICOLO = SimpleNamespace(id="F-1", tipo="CIVILE")


@pytest.fixture
def scadenziario(tmp_path):
    return GestioneScadenziario(str(tmp_path / "scadenze.json"))


def test_la_prima_udienza_propone_le_tre_memorie_a_ritroso_come_bozze(scadenziario):
    esito = allinea_scadenze_udienza(_udienza("2027-03-15"), FASCICOLO, scadenziario, oggi=OGGI)
    assert esito == {"proposte": 3, "ricalcolate": 0, "da_verificare": 0}
    memorie = sorted(scadenziario.tutte(solo_aperte=False), key=lambda s: s.data_scadenza)
    assert [s.stato for s in memorie] == [StatoTermine.BOZZA] * 3
    assert all(s.id_appuntamento == "APP-1" and s.id_fascicolo == "F-1" for s in memorie)
    assert all(s.data_scadenza < "2027-03-15" for s in memorie)
    # Un secondo giro non duplica.
    assert allinea_scadenze_udienza(_udienza("2027-03-15"), FASCICOLO, scadenziario, oggi=OGGI)["proposte"] == 0


def test_il_rinvio_sposta_le_memorie_ma_non_quelle_cambiate_a_mano(scadenziario):
    allinea_scadenze_udienza(_udienza("2027-03-15"), FASCICOLO, scadenziario, oggi=OGGI)
    memorie = sorted(scadenziario.tutte(solo_aperte=False), key=lambda s: s.data_scadenza)
    prima_n1 = memorie[0].data_scadenza
    scadenziario.aggiorna(memorie[2].id, data_scadenza="2027-03-01")  # n. 3 cambiata dall'avvocato
    esito = allinea_scadenze_udienza(_udienza("2027-04-15"), FASCICOLO, scadenziario, oggi=OGGI)
    assert esito == {"proposte": 0, "ricalcolate": 2, "da_verificare": 1}
    aggiornate = {s.id: s for s in scadenziario.tutte(solo_aperte=False)}
    assert aggiornate[memorie[0].id].data_scadenza > prima_n1
    assert aggiornate[memorie[2].id].data_scadenza == "2027-03-01"
    assert "verificare il termine" in aggiornate[memorie[2].id].note
    # Il rinvio già registrato non si ripete.
    assert allinea_scadenze_udienza(_udienza("2027-04-15"), FASCICOLO, scadenziario, oggi=OGGI) == {
        "proposte": 0, "ricalcolate": 0, "da_verificare": 0}


def test_solo_termini_futuri_e_solo_prima_udienza_del_civile(scadenziario):
    # Udienza il 20/09 con oggi 01/09: le memorie n. 1 e n. 2 sono già scadute, si propone solo la n. 3.
    assert allinea_scadenze_udienza(_udienza("2026-09-20"), FASCICOLO, scadenziario, oggi=OGGI)["proposte"] == 1
    riunione = _udienza("2027-03-15")
    riunione.tipo = "RIUNIONE"
    assert not e_prima_udienza_di_cognizione(riunione, FASCICOLO)
    assert not e_prima_udienza_di_cognizione(_udienza("2027-03-15", titolo="Udienza istruttoria"), FASCICOLO)
    assert not e_prima_udienza_di_cognizione(_udienza("2027-03-15"), SimpleNamespace(id="F", tipo="LAVORO"))
    annullata = _udienza("2027-03-15")
    annullata.stato = "ANNULLATO"
    assert not e_prima_udienza_di_cognizione(annullata, FASCICOLO)
    assert allinea_scadenze_udienza(_udienza("data-errata"), FASCICOLO, scadenziario, oggi=OGGI)["proposte"] == 0


def test_una_memoria_completata_non_si_tocca(scadenziario):
    allinea_scadenze_udienza(_udienza("2027-03-15"), FASCICOLO, scadenziario, oggi=OGGI)
    for scadenza in scadenziario.tutte(solo_aperte=False):
        scadenziario.aggiorna(scadenza.id, stato=StatoTermine.COMPLETATO.value)
    assert allinea_scadenze_udienza(_udienza("2027-04-15"), FASCICOLO, scadenziario, oggi=OGGI)["ricalcolate"] == 0


def test_il_giro_periodico_allinea_solo_le_udienze_future_collegate(scadenziario):
    from pct.scadenze_da_udienza import allinea_udienze

    collegata = _udienza("2027-03-15", id_fascicolo="F-1")
    senza_fascicolo = _udienza("2027-03-15", id_fascicolo="")
    passata = _udienza("2026-01-10", id_fascicolo="F-1")
    lavoro = _udienza("2027-05-10", id_fascicolo="F-L")
    lavoro.id = "APP-L"
    esito = allinea_udienze([collegata, senza_fascicolo, passata, lavoro], scadenziario, {"F-1": "CIVILE", "F-L": "LAVORO"},
                            oggi=OGGI)
    assert esito == {"proposte": 3, "ricalcolate": 0, "da_verificare": 0}


def test_il_giro_delle_notifiche_allinea_le_memorie_e_non_si_ferma_sugli_errori(scadenziario, monkeypatch):
    from web.services import notifications_runtime

    agenda = SimpleNamespace(tutti=lambda: [_udienza("2099-03-15", id_fascicolo="F-1")])
    monkeypatch.setattr(notifications_runtime, "_fascicolo_tipi_rows", lambda *_a: [{"id": "F-1", "tipo": "CIVILE"}])
    esito = notifications_runtime._allinea_memorie_da_udienza({}, None, agenda, scadenziario)
    assert esito == {"proposte": 3, "ricalcolate": 0, "da_verificare": 0}
    vuota = SimpleNamespace(tutti=lambda: [])
    assert notifications_runtime._allinea_memorie_da_udienza({}, None, vuota, scadenziario)["proposte"] == 0
    rotta = SimpleNamespace(tutti=lambda: (_ for _ in ()).throw(RuntimeError("agenda non disponibile")))
    assert "errore" in notifications_runtime._allinea_memorie_da_udienza({}, None, rotta, scadenziario)
    assert notifications_runtime._fascicolo_tipi_rows({}, None, set()) == []
