"""Transizioni Europe/Rome: istanti distinti e minuti effettivi."""
from datetime import datetime, timedelta, timezone

import pytest

from pct.agenda import Appuntamento, TipoAppuntamento
from pct.daily_plan.clock import Clock
from pct.formatting import parse_datetime_rome


@pytest.mark.parametrize("utc,local,offset,fold", [
    ("2026-03-29T00:59:00Z", "2026-03-29T01:59", 3600, 0),
    ("2026-03-29T01:00:00Z", "2026-03-29T03:00", 7200, 0),
    ("2026-10-25T00:30:00Z", "2026-10-25T02:30", 7200, 0),
    ("2026-10-25T01:30:00Z", "2026-10-25T02:30", 3600, 1),
])
def test_formattazione_e_clock_conservano_transizione(utc, local, offset, fold):
    value = parse_datetime_rome(utc)
    assert value.isoformat(timespec="minutes")[:16] == local
    assert value.utcoffset().total_seconds() == offset
    assert value.fold == fold
    assert Clock(fixed_now=datetime.fromisoformat(utc.replace("Z", "+00:00"))).now() == value
    assert value.astimezone(timezone.utc).isoformat() == utc.replace("Z", "+00:00")


@pytest.mark.parametrize("start,minutes,expected", [
    ("2026-03-29T01:30:00+01:00", 60, "2026-03-29T03:30:00"),
    ("2026-10-25T02:30:00+02:00", 60, "2026-10-25T02:30:00"),
])
def test_durata_appuntamento_usa_minuti_effettivi(start, minutes, expected):
    app = Appuntamento(id="DST", titolo="Prova sintetica", tipo=TipoAppuntamento.ALTRO,
                       data_ora=start, durata_minuti=minutes, luogo="")
    assert app.fine_dt.isoformat() == expected


@pytest.mark.parametrize("start,expected", [
    ("2026-03-29T03:30:00+02:00", "2026-03-29T01:30:00"),
    ("2026-10-25T02:30:00+01:00", "2026-10-25T02:30:00"),
])
def test_promemoria_anticipa_minuti_effettivi(start, expected):
    app = Appuntamento(id="DST", titolo="Prova sintetica", tipo=TipoAppuntamento.ALTRO,
                       data_ora=start, durata_minuti=30, reminder_minuti=60, luogo="")
    assert app.reminder_dt.isoformat() == expected


def test_ora_inesistente_non_persistita_neanche_senza_overlap(tmp_path):
    from pct.agenda import Agenda
    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))
    with pytest.raises(ValueError, match="Ora locale inesistente"):
        agenda.aggiungi(titolo="Prova", tipo=TipoAppuntamento.ALTRO,
                        data_ora="2026-03-29T02:30:00", allow_overlap=True)
    assert agenda.tutti() == []


def test_due_occorrenze_ora_solare_sono_istanti_distinti(tmp_path):
    from pct.agenda import Agenda
    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))
    first = agenda.aggiungi(titolo="Prima", tipo=TipoAppuntamento.ALTRO,
                            data_ora="2026-10-25T02:30:00+02:00", durata_minuti=20)
    second = agenda.aggiungi(titolo="Seconda", tipo=TipoAppuntamento.ALTRO,
                             data_ora="2026-10-25T02:30:00+01:00", durata_minuti=20)
    assert len(agenda.tutti()) == 2
    assert second.reminder_utc - first.reminder_utc == timedelta(hours=1)
    restored = Agenda(db_path=str(tmp_path / "agenda.json"))
    assert restored.get(second.id).data_ora.endswith("+01:00")


@pytest.mark.parametrize("start,end,expected", [
    ("20260329T003000Z", "20260329T013000Z", "2026-03-29T01:30:00"),
    ("20261025T003000Z", "20261025T013000Z", "2026-10-25T02:30:00+02:00"),
])
def test_import_ics_utc_conserva_istante_e_durata(start, end, expected):
    from pct.ical_import import parse_ics
    event, = parse_ics(f"BEGIN:VCALENDAR\nBEGIN:VEVENT\nUID:dst-test\nSUMMARY:Prova\nDTSTART:{start}\nDTEND:{end}\nEND:VEVENT\nEND:VCALENDAR")
    assert event.data_ora == expected
    assert event.durata_minuti == 60


def test_export_calendario_conserva_offset_ora_ripetuta():
    from pct.calendar_sync_engine import privacy_export_event
    app = Appuntamento(id="DST", titolo="Prova", tipo=TipoAppuntamento.ALTRO,
                       data_ora="2026-10-25T02:30:00+02:00", durata_minuti=60, luogo="")
    event = privacy_export_event("agenda", app)
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"])
    assert (end - start).total_seconds() == 3600
    assert event["end"].endswith("+01:00")


def test_anteprima_ics_durata_attraversa_ora_legale():
    from pct.ical_import import parse_ics
    event, = parse_ics("BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20260329T003000Z\nDURATION:PT1H\nEND:VEVENT\nEND:VCALENDAR")
    assert event.ora_display == "01:30 – 03:30"


