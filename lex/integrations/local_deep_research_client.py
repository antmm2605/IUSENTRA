"""Governed HTTP bridge from Lex to Local Deep Research.

The sidecar is useful for public legal research, news, doctrine and scenario
analysis. It is not a free channel for client data: by default the client
blocks queries containing identifiers or studio-reserved legal context before
opening an HTTP session with Local Deep Research.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import os
import time
from typing import Any

import requests

from lex.gateway.privacy_guard import PrivacyGuard, PrivacyResult


IDENTIFYING_REASONS = {
    "email",
    "codice_fiscale",
    "partita_iva_o_numero_11_cifre",
    "telefono",
    "iban",
    "numero_rg",
}

RESERVED_LEGAL_REASONS = {
    "termine_legale:cliente",
    "termine_legale:controparte",
    "termine_legale:fascicolo",
    "termine_legale:polisweb",
    "termine_legale:pst",
    "termine_legale:pdp",
    "termine_legale:pat",
    "termine_legale:ptt",
    "termine_legale:procura alle liti",
    "termine_legale:documento allegato",
    "termine_legale:consulenza legale",
}


class LocalDeepResearchError(RuntimeError):
    """Raised when Local Deep Research returns an unusable response."""


class LocalDeepResearchPolicyError(LocalDeepResearchError):
    """Raised when a query violates IUSENTRA/Lex privacy policy."""


class _CsrfInputParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.token: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "input":
            return
        values = {key: value for key, value in attrs}
        if values.get("name") == "csrf_token" and values.get("value"):
            self.token = values["value"]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "si", "s", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise LocalDeepResearchError(f"Variabile {name} non numerica: {value!r}") from exc


def _extract_login_csrf(html: str) -> str:
    parser = _CsrfInputParser()
    parser.feed(html)
    if not parser.token:
        raise LocalDeepResearchError("CSRF token non trovato nella pagina di login LDR.")
    return parser.token


def _blocked_reasons(result: PrivacyResult) -> list[str]:
    reasons = set(result.reasons)
    return sorted((reasons & IDENTIFYING_REASONS) | (reasons & RESERVED_LEGAL_REASONS))


@dataclass
class LocalDeepResearchClient:
    base_url: str = field(default_factory=lambda: os.getenv("LDR_BASE_URL", "http://local-deep-research:5000"))
    username: str = field(default_factory=lambda: os.getenv("LDR_USERNAME", ""))
    password: str = field(default_factory=lambda: os.getenv("LDR_PASSWORD", ""))
    timeout_seconds: int = field(default_factory=lambda: _env_int("LDR_TIMEOUT_SECONDS", 30))
    allow_sensitive: bool = field(default_factory=lambda: _env_bool("LDR_ALLOW_SENSITIVE", False))
    session: requests.Session | None = field(default=None, repr=False)
    privacy_guard: PrivacyGuard = field(default_factory=PrivacyGuard, repr=False)

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if self.session is None:
            self.session = requests.Session()
        self._csrf_token: str | None = None

    def is_configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    def classify_query(self, query: str) -> PrivacyResult:
        return self.privacy_guard.classify_text(query)

    def validate_query_policy(self, query: str, *, allow_sensitive: bool | None = None) -> PrivacyResult:
        if not query.strip():
            raise ValueError("La query di ricerca non puo' essere vuota.")

        result = self.classify_query(query)
        effective_allow = self.allow_sensitive if allow_sensitive is None else allow_sensitive
        blocked = _blocked_reasons(result)
        if blocked and not effective_allow:
            raise LocalDeepResearchPolicyError(
                "Query non inviata a Local Deep Research: contiene dati o contesto "
                "riservati allo studio. Usa il retrieval tenant-aware di Lex oppure "
                f"riformula la ricerca su fonti pubbliche. Motivi: {', '.join(blocked)}."
            )
        return result

    def login(self) -> None:
        if not self.username or not self.password:
            raise LocalDeepResearchError("Imposta LDR_USERNAME e LDR_PASSWORD prima di usare il bridge LDR.")
        assert self.session is not None

        login_page = self.session.get(f"{self.base_url}/auth/login", timeout=self.timeout_seconds)
        login_page.raise_for_status()
        login_csrf = _extract_login_csrf(login_page.text)

        response = self.session.post(
            f"{self.base_url}/auth/login",
            data={
                "username": self.username,
                "password": self.password,
                "csrf_token": login_csrf,
            },
            timeout=self.timeout_seconds,
            allow_redirects=True,
        )
        response.raise_for_status()

        csrf_response = self.session.get(f"{self.base_url}/auth/csrf-token", timeout=self.timeout_seconds)
        csrf_response.raise_for_status()
        payload = csrf_response.json()
        self._csrf_token = payload.get("csrf_token")
        if not self._csrf_token:
            raise LocalDeepResearchError("Token CSRF API LDR non ricevuto dopo il login.")

    def _headers(self) -> dict[str, str]:
        if not self._csrf_token:
            self.login()
        assert self._csrf_token is not None
        return {"X-CSRF-Token": self._csrf_token}

    def start_research(
        self,
        query: str,
        *,
        search_engines: list[str] | None = None,
        iterations: int = 2,
        model: str | None = None,
        allow_sensitive: bool | None = None,
    ) -> str:
        self.validate_query_policy(query, allow_sensitive=allow_sensitive)
        if iterations < 1:
            raise ValueError("iterations deve essere almeno 1.")
        assert self.session is not None

        body: dict[str, Any] = {
            "query": query,
            "search_engines": search_engines or ["searxng"],
            "iterations": iterations,
        }
        if model:
            body["model"] = model

        response = self.session.post(
            f"{self.base_url}/api/start_research",
            json=body,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        research_id = payload.get("research_id")
        if not research_id:
            raise LocalDeepResearchError(f"Risposta LDR senza research_id: {payload}")
        return str(research_id)

    def get_status(self, research_id: str) -> dict[str, Any]:
        assert self.session is not None
        response = self.session.get(
            f"{self.base_url}/api/research/{research_id}/status",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def get_report(self, research_id: str) -> dict[str, Any]:
        assert self.session is not None
        response = self.session.get(
            f"{self.base_url}/api/report/{research_id}",
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def research_and_wait(
        self,
        query: str,
        *,
        search_engines: list[str] | None = None,
        iterations: int = 2,
        model: str | None = None,
        max_wait_seconds: int = 900,
        poll_seconds: int = 5,
        allow_sensitive: bool | None = None,
    ) -> dict[str, Any]:
        research_id = self.start_research(
            query,
            search_engines=search_engines,
            iterations=iterations,
            model=model,
            allow_sensitive=allow_sensitive,
        )
        deadline = time.monotonic() + max_wait_seconds

        while time.monotonic() < deadline:
            status = self.get_status(research_id)
            state = str(status.get("status", "")).lower()
            if state == "completed":
                return self.get_report(research_id)
            if state in {"failed", "error", "cancelled", "terminated"}:
                raise LocalDeepResearchError(f"Ricerca LDR fallita: {status}")
            time.sleep(poll_seconds)

        raise TimeoutError(f"Ricerca LDR non conclusa entro {max_wait_seconds} secondi: {research_id}")
