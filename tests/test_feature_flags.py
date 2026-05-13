from pathlib import Path

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.feature_flags import (
    FEATURE_FLAG_KEYS,
    app_v2_route_flag_for_path,
    is_feature_enabled,
    resolve_feature_flags,
    set_feature_flag,
)


def _app(tmp_path: Path, *, flags: dict[str, bool] | None = None):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    if flags is not None:
        cfg["FEATURE_FLAGS"] = flags
    return create_app(cfg)


def test_feature_flags_default_off(tmp_path: Path):
    app = _app(tmp_path)

    resolved = resolve_feature_flags(app.config)

    assert set(resolved) == set(FEATURE_FLAG_KEYS)
    assert all(value is False for value in resolved.values())
    assert is_feature_enabled("routes.appV2.docsPanel", app.config) is False
    assert is_feature_enabled("routes.appV2.documents.list", app.config) is False


def test_feature_flag_bulk_config_and_toggle_audit(tmp_path: Path):
    app = _app(tmp_path, flags={"routes.appV2.docsPanel": True})
    events: list[tuple[str, str, str, str]] = []

    assert is_feature_enabled("routes.appV2.docsPanel", app.config) is True
    assert is_feature_enabled("routes.appV2.documents.list", app.config) is True

    updated = set_feature_flag(
        app.config,
        "routes.appV2.docsPanel",
        False,
        actor="pytest",
        audit=lambda *args: events.append(args),
    )

    assert updated["routes.appV2.docsPanel"] is False
    assert updated["routes.appV2.documents.list"] is False
    assert events == [
        (
            "feature_flag_toggled",
            "feature_flag",
            "routes.appV2.docsPanel",
            "pytest ha impostato il flag a spento.",
        )
    ]


def test_feature_flags_api_e_app_v2_route_off_on(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        payload = client.get("/api/v1/ui/feature-flags").get_json()
        blocked = client.get("/app-v2/documenti")

    assert payload["flags"]["routes.appV2.docsPanel"] is False
    assert payload["flags"]["routes.appV2.documents.list"] is False
    assert blocked.status_code == 403
    assert "Funzione non attiva" in blocked.get_data(as_text=True)

    app_enabled = _app(tmp_path / "enabled", flags={"routes.appV2.docsPanel": True})
    _crea_operatore(app_enabled)
    with app_enabled.test_client() as client:
        _login(client)
        response = client.get("/app-v2/documenti")

    assert response.status_code == 200


def test_app_v2_route_flags_cover_dynamic_and_root_paths():
    assert app_v2_route_flag_for_path("") == "routes.appV2.dashboard.home"
    assert app_v2_route_flag_for_path("/app-v2") == "routes.appV2.dashboard.home"
    assert app_v2_route_flag_for_path("/app-v2/documenti") == "routes.appV2.documents.list"
    assert app_v2_route_flag_for_path("fascicoli/ABC/documenti/DEF/editor") == "routes.appV2.documents.editor"
    assert app_v2_route_flag_for_path("/fascicoli") == "routes.appV2.cases.list"
    assert app_v2_route_flag_for_path("/fascicoli/abc") == "routes.appV2.cases.detail"
    assert app_v2_route_flag_for_path("/agenda/nuovo") == "routes.appV2.agenda.create"
    assert app_v2_route_flag_for_path("/impostazioni/calendario") == "routes.appV2.settings.calendarSync"


def test_app_v2_route_default_off_and_canonical_on(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        root = client.get("/app-v2")
        documents = client.get("/app-v2/documenti")

    assert root.status_code == 403
    assert documents.status_code == 403

    enabled = _app(
        tmp_path / "canonical",
        flags={
            "routes.appV2.dashboard.home": True,
            "routes.appV2.documents.list": True,
        },
    )
    _crea_operatore(enabled)
    with enabled.test_client() as client:
        _login(client)
        assert client.get("/app-v2").status_code == 200
        assert client.get("/app-v2/documenti").status_code == 200


def test_feature_flags_do_not_cross_app_configs(tmp_path: Path):
    enabled = _app(tmp_path / "enabled", flags={"routes.appV2.documents.list": True})
    blocked = _app(tmp_path / "blocked")
    _crea_operatore(enabled)
    _crea_operatore(blocked)

    with enabled.test_client() as client:
        _login(client)
        assert client.get("/app-v2/documenti").status_code == 200

    with blocked.test_client() as client:
        _login(client)
        assert client.get("/app-v2/documenti").status_code == 403


def test_mobile_push_actions_reject_when_flag_off(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        response = client.post("/api/push/subscribe", json={"endpoint": "https://push.example/1"})

    assert response.status_code == 403
    assert response.get_json()["code"] == "feature_disabled"
