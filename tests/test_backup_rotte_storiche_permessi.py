"""Rotte storiche dei backup: permessi, ripristino confinato e niente uscita dalla cartella."""

from __future__ import annotations

import zipfile
from pathlib import Path

from pct.auth import RuoloUtente
from pct.backup import GestioneBackup, TipoBackup
from tests.test_topbar_operational_api import _cfg_web, _create_user, _login
from web.app import create_app

JSON = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}


def _app(tmp_path: Path):
    cfg = _cfg_web(tmp_path)
    cfg["BACKUP_DIR"] = str(tmp_path / "backup")
    app = create_app(cfg)
    _create_user(app, "admin2", "Admin12345!")
    _create_user(app, "segreteria", "Segreteria123!", ruolo=RuoloUtente.SEGRETERIA)
    Path(app.config["AGENDA_DB"]).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["AGENDA_DB"]).write_text("[]", encoding="utf-8")
    manager = GestioneBackup(directory_backup=cfg["BACKUP_DIR"], percorsi_dati={"agenda": app.config["AGENDA_DB"]})
    record = manager.esegui_backup(tipo=TipoBackup.COMPLETO)
    return app, record.id


def test_segreteria_non_scarica_ne_elimina_ne_ripristina(tmp_path):
    app, id_bk = _app(tmp_path)
    esterna = tmp_path / "fuori"
    with app.test_client() as client:
        _login(client, "segreteria", "Segreteria123!")
        assert client.get(f"/backup/{id_bk}/scarica", headers=JSON).status_code == 403
        assert client.post(f"/backup/{id_bk}/elimina", headers=JSON).status_code == 403
        assert client.post(f"/backup/{id_bk}/verifica", headers=JSON).status_code == 403
        assert client.post("/backup/esegui", headers=JSON).status_code == 403
        assert client.post(f"/backup/{id_bk}/ripristina", data={"destinazione": str(esterna)}, headers=JSON).status_code == 403
        assert client.get("/api/backup/statistiche").status_code == 403
    assert not esterna.exists()
    assert (tmp_path / "backup").exists() and any((tmp_path / "backup").glob("*.zip"))


def test_ripristino_storico_resta_nella_cartella_dei_ripristini(tmp_path):
    app, id_bk = _app(tmp_path)
    esterna = tmp_path / "fuori"
    with app.test_client() as client:
        _login(client, "admin2", "Admin12345!")
        risposta = client.post(f"/backup/{id_bk}/ripristina", data={"destinazione": str(esterna)})
        assert risposta.status_code == 302
        scarico = client.get(f"/backup/{id_bk}/scarica")
        assert scarico.status_code == 200
    assert not esterna.exists()
    assert (tmp_path / "ripristini" / "fuori").is_dir()


def test_ripristino_ignora_voci_dello_zip_che_escono_dalla_cartella(tmp_path):
    dati = tmp_path / "agenda.json"
    dati.write_text("[]", encoding="utf-8")
    manager = GestioneBackup(directory_backup=str(tmp_path / "backup"), percorsi_dati={"agenda": str(dati)})
    record = manager.esegui_backup(tipo=TipoBackup.COMPLETO)
    percorso = Path(record.percorso_file)
    with zipfile.ZipFile(percorso, "a") as zf:
        zf.writestr("../evaso.txt", "non deve uscire")
    from pct.backup import _sha256_file

    record.hash_file = _sha256_file(percorso)
    manager._salva_registro()
    esito = manager.ripristina(record.id, str(tmp_path / "ripristini" / "prova"))
    assert not (tmp_path / "ripristini" / "evaso.txt").exists()
    assert any("fuori dalla cartella" in e["errore"] for e in esito["errori"])
