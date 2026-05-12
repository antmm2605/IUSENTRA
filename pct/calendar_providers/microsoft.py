"""Provider Microsoft Graph Calendar server-side."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from .base import CalendarProviderError, normalise_provider_event


class MicrosoftCalendarProvider:
    provider_name = "microsoft"
    api_base = "https://graph.microsoft.com/v1.0"

    def _credentials(self, account: dict[str, Any]) -> dict[str, Any]:
        return dict(account.get("credentials") or {})

    def _refresh(self, credentials: dict[str, Any]) -> dict[str, Any]:
        refresh_token = str(credentials.get("refresh_token") or "")
        client_id = str(credentials.get("client_id") or "")
        client_secret = str(credentials.get("client_secret") or "")
        tenant = str(credentials.get("tenant") or "common")
        if not refresh_token or not client_id or not client_secret:
            return credentials
        response = requests.post(
            f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": "offline_access Calendars.ReadWrite",
            },
            timeout=20,
        )
        if response.status_code >= 400:
            raise CalendarProviderError("Aggiornamento token Microsoft non riuscito.")
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
            raise CalendarProviderError("Account Microsoft non collegato.")
        return {"Authorization": f"Bearer {token}", "Accept": "application/json", "Prefer": 'outlook.timezone="UTC"'}

    def list_calendars(self, account: dict[str, Any]) -> list[dict[str, Any]]:
        response = requests.get(f"{self.api_base}/me/calendars", headers=self._headers(account), timeout=20)
        if response.status_code >= 400:
            raise CalendarProviderError("Lista calendari Microsoft non disponibile.")
        return [
            {
                "provider_calendar_id": item.get("id", ""),
                "name": item.get("name", "Microsoft 365 Calendar"),
                "role": "completo",
                "direction": "bidirectional",
                "enabled": True,
            }
            for item in response.json().get("value", [])
        ]

    def _map_event(self, item: dict[str, Any]) -> dict[str, Any]:
        start = item.get("start") or {}
        end = item.get("end") or {}
        return normalise_provider_event(
            {
                "id": item.get("id", ""),
                "uid": item.get("iCalUId") or item.get("uid") or item.get("id", ""),
                "title": item.get("subject", "Evento calendario"),
                "description": (item.get("body") or {}).get("content", ""),
                "location": (item.get("location") or {}).get("displayName", ""),
                "start": start.get("dateTime", ""),
                "end": end.get("dateTime", ""),
                "all_day": bool(item.get("isAllDay")),
                "status": "cancelled" if item.get("isCancelled") else "confirmed",
                "etag": item.get("@odata.etag", ""),
                "change_key": item.get("changeKey", ""),
                "updated_at": item.get("lastModifiedDateTime", ""),
                "categories": item.get("categories", []),
                "raw": item,
            }
        )

    def pull_changes(self, account: dict[str, Any], calendar: dict[str, Any], cursor: str = "") -> dict[str, Any]:
        calendar_id = str(calendar.get("provider_calendar_id") or "")
        url = cursor or f"{self.api_base}/me/calendars/{calendar_id}/events/delta"
        response = requests.get(url, headers=self._headers(account), timeout=30)
        if response.status_code >= 400:
            raise CalendarProviderError("Lettura eventi Microsoft non riuscita.")
        payload = response.json()
        return {
            "ok": True,
            "events": [self._map_event(item) for item in payload.get("value", [])],
            "cursor": payload.get("@odata.deltaLink") or payload.get("@odata.nextLink") or cursor,
            "full_snapshot": not bool(cursor),
        }

    def _to_graph_event(self, event: dict[str, Any]) -> dict[str, Any]:
        return {
            "subject": event.get("title") or "Evento IUSENTRA",
            "body": {"contentType": "text", "content": event.get("description") or ""},
            "location": {"displayName": event.get("location") or ""},
            "start": {"dateTime": event.get("start"), "timeZone": "UTC"},
            "end": {"dateTime": event.get("end") or event.get("start"), "timeZone": "UTC"},
            "isAllDay": bool(event.get("all_day")),
            "categories": list(event.get("categories") or []),
        }

    def push_event(self, account: dict[str, Any], calendar: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        calendar_id = str(calendar.get("provider_calendar_id") or "")
        binding = event.get("binding") if isinstance(event.get("binding"), dict) else {}
        event_id = str(binding.get("external_event_id") or "")
        headers = {**self._headers(account), "Content-Type": "application/json"}
        payload = self._to_graph_event(event)
        if event_id:
            response = requests.patch(f"{self.api_base}/me/calendars/{calendar_id}/events/{event_id}", headers=headers, json=payload, timeout=30)
        else:
            response = requests.post(f"{self.api_base}/me/calendars/{calendar_id}/events", headers=headers, json=payload, timeout=30)
        if response.status_code >= 400:
            raise CalendarProviderError("Scrittura evento Microsoft non riuscita.")
        return {"ok": True, "event": self._map_event(response.json())}

    def delete_event(self, account: dict[str, Any], calendar: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
        event_id = str(binding.get("external_event_id") or "")
        if not event_id:
            return {"ok": True, "missing": True, "deleted": True}
        calendar_id = str(calendar.get("provider_calendar_id") or "")
        response = requests.delete(f"{self.api_base}/me/calendars/{calendar_id}/events/{event_id}", headers=self._headers(account), timeout=20)
        if response.status_code >= 400 and response.status_code != 404:
            raise CalendarProviderError("Eliminazione evento Microsoft non riuscita.")
        return {"ok": True, "deleted": True}
