from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from lex.integrations.local_deep_research_client import (
    LocalDeepResearchClient,
    LocalDeepResearchPolicyError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class DummyResponse:
    def __init__(self, *, text: str = "", payload: dict[str, Any] | None = None, status_code: int = 200) -> None:
        self.text = text
        self._payload = payload or {}
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._payload


class DummySession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def get(self, url: str, **kwargs: Any) -> DummyResponse:
        self.calls.append(("GET", url, kwargs))
        if url.endswith("/auth/login"):
            return DummyResponse(text='<input name="csrf_token" value="login-csrf">')
        if url.endswith("/auth/csrf-token"):
            return DummyResponse(payload={"csrf_token": "api-csrf"})
        if url.endswith("/api/research/R-1/status"):
            return DummyResponse(payload={"status": "completed"})
        if url.endswith("/api/report/R-1"):
            return DummyResponse(payload={"summary": "ricerca completata", "sources": []})
        raise AssertionError(url)

    def post(self, url: str, **kwargs: Any) -> DummyResponse:
        self.calls.append(("POST", url, kwargs))
        if url.endswith("/auth/login"):
            assert kwargs["data"]["csrf_token"] == "login-csrf"
            return DummyResponse(payload={"ok": True})
        if url.endswith("/api/start_research"):
            assert kwargs["headers"] == {"X-CSRF-Token": "api-csrf"}
            assert kwargs["json"]["search_engines"] == ["searxng"]
            return DummyResponse(payload={"research_id": "R-1"})
        raise AssertionError(url)


def test_client_esegue_login_csrf_ricerca_polling_e_report_senza_live_http(monkeypatch):
    session = DummySession()
    client = LocalDeepResearchClient(
        base_url="http://ldr.test",
        username="utente",
        password="password",
        session=session,
    )
    monkeypatch.setattr("time.sleep", lambda seconds: None)

    report = client.research_and_wait(
        "Aggiornamenti recenti sulla mediazione civile obbligatoria in Italia",
        iterations=1,
    )

    assert report["summary"] == "ricerca completata"
    assert [call[0] for call in session.calls] == ["GET", "POST", "GET", "POST", "GET", "GET"]


def test_client_blocca_query_con_dati_di_fascicolo_prima_del_login():
    session = DummySession()
    client = LocalDeepResearchClient(
        base_url="http://ldr.test",
        username="utente",
        password="password",
        session=session,
    )

    with pytest.raises(LocalDeepResearchPolicyError) as exc:
        client.start_research("Fascicolo RG 1234/2024 del cliente RSSMRA80A01H501U")

    assert "retrieval tenant-aware di Lex" in str(exc.value)
    assert session.calls == []


def test_compose_ldr_usa_profili_data_root_e_credenziali_non_committate():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.ldr.yml").read_text(encoding="utf-8"))
    ldr = compose["services"]["local-deep-research"]
    searxng = compose["services"]["searxng"]
    app_env = compose["services"]["app"]["environment"]

    assert ldr["profiles"] == ["ldr"]
    assert ldr["ports"] == ["${LDR_BIND_ADDR:-127.0.0.1}:${LDR_PORT:-5000}:5000"]
    assert "${IUSENTRA_DATA_DIR:-./data}/local-deep-research:/data" in ldr["volumes"]
    assert "${IUSENTRA_DATA_DIR:-./data}/searxng:/etc/searxng" in searxng["volumes"]
    assert app_env["LDR_USERNAME"] == "${LDR_USERNAME:-}"
    assert app_env["LDR_PASSWORD"] == "${LDR_PASSWORD:-}"
    assert app_env["LEX_EXTERNAL_ALLOWED"] == "0"


def test_ollama_sidecar_resta_su_loopback_e_ha_healthcheck():
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    ollama = compose["services"]["ollama"]

    assert ollama["ports"] == ["127.0.0.1:11434:11434"]
    assert ollama["healthcheck"]["test"] == ["CMD", "ollama", "list"]
