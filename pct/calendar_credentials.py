"""Cifratura delle credenziali dei calendari esterni."""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class CalendarCredentialError(RuntimeError):
    """Errore nella gestione delle credenziali calendario."""


_ENV_KEYS = (
    "IUSENTRA_CALENDAR_CREDENTIALS_KEY",
    "PCT_CALENDAR_CREDENTIALS_KEY",
    "CALENDAR_CREDENTIALS_KEY",
)
_DEMO_SEED = b"iusentra-calendar-sync-demo-key-v1"


def _is_production_env() -> bool:
    values = [
        os.getenv("IUSENTRA_ENV", ""),
        os.getenv("PCT_ENV", ""),
        os.getenv("FLASK_ENV", ""),
        os.getenv("RAILWAY_ENVIRONMENT", ""),
        os.getenv("RENDER", ""),
    ]
    return any(str(value).strip().lower() in {"production", "prod", "1", "true"} for value in values)


def _derive_key(raw: str | bytes) -> bytes:
    if isinstance(raw, str):
        raw_text = raw.strip()
        if raw_text:
            try:
                Fernet(raw_text.encode("ascii"))
                return raw_text.encode("ascii")
            except Exception:
                raw = raw_text.encode("utf-8")
        else:
            raw = b""
    digest = hashlib.sha256(bytes(raw)).digest()
    return base64.urlsafe_b64encode(digest)


def resolve_master_key(*, allow_demo_fallback: bool = True) -> tuple[bytes, str]:
    for name in _ENV_KEYS:
        value = os.getenv(name, "").strip()
        if value:
            return _derive_key(value), name
    if not allow_demo_fallback or _is_production_env():
        raise CalendarCredentialError(
            "Chiave master calendario mancante. Configurare IUSENTRA_CALENDAR_CREDENTIALS_KEY."
        )
    return _derive_key(_DEMO_SEED), "demo-test-deterministic"


@dataclass
class CalendarCredentialVault:
    master_key: bytes | str | None = None
    allow_demo_fallback: bool = True

    def _fernet(self) -> Fernet:
        key = _derive_key(self.master_key) if self.master_key else resolve_master_key(
            allow_demo_fallback=self.allow_demo_fallback
        )[0]
        return Fernet(key)

    def encrypt(self, credentials: dict[str, Any] | None) -> str:
        payload = json.dumps(credentials or {}, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
        return "fernet:v1:" + self._fernet().encrypt(payload).decode("ascii")

    def decrypt(self, encrypted_value: str | None) -> dict[str, Any]:
        raw = str(encrypted_value or "").strip()
        if not raw:
            return {}
        token = raw.split("fernet:v1:", 1)[1] if raw.startswith("fernet:v1:") else raw
        try:
            decoded = self._fernet().decrypt(token.encode("ascii"))
        except (InvalidToken, ValueError) as exc:
            raise CalendarCredentialError("Credenziali calendario non decifrabili.") from exc
        data = json.loads(decoded.decode("utf-8"))
        return data if isinstance(data, dict) else {}


def credentials_key_status() -> dict[str, Any]:
    try:
        _key, source = resolve_master_key(allow_demo_fallback=True)
        return {
            "configured": source != "demo-test-deterministic",
            "source": source,
            "demo_fallback": source == "demo-test-deterministic",
        }
    except CalendarCredentialError as exc:
        return {"configured": False, "source": "", "demo_fallback": False, "error": str(exc)}
