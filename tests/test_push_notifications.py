import json
import re
from types import SimpleNamespace
from pathlib import Path

from pct.auth import GestioneUtenti, RuoloUtente
from pct.notifications import NotificationRecord, NotificationRepository, NotificationService
from pct.notifications.service import PushDispatchSummary
from pct.notifications.generate_vapid import generate_vapid_key_pair
from pct.notifications.web_push import load_web_push_config, safe_web_push_payload, web_push_config_diagnostics
from tests.test_topbar_operational_api import _cfg_web, _create_user, _login
from web.app import create_app


WEB_PUSH_ENV = (
    "IUSENTRA_WEB_PUSH_ENABLED",
    "IUSENTRA_VAPID_PUBLIC_KEY",
    "IUSENTRA_VAPID_PRIVATE_KEY",
    "IUSENTRA_VAPID_SUBJECT",
)


def _repo(tmp_path) -> NotificationRepository:
    return NotificationRepository(tmp_path / "notifications.db")


def _notification(**overrides):
    data = {
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "type": "deadline",
        "priority": "urgent",
        "title": "Scadenza fascicolo riservato",
        "body": "Dettaglio visibile solo nel gestionale",
        "href": "/scadenziario/termine-1/modifica",
        "source_type": "deadline",
        "source_id": "termine-1",
        "dedupe_key": "deadline:termine-1",
    }
    data.update(overrides)
    return NotificationRecord(**data)


def _subscription_payload(endpoint="https://push.example/sub-1"):
    return {
        "endpoint": endpoint,
        "keys": {
            "p256dh": "p256dh-key",
            "auth": "auth-secret",
        },
        "deviceLabel": "Tablet studio",
    }


def _stored_user_id(app, username="operatore") -> str:
    with app.app_context():
        users = GestioneUtenti(
            db_path=app.config["AUTH_DB"],
            audit_path=app.config["AUDIT_DB"],
            secret_key=app.secret_key,
        ).tutti()
    for user in users:
        if user.username == username:
            return str(user.id or user.username)
    return username


def _enable_mobile_push(cfg: dict) -> dict:
    flags = dict(cfg.get("FEATURE_FLAGS") or {})
    flags["notifications.mobilePush"] = True
    cfg["FEATURE_FLAGS"] = flags
    return cfg


def test_generazione_vapid_produce_base64url_senza_padding():
    pair = generate_vapid_key_pair()

    assert pair.public_key
    assert pair.private_key
    assert "=" not in pair.public_key
    assert "=" not in pair.private_key
    assert re.fullmatch(r"[A-Za-z0-9_-]+", pair.public_key)
    assert re.fullmatch(r"[A-Za-z0-9_-]+", pair.private_key)
    assert len(pair.public_key) >= 80
    assert len(pair.private_key) >= 40


def test_load_web_push_config_configurazione_e_diagnostica(monkeypatch):
    for key in WEB_PUSH_ENV:
        monkeypatch.delenv(key, raising=False)

    assert load_web_push_config({}).configured is False
    assert load_web_push_config({"IUSENTRA_WEB_PUSH_ENABLED": "1"}).configured is False
    assert (
        load_web_push_config(
            {
                "IUSENTRA_WEB_PUSH_ENABLED": "1",
                "IUSENTRA_VAPID_PUBLIC_KEY": "public-key",
            }
        ).configured
        is False
    )
    config = load_web_push_config(
        {
            "IUSENTRA_WEB_PUSH_ENABLED": "1",
            "IUSENTRA_VAPID_PUBLIC_KEY": "public-key",
            "IUSENTRA_VAPID_PRIVATE_KEY": "private-key",
            "IUSENTRA_VAPID_SUBJECT": "mailto:admin@example.com",
        }
    )
    diagnostics = web_push_config_diagnostics(config, include_subject=True)

    assert config.configured is True
    assert diagnostics["configured"] is True
    assert diagnostics["missing"] == []
    assert diagnostics["hasPrivateKey"] is True
    assert "private-key" not in json.dumps(diagnostics)


def test_diagnostica_segnala_variabili_mancanti_senza_segreti(monkeypatch):
    for key in WEB_PUSH_ENV:
        monkeypatch.delenv(key, raising=False)

    diagnostics = web_push_config_diagnostics(
        {
            "IUSENTRA_WEB_PUSH_ENABLED": "0",
            "IUSENTRA_VAPID_PUBLIC_KEY": "",
            "IUSENTRA_VAPID_PRIVATE_KEY": "secret-private",
            "IUSENTRA_VAPID_SUBJECT": "mailto:admin@example.com",
        }
    )

    assert diagnostics["enabled"] is False
    assert diagnostics["hasPrivateKey"] is True
    assert "IUSENTRA_WEB_PUSH_ENABLED" in diagnostics["missing"]
    assert "IUSENTRA_VAPID_PUBLIC_KEY" in diagnostics["missing"]
    assert "IUSENTRA_VAPID_PRIVATE_KEY" not in diagnostics["missing"]
    assert "secret-private" not in json.dumps(diagnostics)


