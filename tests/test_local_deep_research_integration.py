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


@pytest.mark.parametrize("input_value", [None, "", "  "])
def test_timeout_ldr_usa_il_default_se_non_configurato(monkeypatch, input_value):
    if input_value is None:
        monkeypatch.delenv("LDR_TIMEOUT_SECONDS", raising=False)
    else:
        monkeypatch.setenv("LDR_TIMEOUT_SECONDS", input_value)
    client = LocalDeepResearchClient()
    assert client.timeout_seconds == 30


def test_configurazione_ldr_convalida_timeout_e_credenziali(monkeypatch):
    from lex.integrations.local_deep_research_client import LocalDeepResearchError

    monkeypatch.setenv("LDR_TIMEOUT_SECONDS", "non numerico")
    with pytest.raises(LocalDeepResearchError, match="LDR_TIMEOUT_SECONDS"):
        LocalDeepResearchClient()
    monkeypatch.setenv("LDR_TIMEOUT_SECONDS", "12")
    monkeypatch.setenv("LDR_ALLOW_SENSITIVE", "false")
    client = LocalDeepResearchClient(base_url="http://ldr.test/", username="", password="")
    assert client.base_url == "http://ldr.test" and client.timeout_seconds == 12
    assert not client.allow_sensitive and not client.is_configured()
    with pytest.raises(LocalDeepResearchError, match="LDR_USERNAME"):
        client.login()


@pytest.mark.parametrize("risposta_mancante", ["login_csrf", "api_csrf", "research_id"])
def test_ldr_interrompe_il_flusso_se_manca_un_dato_del_protocollo(risposta_mancante):
    from lex.integrations.local_deep_research_client import LocalDeepResearchError

    class Sessione(DummySession):
        def get(self, url, **kwargs):
            if url.endswith("/auth/login") and risposta_mancante == "login_csrf":
                return DummyResponse(text="<form><p>Accedi</p><input name='username'></form>")
            if url.endswith("/auth/csrf-token") and risposta_mancante == "api_csrf":
                return DummyResponse()
            return super().get(url, **kwargs)

        def post(self, url, **kwargs):
            if url.endswith("/api/start_research"):
                assert kwargs["json"]["model"] == "modello-locale"
                if risposta_mancante == "research_id":
                    return DummyResponse()
            return super().post(url, **kwargs)

    client = LocalDeepResearchClient(base_url="http://ldr.test", username="test", password="fittizia", session=Sessione())
    assert client.is_configured()
    with pytest.raises(LocalDeepResearchError, match="CSRF|research_id"):
        client.start_research("Indice pubblico delle pubblicazioni", model="modello-locale")


def test_ldr_rifiuta_richiesta_vuota_o_iterazioni_nulle_prima_della_rete():
    session = DummySession()
    client = LocalDeepResearchClient(session=session)
    with pytest.raises(ValueError, match="vuota"):
        client.start_research("  ")
    with pytest.raises(ValueError, match="almeno 1"):
        client.start_research("Indice delle pubblicazioni", iterations=0)
    assert session.calls == []


@pytest.mark.parametrize("stato", ["failed", "running"])
def test_ldr_distingue_ricerca_fallita_da_tempo_massimo(monkeypatch, stato):
    from lex.integrations import local_deep_research_client as ldr

    class Sessione(DummySession):
        def get(self, url, **kwargs):
            if url.endswith("/status"):
                return DummyResponse(payload={"status": stato})
            return super().get(url, **kwargs)

    client = LocalDeepResearchClient(base_url="http://ldr.test", username="test", password="fittizia", session=Sessione())
    tempi = iter((0, 0.5, 2))
    pause = []
    monkeypatch.setattr(ldr, "time", type("Orologio", (), {
        "monotonic": staticmethod(lambda: next(tempi)), "sleep": staticmethod(pause.append),
    }))
    errore = TimeoutError if stato == "running" else ldr.LocalDeepResearchError
    with pytest.raises(errore, match="non conclusa|fallita"):
        client.research_and_wait("Indice pubblico delle pubblicazioni", max_wait_seconds=1, poll_seconds=1)
    assert pause == ([1] if stato == "running" else [])
