from pathlib import Path
from web.services.quickorganizer_progress import import_lock
from tests.test_applicazioni import _cfg_web, _crea_operatore, _login
from tests.test_quickorganizer_import import _write_package
from web.app import create_app
from web.services.quickorganizer_import import staging_root_for_anchor


def test_authenticated_import_selection_progress_original_and_reimport(tmp_path: Path):
    app = create_app({**_cfg_web(tmp_path / "studio"), "STORAGE_MODE_DEFAULT": "SQLITE"})
    _crea_operatore(app)
    source = _write_package(tmp_path / "package.zip")
    with app.test_client() as client:
        _login(client)
        with source.open("rb") as stream:
            response = client.post("/api/v1/ui/import/quickorganizer/anteprima", data={"pacchetto": (stream, "package.zip")})
        assert response.status_code == 200
        preview = response.get_json()
        import_id = preview["importId"]
        prefix = f"/api/v1/ui/import/quickorganizer/{import_id}"
        refreshed = client.get(prefix + "/anteprima")
        assert refreshed.status_code == 200
        assert refreshed.get_json()["analysis"]["inventory"]
        full_source = client.get(prefix + "/pacchetto")
        assert full_source.status_code == 200
        assert full_source.data == source.read_bytes()
        original = client.get(prefix + "/originale/0")
        assert original.status_code == 200
        assert original.data
        assert original.headers["Cache-Control"] == "private, no-store"
        payload = {"importId": import_id, "selection": {"matterIds": ["101"], "documents": False, "emails": True, "appointments": False, "unassigned": False}}
        root = staging_root_for_anchor(app.config["FASCICOLI_DB"])
        with import_lock(root / ".import-in-progress.lock"):
            busy = client.post("/api/v1/ui/import/quickorganizer/esegui", json=payload)
        assert busy.status_code == 409
        invalid_source = client.post("/api/v1/ui/import/quickorganizer/esegui", json={**payload, "sourceSha256": "0" * 64})
        assert invalid_source.status_code == 400
        imported = client.post("/api/v1/ui/import/quickorganizer/esegui", json=payload)
        assert imported.status_code == 200, imported.get_json()
        assert imported.get_json()["summary"]["documentsImported"] == 0
        assert imported.get_json()["summary"]["emailsImported"] == 1
        state = client.get(prefix + "/stato").get_json()
        assert state["status"] == "complete"
        repeated = client.post("/api/v1/ui/import/quickorganizer/esegui", json=payload)
        assert repeated.status_code == 200
        assert repeated.get_json()["summary"]["emailsImported"] == 0
    with app.test_client() as anonymous:
        response = anonymous.get(prefix + "/originale/0")
        assert response.status_code in (302, 401, 403)

    other_app = create_app({**_cfg_web(tmp_path / "other-studio"), "STORAGE_MODE_DEFAULT": "SQLITE"})
    _crea_operatore(other_app)
    with other_app.test_client() as other:
        _login(other)
        for endpoint in ("/originale/0", "/pacchetto", "/anteprima"):
            denied = other.get(prefix + endpoint)
            assert denied.status_code == 400
        other_state = other.get(prefix + "/stato").get_json()
        assert other_state["status"] == "idle"
