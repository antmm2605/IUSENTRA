from __future__ import annotations

import threading
from pathlib import Path

import pytest

from pct.config_studio import ConfigPEC, ConfigSMTP, ConfigStudio, GestioneConfigStudio
from pct.email_client import GestioneEmailRicevute
from tests.test_email_client import _autentica_admin_session, _cfg_web
from web.app import create_app
from web.services import mailbox_sync_runtime as runtime
from web.services.tenant_paths import TenantDataPathError


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
        "STUDIO_DB": str(tmp_path / "studio.db"),
    }


def test_mailbox_sync_runtime_salti_ravvicinati_per_cooldown(tmp_path, monkeypatch):
    runtime.clear_mailbox_sync_runtime_state()
    calls: list[str] = []

    def _fake_pec(ctx, **_kwargs):
        calls.append(f"pec:{ctx.tenant_label}")
        return {"ok": True, "nuove": 1}

    def _fake_ordinary(ctx, **_kwargs):
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


def test_mailbox_sync_runtime_applica_limite_automatico(tmp_path, monkeypatch):
    runtime.clear_mailbox_sync_runtime_state()
    observed: list[tuple[str, int, bool]] = []

    def _fake_pec(ctx, *, limite: int, incremental_only: bool):
        observed.append(("pec", limite, incremental_only))
        return {"ok": True, "nuove": 1}

    def _fake_ordinary(ctx, *, limite: int, incremental_only: bool):
        observed.append(("ordinary", limite, incremental_only))
        return {"ok": True, "nuove": 2}

    monkeypatch.setattr(runtime, "run_pec_mailbox_sync", _fake_pec)
    monkeypatch.setattr(runtime, "run_ordinary_mailbox_sync", _fake_ordinary)

    report = runtime.sync_mailboxes_for_paths(
        _paths(tmp_path),
        tenant_label="studio-a",
        cooldown_seconds=0,
        limite=25,
    )

    assert report["pec"]["skipped"] is False
    assert report["ordinary"]["skipped"] is False
    assert observed == [("pec", 25, True), ("ordinary", 25, True)]


def test_mailbox_sync_runtime_incrementale_per_pec_e_ordinaria(tmp_path, monkeypatch):
    runtime.clear_mailbox_sync_runtime_state()
    observed: list[tuple[str, int, bool]] = []

    def _fake_pec(ctx, *, limite: int, incremental_only: bool):
        observed.append(("pec", limite, incremental_only))
        return {"ok": True, "nuove": 1}

    def _fake_ordinary(ctx, *, limite: int, incremental_only: bool):
        observed.append(("ordinary", limite, incremental_only))
        return {"ok": True, "nuove": 2}

    monkeypatch.setattr(runtime, "run_pec_mailbox_sync", _fake_pec)
    monkeypatch.setattr(runtime, "run_ordinary_mailbox_sync", _fake_ordinary)

    report = runtime.sync_mailboxes_for_paths(
        _paths(tmp_path),
        tenant_label="studio-a",
        cooldown_seconds=0,
        limite=25,
        incremental_only=True,
    )

    assert report["pec"]["skipped"] is False
    assert report["ordinary"]["skipped"] is False
    assert observed == [("pec", 25, True), ("ordinary", 25, True)]


def test_mailbox_sync_runtime_lock_concorrente_salti_already_running(tmp_path, monkeypatch):
    runtime.clear_mailbox_sync_runtime_state()
    entered = threading.Event()
    release = threading.Event()

    def _blocking_pec(ctx, **_kwargs):
        entered.set()
        release.wait(timeout=5)
        return {"ok": True}

    monkeypatch.setattr(runtime, "run_pec_mailbox_sync", _blocking_pec)
    monkeypatch.setattr(runtime, "run_ordinary_mailbox_sync", lambda ctx, **_kwargs: {"ok": True})
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
    cfg["MULTI_TENANT"] = False
    app = create_app(cfg)
    app.config["API_KEY"] = "react-test-key"
    headers = {"X-API-Key": "react-test-key"}

    monkeypatch.setattr(runtime, "run_pec_mailbox_sync", lambda ctx, **_kwargs: {"ok": True, "nuove": 0})
    monkeypatch.setattr(runtime, "run_ordinary_mailbox_sync", lambda ctx, **_kwargs: {"ok": True, "nuove": 0})

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
    cfg["MULTI_TENANT"] = False
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
    assert pec.get_json()["messaggio"] == "Sincronizzazione PEC completata."
    assert ordinary.status_code == 200
    assert ordinary.get_json()["messaggio"] == "Sincronizzazione email ordinaria completata."


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


def test_sync_pec_automatico_aggiorna_depositi_e_cancelleria(tmp_path, monkeypatch):
    runtime.clear_mailbox_sync_runtime_state()
    paths = _paths(tmp_path)
    GestioneConfigStudio(paths["STUDIO_CONFIG"]).aggiorna(
        ConfigStudio(
            pec=ConfigPEC(
                indirizzo="studio@example.invalid",
                password="segreta",
                smtp_host="smtp.example.invalid",
                smtp_port=465,
                imap_host="imap.example.invalid",
                imap_port=993,
                use_ssl=True,
            )
        )
    )
    ctx = runtime.mailbox_context_from_paths(paths, tenant_label="studio-a")
    observed: dict[str, str] = {}

    def _fake_workflow(gestione_email, gestione_fascicoli, config_pec, **kwargs):
        observed["email_db"] = str(gestione_email.db_path)
        observed["fascicoli_db"] = str(gestione_fascicoli.db_path)
        observed["state_path"] = str(kwargs.get("state_path", ""))
        observed["incremental_only"] = str(bool(kwargs.get("incremental_only")))
        observed["pec"] = config_pec.indirizzo
        return {
            "sync": {"nuove": 1, "pst_trovate": 1, "allegati_salvati": 0, "errore": ""},
            "auto_esiti": ["Fascicolo RG 1/2026: deposito aggiornato"],
            "poll": {"trovati": 1, "associati": 1, "duplicati": 0, "errori": 0},
        }

    monkeypatch.setattr("pct.email_client.sincronizza_pec_e_fascicoli", _fake_workflow)

    result = runtime.run_pec_mailbox_sync(ctx, limite=25)

    assert result["ok"] is True
    assert result["nuove"] == 1
    assert result["pst_trovate"] == 1
    assert result["esiti_aggiornati"] == 1
    assert result["comunicazioni_cancelleria"] == 1
    assert observed["email_db"] == paths["EMAIL_CASELLA_DB"]
    assert observed["fascicoli_db"] == paths["FASCICOLI_DB"]
    assert observed["pec"] == "studio@example.invalid"
    assert observed["incremental_only"] == "True"
    assert observed["state_path"].endswith("pec_cancelleria_state.json")


def test_mailbox_sync_multi_tenant_blocca_path_email_globali(tmp_path):
    app = create_app({**_cfg_web(tmp_path / "root"), "MULTI_TENANT": True})
    tenant_root = tmp_path / "tenants" / "studio-a"
    paths = _paths(tenant_root)
    paths["EMAIL_CASELLA_DB"] = str(tmp_path / "email" / "casella.json")

    with app.app_context(), pytest.raises(TenantDataPathError):
        ctx = runtime.mailbox_context_from_paths(paths, tenant_label="studio-a")
        runtime.run_pec_mailbox_sync(ctx)
