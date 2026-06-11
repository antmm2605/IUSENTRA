"""Accesso sicuro al Portale Cliente: magic-link monouso + sfida OTP.

Sicurezza per progettazione (coerente col login guard dello studio):
- token magic-link **opaco**, generato con `secrets`, salvato **solo come hash**
  (mai in chiaro), a tempo (TTL) e **monouso** (consumato all'uso);
- sfida **OTP** a tempo, salvata solo come hash, con **limite tentativi** (anti
  forza bruta): superata la soglia la sfida è bloccata;
- confronti a **tempo costante** (`hmac.compare_digest`);
- storage-agnostico: il chiamante inietta uno store (in produzione tenant-aware);
- il cliente non sceglie mai tenant/pratica: tutto è risolto lato server dal
  grant emesso dallo studio.

Questa è la primitiva di accesso; l'invio dell'OTP sul canale (email/SMS/PEC) e
l'aggancio alla sessione del portale avvengono nel wiring successivo.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_secret(value: str, *, pepper: str = "") -> str:
    """Hash non reversibile del segreto (token/OTP). Mai salvare il valore in chiaro."""

    cleaned = str(value or "")
    if not cleaned:
        return ""
    return hashlib.sha256(f"{pepper}|{cleaned}".encode("utf-8")).hexdigest()


def constant_time_match(value: str, expected_hash: str, *, pepper: str = "") -> bool:
    if not value or not expected_hash:
        return False
    return hmac.compare_digest(hash_secret(value, pepper=pepper), str(expected_hash))


def generate_magic_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def generate_otp(digits: int = 6) -> str:
    digits = max(4, min(int(digits or 6), 10))
    return "".join(secrets.choice("0123456789") for _ in range(digits))


@runtime_checkable
class AccessStore(Protocol):
    def save_grant(self, grant_id: str, record: dict[str, Any]) -> None: ...
    def load_grant(self, grant_id: str) -> dict[str, Any] | None: ...
    def update_grant(self, grant_id: str, record: dict[str, Any]) -> None: ...


class InMemoryAccessStore:
    """Store in memoria per test/sviluppo. In produzione: store tenant-aware."""

    def __init__(self) -> None:
        self._grants: dict[str, dict[str, Any]] = {}

    def save_grant(self, grant_id: str, record: dict[str, Any]) -> None:
        self._grants[grant_id] = dict(record)

    def load_grant(self, grant_id: str) -> dict[str, Any] | None:
        record = self._grants.get(grant_id)
        return dict(record) if record is not None else None

    def update_grant(self, grant_id: str, record: dict[str, Any]) -> None:
        self._grants[grant_id] = dict(record)


@dataclass(frozen=True)
class AccessResult:
    ok: bool
    reason: str = ""
    locked: bool = False
    otp_code: str = ""  # valorizzato solo da start_otp, da consegnare via canale


class PortalAccessManager:
    def __init__(
        self,
        store: AccessStore,
        *,
        pepper: str = "",
        magic_ttl_minutes: int = 15,
        otp_ttl_minutes: int = 10,
        max_otp_attempts: int = 5,
    ) -> None:
        self.store = store
        self.pepper = pepper
        self.magic_ttl = timedelta(minutes=max(1, magic_ttl_minutes))
        self.otp_ttl = timedelta(minutes=max(1, otp_ttl_minutes))
        self.max_otp_attempts = max(1, max_otp_attempts)

    def issue_magic_link(self, *, tenant_id: str, client_id: str, matter_id: str = "", now: datetime | None = None) -> tuple[str, str]:
        """Emette un grant: ritorna (grant_id, token_in_chiaro da inviare una sola volta)."""

        now = now or _now()
        grant_id = secrets.token_urlsafe(16)
        token = generate_magic_token()
        self.store.save_grant(
            grant_id,
            {
                "grant_id": grant_id,
                "tenant_id": str(tenant_id),
                "client_id": str(client_id),
                "matter_id": str(matter_id),
                "magic_hash": hash_secret(token, pepper=self.pepper),
                "magic_expires_at": (now + self.magic_ttl).isoformat(),
                "magic_consumed_at": "",
                "status": "issued",
                "otp_hash": "",
                "otp_expires_at": "",
                "otp_attempts": 0,
                "created_at": now.isoformat(),
            },
        )
        return grant_id, token

    def _expired(self, iso_value: str, now: datetime) -> bool:
        try:
            return datetime.fromisoformat(str(iso_value)) < now
        except (TypeError, ValueError):
            return True

    def start_otp(self, grant_id: str, token: str, *, now: datetime | None = None) -> AccessResult:
        """Verifica il magic-link (monouso) e avvia la sfida OTP."""

        now = now or _now()
        grant = self.store.load_grant(grant_id)
        if not grant:
            return AccessResult(False, "grant_non_trovato")
        if grant.get("status") == "revoked":
            return AccessResult(False, "grant_revocato")
        if grant.get("magic_consumed_at"):
            return AccessResult(False, "magic_link_gia_usato")
        if self._expired(grant.get("magic_expires_at", ""), now):
            return AccessResult(False, "magic_link_scaduto")
        if not constant_time_match(token, str(grant.get("magic_hash") or ""), pepper=self.pepper):
            return AccessResult(False, "token_non_valido")

        otp = generate_otp()
        grant.update(
            {
                "magic_consumed_at": now.isoformat(),
                "otp_hash": hash_secret(otp, pepper=self.pepper),
                "otp_expires_at": (now + self.otp_ttl).isoformat(),
                "otp_attempts": 0,
                "status": "otp_sent",
            }
        )
        self.store.update_grant(grant_id, grant)
        return AccessResult(True, "otp_inviato", otp_code=otp)

    def verify_otp(self, grant_id: str, code: str, *, now: datetime | None = None) -> AccessResult:
        now = now or _now()
        grant = self.store.load_grant(grant_id)
        if not grant:
            return AccessResult(False, "grant_non_trovato")
        if grant.get("status") == "granted":
            return AccessResult(True, "gia_concesso")
        if grant.get("status") == "otp_locked" or int(grant.get("otp_attempts", 0)) >= self.max_otp_attempts:
            return AccessResult(False, "otp_bloccato", locked=True)
        if grant.get("status") != "otp_sent":
            return AccessResult(False, "otp_non_avviato")
        if self._expired(grant.get("otp_expires_at", ""), now):
            return AccessResult(False, "otp_scaduto")

        if not constant_time_match(code, str(grant.get("otp_hash") or ""), pepper=self.pepper):
            grant["otp_attempts"] = int(grant.get("otp_attempts", 0)) + 1
            locked = grant["otp_attempts"] >= self.max_otp_attempts
            if locked:
                grant["status"] = "otp_locked"
            self.store.update_grant(grant_id, grant)
            return AccessResult(False, "otp_errato", locked=locked)

        grant["status"] = "granted"
        grant["granted_at"] = now.isoformat()
        self.store.update_grant(grant_id, grant)
        return AccessResult(True, "accesso_concesso")

    def revoke(self, grant_id: str) -> bool:
        grant = self.store.load_grant(grant_id)
        if not grant:
            return False
        grant["status"] = "revoked"
        self.store.update_grant(grant_id, grant)
        return True


__all__ = [
    "PortalAccessManager",
    "InMemoryAccessStore",
    "AccessStore",
    "AccessResult",
    "hash_secret",
    "constant_time_match",
    "generate_magic_token",
    "generate_otp",
]
