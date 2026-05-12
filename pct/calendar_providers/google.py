"""Provider Google Calendar server-side."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .base import CalendarProviderError, normalise_provider_event


class GoogleCalendarProvider:
    provider_name = "google"
    api_base = "https://www.googleapis.com/calendar/v3"

    def _credentials(self, account: dict[str, Any]) -> dict[str, Any]:
        return dict(account.get("credentials") or {})

    def _refresh(self, credentials: dict[str, Any]) -> dict[str, Any]:
        refresh_token = str(credentials.get("refresh_token") or "")
        client_id = str(credentials.get("client_id") or "")
        client_secret = str(credentials.get("client_secret") or "")
        if not refresh_token or not client_id or not client_secret:
            return credentials
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=20,
        )
        if response.status_code >= 400:
            raise CalendarProviderError("Aggiornamento token Google non riuscito.")
        payload = response.json()
        credentials.update(
            {
                "access_token": payload.get("access_token", credentials.get("access_token", "")),
                "expires_at": (
                    datetime.now(timezone.utc) + timedelta(seconds=int(payload.get("expires_in") or 3600))
                ).isoformat(),
            }
        )
        return credentials

    def _headers(self, account: dict[str, Any]) -> dict[str, str]:
        credentials = self._refresh(self._credentials(account))
        token = str(credentials.get("access_token") or "")
        if not token:
            raise CalendarProviderError("Account Google non collegato.")
        return {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    def list_calendars(self, account: dict[str, Any]) -> list[dict[str, Any]]:
        response = requests.get(f"{self.api_base}/users/me/calendarList", headers=self._headers(account), timeout=20)
        if response.status_code >= 400:
            raise CalendarProviderError("Lista calendari Google non disponibile.")
        return [
            {
                "provider_calendar_id": item.get("id", ""),
                "name": item.get("summary", "Google Calendar"),
                "role": "completo",
                "direction": "bidirectional",
                "enabled": True,
            }
            for item in response.json().get("items", [])
        ]

    def _map_event(self, item: dict[str, Any]) -> dict[str, Any]:
        start = item.get("start") or {}
        end = item.get("end") or {}
        all_day = bool(start.get("date"))
        return normalise_provider_event(
            {
                "id": item.get("id", ""),
                "uid": item.get("iCalUID") or item.get("id", ""),
                "title": item.get("summary", "Evento calendario"),
                "description": item.get("description", ""),
                "location": item.get("location", ""),
                "start": start.get("dateTime") or start.get("date") or "",
                "end": end.get("dateTime") or end.get("date") or "",
                "all_day": all_day,
                "status": item.get("status", "confirmed"),
                "etag": item.get("etag", ""),
                "sequence": item.get("sequence", 0),
                "updated_at": item.get("updated", ""),
                "categories": item.get("extendedProperties", {}).get("private", {}).get("iusentra_categories", "").split(",")
                if item.get("extendedProperties")
                else [],
                "raw": item,
            }
        )

    def pull_changes(self, account: dict[str, Any], calendar: dict[str, Any], cursor: str = "") -> dict[str, Any]:
        calendar_id = str(calendar.get("provider_calendar_id") or "primary")
        params: dict[str, Any] = {"showDeleted": "true", "singleEvents": "false", "maxResults": 2500}
        if cursor:
            params["syncToken"] = cursor
        else:
            params["timeMin"] = (datetime.now(timezone.utc) - timedelta(days=365)).isoformat()
        response = requests.get(
            f"{self.api_base}/calendars/{calendar_id}/events",
            headers=self._headers(account),
            params=params,
            timeout=30,
        )
        if response.status_code == 410 and cursor:
            return self.pull_changes(account, calendar, cursor="")
        if response.status_code >= 400:
            raise CalendarProviderError("Lettura eventi Google non riuscita.")
        payload = response.json()
        return {
            "ok": True,
            "events": [self._map_event(item) for item in payload.get("items", [])],
            "cursor": payload.get("nextSyncToken", cursor),
            "full_snapshot": not bool(cursor),
        }

    def _to_google_event(self, event: dict[str, Any]) -> dict[str, Any]:
        all_day = bool(event.get("all_day"))
        start_key = "date" if all_day else "dateTime"
        payload = {
            "summary": event.get("title") or "Evento IUSENTRA",
            "description": event.get("description") or "",
            "location": event.get("location") or "",
            "start": {start_key: event.get("start")},
            "end": {start_key: event.get("end") or event.get("start")},
            "extendedProperties": {"private": {"iusentra_categories": ",".join(event.get("categories") or [])}},
        }
        if event.get("status") == "cancelled":
            payload["status"] = "cancelled"
        return payload

    def push_event(self, account: dict[str, Any], calendar: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        calendar_id = str(calendar.get("provider_calendar_id") or "primary")
        binding = event.get("binding") if isinstance(event.get("binding"), dict) else {}
        event_id = str(binding.get("external_event_id") or "")
        payload = self._to_google_event(event)
        headers = {**self._headers(account), "Content-Type": "application/json"}
        if event_id:
            response = requests.patch(f"{self.api_base}/calendars/{calendar_id}/events/{event_id}", headers=headers, json=payload, timeout=30)
        else:
            response = requests.post(f"{self.api_base}/calendars/{calendar_id}/events", headers=headers, json=payload, timeout=30)
        if response.status_code >= 400:
            raise CalendarProviderError("Scrittura evento Google non riuscita.")
        return {"ok": True, "event": self._map_event(response.json())}

    def delete_event(self, account: dict[str, Any], calendar: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
        event_id = str(binding.get("external_event_id") or "")
        if not event_id:
            return {"ok": True, "missing": True, "deleted": True}
        calendar_id = str(calendar.get("provider_calendar_id") or "primary")
        response = requests.delete(f"{self.api_base}/calendars/{calendar_id}/events/{event_id}", headers=self._headers(account), timeout=20)
        if response.status_code not in {200, 204, 410} and response.status_code < 400:
            return {"ok": True, "deleted": True}
        if response.status_code >= 400 and response.status_code not in {404, 410}:
            raise CalendarProviderError("Eliminazione evento Google non riuscita.")
        return {"ok": True, "deleted": True}