def test_repository_notifiche_crea_deduplica_e_marca_letta(tmp_path):
    repo = _repo(tmp_path)
    first, created = repo.upsert_notification(_notification())
    second, duplicated = repo.upsert_notification(_notification(body="Aggiornamento senza duplicato"))

    assert created is True
    assert duplicated is False
    assert first.id == second.id
    rows = repo.list_notifications("tenant-a", "user-a")
    assert len(rows) == 1
    assert rows[0].body == "Aggiornamento senza duplicato"

    assert repo.mark_read("tenant-a", "user-a", first.id) is True
    assert repo.list_notifications("tenant-a", "user-a")[0].read_at
    assert repo.list_notifications("tenant-b", "user-a") == []


def test_sync_operational_items_ritira_notifiche_pec_non_piu_generate(tmp_path):
    repo = _repo(tmp_path)
    service = NotificationService(repo)
    repo.upsert_notification(
        _notification(
            title="Classifica PEC e conferma adempimenti",
            body="Scadenza superata",
            source_id="old-pec-generic",
            dedupe_key="deadline:old-pec-generic",
        )
    )

    legacy_item = {
        "id": "PEC_AUDIT:msg-legacy:deadline",
        "type": "pec_deadline",
        "priority": "urgent",
        "title": "Ricevuta protocollo",
        "message": "Sono presenti anomalie non bloccanti: il software registra un promemoria operativo per chiuderle.",
        "href": "/scadenziario/legacy/modifica",
    }
    matrix_item = {
        "id": "PEC_AUDIT:msg-current:deadline",
        "type": "deadline",
        "priority": "important",
        "title": "VINCI ROSA MARIA - SENTENZA EX ART. 429, I comma CPC - RG 1754/2026",
        "message": "Cliente: VINCI ROSA MARIA. Parte/soggetto: Ricorrente principale. Leggere la sentenza e valutare notifica o impugnazione.",
        "href": "/scadenziario/current/modifica",
    }

    first_rows = service.sync_operational_items(tenant_id="tenant-a", user_id="user-a", items=[legacy_item, matrix_item])

    assert [row.dedupe_key for row in first_rows] == ["PEC_AUDIT:msg-current:deadline"]

    rows = service.sync_operational_items(tenant_id="tenant-a", user_id="user-a", items=[matrix_item])

    assert [row.dedupe_key for row in rows] == ["PEC_AUDIT:msg-current:deadline"]
    assert rows[0].title.startswith("VINCI ROSA MARIA")


