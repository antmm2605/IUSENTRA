"""Configurazione production hardening letta da ambiente/app Flask."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if not normalized:
        return default
    return normalized in {"1", "true", "yes", "on"}


def env_value(name: str, default: str = "") -> str:
    return str(os.getenv(name, default) or "").strip()


@dataclass(frozen=True)
class HardeningConfig:
    database_url: str
    redis_url: str
    cache_ttl_seconds: int
    session_redis_enabled: bool
    max_upload_mb: int
    allowed_upload_extensions: tuple[str, ...]
    allowed_upload_mime_types: tuple[str, ...]
    ratelimit_enabled: bool
    ratelimit_default: str
    security_headers_enabled: bool
    csp_report_only: bool
    prometheus_enabled: bool
    backup_dir: Path
    backup_retention_days: int
    backup_encryption_enabled: bool


def load_hardening_config(source: dict[str, Any] | None = None) -> HardeningConfig:
    cfg = dict(source or {})
    testing = as_bool(cfg.get("TESTING"), default=False)
    return HardeningConfig(
        database_url=str(cfg.get("DATABASE_URL") or env_value("DATABASE_URL", "sqlite:///data/iusentra.sqlite")),
        redis_url=str(cfg.get("REDIS_URL") or env_value("REDIS_URL", "redis://localhost:6379/0")),
        cache_ttl_seconds=int(cfg.get("CACHE_TTL_SECONDS") or env_value("CACHE_TTL_SECONDS", "300") or 300),
        session_redis_enabled=as_bool(cfg.get("SESSION_REDIS_ENABLED") or env_value("SESSION_REDIS_ENABLED")),
        max_upload_mb=int(cfg.get("MAX_UPLOAD_MB") or env_value("MAX_UPLOAD_MB", "50") or 50),
        allowed_upload_extensions=_split_csv(
            str(
                cfg.get("ALLOWED_UPLOAD_EXTENSIONS")
                or env_value("ALLOWED_UPLOAD_EXTENSIONS", ".pdf,.p7m,.xml,.docx,.png,.jpg,.jpeg,.zip")
            )
        ),
        allowed_upload_mime_types=_split_csv(
            str(
                cfg.get("ALLOWED_UPLOAD_MIME_TYPES")
                or env_value(
                    "ALLOWED_UPLOAD_MIME_TYPES",
                    "application/pdf,application/xml,text/xml,application/zip,application/pkcs7-mime,image/png,image/jpeg",
                )
            )
        ),
        ratelimit_enabled=as_bool(cfg.get("RATELIMIT_ENABLED") or env_value("RATELIMIT_ENABLED"), default=not testing),
        ratelimit_default=str(cfg.get("RATELIMIT_DEFAULT") or env_value("RATELIMIT_DEFAULT", "120/minute")),
        security_headers_enabled=as_bool(
            cfg.get("SECURITY_HEADERS_ENABLED") or env_value("SECURITY_HEADERS_ENABLED"),
            default=True,
        ),
        csp_report_only=as_bool(cfg.get("CSP_REPORT_ONLY") or env_value("CSP_REPORT_ONLY"), default=testing),
        prometheus_enabled=as_bool(cfg.get("PROMETHEUS_ENABLED") or env_value("PROMETHEUS_ENABLED"), default=True),
        backup_dir=Path(str(cfg.get("BACKUP_DIR") or env_value("BACKUP_DIR", "data/backup"))),
        backup_retention_days=int(cfg.get("BACKUP_RETENTION_DAYS") or env_value("BACKUP_RETENTION_DAYS", "30") or 30),
        backup_encryption_enabled=as_bool(
            cfg.get("BACKUP_ENCRYPTION_ENABLED") or env_value("BACKUP_ENCRYPTION_ENABLED"),
            default=False,
        ),
    )


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip().lower() for item in value.split(",") if item.strip())
