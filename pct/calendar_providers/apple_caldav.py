"""Provider Apple iCloud / CalDAV con polling server-side."""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree as ET

import requests

from pct.ical_import import parse_ics

from .base import CalendarProviderError, build_ics_event, normalise_provider_event


class AppleCalDAVProvider:
    provider_name = "apple_caldav"

    def _credentials(self, account: dict[str, Any]) -> dict[str, Any]:
        return dict(account.get("credentials") or {})

    def _auth(self, account: dict[str, Any]) -> tuple[str, str]:
        credentials = self._credentials(account)
        username = str(credentials.get("username") or account.get("email") or "").strip()
        password = str(credentials.get("password") or "").strip()
        if not username or not password:
            raise CalendarProviderError("Credenziali CalDAV non configurate.")
        return username, password

    def _base_url(self, account: dict[str, Any]) -> str:
        credentials = self._credentials(account)
        return str(credentials.get("server_url") or "https://caldav.icloud.com").rstrip("/")

    def list_calendars(self, account: dict[str, Any]) -> list[dict[str, Any]]:
        base = self._base_url(account)
        body = """<?xml version="1.0" encoding="utf-8"?>
<d:propfind xmlns:d="DAV:" xmlns:cs="http://calendarserver.org/ns/">
  <d:prop><d:displayname/><d:resourcetype/></d:prop>
</d:propfind>"""
        response = requests.request("PROPFIND", base, data=body, auth=self._auth(account), headers={"Depth": "1"}, timeout=30)
        if response.status_code >= 400:
            raise CalendarProviderError("Lista calendari CalDAV non disponibile.")
        calendars: list[dict[str, Any]] = []
        root = ET.fromstring(response.text)
        for response_node in root.findall("{DAV:}response"):
            href = (response_node.findtext("{DAV:}href") or "").strip()
            display = (response_node.findtext(".//{DAV:}displayname") or href.rsplit("/", 2)[-2] or "Calendario iCloud").strip()
            if href and href.rstrip("/") != "/":
                calendars.append(
                    {
                        "provider_calendar_id": href,
                        "name": display,
                        "role": "completo",
                        "direction": "bidirectional",
                        "enabled": True,
                    }
                )
        return calendars or [{"provider_calendar_id": base, "name": "Calendario iCloud", "role": "completo", "direction": "bidirectional", "enabled": True}]

    def pull_changes(self, account: dict[str, Any], calendar: dict[str, Any], cursor: str = "") -> dict[str, Any]:
        base = self._base_url(account)
        calendar_href = str(calendar.get("provider_calendar_id") or base)
        url = calendar_href if calendar_href.startswith("http") else base + "/" + calendar_href.lstrip("/")
        body = """<?xml version="1.0" encoding="utf-8"?>
<c:calendar-query xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">
  <d:prop><d:getetag/><c:calendar-data/></d:prop>
  <c:filter><c:comp-filter name="VCALENDAR"><c:comp-filter name="VEVENT"/></c:comp-filter></c:filter>
</c:calendar-query>"""
        response = requests.request("REPORT", url, data=body, auth=self._auth(account), headers={"Depth": "1", "Content-Type": "application/xml"}, timeout=45)
        if response.status_code >= 400:
            raise CalendarProviderError("Lettura eventi CalDAV non riuscita.")
        events: list[dict[str, Any]] = []
        root = ET.fromstring(response.text)
        for node in root.findall("{DAV:}response"):
            href = (node.findtext("{DAV:}href") or "").strip()
            etag = (node.findtext(".//{DAV:}getetag") or "").strip()
            ics = (node.findtext(".//{urn:ietf:params:xml:ns:caldav}calendar-data") or "").strip()
            for parsed in parse_ics(ics):
                events.append(
                    normalise_provider_event(
                        {
                            "id": href or parsed.uid,
                            "uid": parsed.uid or href,
                            "title": parsed.titolo,
                            "description": parsed.descrizione,
                            "location": parsed.luogo,
                            "start": parsed.data_ora,
                            "end": parsed.fine_ora or parsed.data_ora,
                            "all_day": parsed.tutto_giorno,
                            "status": "cancelled" if parsed.stato_ical == "CANCELLED" else "confirmed",
                            "etag": etag,
                            "organizer": parsed.organizzatore,
                        }
                    )
                )
        return {"ok": True, "events": events, "cursor": "", "full_snapshot": True}

    def push_event(self, account: dict[str, Any], calendar: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        base = self._base_url(account)
        calendar_href = str(calendar.get("provider_calendar_id") or base)
        calendar_url = calendar_href if calendar_href.startswith("http") else base + "/" + calendar_href.lstrip("/")
        binding = event.get("binding") if isinstance(event.get("binding"), dict) else {}
        uid = str(binding.get("external_uid") or event.get("uid") or f"iusentra-{re.sub('[^A-Za-z0-9]+', '-', str(event.get('title') or 'evento')).strip('-')}")
        href = str(binding.get("external_event_id") or "").strip()
        target = href if href.startswith("http") else calendar_url.rstrip("/") + f"/{uid}.ics"
        response = requests.put(target, data=build_ics_event(event, uid), auth=self._auth(account), headers={"Content-Type": "text/calendar; charset=utf-8"}, timeout=30)
        if response.status_code >= 400:
            raise CalendarProviderError("Scrittura evento CalDAV non riuscita.")
        remote = normalise_provider_event(
            {
                "id": target,
                "uid": uid,
                "title": event.get("title"),
                "description": event.get("description"),
                "location": event.get("location"),
                "start": event.get("start"),
                "end": event.get("end"),
                "all_day": event.get("all_day"),
                "etag": response.headers.get("ETag", ""),
            }
        )
        return {"ok": True, "event": remote}

    def delete_event(self, account: dict[str, Any], calendar: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
        href = str(binding.get("external_event_id") or "")
        if not href:
            return {"ok": True, "missing": True, "deleted": True}
        response = requests.delete(href, auth=self._auth(account), timeout=20)
        if response.status_code >= 400 and response.status_code != 404:
            raise CalendarProviderError("Eliminazione evento CalDAV non riuscita.")
        return {"ok": True, "deleted": True}
