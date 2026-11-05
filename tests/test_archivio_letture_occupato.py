"""Archivio delle letture occupato da un altro motore: l'attività si rinvia, il giro non fallisce (05/11/2026)."""

import sqlite3

import pytest

from web.services.archivio_letture_runtime import _se_libero


def test_archivio_occupato_rinvia_l_attivita():
    def occupato():
        raise sqlite3.OperationalError("database is locked")

    assert _se_libero(occupato, 0) == 0
    assert _se_libero(lambda: 3, 0) == 3


def test_altri_errori_non_si_nascondono():
    def rotto():
        raise sqlite3.OperationalError("no such table: letture")

    with pytest.raises(sqlite3.OperationalError):
        _se_libero(rotto, 0)
