from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("embedding_gateway", Path(__file__).resolve().parents[1] / "deploy/private-lex/embedding_docker_gateway.py")
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


@pytest.mark.parametrize("peer,expected", [("172.18.0.3", True), ("172.17.0.2", True), ("100.121.124.9", False), ("8.8.8.8", False), ("127.0.0.1", False), ("invalid", False)])
def test_network_is_local_docker_only(peer, expected):
    assert gateway.allowed_peer(peer) is expected


@pytest.mark.parametrize("path,payload", [("/api/chat", {"model": gateway.MODEL}), ("/api/generate", {"model": gateway.MODEL}), ("/api/pull", {"model": gateway.MODEL}), ("/api/embed?url=http://external", {"model": gateway.MODEL}), ("/api/embed", {"model": "other", "input": "x"}), ("/api/embed", {"model": gateway.MODEL, "input": "x", "options": {"num_gpu": 99}}), ("/api/embed", {"model": gateway.MODEL, "input": ["x"] * 33})])
def test_generation_other_models_and_options_are_denied(path, payload):
    with pytest.raises(ValueError):
        gateway.validate("POST", path, payload)


def test_real_embedder_contract_is_allowed():
    body = {"model": gateway.MODEL, "input": ["task: search result | query: prova"], "truncate": True, "keep_alive": "24h"}
    assert gateway.validate("POST", "/api/embed", body) == body
    assert gateway.validate("GET", "/api/tags") is None


def test_tags_hide_generation_models_and_preserve_digest(monkeypatch):
    class Reply:
        status = 200
        def read(self, limit):
            return b'{"models":[{"name":"embeddinggemma:300m","digest":"expected"},{"name":"private-35b"}]}'
    class Connection:
        def __init__(self, host, port, timeout):
            assert (host, port) == ("127.0.0.1", 11434)
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Reply()
        def close(self):
            pass
    monkeypatch.setattr(gateway.http.client, "HTTPConnection", Connection)
    assert gateway.forward("GET", "/api/tags", None) == (200, {"models": [{"name": gateway.MODEL, "digest": "expected"}]})


def test_gateway_has_dedicated_port_and_loopback_upstream_is_separate():
    assert gateway.BIND == "172.17.0.1"
    assert gateway.BIND_PORT == 11435


def test_embedding_serializzato_con_modello_tenuto_caricato():
    """Decisione del 19/11/2026: una richiesta alla volta e keep_alive lungo per embeddinggemma."""
    assert gateway.IN_FLIGHT._initial_value == 1
    body = {"model": gateway.MODEL, "input": ["prova"]}
    assert gateway.validate("POST", "/api/embed", body)["keep_alive"] == gateway.KEEP_ALIVE == "24h"


def test_risposta_400_di_ollama_porta_il_motivo(monkeypatch):
    class Reply:
        status = 400
        def read(self, limit):
            return b'{"error":"the input length exceeds the context length"}'
    class Connection:
        def __init__(self, host, port, timeout):
            pass
        def request(self, *args, **kwargs):
            pass
        def getresponse(self):
            return Reply()
        def close(self):
            pass
    monkeypatch.setattr(gateway.http.client, "HTTPConnection", Connection)
    stato, corpo = gateway.forward("POST", "/api/embed", {"model": gateway.MODEL, "input": ["x"]})
    assert stato == 400 and corpo["motivo"] == "the input length exceeds the context length"
