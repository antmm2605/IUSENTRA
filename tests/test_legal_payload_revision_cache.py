"""Exercise the exact route cache-key function without bootstrapping tenants."""
import ast
from pathlib import Path
from types import SimpleNamespace

from flask import Flask, g, request, current_app
from web.services.react_payload_cache import ReactPayloadTTLCache


def route_key():
    source = Path(__file__).parents[1] / "web/blueprints/api_v1_react.py"
    function = next(n for n in ast.parse(source.read_text()).body
                    if isinstance(n, ast.FunctionDef) and n.name == "_legal_intelligence_cache_key")
    namespace = {"request": request, "g": g, "current_app": current_app,
                 "_LEGAL_PAYLOAD_CACHE": ReactPayloadTTLCache()}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(source), "exec"), namespace)
    return namespace[function.name]


def test_changed_revision_and_owner_cannot_reuse_cached_payload(monkeypatch):
    snapshot = {"context": "tenant-user-a", "revisions": {"normativa": 11}}
    monkeypatch.setattr("web.services.operational_read_revision.read_authorized_revision_snapshot",
                        lambda _: snapshot)
    key = route_key()
    cache = ReactPayloadTTLCache()
    with Flask(__name__).test_request_context("/ricerca-legale"):
        g.tenant = SimpleNamespace(slug="studio-a")
        g.utente_corrente = object()
        first = key("ricerca-legale")
        cache.set(first, b"previous projection")
        assert cache.get(key("ricerca-legale")) == b"previous projection"
        snapshot["revisions"]["normativa"] = 12
        assert cache.get(key("ricerca-legale")) is None
        snapshot["revisions"]["normativa"] = 11
        snapshot["context"] = "tenant-user-b"
        assert cache.get(key("ricerca-legale")) is None
        snapshot["context"] = "tenant-user-a"
        snapshot["revisions"]["fascicoli"] = 4
        assert cache.get(key("ricerca-legale")) is None


def test_unconfirmed_revision_disables_cache_and_queries_remain_live(monkeypatch):
    def unavailable(_):
        raise RuntimeError("revision unavailable")
    monkeypatch.setattr("web.services.operational_read_revision.read_authorized_revision_snapshot", unavailable)
    key = route_key()
    app = Flask(__name__)
    with app.test_request_context("/ricerca-legale"):
        assert key("ricerca-legale") is None
    with app.test_request_context("/ricerca-legale?q=mediazione"):
        assert key("ricerca-legale") is None