def test_web_push_non_risponde_evento_gia_deduplicato(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    service = NotificationService(repo)
    calls = {"push": 0}

    def fake_dispatch(_record):
        calls["push"] += 1
        return PushDispatchSummary(configured=True, sent=1)

    monkeypatch.setattr(service, "dispatch_web_push", fake_dispatch)

    first = service.create_notification(
        tenant_id="tenant-a",
        user_id="user-a",
        type="pec_deadline",
        priority="important",
        title="Scadenza PEC registrata",
        body="Prima creazione",
        source_type="pec_deadline",
        source_id="msg-1",
        dedupe_key="PEC_AUDIT:msg-1:deadline",
        send_push=True,
    )
    second = service.create_notification(
        tenant_id="tenant-a",
        user_id="user-a",
        type="pec_deadline",
        priority="important",
        title="Scadenza PEC registrata",
        body="Aggiornamento interno",
        source_type="pec_deadline",
        source_id="msg-1",
        dedupe_key="PEC_AUDIT:msg-1:deadline",
        send_push=True,
    )

    assert first[1] is True
    assert second[1] is False
    assert calls["push"] == 1


def test_repository_subscription_salva_e_revoca_solo_tenant_utente(tmp_path):
    repo = _repo(tmp_path)
    service = NotificationService(repo)
    record = service.register_subscription(
        tenant_id="tenant-a",
        user_id="user-a",
        endpoint="https://push.example/sub-1",
        p256dh="p256dh",
        auth="auth",
        user_agent="pytest",
        device_label="Telefono",
    )
    service.register_subscription(
        tenant_id="tenant-b",
        user_id="user-a",
        endpoint="https://push.example/sub-1",
        p256dh="other",
        auth="other",
    )

    assert repo.list_active_subscriptions("tenant-a", "user-a")[0].id == record.id
    assert service.revoke_subscription(
        tenant_id="tenant-a",
        user_id="user-a",
        endpoint="https://push.example/sub-1",
    ) == 1
    assert repo.list_active_subscriptions("tenant-a", "user-a") == []
    assert len(repo.list_active_subscriptions("tenant-b", "user-a")) == 1


def test_api_public_key_senza_config_non_rompe_centro_notifiche(tmp_path):
    cfg = _enable_mobile_push(_cfg_web(tmp_path))
    cfg["NOTIFICATIONS_DB"] = str(tmp_path / "notifications" / "notifications.db")
    app = create_app(cfg)
    _create_user(app, "operatore", "Operatore123!", ruolo=RuoloUtente.AMMINISTRATORE)

    with app.test_client() as client:
        _login(client)
        response = client.get("/api/push/public-key")
        payload = response.get_json()

    assert response.status_code == 200
    assert payload["ok"] is False
    assert payload["configured"] is False
    assert payload["diagnostics"]["hasPublicKey"] is False
    assert "IUSENTRA_VAPID_PUBLIC_KEY" in payload["diagnostics"]["missing"]
    assert "non configurate" in payload["message"]


def test_api_public_key_richiede_autenticazione(tmp_path):
    cfg = _cfg_web(tmp_path)
    cfg["NOTIFICATIONS_DB"] = str(tmp_path / "notifications" / "notifications.db")
    app = create_app(cfg)

    with app.test_client() as client:
        response = client.get("/api/push/public-key")

    assert response.status_code == 401


def test_api_public_key_configurata_non_espone_private_key(tmp_path):
    cfg = _enable_mobile_push(_cfg_web(tmp_path))
    cfg.update(
        {
            "NOTIFICATIONS_DB": str(tmp_path / "notifications" / "notifications.db"),
            "IUSENTRA_WEB_PUSH_ENABLED": "1",
            "IUSENTRA_VAPID_PUBLIC_KEY": "public-key",
            "IUSENTRA_VAPID_PRIVATE_KEY": "private-key-secret",
            "IUSENTRA_VAPID_SUBJECT": "mailto:admin@example.com",
        }
    )
    app = create_app(cfg)
    _create_user(app, "operatore", "Operatore123!", ruolo=RuoloUtente.AMMINISTRATORE)

    with app.test_client() as client:
        _login(client)
        response = client.get("/api/push/public-key")
        payload = response.get_json()

    serialized = json.dumps(payload)
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["configured"] is True
    assert payload["publicKey"] == "public-key"
    assert payload["diagnostics"]["hasPrivateKey"] is True
    assert "private-key-secret" not in serialized
    assert "IUSENTRA_VAPID_PRIVATE_KEY" not in serialized


def test_api_subscribe_valida_payload_e_persistenza(tmp_path):
    cfg = _enable_mobile_push(_cfg_web(tmp_path))
    cfg["NOTIFICATIONS_DB"] = str(tmp_path / "notifications" / "notifications.db")
    app = create_app(cfg)
    _create_user(app, "operatore", "Operatore123!", ruolo=RuoloUtente.AMMINISTRATORE)

    with app.test_client() as client:
        assert client.post("/api/push/subscribe", json=_subscription_payload()).status_code == 401
        _login(client)
        invalid = client.post("/api/push/subscribe", json={"endpoint": "https://push.example/missing-keys"})
        valid = client.post("/api/push/subscribe", json=_subscription_payload(), headers={"User-Agent": "pytest"})

    assert invalid.status_code == 400
    assert valid.status_code == 200
    assert valid.get_json()["active"] is True
    repo = NotificationRepository(cfg["NOTIFICATIONS_DB"])
    rows = repo.list_active_subscriptions("default", _stored_user_id(app))
    assert len(rows) == 1
    assert rows[0].endpoint == "https://push.example/sub-1"


def test_api_revoca_subscription(tmp_path):
    cfg = _enable_mobile_push(_cfg_web(tmp_path))
    cfg["NOTIFICATIONS_DB"] = str(tmp_path / "notifications" / "notifications.db")
    app = create_app(cfg)
    _create_user(app, "operatore", "Operatore123!", ruolo=RuoloUtente.AMMINISTRATORE)

    with app.test_client() as client:
        _login(client)
        client.post("/api/push/subscribe", json=_subscription_payload())
        revoked = client.delete("/api/push/subscribe", json={"endpoint": "https://push.example/sub-1"})

    assert revoked.status_code == 200
    assert revoked.get_json()["revoked"] == 1
    repo = NotificationRepository(cfg["NOTIFICATIONS_DB"])
    assert repo.list_active_subscriptions("default", _stored_user_id(app)) == []


def test_api_test_push_mockato_invia_payload_non_sensibile(tmp_path, monkeypatch):
    cfg = _enable_mobile_push(_cfg_web(tmp_path))
    cfg.update(
        {
            "NOTIFICATIONS_DB": str(tmp_path / "notifications" / "notifications.db"),
            "IUSENTRA_WEB_PUSH_ENABLED": "1",
            "IUSENTRA_VAPID_PUBLIC_KEY": "public-key",
            "IUSENTRA_VAPID_PRIVATE_KEY": "private-key",
            "IUSENTRA_VAPID_SUBJECT": "mailto:admin@example.com",
        }
    )
    app = create_app(cfg)
    _create_user(app, "operatore", "Operatore123!", ruolo=RuoloUtente.AMMINISTRATORE)
    sent_payloads = []

    def fake_webpush(**kwargs):
        sent_payloads.append(json.loads(kwargs["data"]))

    from pct.notifications import web_push

    monkeypatch.setattr(web_push, "pywebpush", SimpleNamespace(webpush=fake_webpush))

    with app.test_client() as client:
        _login(client)
        client.post("/api/push/subscribe", json=_subscription_payload())
        response = client.post("/api/push/test", json={})
        notifications = client.get("/api/notifications").get_json()

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["sent"] == 1
    assert payload["notificationId"]
    assert any(
        item["id"] == payload["notificationId"] and item["type"] == "test"
        for item in notifications["items"]
    )
    assert sent_payloads[0]["title"] == "IUSENTRA"
    serialized = json.dumps(sent_payloads[0], ensure_ascii=False)
    for forbidden in ("Mario Rossi", "RSSMRA80A01H501U", "RG 123/2026", "EUR 1.000,00"):
        assert forbidden not in serialized


def test_endpoint_scaduto_viene_disabilitato(tmp_path, monkeypatch):
    cfg = _enable_mobile_push(_cfg_web(tmp_path))
    cfg.update(
        {
            "NOTIFICATIONS_DB": str(tmp_path / "notifications" / "notifications.db"),
            "IUSENTRA_WEB_PUSH_ENABLED": "1",
            "IUSENTRA_VAPID_PUBLIC_KEY": "public-key",
            "IUSENTRA_VAPID_PRIVATE_KEY": "private-key",
            "IUSENTRA_VAPID_SUBJECT": "mailto:admin@example.com",
        }
    )
    app = create_app(cfg)
    _create_user(app, "operatore", "Operatore123!", ruolo=RuoloUtente.AMMINISTRATORE)

    class Gone(Exception):
        response = SimpleNamespace(status_code=410)

    def fake_webpush(**_kwargs):
        raise Gone("gone")

    from pct.notifications import web_push

    monkeypatch.setattr(web_push, "pywebpush", SimpleNamespace(webpush=fake_webpush))

    with app.test_client() as client:
        _login(client)
        client.post("/api/push/subscribe", json=_subscription_payload())
        response = client.post("/api/push/test", json={})

    assert response.status_code == 200
    assert response.get_json()["disabled"] == 1
    repo = NotificationRepository(cfg["NOTIFICATIONS_DB"])
    assert repo.list_active_subscriptions("default", _stored_user_id(app)) == []


def test_payload_push_privacy_non_include_dati_sensibili():
    record = _notification(
        title="PEC Mario Rossi RG 123/2026",
        body="Codice fiscale RSSMRA80A01H501U e importo EUR 1.000,00",
        href="/email/messaggio/abc",
    )
    payload = safe_web_push_payload(record)
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["body"] == "IUSENTRA: evento urgente da verificare."
    for forbidden in ("Mario Rossi", "RSSMRA80A01H501U", "RG 123/2026", "EUR 1.000,00"):
        assert forbidden not in serialized


def test_payload_push_assistenza_remota_indica_studio_senza_dati_pratica():
    record = _notification(
        type="support_remote",
        priority="urgent",
        title="Richiesta assistenza Mario Rossi RG 123/2026",
        body="Mario Rossi chiede assistenza sul fascicolo RG 123/2026",
        href="/admin/supporto-remoto?sessione=abc",
        payload_json={"studioName": "Studio Verdi"},
    )
    payload = safe_web_push_payload(record)
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["title"] == "IUSENTRA Assistenza"
    assert payload["body"] == "Richiesta assistenza da Studio Verdi."
    assert payload["href"] == "/admin/supporto-remoto?sessione=abc"
    assert "Studio Verdi" in serialized
    for forbidden in ("Mario Rossi", "RG 123/2026"):
        assert forbidden not in serialized


def test_script_configure_web_push_non_stampa_private_key_di_default():
    script = Path("deploy/hetzner/configure_web_push.sh").read_text(encoding="utf-8")
    verify = Path("deploy/hetzner/verify_web_push.sh").read_text(encoding="utf-8")

    assert "--print-secrets" in script
    assert "Private key non stampata" in script
    assert not re.search(r"echo .*IUSENTRA_VAPID_PRIVATE_KEY", script)
    assert "private key: present" in verify
    assert "IUSENTRA_VAPID_PRIVATE_KEY={private_key}" not in verify
