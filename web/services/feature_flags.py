"""Feature flag governati per la migrazione React/App V2.

I flag qui definiti sono default-off e servono a introdurre nuove capability
senza spegnere le superfici React gia' promosse come operative.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Mapping

from flask import current_app, g, jsonify, request


@dataclass(frozen=True, slots=True)
class FeatureFlagDefinition:
    key: str
    env_var: str
    description: str
    public: bool = True
    default: bool = False


FEATURE_FLAG_DEFINITIONS: tuple[FeatureFlagDefinition, ...] = (
    FeatureFlagDefinition(
        "routes.appV2.docsPanel",
        "IUSENTRA_FF_ROUTES_APPV2_DOCS_PANEL",
        "Pannello documenti fascicolo nella shell App V2 sperimentale.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.commsDeposits",
        "IUSENTRA_FF_ROUTES_APPV2_COMMS_DEPOSITS",
        "Workspace comunicazioni e depositi nella shell App V2 sperimentale.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.uploadClassification",
        "IUSENTRA_FF_ROUTES_APPV2_UPLOAD_CLASSIFICATION",
        "Upload multiplo e classificazione documenti nella shell App V2.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.deadlines",
        "IUSENTRA_FF_ROUTES_APPV2_DEADLINES",
        "Scadenze e termini nella shell App V2 sperimentale.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.agenda",
        "IUSENTRA_FF_ROUTES_APPV2_AGENDA",
        "Agenda nella shell App V2 sperimentale.",
    ),
    FeatureFlagDefinition(
        "routes.appV2.caseFiles",
        "IUSENTRA_FF_ROUTES_APPV2_CASE_FILES",
        "Fascicoli e pratiche nella shell App V2 sperimentale.",
    ),
    FeatureFlagDefinition(
        "notifications.mobilePush",
        "IUSENTRA_FF_NOTIFICATIONS_MOBILE_PUSH",
        "Notifiche Web Push su dispositivo mobile/tablet.",
    ),
)

FEATURE_FLAG_KEYS = frozenset(definition.key for definition in FEATURE_FLAG_DEFINITIONS)
FEATURE_FLAGS_BY_KEY = {definition.key: definition for definition in FEATURE_FLAG_DEFINITIONS}
FEATURE_FLAGS_BY_ENV = {definition.env_var: definition for definition in FEATURE_FLAG_DEFINITIONS}

APP_V2_ROUTE_FLAGS: tuple[tuple[str, str], ...] = (
    ("documenti", "routes.appV2.docsPanel"),
    ("comunicazioni", "routes.appV2.commsDeposits"),
    ("agenda", "routes.appV2.agenda"),
    ("scadenziario", "routes.appV2.deadlines"),
    ("fascicoli", "routes.appV2.caseFiles"),
)

TRUE_VALUES = {"1", "true", "yes", "y", "on", "si", "s"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "none", "null", ""}


def _config_key(flag_key: str) -> str:
    return "FEATURE_FLAG_" + re.sub(r"[^A-Z0-9]+", "_", flag_key.upper()).strip("_")


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    text = str(value or "").strip().lower()
    if text in TRUE_VALUES:
        return True
    if text in FALSE_VALUES:
        return False
    return default


def _mapping_from_raw(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return {str(key): raw for key, raw in value.items()}
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, Mapping):
            return {str(key): raw for key, raw in parsed.items()}
    return {}


def resolve_feature_flags(config: Mapping[str, Any] | None = None) -> dict[str, bool]:
    """Risolve tutti i flag noti, mantenendo default-off in assenza di opt-in."""

    source = config if config is not None else getattr(current_app, "config", {})
    resolved = {definition.key: bool(definition.default) for definition in FEATURE_FLAG_DEFINITIONS}
    bulk_sources = (
        _mapping_from_raw(source.get("FEATURE_FLAGS") if source else None),
        _mapping_from_raw(os.getenv("IUSENTRA_FEATURE_FLAGS", "")),
    )
    for raw_flags in bulk_sources:
        for raw_key, raw_value in raw_flags.items():
            definition = FEATURE_FLAGS_BY_KEY.get(raw_key) or FEATURE_FLAGS_BY_ENV.get(raw_key)
            if definition:
                resolved[definition.key] = _coerce_bool(raw_value, default=definition.default)

    for definition in FEATURE_FLAG_DEFINITIONS:
        config_key = _config_key(definition.key)
        for raw_value in (
            source.get(definition.env_var) if source else None,
            source.get(config_key) if source else None,
            os.getenv(definition.env_var),
        ):
            if raw_value is not None:
                resolved[definition.key] = _coerce_bool(raw_value, default=definition.default)
    return resolved


def feature_flags_payload(config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    flags = resolve_feature_flags(config)
    return {
        "ok": True,
        "flags": flags,
        "defaults": {definition.key: bool(definition.default) for definition in FEATURE_FLAG_DEFINITIONS},
    }


def is_feature_enabled(flag_key: str, config: Mapping[str, Any] | None = None) -> bool:
    if flag_key not in FEATURE_FLAG_KEYS:
        return False
    return bool(resolve_feature_flags(config).get(flag_key, False))


def app_v2_route_flag_for_path(path: str) -> str:
    clean = str(path or "").strip("/")
    first = clean.split("/", 1)[0].lower()
    for segment, flag_key in APP_V2_ROUTE_FLAGS:
        if first == segment:
            return flag_key
    return ""


def set_feature_flag(
    config: dict[str, Any],
    flag_key: str,
    enabled: bool,
    *,
    actor: str = "",
    audit: Callable[[str, str, str, str], Any] | None = None,
) -> dict[str, bool]:
    """Aggiorna un flag in memoria e registra l'evento se il chiamante fornisce audit."""

    if flag_key not in FEATURE_FLAG_KEYS:
        raise ValueError(f"Feature flag non riconosciuto: {flag_key}")
    current = dict(resolve_feature_flags(config))
    current[flag_key] = bool(enabled)
    config["FEATURE_FLAGS"] = current
    if callable(audit):
        details = f"{actor or 'sistema'} ha impostato il flag a {'attivo' if enabled else 'spento'}."
        audit("feature_flag_toggled", "feature_flag", flag_key, details)
    return current


def _audit_denial(flag_key: str) -> None:
    details = f"Accesso bloccato per flag spento: {flag_key}"
    try:
        current_app.logger.warning(
            "policy_denied feature_flag=%s path=%s user=%s",
            flag_key,
            request.path,
            getattr(g.get("utente_corrente"), "username", ""),
        )
        audit = (current_app.extensions.get("core_runtime", {}) or {}).get("audit")
        if callable(audit):
            audit("policy_denied", "feature_flag", flag_key, details)
    except Exception:
        current_app.logger.debug("Audit denial feature flag non registrato.", exc_info=True)


def feature_disabled_response(flag_key: str, *, status: int = 403):
    _audit_denial(flag_key)
    return jsonify(
        {
            "ok": False,
            "code": "feature_disabled",
            "message": "Funzione non attiva per questo studio.",
        }
    ), status


def require_feature_flag(flag_key: str):
    """Decoratore Flask JSON per bloccare funzioni sperimentali flag-off."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            if is_feature_enabled(flag_key):
                return func(*args, **kwargs)
            return feature_disabled_response(flag_key)

        return wrapper

    return decorator
