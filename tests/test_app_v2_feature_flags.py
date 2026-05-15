from __future__ import annotations

import re
from pathlib import Path

from web.services.feature_flags import (
    APP_V2_DEFAULT_OFF_FLAGS,
    APP_V2_DEFAULT_ON_FLAGS,
    FEATURE_FLAG_DEFINITIONS,
    FEATURE_FLAG_KEYS,
    FEATURE_FLAG_CANONICAL_BY_ALIAS,
    APP_V2_ROUTE_FLAGS,
    app_v2_route_flag_for_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


LEGACY_ALIASES = {
    "routes.appV2.docsPanel",
    "routes.appV2.commsDeposits",
    "routes.appV2.uploadClassification",
    "routes.appV2.deadlines",
    "routes.appV2.agenda",
    "routes.appV2.caseFiles",
    "notifications.mobilePush",
}


def _frontend(path: str) -> str:
    return (REPO_ROOT / path).read_text(encoding="utf-8")


def test_app_v2_canonical_flags_have_explicit_rollout_defaults_and_page_scope():
    canonical = [
        definition.key
        for definition in FEATURE_FLAG_DEFINITIONS
        if definition.key.startswith("routes.appV2.") and definition.key not in FEATURE_FLAG_CANONICAL_BY_ALIAS
    ]
    defaults = {definition.key: definition.default for definition in FEATURE_FLAG_DEFINITIONS}
    route_default_on = {key for key in APP_V2_DEFAULT_ON_FLAGS if key.startswith("routes.appV2.")}
    route_default_off = {key for key in APP_V2_DEFAULT_OFF_FLAGS if key.startswith("routes.appV2.")}

    assert len(canonical) >= 45
    assert set(canonical) == route_default_on | route_default_off
    assert all(defaults[key] is True for key in APP_V2_DEFAULT_ON_FLAGS)
    assert all(defaults[key] is False for key in APP_V2_DEFAULT_OFF_FLAGS)
    assert all(defaults[key] is False for key in LEGACY_ALIASES)
    assert all(re.fullmatch(r"routes\.appV2\.[A-Za-z0-9]+\.[A-Za-z0-9]+", key) for key in canonical)
    assert "routes.appV2.documents.list" in canonical
    assert "routes.appV2.settings.calendarSync" in canonical
    assert "routes.appV2.notifications.mobilePush" in canonical
    assert "routes.appV2.telematico.center" in APP_V2_DEFAULT_OFF_FLAGS


def test_app_v2_route_rules_only_reference_known_flags():
    for route, flag in APP_V2_ROUTE_FLAGS:
        assert route.startswith("/")
        assert flag in FEATURE_FLAG_KEYS
        sample = route
        if route.endswith("/") and route != "/":
            sample = route + "esempio"
        sample = sample.replace("{id}", "abc").replace("{id_doc}", "def").replace("*", "abc")
        assert app_v2_route_flag_for_path(sample) == flag


def test_frontend_app_routes_all_have_feature_flags():
    routes_text = _frontend("frontend/src/app/routes.ts")
    route_entries = re.findall(r"\{[^{}\n]*path:\s*'(/app[^']*)'[^{}\n]*\}", routes_text)
    assert route_entries

    missing = [
        route
        for route in route_entries
        if f"path: '{route}'" in routes_text
        and not re.search(rf"path:\s*'{re.escape(route)}'[^{{}}\n]*featureFlag:\s*'routes\.appV2\.", routes_text)
    ]
    assert missing == []


def test_frontend_blocks_flag_off_routes_before_page_fetch():
    app_text = _frontend("frontend/src/App.tsx")
    flags_text = _frontend("frontend/src/lib/featureFlags.ts")

    assert "appV2FeatureFlagForPath(routeKey)" in app_text
    assert "appV2FlagProtectedPath" in app_text
    assert "appV2FlagDenied" in app_text
    assert "effectiveStandalonePage" in app_text
    assert "FeatureUnavailablePage" in app_text
    assert "getDashboard()" in app_text
    assert "if(effectiveStandalonePage)" in app_text
    assert "appV2RouteFlagRules" in flags_text
    assert "'routes.appV2.documents.list'" in flags_text
    assert "'routes.appV2.notifications.mobilePush'" in flags_text
