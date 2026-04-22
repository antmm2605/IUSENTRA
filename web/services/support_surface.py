"""Superficie admin per la console di assistenza remota."""

from __future__ import annotations

from typing import Any

from flask import current_app, request, url_for
from pct.config_studio import GestioneConfigStudio

from web.services.support_runtime import support_repository, support_session_payload


def _is_secure_runtime() -> bool:
    host = str(request.host or "").split(":")[0].strip().lower()
    if host in {"localhost", "127.0.0.1"}:
        return True
    return bool(request.is_secure or current_app.config.get("PREFERRED_URL_SCHEME") == "https")


def _turn_ready() -> bool:
    return bool(
        (current_app.config.get("SUPPORT_TURN_URLS") or [])
        and str(current_app.config.get("SUPPORT_TURN_SHARED_SECRET") or "").strip()
    )


def _platform_support_config_manager() -> GestioneConfigStudio:
    return GestioneConfigStudio(
        config_path=str(
            current_app.config.get("STUDIO_CONFIG")
            or current_app.config.get("CONFIG_STUDIO_DB")
            or "./config/studio.json"
        )
    )


def _lines_to_list(value: str) -> list[str]:
    normalized = str(value or "").replace(";", "\n").replace(",", "\n")
    return [item.strip() for item in normalized.splitlines() if item.strip()]


def current_support_configuration() -> dict[str, Any]:
    cfg = _platform_support_config_manager().config
    support_cfg = getattr(cfg, "support_remote", None)
    stun_urls = list(getattr(support_cfg, "stun_urls", []) or current_app.config.get("SUPPORT_STUN_URLS", []) or [])
    turn_urls = list(getattr(support_cfg, "turn_urls", []) or current_app.config.get("SUPPORT_TURN_URLS", []) or [])
    turn_shared_secret = str(
        getattr(support_cfg, "turn_shared_secret", "")
        or current_app.config.get("SUPPORT_TURN_SHARED_SECRET", "")
        or ""
    ).strip()
    return {
        "stun_urls": stun_urls,
        "turn_urls": turn_urls,
        "turn_shared_secret": turn_shared_secret,
        "turn_ttl_seconds": int(
            getattr(support_cfg, "turn_ttl_seconds", current_app.config.get("SUPPORT_TURN_TTL_SECONDS", 3600))
            or 3600
        ),
        "ws_token_max_age": int(
            getattr(support_cfg, "ws_token_max_age", current_app.config.get("SUPPORT_WS_TOKEN_MAX_AGE", 43200))
            or 43200
        ),
        "advanced_url_template": str(
            getattr(support_cfg, "advanced_url_template", current_app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE", ""))
            or ""
        ).strip(),
        "config_path": str(_platform_support_config_manager()._path),
    }


def save_support_configuration(form: dict[str, Any]) -> dict[str, Any]:
    manager = _platform_support_config_manager()
    current_config = current_support_configuration()
    provided_secret = str(form.get("turn_shared_secret") or "").strip()
    support_payload = {
        "stun_urls": _lines_to_list(str(form.get("stun_urls") or "")),
        "turn_urls": _lines_to_list(str(form.get("turn_urls") or "")),
        "turn_shared_secret": provided_secret or current_config["turn_shared_secret"],
        "turn_ttl_seconds": max(60, int(str(form.get("turn_ttl_seconds") or "3600").strip() or "3600")),
        "ws_token_max_age": max(300, int(str(form.get("ws_token_max_age") or "43200").strip() or "43200")),
        "advanced_url_template": str(form.get("advanced_url_template") or "").strip(),
    }
    manager.aggiorna_sezione("support_remote", support_payload)
    current_app.config["SUPPORT_STUN_URLS"] = list(support_payload["stun_urls"])
    current_app.config["SUPPORT_TURN_URLS"] = list(support_payload["turn_urls"])
    current_app.config["SUPPORT_TURN_SHARED_SECRET"] = support_payload["turn_shared_secret"]
    current_app.config["SUPPORT_TURN_TTL_SECONDS"] = int(support_payload["turn_ttl_seconds"])
    current_app.config["SUPPORT_WS_TOKEN_MAX_AGE"] = int(support_payload["ws_token_max_age"])
    current_app.config["SUPPORT_ADVANCED_URL_TEMPLATE"] = support_payload["advanced_url_template"]
    return current_support_configuration()


def build_support_console_payload(
    *,
    selected_public_id: str = "",
    status_filter: str = "",
    query: str = "",
) -> dict[str, Any]:
    repo = support_repository()
    rows = repo.list_sessions(
        limit=80,
        status=status_filter,
        search=query,
    )
    selected = None
    if selected_public_id:
        selected = repo.get_session_by_public_id(selected_public_id)
    if selected is None and rows:
        selected = rows[0]

    sessions = [support_session_payload(row) for row in rows]
    selected_payload = support_session_payload(selected) if selected else None
    events = repo.list_events(selected_payload["public_id"]) if selected_payload else []
    warnings: list[str] = []
    if not _is_secure_runtime():
        warnings.append(
            "La condivisione schermo del cliente richiede HTTPS o localhost: da remoto il link cliente deve passare da contesto sicuro."
        )
    if not _turn_ready():
        warnings.append(
            "TURN non configurato: in reti esterne o NAT restrittivi alcune sessioni WebRTC possono non partire."
        )
    if not current_app.config.get("SUPPORT_STUN_URLS"):
        warnings.append(
            "Nessun server STUN configurato: aggiungi almeno un endpoint per migliorare la negoziazione WebRTC."
        )
    if not str(current_app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE") or "").strip():
        warnings.append(
            "Controllo remoto avanzato non configurato: lo screen sharing parte subito, ma l'escalation esterna resta disattivata."
        )
    current_config = current_support_configuration()

    return {
        "stats": repo.stats(),
        "filters": {
            "status": status_filter,
            "q": query,
        },
        "sessions": sessions,
        "selected_session": selected_payload,
        "events": events,
        "warnings": warnings,
        "runtime_config": {
            "stun_urls_text": "\n".join(current_config["stun_urls"]),
            "turn_urls_text": "\n".join(current_config["turn_urls"]),
            "turn_shared_secret_present": bool(current_config["turn_shared_secret"]),
            "turn_ttl_seconds": current_config["turn_ttl_seconds"],
            "ws_token_max_age": current_config["ws_token_max_age"],
            "advanced_url_template": current_config["advanced_url_template"],
            "config_path": current_config["config_path"],
        },
        "create_action": url_for("support_remote.create_session_api"),
        "config_action": url_for("support_remote.save_support_config"),
        "operator_rule": "L'assistenza remota parte sempre dal SUPERADMIN. Il cliente entra solo dal link firmato della sessione.",
        "advanced_ready": bool(str(current_app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE", "") or "").strip()),
    }
