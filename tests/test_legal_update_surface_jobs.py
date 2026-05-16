from __future__ import annotations

from types import SimpleNamespace


def test_legal_update_scan_admin_usa_job_con_timeout(monkeypatch):
    import web.services.legal_update_surface as surface

    class _Repo:
        def upsert_sources(self, rows):
            self.rows = rows

        def list_sources(self, *, enabled_only):
            assert enabled_only is True
            return [{"code": "normattiva"}, {"code": "cassazione_massimario"}]

    fake_pipeline = SimpleNamespace(repository=_Repo())
    captured: dict[str, object] = {}

    def _fake_runner(config, **kwargs):
        captured["config"] = config
        captured.update(kwargs)
        return {"ok": True, "reports": [], "autopublished": {"count": 0}}

    monkeypatch.setattr(surface, "build_legal_update_pipeline_runtime", lambda **kwargs: fake_pipeline)
    monkeypatch.setattr(surface, "run_legal_update_batch_with_timeouts", _fake_runner)

    result = surface.run_legal_update_action("scan")

    assert result["ok"] is True
    assert captured["source_codes"] == ["normattiva", "cassazione_massimario"]
    assert captured["item_timeout_seconds"] == 180
    assert captured["publish_max_items"] == 80


def test_legal_update_autopublish_admin_usa_job_per_elemento(monkeypatch):
    import web.services.legal_update_surface as surface

    captured: dict[str, object] = {}

    def _fake_publish(config, **kwargs):
        captured["config"] = config
        captured.update(kwargs)
        return {"ok": True, "published_count": 1, "reports": []}

    monkeypatch.setattr(surface, "build_legal_update_pipeline_runtime", lambda **kwargs: SimpleNamespace())
    monkeypatch.setattr(surface, "run_legal_update_publish_queue_with_timeouts", _fake_publish)

    result = surface.run_legal_update_action("autopublish")

    assert result["ok"] is True
    assert captured["item_timeout_seconds"] == 180
    assert captured["max_items"] == 80
