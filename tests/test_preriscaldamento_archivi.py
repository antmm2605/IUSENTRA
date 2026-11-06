"""Preriscaldamento degli archivi normativi: spento di default, legge l'intero file e si ferma all'arresto."""

from __future__ import annotations

import threading

from pct import preriscaldamento_archivi as pa


def test_spento_senza_variabile(monkeypatch, tmp_path):
    archivio = tmp_path / "normattiva.sqlite"
    archivio.write_bytes(b"x" * 10)
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(archivio))
    monkeypatch.delenv("IUSENTRA_PRERISCALDA_ARCHIVI", raising=False)
    assert pa.avvia_in_sfondo() is None


def test_legge_tutto_il_file_e_rispetta_l_arresto(monkeypatch, tmp_path):
    archivio = tmp_path / "normattiva.sqlite"
    archivio.write_bytes(b"x" * (3 * 1024 * 1024 + 7))
    monkeypatch.setattr(pa, "_BLOCCO", 1024 * 1024)
    monkeypatch.setattr(pa, "_PAUSA_SECONDI", 0)
    assert pa.preriscalda(archivio) == 3 * 1024 * 1024 + 7
    fermo = threading.Event()
    fermo.set()
    assert pa.preriscalda(archivio, fermo=fermo) == 0


def test_archivi_esistenti_senza_doppioni(monkeypatch, tmp_path):
    archivio = tmp_path / "a.sqlite"
    archivio.write_bytes(b"x")
    monkeypatch.setenv("PCT_NORMATTIVA_DB", str(archivio))
    monkeypatch.setenv("PCT_CODICI_LEGGI_DB", str(archivio))
    assert pa.archivi_da_preriscaldare() == [archivio]
