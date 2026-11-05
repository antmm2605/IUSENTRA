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


class _RegistroFinto:
    def __init__(self, righe):
        self.righe, self.accodati = righe, []

    def sintesi_studio(self, tenant_id):
        return self.righe

    def accoda_evento(self, tenant_id, fascicolo_id, **_k):
        self.accodati.append(fascicolo_id)


def test_fascicoli_con_letture_mancanti_entrano_in_coda_a_lotti(monkeypatch):
    """05/11/2026: migliaia di documenti mai indicizzati restavano fermi perché nessun evento li metteva in coda."""
    import web.services.archivio_letture_runtime as runtime

    monkeypatch.setattr(runtime, "_ACCODATI_PENDENTI", {})
    righe = [
        {"fascicolo_id": "A", "aggiornato_il": "2026-11-01", "lettori": {"indice_documentale": {"da_leggere": 3}}},
        {"fascicolo_id": "B", "aggiornato_il": "2026-10-01", "lettori": {"ocr": {"da_leggere": 1}}},
        {"fascicolo_id": "C", "aggiornato_il": "2026-09-01", "lettori": {"indice_documentale": {"da_leggere": 0}}},
        {"fascicolo_id": "D", "aggiornato_il": "2026-08-01", "lettori": {"presidio_economico": {"da_leggere": 9}}},
    ]
    registro = _RegistroFinto(righe)
    assert runtime.accoda_letture_pendenti(registro, "studio", limite=1, adesso=1000.0) == 1
    assert registro.accodati == ["B"]  # il meno recente fra quelli con letture di base mancanti
    assert runtime.accoda_letture_pendenti(registro, "studio", limite=5, adesso=1100.0) == 1
    assert registro.accodati == ["B", "A"]  # B non torna in coda prima di 6 ore; C e D non hanno letture di base mancanti
    assert runtime.accoda_letture_pendenti(registro, "studio", limite=5, adesso=1000.0 + 7 * 3600) == 2
