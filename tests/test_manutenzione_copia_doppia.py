"""Le due manutenzioni sulla copia doppia, dalla console del superadmin.

Si innestano sulla superficie «Server e manutenzione» che esisteva gia', con
la sua convenzione: una rotta che analizza e non tocca niente, una che
applica. Sono rotte distinte e con un nome proprio — non c'e' nessun comando
che arrivi dalla richiesta.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from pct.manutenzione_dati_json import conta_eccesso, esamina_tutti, sgrassa
from pct.tenant import GestioneTenant
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _archivio(data_root: Path, quanti: int = 3) -> Path:
    db = data_root / "tenants" / "studio-prova" / "studio.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db)) as conn:
        conn.execute("CREATE TABLE fascicoli (id TEXT PRIMARY KEY, dati_json TEXT)")
        for i in range(quanti):
            payload = {
                "id": f"F{i}",
                "titolo": f"Pratica {i}",
                "documenti": [{"id": f"D{i}", "nome": "atto.pdf", "note": "x" * 500}],
                "attivita": [],
                "depositi_pct": [],
            }
            conn.execute("INSERT INTO fascicoli VALUES (?,?)", (f"F{i}", json.dumps(payload)))
        conn.commit()
    return db


def _payload(db: Path) -> dict:
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        return json.loads(conn.execute("SELECT dati_json FROM fascicoli LIMIT 1").fetchone()[0])


# ------------------------------------------------------------------ logica


def test_l_analisi_non_modifica_niente(tmp_path: Path):
    db = _archivio(tmp_path / "data")

    esito = conta_eccesso(db)

    assert esito.fascicoli == 3
    assert esito.da_sgrassare == 3
    assert esito.byte_in_eccesso > 0
    assert esito.riscritte == 0
    assert "documenti" in _payload(db)  # l'archivio e' intatto


def test_la_riscrittura_toglie_solo_la_copia(tmp_path: Path):
    db = _archivio(tmp_path / "data")

    esito = sgrassa(db)

    assert esito.riscritte == 3
    payload = _payload(db)
    assert "documenti" not in payload
    assert "attivita" not in payload
    assert payload["titolo"] == "Pratica 0"  # il resto resta


def test_rieseguire_non_fa_danni(tmp_path: Path):
    db = _archivio(tmp_path / "data")
    sgrassa(db)

    assert sgrassa(db).riscritte == 0


def test_un_archivio_illeggibile_viene_dichiarato(tmp_path: Path):
    """Un guasto non deve passare per «non c'era niente da fare»."""

    finto = tmp_path / "data" / "tenants" / "rotto" / "studio.db"
    finto.parent.mkdir(parents=True, exist_ok=True)
    finto.write_text("non sono un database", encoding="utf-8")

    esito = conta_eccesso(finto)

    assert esito.errore
    assert esito.da_sgrassare == 0


def test_senza_archivi_lo_dice(tmp_path: Path):
    esito = esamina_tutti(tmp_path / "vuoto")

    assert esito["ok"] is False
    assert "Nessuno studio.db" in esito["messaggio"]


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
        r = client.post("/admin/server-manutenzione/applica-copia-doppia-fascicoli")

    assert r.status_code in (302, 401, 403)


def test_la_rotta_di_analisi_risponde_e_non_tocca_l_archivio(tmp_path: Path):
    db = _archivio(tmp_path / "data")
    app = _app(tmp_path)
    with app.test_client() as client:
        _entra(client)
        r = client.post("/admin/server-manutenzione/analizza-copia-doppia-fascicoli")

    assert r.status_code == 200
    assert "documenti" in _payload(db)


def test_la_rotta_che_applica_riscrive(tmp_path: Path):
    db = _archivio(tmp_path / "data")
    app = _app(tmp_path)
    with app.test_client() as client:
        _entra(client)
        r = client.post("/admin/server-manutenzione/applica-copia-doppia-fascicoli")

    assert r.status_code == 200
    assert "documenti" not in _payload(db)
