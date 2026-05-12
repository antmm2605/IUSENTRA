"""Provider WebCal/ICS basato sul gestore esistente."""

from __future__ import annotations

from typing import Any

from pct.calendar_sync import GestioneCalendarSync

from .base import CalendarProviderError, normalise_provider_event


class WebCalProvider:
    provider_name = "webcal"

    def list_calendars(self, account: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "id": str(account.get("id") or "webcal"),
                "provider_calendar_id": str(account.get("source_url") or account.get("id") or "webcal"),
                "name": str(account.get("display_name") or "Calendario WebCal"),
                "role": "import_only",
                "direction": "inbound",
                "enabled": True,
            }
        ]

    def pull_changes(
        self,
        account: dict[str, Any],
        calendar: dict[str, Any],
        cursor: str = "",
    ) -> dict[str, Any]:
        source_url = str(calendar.get("source_url") or account.get("source_url") or "").strip()
        if not source_url:
            raise CalendarProviderError("Link calendario mancante.")
        preview = GestioneCalendarSync(db_path=str(account.get("_compat_db_path") or "./agenda/calendar_sync.json")).preview_remote_calendar(source_url)
        events = []
        for item in preview["events"]:
            events.append(
                normalise_provider_event(
                    {
                        "id": item.uid,
                        "uid": item.uid,
                        "title": item.titolo,
                        "description": item.descrizione,
                        "location": item.luogo,
                        "start": item.data_ora,
                        "end": item.fine_ora or item.data_ora,
                        "all_day": item.tutto_giorno,
                        "status": "cancelled" if item.stato_ical == "CANCELLED" else "confirmed",
                        "organizer": item.organizzatore,
                        "rrule": item.rrule,
                    }
                )
            )
        return {
            "ok": True,
            "events": events,
            "cursor": preview.get("source_hash", ""),
            "full_snapshot": True,
            "source_url": preview.get("source_url", source_url),
        }

    def push_event(self, account: dict[str, Any], calendar: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        raise CalendarProviderError("Il calendario WebCal consente solo l'importazione.")

    def delete_event(self, account: dict[str, Any], calendar: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
        raise CalendarProviderError("Il calendario WebCal consente solo l'importazione.")
