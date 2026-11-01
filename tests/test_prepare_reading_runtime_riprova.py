"""Il deploy ritenta la preparazione del registro se è occupato dalla versione in servizio (01/11/2026)."""

import sqlite3

import pytest

from tools import prepare_reading_runtime as strumento


def test_blocco_temporaneo_si_ritenta(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)
    tentativi = []

    def operazione():
        tentativi.append(1)
        if len(tentativi) < 3:
            raise sqlite3.OperationalError("database is locked")
        return ["ok"]

    assert strumento._con_riprova(operazione) == ["ok"]
    assert len(tentativi) == 3


def test_blocco_persistente_ferma_il_deploy(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _s: None)

    def operazione():
        raise sqlite3.OperationalError("database is locked")

    with pytest.raises(sqlite3.OperationalError):
        strumento._con_riprova(operazione, tentativi=2)


def test_altri_errori_non_si_ritentano():
    tentativi = []

    def operazione():
        tentativi.append(1)
        raise sqlite3.OperationalError("no such table: letture_eventi")

    with pytest.raises(sqlite3.OperationalError):
        strumento._con_riprova(operazione)
    assert len(tentativi) == 1
