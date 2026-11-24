"""Tempo del recupero storico della Gazzetta in ogni giro orario, regolabile dall'ambiente (2.490.2)."""

import pytest

from pct.gazzetta.pianificazione import TEMPO_STORICO_MASSIMO, tempo_storico


@pytest.fixture(autouse=True)
def _ambiente_pulito(monkeypatch):
    monkeypatch.delenv("PCT_GAZZETTA_TEMPO_STORICO", raising=False)
    monkeypatch.delenv("GAZZETTA_TEMPO_STORICO", raising=False)


def test_valore_predefinito_venti_minuti():
    assert tempo_storico({}) == 1200.0


def test_variabile_d_ambiente_cinquanta_minuti(monkeypatch):
    monkeypatch.setenv("PCT_GAZZETTA_TEMPO_STORICO", "3000")
    assert tempo_storico({}) == 3000.0


def test_configurazione_prevale_sull_ambiente(monkeypatch):
    monkeypatch.setenv("PCT_GAZZETTA_TEMPO_STORICO", "3000")
    assert tempo_storico({"GAZZETTA_TEMPO_STORICO": "600"}) == 600.0


@pytest.mark.parametrize("valore, atteso", [("9999", TEMPO_STORICO_MASSIMO), ("5", 30.0), ("abc", 1200.0), ("", 1200.0)])
def test_limiti_e_valori_non_validi(monkeypatch, valore, atteso):
    monkeypatch.setenv("PCT_GAZZETTA_TEMPO_STORICO", valore)
    assert tempo_storico({}) == atteso


def test_il_giro_orario_usa_il_tempo_regolato(monkeypatch, tmp_path):
    import pct.gazzetta.pianificazione as pianificazione
    import pct.gazzetta.storico as storico

    ricevuto = {}
    monkeypatch.setenv("PCT_GAZZETTA_TEMPO_STORICO", "3000")
    monkeypatch.setattr(pianificazione, "esegui_giro", lambda archivio, **_: {"fascicoli_nuovi": 0})
    monkeypatch.setattr(storico, "esegui_tratto", lambda archivio, tempo_massimo: ricevuto.setdefault("t", tempo_massimo) and {"ok": True})
    config = {"GAZZETTA_UFFICIALE_DB": str(tmp_path / "gazzetta.sqlite")}
    pianificazione.esegui_da_pianificazione(config, con_storico=True)
    assert 2990.0 < ricevuto["t"] <= 3000.0


def test_il_tempo_dei_trenta_giorni_e_di_normattiva_si_toglie_dal_recupero_storico(monkeypatch, tmp_path):
    """Verifica del 24/11/2026 sull'8080: 42 minuti prima del recupero storico, giro di 103 minuti con 3000 s."""
    from pct.gazzetta import pianificazione, storico

    orologio = {"t": 1000.0}
    monkeypatch.setattr("time.monotonic", lambda: orologio["t"])

    def giro_lento(archivio, **_):
        orologio["t"] += 1800.0  # 30 minuti fra elenco dei 30 giorni e collegamento Normattiva
        return {"fascicoli_nuovi": 0}

    ricevuto = {}
    monkeypatch.setenv("PCT_GAZZETTA_TEMPO_STORICO", "3000")
    monkeypatch.setattr(pianificazione, "esegui_giro", giro_lento)
    monkeypatch.setattr(storico, "esegui_tratto", lambda archivio, tempo_massimo: ricevuto.setdefault("t", tempo_massimo) and {"ok": True})
    pianificazione.esegui_da_pianificazione({"GAZZETTA_UFFICIALE_DB": str(tmp_path / "g.sqlite")}, con_storico=True)
    assert ricevuto["t"] == 1200.0


def test_recupero_storico_rinviato_se_il_giro_ha_gia_usato_il_tempo(monkeypatch, tmp_path):
    from pct.gazzetta import pianificazione, storico

    orologio = {"t": 0.0}
    monkeypatch.setattr("time.monotonic", lambda: orologio["t"])

    def giro_lunghissimo(archivio, **_):
        orologio["t"] += 3500.0
        return {"fascicoli_nuovi": 0}

    def non_chiamare(*_a, **_k):
        raise AssertionError("il recupero storico non deve partire oltre il tempo del giro")

    monkeypatch.setenv("PCT_GAZZETTA_TEMPO_STORICO", "3000")
    monkeypatch.setattr(pianificazione, "esegui_giro", giro_lunghissimo)
    monkeypatch.setattr(storico, "esegui_tratto", non_chiamare)
    esito = pianificazione.esegui_da_pianificazione({"GAZZETTA_UFFICIALE_DB": str(tmp_path / "g.sqlite")}, con_storico=True)
    assert esito["storico"]["rinviato"] is True
