from __future__ import annotations

from types import SimpleNamespace

from web.services import react_practice_engine_bridge as bridge


class _Fascicoli:
    def __init__(self, fascicolo=None):
        self._fascicolo = fascicolo

    def get(self, fascicolo_id):
        return self._fascicolo if self._fascicolo and self._fascicolo.id == fascicolo_id else None


class _Clienti:
    def get(self, _id_cliente):
        return SimpleNamespace(id="C1", nome="Cliente")


def test_regia_usa_metodi_scoped_quando_disponibili(monkeypatch):
    fascicolo = SimpleNamespace(id="F1", id_cliente="C1")
    calls: list[str] = []

    class Preventivi:
        def preventivi_per_fascicolo(self, fascicolo_id):
            calls.append(f"preventivi:{fascicolo_id}")
            return ["preventivo-scoped"]

        def conferimenti_per_fascicolo(self, fascicolo_id):
            calls.append(f"conferimenti:{fascicolo_id}")
            return ["conferimento-scoped"]

        def tutti_preventivi(self):
            raise AssertionError("fallback preventivi non deve essere usato")

    class Fatturazione:
        def per_fascicolo(self, fascicolo_id):
            calls.append(f"parcelle:{fascicolo_id}")
            return ["parcella-scoped"]

        def tutte(self):
            raise AssertionError("fallback parcelle non deve essere usato")

    captured = {}

    def _fake_build(repo, **kwargs):
        captured.update(kwargs)
        return {"source": "repository reale", "mock_fallback": False, "page_state": "operativa"}

    monkeypatch.setattr(bridge, "build_regia_payload", _fake_build)

    payload = bridge.build_react_practice_engine_payload(
        fascicolo_id="F1",
        get_fascicoli=lambda: _Fascicoli(fascicolo),
        get_clienti=lambda: _Clienti(),
        get_preventivi=Preventivi,
        get_fatturazione=Fatturazione,
        get_practice_engine=lambda: object(),
    )

    assert payload["mock_fallback"] is False
    assert calls == ["preventivi:F1", "conferimenti:F1", "parcelle:F1"]
    assert captured["preventivi"] == ["preventivo-scoped"]
    assert captured["conferimenti"] == ["conferimento-scoped"]
    assert captured["parcelle"] == ["parcella-scoped"]


def test_regia_fallback_solo_se_metodo_scoped_assente(monkeypatch):
    fascicolo = SimpleNamespace(id="F1", id_cliente="")

    class Preventivi:
        def tutti_preventivi(self):
            return ["preventivo-all"]

        def tutti_conferimenti(self):
            return ["conferimento-all"]

    class Fatturazione:
        def tutte(self):
            return ["parcella-all"]

    captured = {}
    monkeypatch.setattr(
        bridge,
        "build_regia_payload",
        lambda repo, **kwargs: captured.setdefault("kwargs", kwargs) or {"source": "repository reale", "mock_fallback": False, "page_state": "operativa"},
    )

    bridge.build_react_practice_engine_payload(
        fascicolo_id="F1",
        get_fascicoli=lambda: _Fascicoli(fascicolo),
        get_clienti=lambda: _Clienti(),
        get_preventivi=Preventivi,
        get_fatturazione=Fatturazione,
        get_practice_engine=lambda: object(),
    )

    assert captured["kwargs"]["preventivi"] == ["preventivo-all"]
    assert captured["kwargs"]["conferimenti"] == ["conferimento-all"]
    assert captured["kwargs"]["parcelle"] == ["parcella-all"]


def test_regia_fascicolo_non_trovato_resta_senza_mock():
    payload = bridge.build_react_practice_engine_payload(
        fascicolo_id="missing",
        get_fascicoli=lambda: _Fascicoli(None),
        get_clienti=lambda: _Clienti(),
        get_preventivi=lambda: object(),
        get_fatturazione=lambda: object(),
        get_practice_engine=lambda: object(),
    )

    assert payload["page_state"] == "non_trovato"
    assert payload["mock_fallback"] is False
