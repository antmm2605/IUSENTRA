import json
import re
from datetime import datetime, timedelta
from types import SimpleNamespace
from pathlib import Path
from zoneinfo import ZoneInfo

from pct.auth import GestioneUtenti, RuoloUtente
from pct.notifications import (
    NotificationPreferences,
    NotificationRecord,
    NotificationRepository,
    NotificationService,
)
from pct.notifications.service import PushDispatchSummary, _quiet_now
from pct.notifications.generate_vapid import generate_vapid_key_pair
from pct.notifications.web_push import (
    load_web_push_config,
    safe_remote_hearing_url,
    safe_web_push_payload,
    web_push_config_diagnostics,
)
from web.services.topbar_operational import (
    _notification as _topbar_notification,
    _notification_items,
    _notification_operational_sort_key,
    _record_to_topbar_item,
    _remote_hearing_notification_payload,
    agenda_scadenziario_notification_items,
)
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


def test_sync_operational_items_non_scade_record_worker_pec_fuori_finestra(tmp_path):
    repo = _repo(tmp_path)
    service = NotificationService(repo)
    worker, _created, _summary = service.create_notification(
        tenant_id="tenant-a",
        user_id="user-a",
        type="pec_deadline",
        priority="important",
        title="Udienza PEC registrata",
        body="Udienza futura già materializzata dal worker.",
        source_type="pec_deadline",
        source_id="msg-futuro",
        dedupe_key="PEC_AUDIT:msg-futuro:deadline",
        send_push=False,
    )
    service.create_notification(
        tenant_id="tenant-a",
        user_id="user-a",
        type="deadline",
        priority="important",
        title="Scadenza temporanea",
        body="Voce generata dalla finestra operativa.",
        source_type="deadline",
        source_id="deadline-temporanea",
        dedupe_key="deadline:temporanea:2026-12-31",
        send_push=False,
    )

    service.sync_operational_items(tenant_id="tenant-a", user_id="user-a", items=[])

    worker_after = repo.get_notification_by_dedupe_key(
        "tenant-a",
        "user-a",
        "PEC_AUDIT:msg-futuro:deadline",
    )
    temporary_after = repo.get_notification_by_dedupe_key(
        "tenant-a",
        "user-a",
        "deadline:temporanea:2026-12-31",
    )
    assert worker_after is not None
    assert worker_after.id == worker.id
    assert worker_after.expires_at == ""
    assert temporary_after is not None
    assert temporary_after.expires_at
    assert [row.dedupe_key for row in repo.list_notifications("tenant-a", "user-a")] == [
        "PEC_AUDIT:msg-futuro:deadline"
    ]


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


