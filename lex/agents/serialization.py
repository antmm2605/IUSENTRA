"""Serializzazione pubblica e redazione dati per il layer agentico Lex."""

from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

from .models import AgentMetric, AgentPlan, AgentProposal, AgentRun, AgentStep


SENSITIVE_KEYS = {
    "codice_fiscale",
    "cf",
    "iban",
    "email",
    "pec",
    "password",
    "token",
    "secret",
    "api_key",
    "path",
    "percorso",
    "root",
    "filesystem_path",
    "contenuto",
    "content",
    "body",
    "testo",
    "raw",
    "tenant_id",
    "studio_id",
    "user_id",
}
CONTROL_KEYS = {"tenant_id", "studio_id", "user_id", "token", "api_key", "path", "percorso", "root"}
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
CF_RE = re.compile(r"\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b", re.IGNORECASE)
IBAN_RE = re.compile(r"\bIT[0-9A-Z]{25}\b", re.IGNORECASE)
WIN_PATH_RE = re.compile(r"[A-Za-z]:\\[^\s]+")
UNIX_PATH_RE = re.compile(r"(?<!https:)\/(?:data|home|opt|var|tmp|mnt|Users|usr)\/[^\s]+")


def _looks_like_path(value: str) -> bool:
    if WIN_PATH_RE.search(value) or UNIX_PATH_RE.search(value):
        return True
    try:
        return bool(PureWindowsPath(value).drive and "\\" in value)
    except Exception:
        pass
    try:
        return value.startswith("/") and len(PurePosixPath(value).parts) > 2
    except Exception:
        return False


def redact_value(value: Any, *, key: str = "") -> Any:
    normalized_key = str(key or "").lower()
    if normalized_key in SENSITIVE_KEYS or any(part in normalized_key for part in ("password", "token", "secret", "iban", "codice_fiscale")):
        return "[omesso]"
    if isinstance(value, dict):
        return {str(k): redact_value(v, key=str(k)) for k, v in value.items() if str(k).lower() not in CONTROL_KEYS}
    if isinstance(value, list):
        return [redact_value(item, key=key) for item in value[:50]]
    if isinstance(value, tuple):
        return [redact_value(item, key=key) for item in value[:50]]
    if isinstance(value, str):
        text = value
        if _looks_like_path(text):
            return "[percorso omesso]"
        text = EMAIL_RE.sub("[email omessa]", text)
        text = CF_RE.sub("[codice fiscale omesso]", text)
        text = IBAN_RE.sub("[iban omesso]", text)
        if len(text) > 700:
            return text[:700].rstrip() + "..."
        return text
    return value


def public_dict(value: Any) -> Any:
    if isinstance(value, AgentRun):
        payload = value.to_dict()
    elif isinstance(value, AgentPlan):
        payload = value.to_dict()
    elif isinstance(value, AgentStep):
        payload = value.to_dict()
    elif isinstance(value, AgentProposal):
        payload = value.to_dict()
    elif isinstance(value, AgentMetric):
        payload = value.to_dict()
    elif hasattr(value, "to_dict"):
        payload = value.to_dict()
    else:
        payload = value
    return redact_value(payload)


def redact_for_audit(value: Any) -> Any:
    return redact_value(value)

