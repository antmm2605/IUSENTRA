"""Health check professionali per live/readiness/dependencies."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from core.cache import CacheClient
from core.database import ping_database


def live_payload(version: str) -> tuple[dict[str, Any], int]:
    return {"status": "healthy", "ok": True, "versione": version}, 200


def ready_payload(*, version: str, database_url: str, redis_url: str, storage_root: str | Path = "data") -> tuple[dict[str, Any], int]:
    checks = {
        "database": _check_database(database_url),
        "redis": _check_redis(redis_url, required=False),
        "filesystem": _check_filesystem(storage_root),
    }
    status = _aggregate_status(checks)
    return {"status": status, "ok": status != "unhealthy", "versione": version, "checks": checks}, (200 if status != "unhealthy" else 503)


def dependencies_payload(*, version: str, database_url: str, redis_url: str, ollama_url: str = "", smtp_configured: bool = False) -> tuple[dict[str, Any], int]:
    checks = {
        "database": _check_database(database_url),
        "redis": _check_redis(redis_url, required=False),
        "rq": _check_redis(redis_url, required=False),
        "ollama": {"status": "degraded", "ok": False, "message": "non configurato"} if not ollama_url else {"status": "unknown", "ok": False, "message": "verifica runtime demandata al provider AI"},
        "smtp": {"status": "healthy" if smtp_configured else "degraded", "ok": smtp_configured, "message": "configurato" if smtp_configured else "non configurato"},
    }
    status = _aggregate_status(checks)
    return {"status": status, "ok": status != "unhealthy", "versione": version, "checks": checks}, (200 if status != "unhealthy" else 503)


def _check_database(database_url: str) -> dict[str, Any]:
    ok, message = ping_database(database_url)
    return {"status": "healthy" if ok else "unhealthy", "ok": ok, "message": message}


def _check_redis(redis_url: str, *, required: bool) -> dict[str, Any]:
    status = CacheClient(redis_url).status()
    if status.backend == "memory" and not required:
        return {"status": "degraded", "ok": True, "backend": status.backend, "message": status.message}
    return {"status": "healthy" if status.ok else "unhealthy", "ok": status.ok, "backend": status.backend, "message": status.message}


def _check_filesystem(path: str | Path) -> dict[str, Any]:
    try:
        root = Path(path)
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".iusentra-health"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return {"status": "healthy", "ok": True, "message": str(root)}
    except Exception as exc:
        return {"status": "unhealthy", "ok": False, "message": str(exc)}


def _aggregate_status(checks: dict[str, dict[str, Any]]) -> str:
    statuses = {str(item.get("status")) for item in checks.values()}
    if "unhealthy" in statuses:
        return "unhealthy"
    if "degraded" in statuses or "unknown" in statuses:
        return "degraded"
    return "healthy"
