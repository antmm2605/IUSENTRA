from datetime import date, timedelta

from pct.agenda import Agenda
from pct.calendar_sync import GestioneCalendarSync


class _FakeResponse:
    def __init__(self, text: str, url: str = "https://calendar.example.com/feed.ics", status_code: int = 200):
        self.content = text.encode("utf-8")
        self.url = url
        self.status_code = status_code
        self.headers = {"content-type": "text/calendar; charset=utf-8"}


def _domani_ore(ora: str) -> str:
    d = date.today() + timedelta(days=1)
    return f"{d.strftime('%Y%m%d')}T{ora.replace(':', '')}00"


def test_preview_remote_calendar(tmp_path):
    sync = GestioneCalendarSync(db_path=str(tmp_path / "calendar_sync.json"))
    ics = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:test-1\r\n"
        "SUMMARY:Udienza esterna\r\n"
        f"DTSTART:{_domani_ore('09:30')}\r\n"
        f"DTEND:{_domani_ore('10:30')}\r\n"
        "LOCATION:Tribunale\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )

    preview = sync.preview_remote_calendar(
        "webcal://calendar.example.com/feed.ics",
        request_get=lambda *args, **kwargs: _FakeResponse(ics),
    )

    assert preview["source_url"] == "https://calendar.example.com/feed.ics"
    assert len(preview["events"]) == 1
    assert preview["events"][0].titolo == "Udienza esterna"
    assert len(preview["source_hash"]) == 64


def test_sync_profile_creates_and_updates(tmp_path):
    agenda = Agenda(db_path=str(tmp_path / "agenda.json"))
    sync = GestioneCalendarSync(db_path=str(tmp_path / "calendar_sync.json"))
    profilo = sync.create_profile(
        nome="Google personale",
        provider="google",
        source_url="https://calendar.example.com/feed.ics",
    )

    ics_v1 = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:test-2\r\n"
        "SUMMARY:Riunione iniziale\r\n"
        f"DTSTART:{_domani_ore('11:00')}\r\n"
        f"DTEND:{_domani_ore('12:00')}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    report_v1 = sync.sync_profile(
        profilo["id"],
        agenda=agenda,
        request_get=lambda *args, **kwargs: _FakeResponse(ics_v1),
    )
    assert report_v1["created"] == 1
    assert report_v1["updated"] == 0

    ics_v2 = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:test-2\r\n"
        "SUMMARY:Riunione aggiornata\r\n"
        f"DTSTART:{_domani_ore('12:00')}\r\n"
        f"DTEND:{_domani_ore('13:00')}\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    report_v2 = sync.sync_profile(
        profilo["id"],
        agenda=agenda,
        request_get=lambda *args, **kwargs: _FakeResponse(ics_v2),
    )
    assert report_v2["created"] == 0
    assert report_v2["updated"] == 1
    assert agenda.tutti()[0].titolo == "Riunione aggiornata"