def test_ics_ora_inesistente_resta_visibile_ma_non_e_persistita(tmp_path):
    from pct.agenda import Agenda
    from pct.ical_import import parse_ics
    event, = parse_ics("BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20260329T023000\nEND:VEVENT\nEND:VCALENDAR")
    assert event.data_ora == "2026-03-29T02:30:00"
    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))
    with pytest.raises(ValueError, match="Ora locale inesistente"):
        agenda.aggiungi(titolo=event.titolo, tipo=TipoAppuntamento.ALTRO, data_ora=event.data_ora)
    assert agenda.tutti() == []


def test_clock_giorno_italiano_anche_con_host_utc():
    assert Clock(fixed_now=datetime(2026, 7, 1, 22, 30, tzinfo=timezone.utc)).today().isoformat() == "2026-07-02"
    assert Clock(fixed_now=datetime(2026, 1, 1, 22, 30, tzinfo=timezone.utc)).today().isoformat() == "2026-01-01"


def test_promemoria_ora_ripetuta_seleziona_solo_istante_corretto(tmp_path, monkeypatch):
    import pct.agenda as module
    agenda = module.Agenda(db_path=str(tmp_path / "agenda.json"))
    first = agenda.aggiungi(titolo="Prima", tipo=TipoAppuntamento.ALTRO,
                            data_ora="2026-10-25T02:30:00+02:00", durata_minuti=10, reminder_minuti=0)
    agenda.aggiungi(titolo="Seconda", tipo=TipoAppuntamento.ALTRO,
                     data_ora="2026-10-25T02:30:00+01:00", durata_minuti=10, reminder_minuti=0)

    class Fixed(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 25, 0, 20, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(module, "datetime", Fixed)
    assert [item.id for item in agenda.prossimi_reminder(20)] == [first.id]


def test_modifica_ora_inesistente_preserva_valore_precedente(tmp_path):
    from pct.agenda import Agenda
    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))
    app = agenda.aggiungi(titolo="Prova", tipo=TipoAppuntamento.ALTRO,
                          data_ora="2026-03-29T09:00:00")
    with pytest.raises(ValueError, match="Ora locale inesistente"):
        agenda.modifica(app.id, titolo="Non deve cambiare", data_ora="2026-03-29T02:30:00")
    assert agenda.get(app.id).titolo == "Prova"
    assert agenda.get(app.id).data_ora == "2026-03-29T09:00:00"


def test_job_cron_dichiarano_fuso_studio_anche_su_host_utc():
    import ast
    from pathlib import Path
    from apscheduler.triggers.cron import CronTrigger
    import pct.scheduler as scheduler_module
    tree = ast.parse(Path(scheduler_module.__file__).read_text(encoding="utf-8-sig"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "CronTrigger"]
    assert calls
    for call in calls:
        timezone_arg = next((kw.value for kw in call.keywords if kw.arg == "timezone"), None)
        assert isinstance(timezone_arg, ast.Constant) and timezone_arg.value == "Europe/Rome", call.lineno
    trigger = CronTrigger(hour=9, minute=0, timezone="Europe/Rome")
    for day, expected_hour in [("2026-03-28", 8), ("2026-03-29", 7),
                               ("2026-10-24", 7), ("2026-10-25", 8)]:
        now = datetime.fromisoformat(day).replace(tzinfo=timezone.utc)
        fired = trigger.get_next_fire_time(None, now)
        assert fired.hour == 9
        assert fired.astimezone(timezone.utc).hour == expected_hour


@pytest.mark.parametrize("start,end", [
    ("2026-03-29T01:30:00+01:00", "2026-03-29T03:30+02:00"),
    ("2026-10-25T02:30:00+02:00", "2026-10-25T02:30+01:00"),
])
def test_payload_agenda_react_conserva_durata_e_offset(start, end):
    from web.services.react_agenda_bridge import _agenda_event
    app = Appuntamento(id="DST", titolo="Prova sintetica", tipo=TipoAppuntamento.ALTRO,
                       data_ora=start, durata_minuti=60, luogo="")
    payload = _agenda_event(app)
    assert payload["end"] == end
    assert (datetime.fromisoformat(payload["end"]) - datetime.fromisoformat(payload["start"])).total_seconds() == 3600


def test_orario_legacy_inesistente_resta_consultabile_senza_riscriverlo():
    app = Appuntamento(id="DST", titolo="Storico", tipo=TipoAppuntamento.ALTRO,
                       data_ora="2026-03-29T02:30:00", durata_minuti=60, luogo="")
    assert app.data_ora_dt.isoformat() == "2026-03-29T02:30:00"
    assert app.to_dict()["data_ora"] == "2026-03-29T02:30:00"


@pytest.mark.parametrize("kind", ["cron", "interval"])
def test_job_registrati_usano_fuso_italiano_indipendente_da_host(kind):
    from pct.scheduler_registry import _job_trigger
    trigger = _job_trigger({"trigger_kind": kind, "hour": "9", "minute": "0", "interval_minutes": 60})
    assert str(trigger.timezone) == "Europe/Rome"
    if kind == "cron":
        fired = trigger.get_next_fire_time(None, datetime(2026, 7, 1, 0, tzinfo=timezone.utc))
        assert fired.astimezone(timezone.utc).hour == 7
