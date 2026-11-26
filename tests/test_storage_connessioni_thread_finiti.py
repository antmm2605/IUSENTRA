"""Le connessioni a studio.db dei thread già finiti si chiudono: i file aperti non crescono a ogni giro.

26/11/2026: lo scheduler arrivò a 1.019 file aperti su 1.024 (353 studio.db e 350 studio.db-wal di un solo
studio) e da lì ogni lavoro falliva con «unable to open database file». Ogni lettura in sfondo gira in un
thread nuovo (``archivio-letture-<fascicolo>``), apre la sua connessione per thread e finisce; l'elenco
delle connessioni di ``StudioDB`` la teneva in vita per sempre.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import pytest

from pct.storage import StudioDB

pytestmark = pytest.mark.skipif(not Path("/proc/self/fd").is_dir(), reason="serve /proc/self/fd (Linux)")


def _file_aperti(cartella: Path) -> int:
    radice = str(cartella)
    aperti = 0
    for voce in os.listdir("/proc/self/fd"):
        try:
            destinazione = os.readlink(f"/proc/self/fd/{voce}")
        except OSError:
            continue
        if destinazione.startswith(radice):
            aperti += 1
    return aperti


def _giro_in_thread_nuovo(percorso: str) -> None:
    """Un giro di un lavoro dello scheduler: thread nuovo, connessione per thread, thread finito."""

    def lavoro() -> None:
        db = StudioDB.get(percorso)
        db.conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()

    filo = threading.Thread(target=lavoro, name="archivio-letture-prova", daemon=True)
    filo.start()
    filo.join()


def test_giri_in_thread_nuovi_non_fanno_crescere_i_file_aperti(tmp_path):
    percorso = str(tmp_path / "studio.db")
    db = StudioDB.get(percorso)
    try:
        db.conn.execute("SELECT 1").fetchone()
        for _ in range(5):
            _giro_in_thread_nuovo(percorso)
        dopo_pochi = _file_aperti(tmp_path)

        for _ in range(60):
            _giro_in_thread_nuovo(percorso)
        dopo_molti = _file_aperti(tmp_path)

        # Restano la connessione del thread principale e quella dell'ultimo giro (si chiude al giro dopo):
        # il numero non dipende da quanti giri sono passati.
        assert dopo_molti <= dopo_pochi, (dopo_pochi, dopo_molti)
        assert dopo_molti <= 8, dopo_molti
        assert len(db._connessioni) <= 2
    finally:
        db.chiudi_tutte()
        StudioDB.invalidate(percorso)
    assert _file_aperti(tmp_path) == 0


def test_chiudi_tutte_chiude_ancora_le_connessioni_dei_thread_vivi(tmp_path):
    percorso = str(tmp_path / "studio.db")
    db = StudioDB.get(percorso)
    pronto, fine = threading.Event(), threading.Event()

    def thread_vivo() -> None:
        db.conn.execute("SELECT 1").fetchone()
        pronto.set()
        fine.wait(10)

    filo = threading.Thread(target=thread_vivo, daemon=True)
    filo.start()
    try:
        assert pronto.wait(10)
        db.conn.execute("SELECT 1").fetchone()
        assert db.chiudi_tutte() == 2
        assert _file_aperti(tmp_path) == 0
    finally:
        fine.set()
        filo.join(10)
        StudioDB.invalidate(percorso)
