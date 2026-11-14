"""Una sola regola per la «prossima scadenza» dell'elenco: vista operativa ed economica dicono la stessa data."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

from web.services import react_fascicoli_bridge as bridge


def _fascicolo(**valori):
    base = dict(id="F1", prossima_scadenza=None, documenti=[SimpleNamespace(id="D1")], documenti_non_caricati=False)
    base.update(valori)
    return SimpleNamespace(**base)


def _giorno(delta: int) -> str:
    return (date.today() + timedelta(days=delta)).isoformat()


def test_vince_la_data_piu_vicina_fra_attivita_scadenziario_e_archivio(monkeypatch):
    archivio = SimpleNamespace(id="archivio-1", data_scadenza=_giorno(5), data=_giorno(5))
    monkeypatch.setattr(bridge, "_automatic_next_deadline_from_documents", lambda _f: archivio)
    termine = SimpleNamespace(id="S1", data_scadenza=_giorno(20))
    attivita = SimpleNamespace(id="A1", data=_giorno(30))
    scelta = bridge._next_deadline(_fascicolo(prossima_scadenza=attivita), {"F1": [termine]})
    assert scelta is archivio


def test_termine_scaduto_dello_scadenziario_resta_in_evidenza(monkeypatch):
    monkeypatch.setattr(bridge, "_automatic_next_deadline_from_documents",
                        lambda _f: SimpleNamespace(id="a", data_scadenza=_giorno(3)))
    scaduto = SimpleNamespace(id="S1", data_scadenza=_giorno(-2))
    assert bridge._next_deadline(_fascicolo(), {"F1": [scaduto]}) is scaduto


def test_data_dell_archivio_trascorsa_non_e_la_prossima(monkeypatch):
    monkeypatch.setattr(bridge, "_automatic_next_deadline_from_documents",
                        lambda _f: SimpleNamespace(id="a", data_scadenza=_giorno(-30)))
    termine = SimpleNamespace(id="S1", data_scadenza=_giorno(40))
    assert bridge._next_deadline(_fascicolo(), {"F1": [termine]}) is termine


def test_senza_documenti_l_archivio_non_si_consulta(monkeypatch):
    chiamate = []
    monkeypatch.setattr(bridge, "_automatic_next_deadline_from_documents", lambda f: chiamate.append(f))
    assert bridge._next_deadline(_fascicolo(documenti=[]), {"F1": []}) is None
    assert chiamate == []


def test_a_parita_di_giorno_vale_l_ordine_delle_fonti(monkeypatch):
    archivio = SimpleNamespace(id="archivio", data_scadenza=_giorno(7))
    monkeypatch.setattr(bridge, "_automatic_next_deadline_from_documents", lambda _f: archivio)
    termine = SimpleNamespace(id="S1", data_scadenza=_giorno(7))
    assert bridge._next_deadline(_fascicolo(), {"F1": [termine]}) is termine


def test_vista_economica_legge_le_righe_salvate():
    from web.services.fascicoli_list_runtime import enrich_economic_page

    righe = [{"id": "F1", "nextDeadlineIso": "2026-12-01", "paymentSummary": {"state": "completo"}}]
    assert enrich_economic_page(None, "t", "", righe) is righe
