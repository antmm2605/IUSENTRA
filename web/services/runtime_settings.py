"""Runtime configuration helpers extracted from web.app."""

from __future__ import annotations

import os
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from flask import Flask

from pct.local_ai import strip_api_suffix
from web.services.hosted_runtime import apply_hosted_local_ai_safety_overrides


def _list_from_runtime_value(value: Any) -> list[str]:
    raw = value if value is not None else ""
    if isinstance(raw, (list, tuple, set)):
        return [str(item or "").strip() for item in raw if str(item or "").strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            return [str(item or "").strip() for item in parsed if str(item or "").strip()]
    return [chunk.strip() for chunk in text.split(",") if chunk.strip()]


def apply_runtime_settings(
    app: Flask,
    cfg: Mapping[str, Any],
    *,
    data_peer_path: Callable[[str, str, str], str],
) -> None:
    """Populate runtime configuration for AI, studio settings, and tenancy."""
    app.config["BACKUP_ORA"] = os.getenv("PCT_BACKUP_ORA", "02:00")
    app.config["WA_REMINDER_ORA"] = os.getenv("PCT_WA_REMINDER_ORA", "18:00")

    app.config["LOCAL_AI_DB"] = cfg.get(
        "LOCAL_AI_DB",
        os.getenv(
            "PCT_LOCAL_AI_DB",
            data_peer_path(app.config["CLIENTI_DB"], "intelligence", "local_ai.db"),
        ),
    )
    app.config["LOCAL_AI_POLICY"] = cfg.get(
        "LOCAL_AI_POLICY",
        os.getenv("PCT_LOCAL_AI_POLICY", "./config/ai-policy.json"),
    )
    app.config["LOCAL_AI_MODELS_DIR"] = cfg.get(
        "LOCAL_AI_MODELS_DIR",
        os.getenv(
            "PCT_LOCAL_AI_MODELS_DIR",
            str(Path(app.config["LOCAL_AI_DB"]).parent / "models"),
        ),
    )
    app.config["LOCAL_AI_ENABLED"] = os.getenv(
        "PCT_LOCAL_AI_ENABLED", "1"
    ).lower() not in ("0", "false", "no")
    app.config["LOCAL_AI_BASE_URL"] = os.getenv(
        "PCT_LOCAL_AI_BASE_URL", "http://127.0.0.1:11434/api"
    )
    app.config["LOCAL_AI_AUTO_BOOTSTRAP"] = os.getenv(
        "PCT_LOCAL_AI_AUTO_BOOTSTRAP", "1"
    ).lower() not in ("0", "false", "no")
    app.config["LOCAL_AI_CHAT_MODEL"] = os.getenv("PCT_LOCAL_AI_CHAT_MODEL", "")
    app.config["LOCAL_AI_EMBED_MODEL"] = os.getenv("PCT_LOCAL_AI_EMBED_MODEL", "")
    app.config["LOCAL_AI_KEEP_ALIVE"] = os.getenv("PCT_LOCAL_AI_KEEP_ALIVE", "10m")
    app.config["LOCAL_AI_AUTO_INDEX_DOCUMENTS"] = os.getenv(
        "PCT_LOCAL_AI_AUTO_INDEX_DOCUMENTS", "1"
    ).lower() not in ("0", "false", "no")

    app.config["OLLAMA_URL"] = os.getenv(
        "PCT_OLLAMA_URL", strip_api_suffix(app.config["LOCAL_AI_BASE_URL"])
    )
    app.config["OLLAMA_MODEL"] = os.getenv(
        "PCT_OLLAMA_MODEL", app.config["LOCAL_AI_CHAT_MODEL"] or "mistral"
    )

    app.config["PAGAMENTI_DIR"] = cfg.get(
        "PAGAMENTI_DIR", os.getenv("PCT_PAGAMENTI_DIR", "./pagamenti")
    )
    app.config["TENANTS_REGISTRY"] = cfg.get(
        "TENANTS_REGISTRY", os.getenv("PCT_TENANTS_REGISTRY", "./data/tenants.json")
    )
    if "MULTI_TENANT" in cfg:
        app.config["MULTI_TENANT"] = bool(cfg.get("MULTI_TENANT"))
    else:
        app.config["MULTI_TENANT"] = os.getenv("PCT_MULTI_TENANT", "1").lower() not in (
            "0",
            "false",
            "no",
        )
    app.config["STUDIO_CONFIG"] = cfg.get(
        "STUDIO_CONFIG", os.getenv("PCT_STUDIO_CONFIG", "./config/studio.json")
    )
    app.config["CONFIG_STUDIO_DB"] = cfg.get(
        "CONFIG_STUDIO_DB",
        os.getenv("PCT_CONFIG_STUDIO_DB", app.config["STUDIO_CONFIG"]),
    )
    app.config["SUPPORT_DB"] = cfg.get(
        "SUPPORT_DB",
        os.getenv(
            "PCT_SUPPORT_DB",
            data_peer_path(app.config["AUTH_DB"], "support", "assistenza_remota.db"),
        ),
    )
    app.config["SUPPORT_STUN_URLS"] = _list_from_runtime_value(
        cfg.get("SUPPORT_STUN_URLS", os.getenv("PCT_SUPPORT_STUN_URLS", ""))
    )
    app.config["SUPPORT_TURN_URLS"] = _list_from_runtime_value(
        cfg.get("SUPPORT_TURN_URLS", os.getenv("PCT_SUPPORT_TURN_URLS", ""))
    )
    app.config["SUPPORT_TURN_SHARED_SECRET"] = str(
        cfg.get(
            "SUPPORT_TURN_SHARED_SECRET",
            os.getenv("PCT_SUPPORT_TURN_SHARED_SECRET", ""),
        )
        or ""
    ).strip()
    app.config["SUPPORT_TURN_TTL_SECONDS"] = int(
        cfg.get(
            "SUPPORT_TURN_TTL_SECONDS",
            os.getenv("PCT_SUPPORT_TURN_TTL_SECONDS", "3600"),
        )
        or 3600
    )
    app.config["SUPPORT_WS_TOKEN_MAX_AGE"] = int(
        cfg.get(
            "SUPPORT_WS_TOKEN_MAX_AGE",
            os.getenv("PCT_SUPPORT_WS_TOKEN_MAX_AGE", "43200"),
        )
        or 43200
    )
    app.config["SUPPORT_ADVANCED_URL_TEMPLATE"] = str(
        cfg.get(
            "SUPPORT_ADVANCED_URL_TEMPLATE",
            os.getenv("PCT_SUPPORT_ADVANCED_URL_TEMPLATE", ""),
        )
        or ""
    ).strip()

    apply_persistent_studio_overrides(app)
    apply_hosted_local_ai_safety_overrides(app, dict(cfg))


def apply_persistent_studio_overrides(app: Flask) -> None:
    """Overlay persisted studio settings on top of environment defaults."""
    try:
        from pct.config_studio import GestioneConfigStudio as _GCS

        gestione = _GCS(app.config["STUDIO_CONFIG"])
        studio_cfg = gestione.config

        if studio_cfg.studio.nome:
            app.config["STUDIO_NOME"] = studio_cfg.studio.nome
            app.config["STUDIO_AVVOCATO"] = studio_cfg.studio.avvocato
            app.config["STUDIO_PIVA"] = studio_cfg.studio.piva
            app.config["STUDIO_CF"] = studio_cfg.studio.cf
            app.config["STUDIO_INDIRIZZO"] = studio_cfg.studio.indirizzo
            app.config["STUDIO_IBAN"] = studio_cfg.studio.iban

        if studio_cfg.whatsapp.twilio_sid:
            app.config["TWILIO_SID"] = studio_cfg.whatsapp.twilio_sid
            app.config["TWILIO_TOKEN"] = studio_cfg.whatsapp.twilio_token
            app.config["TWILIO_NUMERO"] = studio_cfg.whatsapp.twilio_numero
        if studio_cfg.whatsapp.callmebot_key:
            app.config["CALLMEBOT_KEY"] = studio_cfg.whatsapp.callmebot_key

        if studio_cfg.scheduler.backup_ora:
            app.config["BACKUP_ORA"] = studio_cfg.scheduler.backup_ora
            app.config["WA_REMINDER_ORA"] = studio_cfg.scheduler.wa_reminder_ora

        app.config["LOCAL_AI_ENABLED"] = bool(getattr(studio_cfg.ai, "enabled", True))
        app.config["LOCAL_AI_BASE_URL"] = getattr(
            studio_cfg.ai, "base_url", "http://127.0.0.1:11434/api"
        )
        app.config["LOCAL_AI_AUTO_BOOTSTRAP"] = bool(
            getattr(studio_cfg.ai, "auto_bootstrap", True)
        )
        app.config["LOCAL_AI_CHAT_MODEL"] = getattr(studio_cfg.ai, "chat_model", "")
        app.config["LOCAL_AI_EMBED_MODEL"] = getattr(studio_cfg.ai, "embed_model", "")
        app.config["LOCAL_AI_KEEP_ALIVE"] = getattr(
            studio_cfg.ai, "keep_alive", "10m"
        )
        app.config["LOCAL_AI_AUTO_INDEX_DOCUMENTS"] = bool(
            getattr(studio_cfg.ai, "auto_index_documents", True)
        )
        app.config["OLLAMA_URL"] = strip_api_suffix(app.config["LOCAL_AI_BASE_URL"])
        if app.config["LOCAL_AI_CHAT_MODEL"]:
            app.config["OLLAMA_MODEL"] = app.config["LOCAL_AI_CHAT_MODEL"]

        support_cfg = getattr(studio_cfg, "support_remote", None)
        if support_cfg is not None:
            app.config["SUPPORT_STUN_URLS"] = _list_from_runtime_value(
                getattr(support_cfg, "stun_urls", app.config.get("SUPPORT_STUN_URLS", []))
            )
            app.config["SUPPORT_TURN_URLS"] = _list_from_runtime_value(
                getattr(support_cfg, "turn_urls", app.config.get("SUPPORT_TURN_URLS", []))
            )
            app.config["SUPPORT_TURN_SHARED_SECRET"] = str(
                getattr(
                    support_cfg,
                    "turn_shared_secret",
                    app.config.get("SUPPORT_TURN_SHARED_SECRET", ""),
                )
                or ""
            ).strip()
            app.config["SUPPORT_TURN_TTL_SECONDS"] = int(
                getattr(
                    support_cfg,
                    "turn_ttl_seconds",
                    app.config.get("SUPPORT_TURN_TTL_SECONDS", 3600),
                )
                or 3600
            )
            app.config["SUPPORT_WS_TOKEN_MAX_AGE"] = int(
                getattr(
                    support_cfg,
                    "ws_token_max_age",
                    app.config.get("SUPPORT_WS_TOKEN_MAX_AGE", 43200),
                )
                or 43200
            )
            app.config["SUPPORT_ADVANCED_URL_TEMPLATE"] = str(
                getattr(
                    support_cfg,
                    "advanced_url_template",
                    app.config.get("SUPPORT_ADVANCED_URL_TEMPLATE", ""),
                )
                or ""
            ).strip()

        app.config["SMTP_HOST"] = studio_cfg.smtp.host or os.getenv("PCT_SMTP_HOST", "")
        app.config["SMTP_PORT"] = studio_cfg.smtp.port or int(
            os.getenv("PCT_SMTP_PORT", "587")
        )
        app.config["SMTP_USER"] = studio_cfg.smtp.username or os.getenv(
            "PCT_SMTP_USER", ""
        )
        app.config["SMTP_PASS"] = studio_cfg.smtp.password or os.getenv(
            "PCT_SMTP_PASS", ""
        )
        app.config["SMTP_FROM"] = studio_cfg.smtp.from_address or os.getenv(
            "PCT_SMTP_FROM", ""
        )
        app.config["SMTP_FROM_NAME"] = studio_cfg.smtp.from_name or app.config.get(
            "STUDIO_NOME", "Studio Legale"
        )
        app.config["SMTP_USE_TLS"] = studio_cfg.smtp.use_tls
    except Exception:
        app.config.setdefault("SMTP_HOST", os.getenv("PCT_SMTP_HOST", ""))
        app.config.setdefault("SMTP_PORT", int(os.getenv("PCT_SMTP_PORT", "587")))
        app.config.setdefault("SMTP_USER", os.getenv("PCT_SMTP_USER", ""))
        app.config.setdefault("SMTP_PASS", os.getenv("PCT_SMTP_PASS", ""))
        app.config.setdefault("SMTP_FROM", os.getenv("PCT_SMTP_FROM", ""))
        app.config.setdefault(
            "SMTP_FROM_NAME", app.config.get("STUDIO_NOME", "Studio Legale")
        )
        app.config.setdefault("SMTP_USE_TLS", True)
