from __future__ import annotations

from pathlib import Path

from tests.test_applicazioni import _crea_operatore, _login
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.app_v2_routing import (
    LEGACY_TO_APP_V2_TARGETS,
    UNSAFE_QUERY_PARAMS,
    build_app_v2_path,
    get_legacy_fallback_path,
    is_safe_internal_path,
    sanitize_query_params,
    should_redirect_to_app_v2,
)
from web.services.feature_flags import app_v2_route_flag_for_path


def _app(tmp_path: Path, *, flags: dict[str, bool] | None = None):
    _write_studio_config(tmp_path / "config" / "studio.json")
    cfg = _cfg_web(tmp_path)
    if flags is not None:
        cfg["FEATURE_FLAGS"] = flags
    return create_app(cfg)


def test_app_v2_safe_path_rejects_open_redirect_targets():
    for value in (
        "",
        "https://evil.example/app-v2",
        "//evil.example/app-v2",
        "/\\evil",
        "/app-v2/documenti#fragment",
        "/app-v2/%2e%2e/admin",
        "/app-v2/\nadmin",
    ):
        assert is_safe_internal_path(value) is False

    assert is_safe_internal_path("/app-v2/documenti?tab=template") is True


def test_app_v2_redirect_path_preserves_allowed_query_and_drops_sensitive_params():
    target = build_app_v2_path(
        "/fascicoli",
        {
            "q": "Rossi",
            "page": "2",
            "next": "https://evil.example",
            "redirect": "//evil.example",
            "tenant_id": "tenant-b",
            "debug": "1",
            "token": "secret",
        },
    )

    assert target == "/app-v2/fascicoli?q=Rossi&page=2"
    assert "evil.example" not in target
    assert "tenant-b" not in target
    assert all(key not in target for key in UNSAFE_QUERY_PARAMS)


def test_app_v2_redirect_path_preserves_dynamic_ids_without_unsafe_query():
    target = build_app_v2_path(
        "/fascicoli/ABC123/documenti/Doc-456/editor",
        {"tab": "testo", "return_url": "//evil.example"},
    )

    assert target == "/app-v2/fascicoli/ABC123/documenti/Doc-456/editor?tab=testo"
    assert app_v2_route_flag_for_path(target) == "routes.appV2.documents.editor"


def test_app_v2_redirect_decision_is_enabled_by_default_and_still_flag_gated(tmp_path: Path):
    app = _app(tmp_path)
    on = should_redirect_to_app_v2("/documenti", {"tab": "template"}, config=app.config)

    assert on.allowed is True
    assert on.target == "/app-v2/documenti?tab=template"
    assert on.flag_key == "routes.appV2.documents.list"

    disabled = _app(tmp_path / "disabled", flags={"routes.appV2.documents.list": False})
    off = should_redirect_to_app_v2("/documenti", {"tab": "template"}, config=disabled.config)

    assert off.allowed is False
    assert off.target == "/app-v2/documenti?tab=template"
    assert off.flag_key == "routes.appV2.documents.list"
    assert off.reason == "feature flag spento"


def test_app_v2_redirect_decision_unknown_routes_fail_closed(tmp_path: Path):
    app = _app(tmp_path)
    decision = should_redirect_to_app_v2("/portale/pubblico", {"q": "rossi"}, config=app.config)

    assert decision.allowed is False
    assert decision.target == ""
    assert "mapping" in decision.reason


def test_app_v2_mapping_targets_are_internal_and_have_known_flags():
    missing: list[str] = []
    unsafe: list[str] = []
    for legacy_path, target in LEGACY_TO_APP_V2_TARGETS.items():
        if not is_safe_internal_path(target):
            unsafe.append(f"{legacy_path} -> {target}")
            continue
        if not app_v2_route_flag_for_path(target):
            missing.append(f"{legacy_path} -> {target}")

    assert unsafe == []
    assert missing == []


def test_app_v2_fallback_path_drops_unsafe_query_params():
    fallback = get_legacy_fallback_path(
        "/fascicoli",
        {"q": "Rossi", "next": "https://evil.example", "tenant_id": "tenant-b"},
    )

    assert fallback == "/fascicoli?q=Rossi"
    assert "evil.example" not in fallback
    assert "tenant-b" not in fallback


def test_app_v2_fallback_path_preserves_legacy_case_sensitive_paths():
    fallback = get_legacy_fallback_path("/polisWeb", {"q": "Palmi", "redirect": "//evil.example"})

    assert fallback == "/polisWeb?q=Palmi"
    assert "evil.example" not in fallback


def test_app_v2_routes_do_not_capture_api_or_static_paths(tmp_path: Path):
    app = _app(tmp_path)
    _crea_operatore(app)

    with app.test_client() as client:
        _login(client)
        api = client.get("/api/v1/ui/feature-flags")
        static_missing = client.get("/static/non-esiste-app-v2.js")

    assert api.status_code == 200
    assert api.is_json
    assert static_missing.status_code == 404
    assert "IUSENTRA - React Shell" not in static_missing.get_data(as_text=True)


def test_frontend_router_strips_query_before_matching_app_routes():
    source = Path("frontend/src/app/router.tsx").read_text(encoding="utf-8")

    assert "stripRoutingDecorators" in source
    assert "LEGACY_ROUTE_TARGETS[clean] || clean" in source
    assert "pathname.split(/[?#]/)[0]" in source
