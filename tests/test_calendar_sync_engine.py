from pct.agenda import Appuntamento, TipoAppuntamento
from pct.calendar_sync_engine import CalendarSyncEngine, PRIVACY_BUSY, PRIVACY_COMPLETE, PRIVACY_REDUCED, privacy_export_event
from pct.scadenziario import TipoTermine


def _engine(tmp_path) -> CalendarSyncEngine:
    return CalendarSyncEngine.from_paths(
        agenda_db=str(tmp_path / "agenda.json"),
        scadenziario_db=str(tmp_path / "scadenze.json"),
        sync_db=str(tmp_path / "calendar_sync.json"),
        tenant_id="tenant-test",
    )


def _connect_demo(engine: CalendarSyncEngine, *, direction: str = "bidirectional", role: str = "completo"):
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
            "role": role,
            "direction": direction,
            "enabled": True,
            "privacy_level": PRIVACY_REDUCED,
        }
    )
    return account, calendar


def _sample_appointment(engine: CalendarSyncEngine, title: str = "Udienza TAR"):
    return engine.agenda.aggiungi(
        titolo=title,
        tipo=TipoAppuntamento.UDIENZA,
        data_ora="2026-06-01T09:00:00",
        durata_minuti=60,
        luogo="Tribunale",
        cliente="Cliente Riservato",
        procedimento="RG 123/2026",
        note="Nota riservata",
    )


def test_push_iusentra_to_remote_demo_creates_binding(tmp_path):
    engine = _engine(tmp_path)
    account, calendar = _connect_demo(engine)
    appointment = _sample_appointment(engine)

    result = engine.push_local_event("agenda", appointment.id, account["id"], calendar["id"])
    binding = result["binding"]
    remote = engine.providers["demo"].get_event(binding["external_event_id"])

    assert result["ok"] is True
    assert binding["local_id"] == appointment.id
    assert remote["title"] == "[UDIENZA] Impegno di studio"
    assert remote["description"] == "Dettagli riservati in IUSENTRA."


def test_local_update_pushes_remote_update_and_refreshes_change_keys(tmp_path):
    engine = _engine(tmp_path)
    account, calendar = _connect_demo(engine)
    appointment = _sample_appointment(engine)
    first = engine.push_local_event("agenda", appointment.id, account["id"], calendar["id"])

    engine.agenda.modifica(appointment.id, titolo="Udienza rinviata", durata_minuti=90)
    second = engine.push_local_event("agenda", appointment.id, account["id"], calendar["id"])

    assert second["binding"]["external_event_id"] == first["binding"]["external_event_id"]
    assert second["binding"]["etag"] != first["binding"]["etag"]
    assert second["binding"]["change_key"] != first["binding"]["change_key"]


def test_pull_remote_demo_creates_iusentra_appointment(tmp_path):
    engine = _engine(tmp_path)
    account, calendar = _connect_demo(engine, direction="inbound", role="agenda")
    engine.providers["demo"].create_remote_event(
        account["id"],
        calendar["provider_calendar_id"],
        {
            "title": "[UDIENZA] Udienza da calendario",
            "description": "Arrivata dal calendario esterno",
            "start": "2026-06-02T11:00:00",
            "end": "2026-06-02T12:00:00",
        },
    )

    report = engine.pull_remote_changes(account["id"], calendar["id"])

    assert report["created"] == 1
    assert engine.agenda.tutti()[0].titolo == "Udienza da calendario"
    assert engine.repository.list_bindings(engine.tenant_id)[0]["local_type"] == "agenda"


def test_bidirectional_local_remote_changes_open_conflict(tmp_path):
    engine = _engine(tmp_path)
    account, calendar = _connect_demo(engine)
    appointment = _sample_appointment(engine)
    pushed = engine.push_local_event("agenda", appointment.id, account["id"], calendar["id"])

    engine.agenda.modifica(appointment.id, titolo="Titolo locale")
    engine.providers["demo"].update_remote_event(pushed["binding"]["external_event_id"], {"title": "Titolo esterno"})
    report = engine.pull_remote_changes(account["id"], calendar["id"])

    assert report["conflicts"] == 1
    conflict = engine.conflicts.list_conflicts(engine.tenant_id)[0]
    assert conflict["conflict_type"] == "modifica_concorrente"
    assert engine.agenda.get(appointment.id).titolo == "Titolo locale"


def test_peremptory_deadline_remote_delete_opens_conflict_without_deleting(tmp_path):
    engine = _engine(tmp_path)
    account, calendar = _connect_demo(engine)
    deadline = engine.scadenziario.nuova(
        titolo="Deposito perentorio",
        tipo=TipoTermine.TERMINE_PERENTORIO,
        data_scadenza="2026-06-10",
        perentorio=True,
    )
    pushed = engine.push_local_event("scadenza", deadline.id, account["id"], calendar["id"])

    engine.providers["demo"].delete_remote_event(pushed["binding"]["external_event_id"])
    report = engine.pull_remote_changes(account["id"], calendar["id"])

    assert report["conflicts"] == 1
    assert engine.scadenziario.get(deadline.id).stato.value == "APERTO"
    conflict = engine.conflicts.list_conflicts(engine.tenant_id)[0]
    assert conflict["conflict_type"] == "scadenza_perentoria_cancellata"


def test_privacy_export_levels_hide_sensitive_content():
    appointment = Appuntamento(
        id="A1",
        titolo="Udienza cliente Rossi",
        tipo=TipoAppuntamento.UDIENZA,
        data_ora="2026-06-01T09:00:00",
        durata_minuti=60,
        luogo="Tribunale",
        cliente="Cliente Rossi",
        procedimento="RG 123/2026",
        tribunale="TAR",
        note="Strategia riservata",
    )

    complete = privacy_export_event("agenda", appointment, PRIVACY_COMPLETE)
    reduced = privacy_export_event("agenda", appointment, PRIVACY_REDUCED)
    busy = privacy_export_event("agenda", appointment, PRIVACY_BUSY)

    assert "Cliente Rossi" in complete["description"]
    assert "Strategia riservata" in complete["description"]
    assert "Cliente Rossi" not in reduced["description"]
    assert "Strategia riservata" not in reduced["description"]
    assert reduced["title"] == "[UDIENZA] Impegno di studio"
    assert busy["title"] == "Occupato"
    assert busy["description"] == ""