def test_web_push_risponde_solo_agli_arricchimenti_del_collegamento_audiovisivo(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    service = NotificationService(repo)
    calls: list[dict[str, object]] = []

    def fake_dispatch(record):
        calls.append(dict(record.payload_json))
        return PushDispatchSummary(configured=True, sent=1)

    monkeypatch.setattr(service, "dispatch_web_push", fake_dispatch)
    common = {
        "tenant_id": "tenant-a",
        "user_id": "user-a",
        "type": "pec_deadline",
        "priority": "important",
        "source_type": "pec_deadline",
        "source_id": "msg-udienza",
        "dedupe_key": "PEC_AUDIT:msg-udienza:deadline",
        "redispatch_on_remote_hearing_enrichment": True,
    }

    first = service.create_notification(
        **common,
        title="Scadenza PEC registrata",
        body="Prima acquisizione senza dati audiovisivi.",
        payload_json={"deadlineId": "scad-1"},
        send_push=False,
    )
    service.mark_read("tenant-a", "user-a", first[0].id)

    missing_link = service.create_notification(
        **common,
        title="Udienza audiovisiva registrata",
        body="Collegamento da acquisire dal documento.",
        payload_json={
            "deadlineId": "scad-1",
            "agendaId": "agenda-1",
            "remoteHearingDetected": True,
            "remoteHearingPdfRequired": True,
        },
        send_push=False,
    )
    accepted_link = service.create_notification(
        **common,
        title="Udienza audiovisiva registrata",
        body="Collegamento disponibile e da controllare.",
        payload_json={
            "deadlineId": "scad-1",
            "agendaId": "agenda-1",
            "remoteHearingDetected": True,
            "remoteHearingUrl": "https://teams.microsoft.com/l/meetup-join/19%3ameeting_test",
            "remoteHearingVerified": False,
        },
        send_push=False,
    )
    verified_link = service.create_notification(
        **common,
        title="Udienza audiovisiva registrata",
        body="Collegamento verificato e disponibile.",
        payload_json={
            "deadlineId": "scad-1",
            "agendaId": "agenda-1",
            "remoteHearingDetected": True,
            "remoteHearingUrl": "https://teams.microsoft.com/l/meetup-join/19%3ameeting_test",
            "remoteHearingVerified": True,
        },
        send_push=True,
    )
    unchanged = service.create_notification(
        **common,
        title="Udienza audiovisiva registrata",
        body="Collegamento verificato e disponibile.",
        payload_json=dict(verified_link[0].payload_json),
        send_push=True,
    )

    assert first[1] is True
    assert missing_link[1] is False
    assert missing_link[0].read_at != ""
    assert accepted_link[1] is False
    assert accepted_link[0].read_at != ""
    assert verified_link[1] is False
    assert verified_link[0].read_at == ""
    assert unchanged[1] is False
    assert len(calls) == 1
    assert calls[0]["remoteHearingVerified"] is True
    rows = repo.list_notifications("tenant-a", "user-a")
    assert len(rows) == 1
    assert rows[0].payload_json["remoteHearingVerified"] is True


def test_web_push_sync_avvisa_link_udienza_da_acquisire_senza_dati_sensibili(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    service = NotificationService(repo)
    calls: list[dict[str, object]] = []
    from web.services.pec_pipeline_runtime import build_pec_deadline_notification, should_send_pec_deadline_web_push

    access_info = (
        "Istruzioni per acquisire il link udienza: depositare o comunicare una nota "
        "nel fascicolo telematico entro il 05/11/2026 con indirizzo e-mail per ricevere "
        "il link e numero di telefono mobile per eventuali difficoltà di collegamento."
    )

    def fake_dispatch(record):
        calls.append(safe_web_push_payload(record))
        return PushDispatchSummary(configured=True, sent=1)

    monkeypatch.setattr(service, "dispatch_web_push", fake_dispatch)
    records = service.sync_operational_items(
        tenant_id="tenant-a",
        user_id="user-a",
        items=[
            {
                "id": "PEC_AUDIT:msg-link-da-acquisire:deadline",
                "type": "hearing",
                "priority": "urgent",
                "title": "Udienza audiovisiva registrata",
                "message": f"Presidio PEC automatico: {access_info}",
                "href": "/agenda/agenda-link-da-acquisire",
                "sourceType": "pec_deadline",
                "remoteHearingDetected": True,
                "remoteHearingPdfRequired": True,
                "remoteHearingAccessInfo": access_info,
            }
        ],
    )

    assert len(records) == 1
    assert len(calls) == 1
    assert calls[0]["title"] == "IUSENTRA · Udienza"
    assert calls[0]["body"] == "Udienza audiovisiva: controlla il collegamento in IUSENTRA."
    assert "remoteHearingUrl" not in calls[0]
    assert "indirizzo e-mail" not in json.dumps(calls[0], ensure_ascii=False)
    assert records[0].payload_json["remoteHearingPdfRequired"] is True
    assert records[0].payload_json["remoteHearingAccessInfo"] == access_info
    topbar_item = _record_to_topbar_item(records[0])
    assert "Istruzioni per acquisire il link udienza" in topbar_item["body"]
    assert topbar_item["secondaryLabel"] is None
    scheduler_notification = build_pec_deadline_notification(
        {
            "deadline_id": "SCAD-LINK",
            "agenda": {"agenda_id": "AGENDA-LINK"},
            "due_date": "2026-11-23",
            "remote_hearing": {
                "remote_hearing_detected": True,
                "remote_hearing_access_info": access_info,
                "remote_hearing_platform": "altra",
                "remote_hearing_pdf_required": True,
            },
        },
        source_id="msg-link-da-acquisire",
        automatic=True,
    )
    assert access_info in scheduler_notification["body"]
    assert scheduler_notification["payload_json"]["remoteHearingPlatform"] == ""
    assert should_send_pec_deadline_web_push(scheduler_notification) is True


def test_topbar_operativa_riporta_istruzioni_pdf_senza_piattaforma_generica(tmp_path):
    now = datetime(2026, 11, 22, 10, 0, tzinfo=ZoneInfo("Europe/Rome"))
    access_info = (
        "Istruzioni per acquisire il link udienza: depositare o comunicare una nota "
        "nel fascicolo telematico entro il 05/11/2026 con indirizzo e-mail per ricevere "
        "il link e numero di telefono mobile per eventuali difficoltà di collegamento."
    )
    deadline = SimpleNamespace(
        id="deadline-link-da-acquisire",
        id_appuntamento="",
        titolo="Fissazione udienza - 23/11/2026 - RG 393/2026",
        data_scadenza="2026-11-23",
        legal_due_at="",
        stato="APERTO",
        priorita="ALTA",
        perentorio=False,
        note="PEC_AUDIT:msg-link-da-acquisire\nLink udienza audiovisiva: da acquisire dal PDF allegato.",
        remote_hearing_detected=True,
        remote_hearing_mode="mista",
        remote_hearing_url="",
        remote_hearing_source="2141414s.pdf.zip",
        remote_hearing_verified=False,
        remote_hearing_time="15:00",
        remote_hearing_platform="altra",
        remote_hearing_meeting_id="",
        remote_hearing_passcode="",
        remote_hearing_access_info=access_info,
        remote_hearing_pdf_required=True,
    )

    class _AgendaStore:
        def tutti(self):
            return []

    class _DeadlineStore:
        def tutte(self, *args, **kwargs):
            return [deadline]

    app = create_app(_cfg_web(tmp_path))
    with app.app_context():
        items = agenda_scadenziario_notification_items(
            _AgendaStore(),
            _DeadlineStore(),
            now=now,
        )

    assert len(items) == 1
    assert items[0]["remoteHearingAccessInfo"] == access_info
    assert items[0]["remoteHearingPlatform"] == ""
    assert access_info in items[0]["message"]
    assert "Piattaforma: altra" not in items[0]["message"]


def test_topbar_ripulisce_piattaforma_generica_da_record_persistito():
    record = _notification(
        type="pec_deadline",
        title="Udienza PEC registrata",
        body="Presidio PEC automatico: udienza collegata ad Agenda e Scadenziario per il 08/10/2026. Piattaforma: altra",
        payload_json={
            "remoteHearingDetected": True,
            "remoteHearingMode": "audiovisiva",
            "remoteHearingPlatform": "altra",
        },
    )

    item = _record_to_topbar_item(record)

    assert item["message"] == "Presidio PEC automatico: udienza collegata ad Agenda e Scadenziario per il 08/10/2026."
    assert item["body"] == item["message"]
    assert item["secondaryHref"] is None
    assert "Piattaforma: altra" not in item["message"]


def test_notifiche_agenda_scadenziario_conservano_link_audiovisivo_fino_al_web_push(tmp_path):
    remote_url = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_agenda"
    hearing = SimpleNamespace(
        remote_hearing_detected=True,
        remote_hearing_mode="audiovisiva",
        remote_hearing_url=remote_url,
        remote_hearing_source="Decreto fissazione udienza: link udienza audiovisiva Microsoft Teams",
        remote_hearing_verified=True,
        remote_hearing_time="29/10/2026 ore 09:15",
        remote_hearing_platform="Microsoft Teams",
        remote_hearing_meeting_id="riunione-29-10",
        remote_hearing_passcode="codice-riservato",
        remote_hearing_access_info="Accesso tramite collegamento nel decreto.",
        remote_hearing_pdf_required=False,
    )
    remote_payload = _remote_hearing_notification_payload(hearing)
    item = _topbar_notification(
        "hearing:agenda-1:2026-10-29T09:15:00+02:00",
        "hearing",
        "Fissazione udienza",
        "29/10/2026 alle 09:15 · Collegamento audiovisivo verificato su Microsoft Teams",
        "2026-10-29T09:15:00+02:00",
        "important",
        "/agenda/agenda-1",
        "Apri agenda",
        payload=remote_payload,
    )

    repo = _repo(tmp_path)
    service = NotificationService(repo)
    records = service.sync_operational_items(
        tenant_id="tenant-a",
        user_id="user-a",
        items=[item],
    )

    assert len(records) == 1
    record = records[0]
    assert record.payload_json["remoteHearingUrl"] == remote_url
    assert record.payload_json["remoteHearingVerified"] is True
    assert record.payload_json["remoteHearingPlatform"] == "Microsoft Teams"
    assert record.payload_json["remoteHearingMeetingId"] == "riunione-29-10"
    assert record.payload_json["remoteHearingPasscode"] == "codice-riservato"
    topbar_item = _record_to_topbar_item(record)
    assert topbar_item["secondaryHref"] == remote_url
    assert topbar_item["secondaryLabel"] == "Collegati all'udienza"
    push_payload = safe_web_push_payload(record)
    assert push_payload["remoteHearingUrl"] == remote_url
    assert push_payload["title"] == "IUSENTRA · Udienza"
    assert "codice-riservato" not in json.dumps(push_payload, ensure_ascii=False)


def test_notifiche_imminenti_precedono_scadenze_urgenti_storiche():
    now = datetime(2026, 7, 17, 8, 0, tzinfo=ZoneInfo("Europe/Rome"))
    items = [
        {
            "priority": "urgent",
            "createdAt": f"{year}-01-10",
            "title": f"Scadenza storica {year}",
        }
        for year in range(1980, 2025)
    ]
    items.append(
        {
            "priority": "important",
            "createdAt": "2026-07-17T16:45:00+02:00",
            "title": "Udienza audiovisiva imminente",
        }
    )

    items.sort(key=lambda item: _notification_operational_sort_key(item, now=now))

    assert items[0]["title"] == "Udienza audiovisiva imminente"
    assert items[:40][-1]["title"] != "Udienza audiovisiva imminente"


def test_notifiche_non_duplicano_scadenza_collegata_a_udienza_imminente(monkeypatch, tmp_path):
    now = datetime.now(ZoneInfo("Europe/Rome"))
    remote_url = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_unica"
    appointment = SimpleNamespace(
        id="agenda-linked",
        external_uid="PEC_AUDIT:msg-linked:deadline",
        titolo="Fissazione udienza audiovisiva",
        tipo="UDIENZA",
        data_ora=(now.replace(microsecond=0) + timedelta(hours=2)).isoformat(),
        data_ora_dt=now.replace(microsecond=0) + timedelta(hours=2),
        remote_hearing_detected=False,
        remote_hearing_mode="",
        remote_hearing_url="",
        remote_hearing_source="",
        remote_hearing_verified=False,
        remote_hearing_platform="",
        remote_hearing_meeting_id="",
        remote_hearing_passcode="",
        remote_hearing_access_info="",
        remote_hearing_pdf_required=False,
    )
    deadline = SimpleNamespace(
        id="deadline-linked",
        id_appuntamento=appointment.id,
        note="PEC_AUDIT:msg-linked",
        titolo=appointment.titolo,
        data_scadenza=now.date().isoformat(),
        legal_due_at="",
        stato="APERTO",
        priorita="ALTA",
        perentorio=False,
        remote_hearing_detected=True,
        remote_hearing_mode="audiovisiva",
        remote_hearing_url=remote_url,
        remote_hearing_source="Decreto fissazione udienza",
        remote_hearing_verified=True,
        remote_hearing_platform="Microsoft Teams",
        remote_hearing_meeting_id="riunione-unica",
        remote_hearing_passcode="codice-unico",
        remote_hearing_access_info="Aprire il collegamento verificato.",
        remote_hearing_pdf_required=False,
    )

    class _Store:
        def __init__(self, rows):
            self.rows = rows

        def tutti(self, *args, **kwargs):
            return self.rows

        def tutte(self, *args, **kwargs):
            return self.rows

    monkeypatch.setattr(
        "web.services.topbar_operational._has_perm",
        lambda _user, permission: permission in {"agenda.leggi", "scadenziario.leggi"},
    )
    monkeypatch.setattr("web.services.topbar_operational.get_agenda", lambda: _Store([appointment]))
    monkeypatch.setattr("web.services.topbar_operational.get_scadenziario", lambda: _Store([deadline]))

    app = create_app(_cfg_web(tmp_path))
    with app.test_request_context("/api/notifications"):
        items = _notification_items(SimpleNamespace())

    matching = [item for item in items if item["title"] == appointment.titolo]
    assert len(matching) == 1
    assert matching[0]["id"] == "PEC_AUDIT:msg-linked:deadline"
    assert matching[0]["sourceType"] == "pec_deadline"
    assert matching[0]["type"] == "hearing"
    assert matching[0]["href"] == f"/agenda/{appointment.id}"
    assert matching[0]["remoteHearingUrl"] == remote_url


def test_notifica_unisce_udienza_non_collegata_e_conserva_link_verificato(tmp_path, monkeypatch):
    now = datetime(2026, 7, 17, 8, 0, tzinfo=ZoneInfo("Europe/Rome"))
    starts_at = now + timedelta(hours=2)
    remote_url = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_unlinked"
    appointment = SimpleNamespace(
        id="agenda-unlinked",
        external_uid="PEC_AUDIT:msg-unlinked:deadline",
        note="PEC_AUDIT:msg-unlinked",
        titolo="Fissazione udienza",
        tipo="UDIENZA",
        data_ora=starts_at.isoformat(),
        data_ora_dt=starts_at,
        remote_hearing_detected=False,
        remote_hearing_mode="",
        remote_hearing_url="",
        remote_hearing_source="",
        remote_hearing_verified=False,
        remote_hearing_pdf_required=False,
    )
    deadline = SimpleNamespace(
        id="deadline-unlinked",
        id_appuntamento="",
        note="PEC_AUDIT:msg-unlinked",
        titolo="Fissazione udienza",
        data_scadenza=now.date().isoformat(),
        legal_due_at="",
        stato="APERTO",
        priorita="ALTA",
        perentorio=False,
        remote_hearing_detected=True,
        remote_hearing_mode="audiovisiva",
        remote_hearing_url=remote_url,
        remote_hearing_source="decreto-udienza.pdf.zip",
        remote_hearing_verified=True,
        remote_hearing_time="17/07/2026 alle 10:00",
        remote_hearing_platform="Microsoft Teams",
        remote_hearing_meeting_id="riunione-unlinked",
        remote_hearing_passcode="codice-riservato",
        remote_hearing_access_info="Collegamento verificato nel decreto.",
        remote_hearing_pdf_required=False,
    )

    class _AgendaStore:
        def tutti(self):
            return [appointment]

    class _DeadlineStore:
        def tutte(self, *args, **kwargs):
            return [deadline]

    app = create_app(_cfg_web(tmp_path))
    with app.app_context():
        items = agenda_scadenziario_notification_items(
            _AgendaStore(),
            _DeadlineStore(),
            now=now,
        )

    assert len(items) == 1
    assert items[0]["id"] == "PEC_AUDIT:msg-unlinked:deadline"
    assert items[0]["href"] == "/agenda/agenda-unlinked"
    assert items[0]["type"] == "hearing"
    assert items[0]["remoteHearingUrl"] == remote_url
    assert items[0]["remoteHearingVerified"] is True

    pushed: list[dict[str, object]] = []

    def fake_dispatch(self, record):
        pushed.append(safe_web_push_payload(record))
        return PushDispatchSummary(configured=True, attempted=1, sent=1)

    monkeypatch.setattr(NotificationService, "dispatch_web_push", fake_dispatch)
    service = NotificationService(_repo(tmp_path))
    first = service.sync_operational_items(tenant_id="tenant-a", user_id="user-a", items=items)
    second = service.sync_operational_items(tenant_id="tenant-a", user_id="user-a", items=items)

    assert len(first) == len(second) == 1
    assert first[0].href == "/agenda/agenda-unlinked"
    assert first[0].payload_json["remoteHearingUrl"] == remote_url
    assert len(pushed) == 1
    assert pushed[0]["remoteHearingUrl"] == remote_url


def test_scadenza_audiovisiva_senza_agenda_arriva_al_web_push_con_link_verificato(monkeypatch, tmp_path):
    now = datetime.now(ZoneInfo("Europe/Rome"))
    remote_url = "https://teams.microsoft.com/l/meetup-join/19%3ameeting_scadenziario"
    deadline = SimpleNamespace(
        id="deadline-remote",
        id_appuntamento="",
        titolo="Udienza audiovisiva da Scadenziario",
        data_scadenza=(now.date() + timedelta(days=2)).isoformat(),
        legal_due_at="",
        stato="APERTO",
        priorita="ALTA",
        perentorio=False,
        remote_hearing_detected=True,
        remote_hearing_mode="audiovisiva",
        remote_hearing_url=remote_url,
        remote_hearing_source="Decreto fissazione udienza",
        remote_hearing_verified=True,
        remote_hearing_time="20/07/2026 alle 09:15",
        remote_hearing_platform="Microsoft Teams",
        remote_hearing_meeting_id="riunione-scadenziario",
        remote_hearing_passcode="codice-riservato",
        remote_hearing_access_info="Aprire il collegamento verificato nel decreto.",
        remote_hearing_pdf_required=False,
    )

    class _Store:
        def tutte(self, *args, **kwargs):
            return [deadline]

    monkeypatch.setattr(
        "web.services.topbar_operational._has_perm",
        lambda _user, permission: permission == "scadenziario.leggi",
    )
    monkeypatch.setattr("web.services.topbar_operational.get_scadenziario", _Store)

    app = create_app(_cfg_web(tmp_path))
    with app.test_request_context("/api/notifications"):
        items = _notification_items(SimpleNamespace())

    matching = [item for item in items if item["title"] == deadline.titolo]
    assert len(matching) == 1
    item = matching[0]
    assert item["href"] == f"/scadenziario/{deadline.id}"
    assert item["remoteHearingUrl"] == remote_url
    assert item["remoteHearingVerified"] is True

    repo = _repo(tmp_path)
    record = NotificationService(repo).sync_operational_items(
        tenant_id="tenant-a",
        user_id="user-a",
        items=[item],
    )[0]
    push_payload = safe_web_push_payload(record)
    assert push_payload["href"] == item["href"]
    assert push_payload["remoteHearingUrl"] == remote_url
    assert "codice-riservato" not in json.dumps(push_payload, ensure_ascii=False)


def test_scheduler_materializza_udienza_collegata_e_push_senza_aprire_pannello(tmp_path, monkeypatch):
    from flask import Flask

    from pct.agenda import Agenda, TipoAppuntamento
    from pct.scadenziario import GestioneScadenziario, TipoTermine
    from web.services.notifications_runtime import (
        materialize_agenda_scadenziario_notifications_for_paths,
    )

    paths = {
        "AUTH_DB": str(tmp_path / "auth" / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "auth" / "audit.json"),
        "AGENDA_DB": str(tmp_path / "agenda" / "appuntamenti.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenziario" / "scadenze.json"),
        "NOTIFICATIONS_DB": str(tmp_path / "notifications" / "notifications.db"),
    }
    GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test-secret",
        bootstrap_admin_credentials_path=str(tmp_path / "auth" / "bootstrap_admin.json"),
    )
    now = datetime.now(ZoneInfo("Europe/Rome")).replace(microsecond=0)
    starts_at = now + timedelta(hours=2)
    message_id = "msg-scheduler-linked"
    dedupe_key = f"PEC_AUDIT:{message_id}:deadline"
    remote_url = (
        "https://teams.microsoft.com/l/meetup-join/19%3aMeeting_CASE"
        "?context=%7B%22Tid%22%3A%22Tenant-ABC%22%7D"
    )
    appointment = Agenda(paths["AGENDA_DB"]).aggiungi(
        titolo="Udienza audiovisiva scheduler",
        tipo=TipoAppuntamento.UDIENZA,
        data_ora=starts_at.isoformat(),
        allow_overlap=True,
        external_uid=dedupe_key,
        external_provider="pec_audit",
        note=f"Cliente: Assistito test\nLink udienza audiovisiva: {remote_url}",
        remote_hearing_detected=True,
        remote_hearing_mode="audiovisiva",
        remote_hearing_url=remote_url,
        remote_hearing_source="decreto-udienza.pdf.zip",
        remote_hearing_verified=True,
        remote_hearing_platform="Microsoft Teams",
    )
    GestioneScadenziario(paths["SCADENZIARIO_DB"]).nuova(
        titolo=appointment.titolo,
        tipo=TipoTermine.UDIENZA,
        data_scadenza=starts_at.date().isoformat(),
        id_appuntamento=appointment.id,
        note=f"PEC_AUDIT:{message_id}\nCliente: Assistito test",
        remote_hearing_detected=True,
        remote_hearing_mode="audiovisiva",
        remote_hearing_url=remote_url,
        remote_hearing_source="decreto-udienza.pdf.zip",
        remote_hearing_verified=True,
        remote_hearing_platform="Microsoft Teams",
    )
    pushed: list[dict[str, object]] = []

    def fake_dispatch(self, record):
        pushed.append(safe_web_push_payload(record))
        return PushDispatchSummary(configured=True, attempted=1, sent=1)

    monkeypatch.setattr(NotificationService, "dispatch_web_push", fake_dispatch)
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test-secret", NOTIFICATIONS_DB=paths["NOTIFICATIONS_DB"])
    with app.app_context():
        first = materialize_agenda_scadenziario_notifications_for_paths(
            paths,
            tenant_label="default",
            tenant_id="default",
        )
        second = materialize_agenda_scadenziario_notifications_for_paths(
            paths,
            tenant_label="default",
            tenant_id="default",
        )

    user_id = _stored_user_id_from_paths(paths)
    records = NotificationRepository(paths["NOTIFICATIONS_DB"]).list_notifications("default", user_id)
    assert first["ok"] is True
    assert first["recipients"] >= 1
    assert first["items"] == first["recipients"], "una sola notifica per l'udienza collegata"
    assert second["ok"] is True
    assert len(records) == 1
    assert records[0].dedupe_key == dedupe_key
    assert records[0].source_type == "pec_deadline"
    assert records[0].payload_json["remoteHearingUrl"] == remote_url
    assert len(pushed) == 1
    assert pushed[0]["remoteHearingUrl"] == remote_url


def _stored_user_id_from_paths(paths: dict[str, str]) -> str:
    users = GestioneUtenti(
        db_path=paths["AUTH_DB"],
        audit_path=paths["AUDIT_DB"],
        secret_key="test-secret",
        crea_admin_se_vuoto=False,
    ).tutti(solo_attivi=True)
    return str(users[0].id or users[0].username)


def test_api_e_worker_condividono_factory_repository_postgresql(tmp_path, monkeypatch):
    from flask import Flask, g

    from web.services import notifications_runtime

    class FakeRepository:
        def __init__(self, db_path, *, postgres_dsn=""):
            self.db_path = str(db_path)
            self.postgres_dsn = postgres_dsn

    database = SimpleNamespace(mode="POSTGRESQL")
    paths = {
        "NOTIFICATIONS_DB": str(tmp_path / "tenant" / "notifications.db"),
        "_TENANT_DATABASE_CONFIG": database,
    }
    monkeypatch.setattr(notifications_runtime, "NotificationRepository", FakeRepository)
    monkeypatch.setattr(notifications_runtime, "tenant_corrente", lambda: SimpleNamespace(database=database))
    monkeypatch.setattr(
        notifications_runtime,
        "resolve_runtime_postgres_dsn",
        lambda **_kwargs: "postgresql://tenant-notifications",
    )
    app = Flask(__name__)
    app.config["NOTIFICATIONS_DB"] = paths["NOTIFICATIONS_DB"]
    with app.test_request_context("/api/notifications"):
        g.data_paths = paths
        api_repository = notifications_runtime.build_notification_repository()
        worker_repository = notifications_runtime.build_notification_repository_for_paths(
            paths,
            database=database,
            config=app.config,
        )

    assert api_repository is worker_repository
    assert api_repository.db_path == paths["NOTIFICATIONS_DB"]
    assert api_repository.postgres_dsn == "postgresql://tenant-notifications"


def test_scheduler_registra_materializzazione_autonoma_agenda_scadenziario():
    from pct.scheduler_registry import default_scheduler_templates

    scheduler_source = Path("pct/scheduler.py").read_text(encoding="utf-8")
    templates = {template.key: template for template in default_scheduler_templates({})}

    assert 'id="agenda_scadenziario_notifications"' in scheduler_source
    assert "materialize_agenda_scadenziario_notifications_for_paths(" in scheduler_source
    assert templates["agenda_scadenziario_notifications"].enabled is True
    assert templates["agenda_scadenziario_notifications"].minute == "2-57/5"
    assert templates["agenda_scadenziario_notifications"].editable is False


def test_ore_silenziose_usano_fuso_italiano_anche_con_ora_utc():
    preferences = NotificationPreferences(
        tenant_id="tenant-a",
        user_id="user-a",
        quiet_hours_enabled=True,
        quiet_hours_start="22:00",
        quiet_hours_end="07:00",
    )

    assert _quiet_now(
        preferences,
        now=datetime(2026, 7, 17, 21, 30, tzinfo=ZoneInfo("UTC")),
    ) is True
    assert _quiet_now(
        preferences,
        now=datetime(2026, 7, 17, 6, 0, tzinfo=ZoneInfo("UTC")),
    ) is False


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


def test_payload_push_udienza_include_collegamento_verificato_senza_dati_pratica():
    remote_url = "https://teams.microsoft.com/l/meetup-join/udienza-test?context=%7B%22Tid%22%3A%22123%22%7D"
    record = _notification(
        type="pec_deadline",
        priority="important",
        title="Udienza Mario Rossi RG 123/2026",
        body="Dettagli riservati della pratica.",
        href="/agenda/AG-1",
        payload_json={
            "remoteHearingDetected": True,
            "remoteHearingUrl": remote_url,
            "remoteHearingSource": "decreto.pdf.zip",
            "remoteHearingVerified": True,
        },
    )

    payload = safe_web_push_payload(record)
    topbar = _record_to_topbar_item(record)
    serialized = json.dumps(payload, ensure_ascii=False)

    assert payload["title"] == "IUSENTRA · Udienza"
    assert payload["body"] == "Udienza audiovisiva: collegamento verificato disponibile."
    assert payload["href"] == "/agenda/AG-1"
    assert payload["remoteHearingUrl"] == remote_url
    assert safe_remote_hearing_url(record.payload_json) == remote_url
    assert topbar["secondaryHref"] == remote_url
    assert topbar["secondaryLabel"] == "Collegati all'udienza"
    for forbidden in ("Mario Rossi", "RG 123/2026", "Dettagli riservati"):
        assert forbidden not in serialized


def test_payload_push_udienza_non_verificata_non_apre_link_esterno():
    remote_url = "https://teams.microsoft.com/l/meetup-join/udienza-da-controllare"
    record = _notification(
        type="pec_deadline",
        priority="important",
        href="/scadenziario/SCAD-1?vista=tutte",
        payload_json={
            "remoteHearingDetected": True,
            "remoteHearingUrl": remote_url,
            "remoteHearingVerified": False,
        },
    )

    payload = safe_web_push_payload(record)
    topbar = _record_to_topbar_item(record)

    assert payload["body"] == "Udienza audiovisiva: controlla il collegamento in IUSENTRA."
    assert "remoteHearingUrl" not in payload
    assert topbar["secondaryHref"] is None
    assert topbar["secondaryLabel"] is None


def test_link_udienza_con_parola_piattaforma_in_dominio_ostile_viene_rifiutato():
    payload = {
        "remoteHearingDetected": True,
        "remoteHearingUrl": "https://teams-login.example.test/udienza/123",
        "remoteHearingVerified": True,
    }

    assert safe_remote_hearing_url(payload) == ""


def test_service_worker_push_udienza_espone_agenda_e_collegamento_verificato():
    script = Path("web/static/sw.js").read_text(encoding="utf-8")

    assert "href.startsWith('/scadenziario/')" in script
    assert "'Apri scadenza'" in script
    assert "href.startsWith('/agenda/')" in script
    assert "'Apri Agenda'" in script
    assert "{ action: 'open-app', title: primaryActionTitle }" in script
    assert "{ action: 'join-hearing', title: 'Collegati' }" in script
    assert "data: { href, notificationId, remoteHearingUrl, version: SW_VERSION }" in script
    assert "event.action === 'join-hearing' && remoteHearingUrl" in script
    assert "self.clients.openWindow(remoteHearingUrl)" in script


def test_attivazione_push_non_puo_restar_bloccata_sul_permesso_browser():
    push_client = Path("frontend/src/lib/pushNotifications.ts").read_text(encoding="utf-8")
    settings_panel = Path(
        "frontend/src/features/impostazioni/components/NotificationsSettingsPanel.tsx"
    ).read_text(encoding="utf-8")

    assert "window.setTimeout(() => finish('timeout'), 15_000)" in push_client
    assert "Richiesta permesso non completata dal browser" in push_client
    assert "finally {" in settings_panel
    assert "window.setTimeout(() => finish(null), 6_000)" in settings_panel
    assert "setPushBusy('')" in settings_panel


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
