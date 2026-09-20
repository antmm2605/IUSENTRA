"""Misura e recupero dello spazio bloccato dentro gli `studio.db`.

Stessa convenzione delle altre manutenzioni: una rotta che legge e non tocca
niente, una che applica. Qui il punto delicato e' che il VACUUM blocca il
database, quindi la logica deve rifiutarsi da sola quando non conviene o
quando il disco non ha il margine richiesto.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pct.manutenzione_database as md
from pct.manutenzione_database import _etichetta, analizza, compatta, esamina_tutti
from pct.tenant import GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _archivio(data_root: Path, *, righe: int = 400, cancella: bool = True) -> Path:
    """Un archivio con pagine libere vere: si riempie e poi si svuota."""
    db = data_root / "tenants" / "studio-prova" / "studio.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db)) as conn:
        conn.execute("CREATE TABLE zavorra (id INTEGER PRIMARY KEY, blob TEXT)")
        conn.executemany(
            "INSERT INTO zavorra VALUES (?, ?)",
            [(i, "x" * 4000) for i in range(righe)],
        )
        conn.commit()
        if cancella:
            conn.execute("DELETE FROM zavorra WHERE id > 20")
            conn.commit()
    return db


# ------------------------------------------------------------------ logica


def test_l_analisi_vede_le_pagine_libere_e_non_tocca_niente(tmp_path: Path):
    db = _archivio(tmp_path / "data")
    prima = db.stat().st_size

    esito = analizza(db)

    assert esito.pagine_libere > 0
    assert esito.byte_liberabili > 0
    assert esito.percento_libero > 0
    assert esito.compattato is False
    assert db.stat().st_size == prima


def test_il_vacuum_restituisce_lo_spazio(tmp_path: Path):
    db = _archivio(tmp_path / "data")
    prima = db.stat().st_size

    esito = compatta(db)

    assert esito.compattato is True
    assert not esito.saltato
    assert db.stat().st_size < prima
    assert esito.byte_dopo < esito.byte_su_disco


def test_un_archivio_gia_compatto_viene_saltato_non_compattato(tmp_path: Path):
    """Senza pagine libere il VACUUM e' solo un blocco in scrittura gratis."""

    db = _archivio(tmp_path / "data", righe=50, cancella=False)

    esito = compatta(db)

    assert esito.compattato is False
    assert "VACUUM costa piu'" in esito.saltato


def test_il_disco_stretto_ferma_il_vacuum(tmp_path: Path, monkeypatch):
    """Meglio non fare niente che riempire il disco a meta' di un VACUUM."""

    db = _archivio(tmp_path / "data")

    class DiscoQuasiPieno:
        free = 1024

    monkeypatch.setattr(md.shutil, "disk_usage", lambda _p: DiscoQuasiPieno)
    prima = db.stat().st_size

    esito = compatta(db)

    assert esito.compattato is False
    assert "liberi sul disco" in esito.saltato
    assert db.stat().st_size == prima


def test_il_peso_conta_anche_il_wal(tmp_path: Path):
    db = _archivio(tmp_path / "data")
    (db.parent / f"{db.name}-wal").write_bytes(b"0" * 5000)

    esito = analizza(db)

    assert esito.byte_su_disco >= db.stat().st_size + 5000


def test_le_misure_restano_leggibili_anche_sui_file_piccoli():
    """«0.0 GiB» non dice niente a chi legge il pannello."""

    assert _etichetta(0) == "0 byte"
    assert _etichetta(5000) == "4.88 KB"
    assert _etichetta(1646592) == "1.57 MB"
    assert _etichetta(13 * 1073741824) == "13.0 GiB"


def test_un_archivio_illeggibile_viene_dichiarato(tmp_path: Path):
    finto = tmp_path / "data" / "tenants" / "rotto" / "studio.db"
    finto.parent.mkdir(parents=True, exist_ok=True)
    finto.write_text("non sono un database", encoding="utf-8")

    esito = analizza(finto)

    assert esito.errore
    assert esito.byte_liberabili == 0


def test_senza_archivi_lo_dice(tmp_path: Path):
    esito = esamina_tutti(tmp_path / "vuoto")

    assert esito["ok"] is False
    assert "Nessuno studio.db" in esito["messaggio"]


def test_il_riepilogo_distingue_analisi_e_compattazione(tmp_path: Path):
    _archivio(tmp_path / "data")

    analisi = esamina_tutti(tmp_path / "data", compattare=False)
    assert analisi["compattazione_eseguita"] is False
    assert analisi["gb_recuperati"] == 0.0
    assert "Nessuna modifica" in analisi["messaggio"]

    applicata = esamina_tutti(tmp_path / "data", compattare=True)
    assert applicata["compattazione_eseguita"] is True
    assert applicata["studi"][0]["compattato"] is True


# ------------------------------------------------------------------ rotte


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    cfg["PCT_DATA_ROOT"] = str(tmp_path / "data")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    GestioneTenant(cfg["TENANTS_REGISTRY"]).crea(
        "Studio Prova", "studio-prova", db_config={"mode": "SQLITE"}
    )
    return create_app(cfg)


def _entra(client):
    client.get("/login")
    client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)


def test_le_rotte_sono_chiuse_senza_superadmin(tmp_path: Path):
    app = _app(tmp_path)
    with app.test_client() as client:
        r = client.post("/admin/server-manutenzione/applica-compattazione-database")

    assert r.status_code in (302, 401, 403)


def test_la_rotta_di_analisi_risponde_e_non_tocca_l_archivio(tmp_path: Path):
    db = _archivio(tmp_path / "data")
    app = _app(tmp_path)
    prima = db.stat().st_size
    with app.test_client() as client:
        _entra(client)
        r = client.post("/admin/server-manutenzione/analizza-spazio-database")

    assert r.status_code == 200
    assert db.stat().st_size == prima


def test_la_rotta_che_applica_compatta(tmp_path: Path):
    db = _archivio(tmp_path / "data")
    app = _app(tmp_path)
    prima = db.stat().st_size
    with app.test_client() as client:
        _entra(client)
        r = client.post("/admin/server-manutenzione/applica-compattazione-database")

    assert r.status_code == 200
    assert db.stat().st_size < prima
