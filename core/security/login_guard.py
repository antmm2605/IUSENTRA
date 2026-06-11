"""Protezione anti brute-force / credential stuffing per il login.

Base di sicurezza: il gestionale custodisce dati legali riservati e l'accesso
avviene con username/password. ``pct.auth.GestioneUtenti.autentica`` non conta i
tentativi falliti e il rate limit generico (flask-limiter) applica solo un tetto
per IP/minuto: da soli non fermano un attacco a dizionario sulle credenziali.

Questo modulo aggiunge il blocco temporizzato dell'accesso, indipendente dal
rate limiter, con due chiavi:

* **(IP, username)**: dopo ``max_per_user`` fallimenti consecutivi la coppia
  viene bloccata per ``lock_seconds``. Durante il blocco ogni tentativo è
  respinto **anche con la password corretta** (un attaccante non può infilarsi
  indovinando proprio durante la finestra).
* **IP**: dopo ``max_per_ip`` fallimenti su qualunque username lo stesso IP
  viene bloccato, per fermare lo spraying su molti account.

Il blocco è per (IP, username) e non solo per username: così un attaccante non
può causare un denial-of-service bloccando l'accesso della vittima da remoto.

Lo store è Redis quando disponibile (condiviso fra i worker Gunicorn) con
fallback in memoria a prova di errore: qualsiasi problema Redis degrada sul
backend locale senza mai far cadere il login.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

from flask import Flask


_REDIS_URI_PREFIXES = ("redis://", "rediss://", "unix://")


def _as_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "si", "on"}


def _as_int(value: object, *, default: int, minimum: int = 1) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= minimum else default


@dataclass(frozen=True)
class LoginGuardPolicy:
    enabled: bool
    max_per_user: int
    max_per_ip: int
    window_seconds: int
    lock_seconds: int


class _InMemoryBackend:
    """Backend a finestra fissa thread-safe (fallback sempre disponibile)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, tuple[int, float]] = {}
        self._locks: dict[str, float] = {}

    def incr(self, key: str, window_seconds: int) -> int:
        now = time.monotonic()
        with self._lock:
            count, reset_at = self._counters.get(key, (0, 0.0))
            if now >= reset_at:
                count, reset_at = 0, now + window_seconds
            count += 1
            self._counters[key] = (count, reset_at)
            return count

    def set_lock(self, key: str, lock_seconds: int) -> None:
        with self._lock:
            self._locks[key] = time.monotonic() + lock_seconds

    def lock_remaining(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            deadline = self._locks.get(key, 0.0)
            if deadline <= now:
                self._locks.pop(key, None)
                return 0
            return int(round(deadline - now))

    def clear(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._counters.pop(key, None)
                self._locks.pop(key, None)


class _RedisBackend:
    """Backend Redis best-effort: ogni errore degrada sul backend in memoria."""

    def __init__(self, client: object) -> None:
        self._client = client
        self._fallback = _InMemoryBackend()

    def incr(self, key: str, window_seconds: int) -> int:
        try:
            pipe = self._client.pipeline()
            pipe.incr(key)
            pipe.expire(key, window_seconds)
            count, _ = pipe.execute()
            return int(count)
        except Exception:
            return self._fallback.incr(key, window_seconds)

    def set_lock(self, key: str, lock_seconds: int) -> None:
        try:
            self._client.set(f"lock:{key}", "1", ex=lock_seconds)
        except Exception:
            self._fallback.set_lock(key, lock_seconds)

    def lock_remaining(self, key: str) -> int:
        try:
            ttl = self._client.ttl(f"lock:{key}")
            ttl_int = int(ttl)
            if ttl_int > 0:
                return ttl_int
            return max(0, self._fallback.lock_remaining(key))
        except Exception:
            return self._fallback.lock_remaining(key)

    def clear(self, *keys: str) -> None:
        try:
            redis_keys: list[str] = []
            for key in keys:
                redis_keys.extend((key, f"lock:{key}"))
            if redis_keys:
                self._client.delete(*redis_keys)
        except Exception:
            pass
        self._fallback.clear(*keys)


class LoginAttemptGuard:
    """Blocco temporizzato dei tentativi di accesso falliti."""

    def __init__(self, policy: LoginGuardPolicy, backend: object) -> None:
        self.policy = policy
        self._backend = backend

    @property
    def enabled(self) -> bool:
        return self.policy.enabled

    @staticmethod
    def _norm_ip(ip: str) -> str:
        return (ip or "sconosciuto").strip() or "sconosciuto"

    @staticmethod
    def _norm_user(username: str) -> str:
        return (username or "").strip().lower()

    def _pair_key(self, ip: str, username: str) -> str:
        return f"login:pair:{self._norm_ip(ip)}:{self._norm_user(username)}"

    def _ip_key(self, ip: str) -> str:
        return f"login:ip:{self._norm_ip(ip)}"

    def lock_remaining_seconds(self, ip: str, username: str) -> int:
        if not self.policy.enabled:
            return 0
        pair = self._backend.lock_remaining(self._pair_key(ip, username))
        per_ip = self._backend.lock_remaining(self._ip_key(ip))
        return max(pair, per_ip)

    def is_locked(self, ip: str, username: str) -> bool:
        return self.lock_remaining_seconds(ip, username) > 0

    def register_failure(self, ip: str, username: str) -> int:
        """Conta il tentativo fallito; attiva il blocco al superamento delle soglie.

        Ritorna i secondi di blocco residui (0 se non bloccato)."""

        if not self.policy.enabled:
            return 0
        pair_key = self._pair_key(ip, username)
        ip_key = self._ip_key(ip)
        pair_count = self._backend.incr(pair_key, self.policy.window_seconds)
        ip_count = self._backend.incr(ip_key, self.policy.window_seconds)
        if pair_count >= self.policy.max_per_user:
            self._backend.set_lock(pair_key, self.policy.lock_seconds)
        if ip_count >= self.policy.max_per_ip:
            self._backend.set_lock(ip_key, self.policy.lock_seconds)
        return self.lock_remaining_seconds(ip, username)

    def register_success(self, ip: str, username: str) -> None:
        """Azzera contatore e blocco della coppia (IP, username) dopo un accesso valido.

        Il contatore per-IP resta: un IP che ha spruzzato molti account non viene
        "ripulito" solo perché ne ha indovinato uno."""

        if not self.policy.enabled:
            return
        self._backend.clear(self._pair_key(ip, username))


def _policy_from_config(app: Flask) -> LoginGuardPolicy:
    def cfg(key: str, env: str, default: object) -> object:
        if key in app.config and app.config.get(key) is not None:
            return app.config.get(key)
        env_value = os.environ.get(env)
        return env_value if env_value is not None else default

    enabled = _as_bool(
        cfg("LOGIN_GUARD_ENABLED", "LOGIN_GUARD_ENABLED", None),
        default=not app.testing,
    )
    return LoginGuardPolicy(
        enabled=enabled,
        max_per_user=_as_int(
            cfg("LOGIN_GUARD_MAX_PER_USER", "LOGIN_GUARD_MAX_PER_USER", 5), default=5
        ),
        max_per_ip=_as_int(
            cfg("LOGIN_GUARD_MAX_PER_IP", "LOGIN_GUARD_MAX_PER_IP", 20), default=20
        ),
        window_seconds=_as_int(
            cfg("LOGIN_GUARD_WINDOW_SECONDS", "LOGIN_GUARD_WINDOW_SECONDS", 900),
            default=900,
            minimum=30,
        ),
        lock_seconds=_as_int(
            cfg("LOGIN_GUARD_LOCK_SECONDS", "LOGIN_GUARD_LOCK_SECONDS", 900),
            default=900,
            minimum=30,
        ),
    )


def _build_backend(app: Flask) -> object:
    storage_uri = str(
        app.config.get("RATELIMIT_STORAGE_URI")
        or app.config.get("REDIS_URL")
        or os.environ.get("REDIS_URL")
        or ""
    ).strip()
    if storage_uri.lower().startswith(_REDIS_URI_PREFIXES):
        try:
            import redis

            client = redis.Redis.from_url(
                storage_uri, socket_connect_timeout=0.25, socket_timeout=0.25
            )
            client.ping()
            app.logger.info("Login guard: store Redis attivo (%s).", storage_uri)
            return _RedisBackend(client)
        except Exception as exc:  # pragma: no cover - dipende dall'ambiente
            app.logger.warning(
                "Login guard: Redis non raggiungibile (%s), uso store in memoria.", exc
            )
    return _InMemoryBackend()


def get_login_guard(app: Flask) -> LoginAttemptGuard:
    """Ritorna (e memorizza) il guard di login per l'app corrente."""

    guard = app.extensions.get("login_attempt_guard")
    if isinstance(guard, LoginAttemptGuard):
        return guard
    guard = LoginAttemptGuard(_policy_from_config(app), _build_backend(app))
    app.extensions["login_attempt_guard"] = guard
    return guard


__all__ = [
    "LoginAttemptGuard",
    "LoginGuardPolicy",
    "get_login_guard",
]
