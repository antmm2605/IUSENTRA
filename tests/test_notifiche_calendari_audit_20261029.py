"""Regressioni audit 29/10/2026: bozze, preavvisi configurati e retry calendari.

D2 - le BOZZE (proposte non confermate) non generano notifiche ne' Web Push.
D3 - le BOZZE non vengono pubblicate sui calendari esterni; un errore su un
     elemento non interrompe la sincronizzazione; "Riprova calendari" riprende
     davvero i job falliti con backoff e limite di tentativi, senza duplicati.
D4 - i giorni di preavviso configurati sul termine (giorni_preavviso) generano
     una notifica per soglia raggiunta, senza ripetere l'avviso ogni 5 minuti.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from pct.calendar_providers.base import CalendarProviderError
from pct.calendar_sync_engine import (
    RETRY_MAX_ATTEMPTS,
    CalendarSyncEngine,
    PRIVACY_REDUCED,
    privacy_export_event,
)
from pct.notifications import NotificationRepository, NotificationService
from pct.notifications.service import PushDispatchSummary
from pct.scadenziario import GestioneScadenziario, Scadenza, StatoTermine, TipoTermine
from web.services.topbar_operational import (
    _deadline_status,
    _reached_reminder_threshold,
    agenda_scadenziario_notification_items,
)

ROME = ZoneInfo("Europe/Rome")


class _NoAgenda:
    def tutti(self):
        return []


class _Deadlines:
    def __init__(self, rows):
        self.rows = rows

    def tutte(self, *args, **kwargs):
        return list(self.rows)


def _deadline(days: int, *, today: date, stato: str = "APERTO", preavviso=None, **extra):
    data = dict(
        id=f"sc-{days}-{stato.lower()}",
        id_appuntamento="",
        titolo=f"Termine tra {days} giorni ({stato})",
        data_scadenza=(today + timedelta(days=days)).isoformat(),
        legal_due_at="",
        stato=stato,
        priorita="MEDIA",
        perentorio=False,
        note="",
    )
    if preavviso is not None:
        data["giorni_preavviso"] = preavviso
    data.update(extra)
    return SimpleNamespace(**data)


# --------------------------------------------------------------------------- D2


def test_bozza_e_stato_draft_non_operativo():
    today = date(2026, 10, 29)
    assert _deadline_status(_deadline(-3, today=today, stato="BOZZA"), today) == "draft"
    assert _deadline_status(_deadline(-3, today=today, stato="APERTO"), today) == "overdue"


def test_bozze_perentorie_o_scadute_non_generano_notifiche_urgenti():
    now = datetime(2026, 10, 29, 10, 0, tzinfo=ROME)
    today = now.date()
    rows = [
        _deadline(1, today=today, stato="BOZZA", perentorio=True, priorita="CRITICA"),
        _deadline(-2, today=today, stato="BOZZA"),
        _deadline(0, today=today, stato="BOZZA", preavviso=[30, 15, 7, 3, 1, 0]),
        _deadline(1, today=today, stato="ANNULLATO", perentorio=True),
        _deadline(1, today=today, stato="COMPLETATO", perentorio=True),
        _deadline(1, today=today, stato="APERTO", perentorio=True),
    ]
    items = agenda_scadenziario_notification_items(_NoAgenda(), _Deadlines(rows), include_agenda=False, now=now)
    assert [item["id"] for item in items] == [f"deadline:sc-1-aperto:{(today + timedelta(days=1)).isoformat()}"]
    assert items[0]["priority"] == "urgent"


def test_bozza_non_arriva_al_web_push(monkeypatch, tmp_path):
    now = datetime(2026, 10, 29, 10, 0, tzinfo=ROME)
    pushed: list[str] = []

    def fake_dispatch(self, record):
        pushed.append(record.dedupe_key)
        return PushDispatchSummary(configured=True, attempted=1, sent=1)

    monkeypatch.setattr(NotificationService, "dispatch_web_push", fake_dispatch)
    service = NotificationService(NotificationRepository(tmp_path / "notifications.db"))
    rows = [_deadline(1, today=now.date(), stato="BOZZA", perentorio=True, priorita="CRITICA")]
    items = agenda_scadenziario_notification_items(_NoAgenda(), _Deadlines(rows), include_agenda=False, now=now)
    service.sync_operational_items(tenant_id="t", user_id="u", items=items, expire_source_types={"deadline"})
    assert items == []
    assert pushed == []


def test_bozza_reale_dello_scadenziario_esclusa(tmp_path):
    gestione = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    today = datetime.now(ROME).date()
    bozza = Scadenza(titolo="Proposta da PEC", data_scadenza=(today + timedelta(days=1)).isoformat(), perentorio=True)
    bozza.stato = StatoTermine.BOZZA
    aperta = Scadenza(titolo="Termine confermato", data_scadenza=(today + timedelta(days=1)).isoformat(), perentorio=True)
    gestione._scadenze[bozza.id] = bozza
    gestione._scadenze[aperta.id] = aperta
    items = agenda_scadenziario_notification_items(_NoAgenda(), gestione, include_agenda=False)
    assert [item["title"] for item in items] == ["Termine confermato"]


# --------------------------------------------------------------------------- D4


@pytest.mark.parametrize(
    ("days", "expected"),
    [(45, None), (30, 30), (20, 30), (15, 15), (10, 15), (7, 7), (5, 7), (3, 3), (2, 3), (1, 1), (0, 0), (-4, 0)],
)
def test_soglia_di_preavviso_raggiunta(days, expected):
    scadenza = SimpleNamespace(giorni_preavviso=[30, 15, 7, 3, 1, 0])
    assert _reached_reminder_threshold(scadenza, days) == expected


def test_soglia_tollera_dati_sporchi():
    assert _reached_reminder_threshold(SimpleNamespace(giorni_preavviso=["7", None, "x", -1]), 5) == 7
    assert _reached_reminder_threshold(SimpleNamespace(), 1) is None
    assert _reached_reminder_threshold(SimpleNamespace(giorni_preavviso=None), 1) is None


def test_preavvisi_configurati_generano_notifiche_oltre_i_due_giorni():
    now = datetime(2026, 10, 29, 9, 0, tzinfo=ROME)
    today = now.date()
    soglie = [30, 15, 7, 3, 1, 0]
    rows = [_deadline(n, today=today, preavviso=soglie) for n in (31, 30, 15, 7, 3, 2)]
    items = agenda_scadenziario_notification_items(_NoAgenda(), _Deadlines(rows), include_agenda=False, now=now)
    by_title = {item["title"]: item["id"] for item in items}
    assert "Termine tra 31 giorni (APERTO)" not in by_title
    for days, threshold in ((30, 30), (15, 15), (7, 7), (3, 3), (2, 3)):
        due = (today + timedelta(days=days)).isoformat()
        assert by_title[f"Termine tra {days} giorni (APERTO)"] == f"deadline:sc-{days}-aperto:{due}:preavviso:{threshold}"


def test_senza_preavvisi_resta_il_comportamento_storico():
    now = datetime(2026, 10, 29, 9, 0, tzinfo=ROME)
    today = now.date()
    rows = [_deadline(n, today=today) for n in (5, 2, -1)] + [_deadline(40, today=today, perentorio=True)]
    items = agenda_scadenziario_notification_items(_NoAgenda(), _Deadlines(rows), include_agenda=False, now=now)
    ids = sorted(item["id"] for item in items)
    assert ids == sorted(
        [
            f"deadline:sc-2-aperto:{(today + timedelta(days=2)).isoformat()}",
            f"deadline:sc--1-aperto:{(today - timedelta(days=1)).isoformat()}",
            f"deadline:sc-40-aperto:{(today + timedelta(days=40)).isoformat()}",
        ]
    )


def test_now_utc_usa_il_giorno_italiano():
    # 23:30 UTC del 28/10 = 00:30 del 29/10 a Roma: la scadenza del 29 e' "oggi".
    now_utc = datetime(2026, 10, 28, 23, 30, tzinfo=timezone.utc)
    today_rome = date(2026, 10, 29)
    rows = [_deadline(0, today=today_rome, preavviso=[7, 3, 1, 0])]
    items = agenda_scadenziario_notification_items(_NoAgenda(), _Deadlines(rows), include_agenda=False, now=now_utc)
    assert items[0]["message"] == "Scadenza oggi"
    assert items[0]["id"].endswith(":preavviso:0")


def test_preavviso_naive_e_aware_mescolati():
    now_naive = datetime(2026, 10, 29, 9, 0)
    rows = [_deadline(7, today=date(2026, 10, 29), preavviso=[7])]
    items = agenda_scadenziario_notification_items(_NoAgenda(), _Deadlines(rows), include_agenda=False, now=now_naive)
    assert items and items[0]["id"].endswith(":preavviso:7")


def test_un_push_per_soglia_senza_spam_del_job_ogni_5_minuti(monkeypatch, tmp_path):
    pushed: list[str] = []

    def fake_dispatch(self, record):
        pushed.append(record.dedupe_key)
        return PushDispatchSummary(configured=True, attempted=1, sent=1)

    monkeypatch.setattr(NotificationService, "dispatch_web_push", fake_dispatch)
    repository = NotificationRepository(tmp_path / "notifications.db")
    service = NotificationService(repository)
    due = date(2026, 12, 15)
    deadline = SimpleNamespace(
        id="rc-1",
        id_appuntamento="",
        titolo="Recupero crediti",
        data_scadenza=due.isoformat(),
        legal_due_at="",
        stato="APERTO",
        priorita="MEDIA",
        perentorio=False,
        note="",
        giorni_preavviso=[30, 15, 7, 3, 1, 0],
    )
    store = _Deadlines([deadline])
    day = due - timedelta(days=35)
    while day <= due:
        # Tre esecuzioni del job nella stessa giornata (ogni 5 minuti).
        for minute in (0, 5, 10):
            now = datetime(day.year, day.month, day.day, 9, minute, tzinfo=ROME)
            items = agenda_scadenziario_notification_items(_NoAgenda(), store, include_agenda=False, now=now)
            service.sync_operational_items(tenant_id="t", user_id="u", items=items, expire_source_types={"deadline"})
        day += timedelta(days=1)

    assert pushed == [f"deadline:rc-1:{due.isoformat()}:preavviso:{t}" for t in (30, 15, 7, 3, 1, 0)]
    active = repository.list_notifications("t", "u", limit=50)
    assert [record.dedupe_key for record in active] == [f"deadline:rc-1:{due.isoformat()}:preavviso:0"]


# --------------------------------------------------------------------------- D3


def _engine(tmp_path) -> CalendarSyncEngine:
    return CalendarSyncEngine.from_paths(
        agenda_db=str(tmp_path / "agenda.json"),
        scadenziario_db=str(tmp_path / "scadenze.json"),
        sync_db=str(tmp_path / "calendar_sync.json"),
        tenant_id="tenant-audit",
    )


def _connect_demo(engine: CalendarSyncEngine, *, direction: str = "outbound"):
    account = engine.repository.upsert_account(
        {
            "tenant_id": engine.tenant_id,
            "provider": "demo",
            "display_name": "Calendario locale",
            "email": "demo@example.test",
            "auth_type": "demo",
            "encrypted_credentials": engine.credentials.encrypt({"mode": "test"}),
            "status": "active",
        }
    )
    calendar = engine.repository.upsert_calendar(
        {
            "tenant_id": engine.tenant_id,
            "account_id": account["id"],
            "provider": "demo",
            "provider_calendar_id": "demo-primary",
            "name": "Calendario prova",
            "role": "completo",
            "direction": direction,
            "enabled": True,
            "privacy_level": PRIVACY_REDUCED,
        }
    )
    return account, calendar


def _remote_events(engine: CalendarSyncEngine) -> list[dict]:
    return list(engine.providers["demo"]._load()["events"].values())


def _bozza(engine: CalendarSyncEngine, titolo: str = "Impugnazione - termine lungo"):
    scadenza = engine.scadenziario.nuova(
        titolo=titolo, tipo=TipoTermine.TERMINE_PERENTORIO, data_scadenza="2027-05-03", perentorio=True
    )
    engine.scadenziario.aggiorna(scadenza.id, stato=StatoTermine.BOZZA)
    return engine.scadenziario.get(scadenza.id)


def test_privacy_export_bozza_non_e_confermata():
    scadenza = Scadenza(titolo="Proposta", data_scadenza="2027-01-10")
    scadenza.stato = StatoTermine.BOZZA
    assert privacy_export_event("scadenza", scadenza)["status"] == "tentative"


def test_sync_account_non_pubblica_bozze(tmp_path):
    engine = _engine(tmp_path)
    account, _calendar = _connect_demo(engine)
    _bozza(engine)
    engine.scadenziario.nuova(titolo="Termine confermato", tipo=TipoTermine.ALTRO, data_scadenza="2026-11-20")

    report = engine.sync_account(account["id"])

    titles = [event["title"] for event in _remote_events(engine)]
    assert titles == ["Scadenza: Termine confermato"]
    assert report["ok"] is True
    assert report["pushed"] == 1 and report["skipped"] == 1


def test_termine_riportato_in_bozza_rimuove_evento_remoto_una_volta(tmp_path):
    engine = _engine(tmp_path)
    account, calendar = _connect_demo(engine)
    scadenza = engine.scadenziario.nuova(titolo="Termine", tipo=TipoTermine.ALTRO, data_scadenza="2026-12-01")
    engine.push_local_event("scadenza", scadenza.id, account["id"], calendar["id"])
    assert [event["deleted"] for event in _remote_events(engine)] == [False]

    engine.scadenziario.aggiorna(scadenza.id, stato=StatoTermine.BOZZA)
    provider = engine.providers["demo"]
    deletes = {"n": 0}
    original_delete = provider.delete_event

    def counting_delete(*args, **kwargs):
        deletes["n"] += 1
        return original_delete(*args, **kwargs)

    provider.delete_event = counting_delete
    first = engine.push_local_event("scadenza", scadenza.id, account["id"], calendar["id"])
    second = engine.push_local_event("scadenza", scadenza.id, account["id"], calendar["id"])

    assert first["deleted"] is True and first["reason"] == "bozza_non_confermata"
    assert second == {"ok": True, "skipped": True, "reason": "bozza_non_confermata"}
    assert deletes["n"] == 1
    assert [event["deleted"] for event in _remote_events(engine)] == [True]

    # Confermata di nuovo: ripubblica lo stesso evento, senza duplicati.
    engine.scadenziario.aggiorna(scadenza.id, stato=StatoTermine.APERTO)
    engine.push_local_event("scadenza", scadenza.id, account["id"], calendar["id"])
    events = _remote_events(engine)
    assert len(events) == 1 and events[0]["deleted"] is False


def _flaky_engine(tmp_path, failures: int):
    engine = _engine(tmp_path)
    account, calendar = _connect_demo(engine)
    for index in range(3):
        engine.scadenziario.nuova(titolo=f"S{index}", tipo=TipoTermine.ALTRO, data_scadenza=f"2026-12-0{index + 1}")
    provider = engine.providers["demo"]
    original = provider.push_event
    state = {"calls": 0, "failures_left": failures, "fail_title": "Scadenza: S0"}

    def flaky(account_arg, calendar_arg, event):
        state["calls"] += 1
        if event.get("title") == state["fail_title"] and state["failures_left"] > 0:
            state["failures_left"] -= 1
            raise CalendarProviderError("rete non raggiungibile")
        return original(account_arg, calendar_arg, event)

    provider.push_event = flaky
    return engine, account, calendar, state


def test_sync_account_isola_errore_per_elemento(tmp_path):
    engine, account, _calendar, _state = _flaky_engine(tmp_path, failures=1)

    report = engine.sync_account(account["id"])

    assert report["ok"] is False
    assert report["failed"] == 1 and report["pushed"] == 2
    assert sorted(event["title"] for event in _remote_events(engine)) == ["Scadenza: S1", "Scadenza: S2"]
    failed_jobs = engine.repository.list_jobs(engine.tenant_id, status="failed")
    assert len(failed_jobs) == 1
    job = failed_jobs[0]
    assert job["local_type"] == "scadenza" and job["retry_state"] == "pending"
    assert job["attempts"] == 1 and job["next_retry_at"]
    assert "rete non raggiungibile" in job["error"]


def test_riprova_calendari_rispetta_backoff_e_non_duplica(tmp_path):
    engine, account, _calendar, _state = _flaky_engine(tmp_path, failures=1)
    engine.sync_account(account["id"])
    job = engine.repository.list_jobs(engine.tenant_id, status="failed")[0]
    next_retry = datetime.fromisoformat(job["next_retry_at"].replace("Z", "+00:00"))

    early = engine.sync_due_jobs(now=next_retry - timedelta(seconds=1))
    assert early["processed"] == 0

    retried = engine.sync_due_jobs(now=next_retry + timedelta(seconds=1))
    assert retried == {"ok": True, "processed": 1, "succeeded": 1, "failed": 0, "exhausted": 0}
    assert sorted(event["title"] for event in _remote_events(engine)) == ["Scadenza: S0", "Scadenza: S1", "Scadenza: S2"]
    assert engine.repository.list_jobs(engine.tenant_id, status="failed") == []

    # Un nuovo allineamento aggiorna gli eventi esistenti: nessun duplicato.
    engine.sync_account(account["id"])
    assert len(_remote_events(engine)) == 3


def test_riprova_calendari_limite_tentativi(tmp_path):
    engine, account, _calendar, state = _flaky_engine(tmp_path, failures=100)
    engine.sync_account(account["id"])
    now = datetime.now(timezone.utc)
    for _ in range(RETRY_MAX_ATTEMPTS + 3):
        now += timedelta(hours=7)  # oltre il backoff massimo
        engine.sync_due_jobs(now=now)
    failed = engine.repository.list_jobs(engine.tenant_id, status="failed")
    assert len(failed) == 1
    assert failed[0]["attempts"] == RETRY_MAX_ATTEMPTS
    assert failed[0]["retry_state"] == "exhausted"
    assert failed[0]["next_retry_at"] == ""
    s0_attempts = state["calls"] - 2  # S1 e S2 riusciti al primo giro
    assert s0_attempts == RETRY_MAX_ATTEMPTS


def test_fallimenti_ripetuti_riusano_lo_stesso_job(tmp_path):
    engine, account, _calendar, _state = _flaky_engine(tmp_path, failures=2)
    engine.sync_account(account["id"])
    engine.sync_account(account["id"])
    failed = engine.repository.list_jobs(engine.tenant_id, status="failed")
    assert len(failed) == 1 and failed[0]["attempts"] == 2
    engine.sync_account(account["id"])
    assert engine.repository.list_jobs(engine.tenant_id, status="failed") == []
    assert len(_remote_events(engine)) == 3


def test_job_storici_senza_contesto_vengono_ripresi_con_un_allineamento(tmp_path):
    engine = _engine(tmp_path)
    account, _calendar = _connect_demo(engine)
    engine.scadenziario.nuova(titolo="Termine", tipo=TipoTermine.ALTRO, data_scadenza="2026-12-01")
    legacy = engine.repository.create_job(tenant_id=engine.tenant_id, account_id=account["id"], action="push", status="running")
    engine.repository.update_job(legacy["id"], status="failed", attempts=1, error="rete")

    report = engine.sync_due_jobs()

    assert report["processed"] == 1 and report["ok"] is True
    assert [event["title"] for event in _remote_events(engine)] == ["Scadenza: Termine"]
    assert engine.repository.list_jobs(engine.tenant_id, status="failed") == []
