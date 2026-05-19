from __future__ import annotations

from types import SimpleNamespace


def test_legal_update_scan_admin_usa_autofetch_governato(monkeypatch):
    import web.services.legal_update_surface as surface

    class _Repo:
        def upsert_sources(self, rows):
            self.rows = rows

        def list_sources(self, *, enabled_only):
            assert enabled_only is False
            return [
                {"code": "cassazione_ultime_sent_ord_questioni", "enabled": True},
                {"code": "corte_conti", "enabled": True},
                {"code": "curia_cgue_rss", "enabled": True},
                {"code": "inps_circolari", "enabled": True},
                {"code": "inps_messaggi", "enabled": True},
                {"code": "agcom_provvedimenti", "enabled": True},
                {"code": "anac_documenti", "enabled": True},
                {"code": "garante_privacy", "enabled": True},
                {"code": "gazzetta_ufficiale", "enabled": True},
                {"code": "openga_sentenze", "enabled": True},
            ]

    fake_pipeline = SimpleNamespace(repository=_Repo())
    captured: dict[str, object] = {}

    def _fake_autofetch(config, **kwargs):
        captured["config"] = config
        captured.update(kwargs)
        return {"ok": True, "schema": "iusentra.legal_update_autofetch.v1", "plan": {"selected_count": 2}}

    monkeypatch.setattr(surface, "build_legal_update_pipeline_runtime", lambda **kwargs: fake_pipeline)
    monkeypatch.setattr(surface, "run_legal_update_autofetch_tick", _fake_autofetch)

    result = surface.run_legal_update_action("scan")

    assert result["ok"] is True
    assert result["schema"] == "iusentra.legal_update_autofetch.v1"
    assert captured["source_codes"] == [
        "cassazione_ultime_sent_ord_questioni",
        "corte_conti",
        "curia_cgue_rss",
        "inps_circolari",
        "inps_messaggi",
        "agcom_provvedimenti",
        "anac_documenti",
        "garante_privacy",
        "gazzetta_ufficiale",
    ]
    assert captured["config"].item_timeout_seconds == 120
    assert captured["config"].publish_max_items == 5
    assert captured["config"].source_budget == 3


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
    assert captured["item_timeout_seconds"] == 120
    assert captured["max_items"] == 5


def test_job_fonte_running_stantio_viene_letto_da_verificare():
    import web.services.legal_update_surface as surface

    payload = surface._agent_status_payload(
        {
            "status": "running",
            "started_at": "2026-01-01T00:00:00Z",
            "timeout_seconds": 120,
            "documents_found": 1,
            "processed": 0,
        },
        source_code="cassazione_ultime_sent_ord_questioni",
    )

    assert payload["label"] == "Interrotto, da verificare"
    assert payload["class"] == "danger"
    assert "oltre il tempo atteso" in payload["message"]
