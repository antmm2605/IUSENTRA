"""Configurazione logging strutturato e masking dati sensibili."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

from flask import Flask, has_request_context, request, session


_SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE),
    re.compile(r"\b(?:IT)?\d{11}\b"),
    re.compile(r"\bIT\d{2}[A-Z]\d{10}[A-Z0-9]{12}\b", re.IGNORECASE),
    re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    re.compile(r"\b(?:\+39\s*)?(?:\d[\s.-]?){8,}\b"),
)


def mask_sensitive_log_text(value: str) -> str:
    masked = str(value or "")
    for pattern in _SENSITIVE_PATTERNS:
        masked = pattern.sub("[REDACTED]", masked)
    return masked


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_sensitive_log_text(record.getMessage())
            record.args = ()
        elif isinstance(record.msg, dict):
            try:
                record.msg = json.loads(mask_sensitive_log_text(json.dumps(record.msg, ensure_ascii=False)))
            except Exception:
                record.msg = mask_sensitive_log_text(str(record.msg))
            record.args = ()
        elif record.args:
            record.args = tuple(
                mask_sensitive_log_text(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        return True


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.tenant_slug = ""
        record.request_path = ""
        record.request_method = ""
        record.remote_addr = ""
        record.request_id = ""
        if not has_request_context():
            return True
        record.request_path = str(getattr(request, "path", "") or "")
        record.request_method = str(getattr(request, "method", "") or "")
        record.remote_addr = (
            str(request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
            or str(request.remote_addr or "")
        )
        record.request_id = str(
            request.headers.get("X-Request-Id")
            or request.environ.get("HTTP_X_REQUEST_ID")
            or ""
        ).strip()
        view_args = getattr(request, "view_args", None) or {}
        tenant_slug = (
            str(view_args.get("tenant_slug") or "").strip()
            or str(request.args.get("tenant_slug") or "").strip()
            or str(session.get("tenant_slug") or "").strip()
            or str(session.get("selected_tenant_slug") or "").strip()
        )
        record.tenant_slug = tenant_slug
        return True


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "tenant_slug": str(getattr(record, "tenant_slug", "") or ""),
            "request_method": str(getattr(record, "request_method", "") or ""),
            "request_path": str(getattr(record, "request_path", "") or ""),
            "remote_addr": str(getattr(record, "remote_addr", "") or ""),
            "request_id": str(getattr(record, "request_id", "") or ""),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class HumanReadableFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        tenant = str(getattr(record, "tenant_slug", "") or "")
        method = str(getattr(record, "request_method", "") or "")
        path = str(getattr(record, "request_path", "") or "")
        context_parts = [part for part in (tenant, f"{method} {path}".strip()) if part]
        context = f" [{ ' | '.join(context_parts) }]" if context_parts else ""
        message = super().format(record)
        return f"{message}{context}"


def _structured_logging_mode(app: Flask, cfg: dict[str, Any]) -> str:
    raw = str(
        cfg.get("PCT_LOG_FORMAT")
        or os.getenv("PCT_LOG_FORMAT", "")
        or ("json" if _is_production_runtime(app, cfg) else "text")
    ).strip().lower()
    return "json" if raw == "json" else "text"


def _is_production_runtime(app: Flask, cfg: dict[str, Any]) -> bool:
    if app.config.get("TESTING"):
        return False
    env = str(
        cfg.get("PCT_ENV")
        or os.getenv("PCT_ENV", "")
        or os.getenv("FLASK_ENV", "")
        or os.getenv("ENVIRONMENT", "")
    ).strip().lower()
    if env in {"prod", "production"}:
        return True
    return bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_SERVICE_ID"))


def _logging_level(app: Flask, cfg: dict[str, Any]) -> int:
    raw = str(cfg.get("PCT_LOG_LEVEL") or os.getenv("PCT_LOG_LEVEL", "")).strip().upper()
    if raw:
        return getattr(logging, raw, logging.INFO)
    return logging.DEBUG if app.config.get("TESTING") else logging.INFO


def configure_structured_logging(app: Flask, cfg: dict[str, Any]) -> None:
    level = _logging_level(app, cfg)
    mode = _structured_logging_mode(app, cfg)
    formatter: logging.Formatter
    if mode == "json":
        formatter = JsonLogFormatter()
    else:
        formatter = HumanReadableFormatter(
            "%(asctime)s [%(levelname)s] %(name)s.%(funcName)s:%(lineno)d - %(message)s"
        )

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    handlers = list(root_logger.handlers)
    if not handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler._iusentra_logging_handler = True  # type: ignore[attr-defined]
        root_logger.addHandler(handler)
        handlers = [handler]

    for handler in handlers:
        handler.setLevel(level)
        handler.setFormatter(formatter)
        if not any(isinstance(existing, SensitiveDataFilter) for existing in handler.filters):
            handler.addFilter(SensitiveDataFilter())
        if not any(isinstance(existing, RequestContextFilter) for existing in handler.filters):
            handler.addFilter(RequestContextFilter())

    app.logger.handlers.clear()
    app.logger.propagate = True
    app.logger.setLevel(level)
