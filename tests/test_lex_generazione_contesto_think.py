"""Allineamento produzione/dataset: num_ctx di Lex e think=False anche su /api/generate e sul gateway."""

from __future__ import annotations

import requests

from lex.gateway import config as gateway_config
from lex.gateway.config import GatewayConfig, ProviderConfig
from lex.gateway.messages import ChatMessage
from lex.gateway.providers import ollama as gateway_ollama
from pct import local_ai
from pct.local_ai import OllamaHttpClient, _genera_risposta_completa


class _Risposta:
    def __init__(self, status_code: int = 200, payload: dict | None = None, text: str = ""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


def test_generate_fascicolo_passa_num_ctx_e_think_false(monkeypatch):
    monkeypatch.setenv("LEX_NUM_CTX", "8192")
    inviati: list[dict] = []

    def _request(method, url, json=None, timeout=None):
        inviati.append(json)
        return _Risposta(payload={"response": "ok"})

    monkeypatch.setattr(local_ai.requests, "request", _request)
    client = OllamaHttpClient("http://ollama:11434/api")
    risposta = _genera_risposta_completa(client, "qwen3.5:9b", "prompt lungo", keep_alive="10m")

    assert risposta["response"] == "ok"
    assert inviati[0]["options"] == {"num_ctx": 8192}
    assert inviati[0]["think"] is False
    assert inviati[0]["model"] == "qwen3.5:9b" and inviati[0]["keep_alive"] == "10m"


def test_generate_fascicolo_ripete_senza_think_se_il_modello_non_lo_supporta(monkeypatch):
    monkeypatch.setenv("LEX_NUM_CTX", "4096")
    inviati: list[dict] = []

    def _request(method, url, json=None, timeout=None):
        inviati.append(dict(json))
        if "think" in json:
            return _Risposta(400, text='{"error":"model does not support thinking (think)"}')
        return _Risposta(payload={"response": "ok"})

    monkeypatch.setattr(local_ai.requests, "request", _request)
    client = OllamaHttpClient("http://ollama-think-test:11434/api")
    assert _genera_risposta_completa(client, "gemma3:1b", "p", keep_alive="5m")["response"] == "ok"
    assert [("think" in p) for p in inviati] == [True, False]
    assert inviati[1]["options"] == {"num_ctx": 4096}


def test_generate_fascicolo_client_minimo_usa_generate():
    chiamate: list[tuple] = []

    class _ClientMinimo:
        def generate(self, model_name, prompt, keep_alive="10m"):
            chiamate.append((model_name, prompt, keep_alive))
            return {"response": "ok"}

    assert _genera_risposta_completa(_ClientMinimo(), "m", "p", keep_alive="1m") == {"response": "ok"}
    assert chiamate == [("m", "p", "1m")]


def _provider() -> gateway_ollama.OllamaProvider:
    return gateway_ollama.OllamaProvider(
        ProviderConfig(name="ollama", kind="ollama", base_url="http://ollama:11434", default_model="qwen3.5:9b", is_local=True)
    )


def test_gateway_ollama_payload_con_num_ctx_e_think_false(monkeypatch):
    monkeypatch.setenv("LEX_NUM_CTX", "8192")
    inviati: list[dict] = []

    def _post(url, json=None, timeout=None):
        inviati.append(json)
        return _Risposta(payload={"message": {"content": "Bozza."}})

    monkeypatch.setattr(gateway_ollama.requests, "post", _post)
    risposta = _provider().chat([ChatMessage(role="user", content="Redigi")], temperature=0.1, max_tokens=900)

    assert risposta.content == "Bozza." and risposta.model == "qwen3.5:9b"
    assert inviati[0]["options"] == {"temperature": 0.1, "num_predict": 900, "num_ctx": 8192}
    assert inviati[0]["think"] is False


def test_gateway_ollama_ripete_senza_think(monkeypatch):
    inviati: list[dict] = []

    def _post(url, json=None, timeout=None):
        inviati.append(dict(json))
        if "think" in json:
            return _Risposta(400, text='"think" value is not supported for this model')
        return _Risposta(payload={"message": {"content": "ok"}})

    monkeypatch.setattr(gateway_ollama.requests, "post", _post)
    assert _provider().chat([ChatMessage(role="user", content="x")]).content == "ok"
    assert [("think" in p) for p in inviati] == [True, False]
    assert inviati[1]["options"]["num_ctx"] == 8192


def test_modello_gateway_segue_il_modello_chat_di_lex_non_il_catalogo(monkeypatch):
    for nome in ("LEX_DEFAULT_MODEL", "PCT_LOCAL_AI_CHAT_MODEL", "PCT_LEX_CATALOGO_MODELLO", "OLLAMA_DEFAULT_MODEL"):
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("PCT_LEX_CATALOGO_MODELLO", "maternion/spark-x2.5:4b")
    monkeypatch.setattr(gateway_config, "_modello_chat_lex", lambda: "qwen3.5:9b")
    cfg = GatewayConfig.from_env()
    assert cfg.default_model == "qwen3.5:9b"
    assert cfg.providers["ollama"].default_model == "qwen3.5:9b"

    # senza runtime Lex: prima il modello chat locale, il catalogo solo come ultima riserva
    monkeypatch.setattr(gateway_config, "_modello_chat_lex", lambda: "")
    monkeypatch.setenv("PCT_LOCAL_AI_CHAT_MODEL", "gemma3:12b")
    assert GatewayConfig.from_env().default_model == "gemma3:12b"
    monkeypatch.delenv("PCT_LOCAL_AI_CHAT_MODEL")
    assert GatewayConfig.from_env().default_model == "maternion/spark-x2.5:4b"

    # LEX_DEFAULT_MODEL esplicito prevale sempre
    monkeypatch.setenv("LEX_DEFAULT_MODEL", "llama3.1:8b")
    monkeypatch.setattr(gateway_config, "_modello_chat_lex", lambda: "qwen3.5:9b")
    assert GatewayConfig.from_env().default_model == "llama3.1:8b"


def test_modello_chat_lex_fuori_contesto_flask_e_vuoto():
    assert gateway_config._modello_chat_lex() == ""
