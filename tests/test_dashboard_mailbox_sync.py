from __future__ import annotations

import threading
from pathlib import Path

from pct.config_studio import ConfigSMTP, ConfigStudio, GestioneConfigStudio
from pct.email_client import GestioneEmailRicevute
from tests.test_email_client import _autentica_admin_session, _cfg_web
from web.app import create_app
from web.services import mailbox_sync_runtime as runtime


def _paths(tmp_path: Path) -> dict[str, str]:
    return {
        "EMAIL_CASELLA_DB": str(tmp_path / "pec" / "casella.json"),
        "EMAIL_ORDINARIA_DB": str(tmp_path / "mail" / "ordinaria.json"),
        "STUDIO_CONFIG": str(tmp_path / "config" / "studio.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "fascicoli" / "archivio"),
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi" / "storico.json"),
    }


def test_mailbox_sync_runtime_salti_ravvicinati_per_cooldown(tmp_path, monkeypatch):
    runtime.clear_mailbox_sync_runtime_state()
    calls: list[str] = []

    def _fake_pec(ctx):
        calls.append(f"pec:{ctx.tenant_label}")
        return {"ok": True, "nuove": 1}

    def _fake_ordinary(ctx):
        calls.append(f"ordinary:{ctx.tenant_label}")
        return {"ok": True, "nuove": 2}

    monkeypatch.setattr(runtime, "run_pec_mailbox_sync", _fake_pec)
    monkeypatch.setattr(runtime, "run_ordinary_mailbox_sync", _fake_ordinary)

    first = runtime.sync_mailboxes_for_paths(_paths(tmp_path), tenant_label="studio-a", cooldown_seconds=180)
    second = runtime.sync_mailboxes_for_paths(_paths(tmp_path), tenant_label="studio-a", cooldown_seconds=180)

    assert first["pec"]["skipped"] is False
    assert first["ordinary"]["skipped"] is False
    assert second["pec"]["skipped"] is True
    assert second["pec"]["reason"] == "cooldown"
    assert second["ordinary"]["skipped"] is True
    assert calls == ["pec:studio-a", "ordinary:studio-a"]


def test_mailbox_sync_runtime_lock_concorrente_salti_already_running(tmp_path, monkeypatch):
    runtime.clear_mailbox_sync_runtime_state()
    entered = threading.Event()
    release = threading.Event()

    def _blocking_pec(ctx):
        entered.set()
        release.wait(timeout=5)
        return {"ok": True}

    monkeypatch.setattr(runtime, "run_pec_mailbox_sync", _blocking_pec)
    monkeypatch.setattr(runtime, "run_ordinary_mailbox_sync", lambda ctx: {"ok": True})
    paths = _paths(tmp_path)
    result_holder: dict[str, object] = {}

    thread = threading.Thread(
        target=lambda: result_holder.setdefault("first", runtime.sync_mailboxes_for_paths(paths, tenant_label="studio-a", cooldown_seconds=0)),
        daemon=True,
    )
    thread.start()
    assert entered.wait(timeout=5)

    second = runtime.sync_mailboxes_for_paths(paths, tenant_label="studio-a", cooldown_seconds=0)
    release.set()
    thread.join(timeout=5)

    assert second["pec"]["skipped"] is True
    assert second["pec"]["reason"] == "already_running"
    assert result_holder["first"]["pec"]["skipped"] is False


def test_dashboard_sync_mailboxes_endpoint_invalida_cache(tmp_path, monkeypatch):
    runtime.clear_mailbox_sync_runtime_state()
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)
    app.config["API_KEY"] = "react-test-key"
    headers = {"X-API-Key": "react-test-key"}

    monkeypatch.setattr(runtime, "run_pec_mailbox_sync", lambda ctx: {"ok": True, "nuove": 0})
    monkeypatch.setattr(runtime, "run_ordinary_mailbox_sync", lambda ctx: {"ok": True, "nuove": 0})

    with app.test_client() as client:
        first = client.get("/api/v1/ui/dashboard", headers=headers)
        second = client.get("/api/v1/ui/dashboard", headers=headers)
        sync = client.post("/api/v1/ui/dashboard/sync-mailboxes", headers=headers)
        after_sync = client.get("/api/v1/ui/dashboard", headers=headers)

    assert first.status_code == 200
    assert second.headers["X-IUSENTRA-Cache"] == "HIT"
    assert sync.status_code == 200
    assert sync.get_json()["pec"]["skipped"] is False
    assert after_sync.headers["X-IUSENTRA-Cache"] == "MISS"
    assert after_sync.get_json()["cache"]["ttl_seconds"] == 60


def test_route_manuali_sincronizzazione_restano_compatibili(tmp_path, monkeypatch):
    cfg = _cfg_web(tmp_path)
    app = create_app(cfg)

    import web.blueprints.email_client as email_client_routes
    import web.blueprints.email_ordinaria as email_ordinaria_routes

    monkeypatch.setattr(email_client_routes, "run_pec_mailbox_sync", lambda: {"ok": True, "messaggio": "PEC ok"})
    monkeypatch.setattr(email_ordinaria_routes, "run_ordinary_mailbox_sync", lambda: {"ok": True, "messaggio": "SMTP ok"})

    with app.test_client() as client:
        _autentica_admin_session(app, client, cfg)
        pec = client.post("/email/sincronizza")
        ordinary = client.post("/email-ordinaria/sincronizza")

    assert pec.status_code == 200
    assert pec.get_json()["messaggio"] == "PEC ok"
    assert ordinary.status_code == 200
    assert ordinary.get_json()["messaggio"] == "SMTP ok"


def test_sync_pec_e_ordinaria_usano_database_separati(tmp_path, monkeypatch):
    runtime.clear_mailbox_sync_runtime_state()
    paths = _paths(tmp_path)
    GestioneConfigStudio(paths["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(
            smtp=ConfigSMTP(
                host="smtp.example.it",
                port=587,
                username="studio@example.it",
                password="segreta",
                imap_host="imap.example.it",
                imap_port=993,
                imap_use_ssl=True,
            )
        )
    )
    ctx = runtime.mailbox_context_from_paths(paths, tenant_label="studio-a")
    observed: list[str] = []

    def _fake_sync(self, **kwargs):
        observed.append(str(self.db_path))
        return {"nuove": 0, "allegati_salvati": 0, "errore": ""}

    monkeypatch.setattr(GestioneEmailRicevute, "sincronizza_imap", _fake_sync)

    assert runtime.run_pec_mailbox_sync(ctx)["ok"] is True
    assert runtime.run_ordinary_mailbox_sync(ctx)["ok"] is True
    assert observed == [paths["EMAIL_CASELLA_DB"], paths["EMAIL_ORDINARIA_DB"]]
