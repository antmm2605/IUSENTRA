"""Provider calendario dimostrativo persistente."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from pct import cache as _cache

from .base import event_content_hash, normalise_provider_event, utc_now_iso


class DemoCalendarProvider:
    provider_name = "demo"

    def __init__(self, store_path: str | Path | None = None):
        self.store_path = Path(store_path or "data/demo_calendar/provider_events.json")
        self.store_path.parent.mkdir(parents=True, exist_ok=True)

    def _empty(self) -> dict[str, Any]:
        return {"sequence": 0, "calendars": {}, "events": {}, "changes": []}

    def _load(self) -> dict[str, Any]:
        data = _cache.load(self.store_path, default=self._empty())
        if not isinstance(data, dict):
            data = self._empty()
        for key, fallback in self._empty().items():
            if key not in data:
                data[key] = fallback
        return data

    def _save(self, data: dict[str, Any]) -> None:
        _cache.save(self.store_path, data)

    def _calendar_key(self, account: dict[str, Any], calendar: dict[str, Any] | None = None) -> str:
        account_id = str(account.get("id") or "demo-account")
        provider_calendar_id = ""
        if calendar:
            provider_calendar_id = str(calendar.get("provider_calendar_id") or calendar.get("id") or "")
        return provider_calendar_id or f"{account_id}:demo"

    def _record_change(self, data: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        data["sequence"] = int(data.get("sequence") or 0) + 1
        event["sequence"] = data["sequence"]
        event["updated_at"] = utc_now_iso()
        event["etag"] = f"demo-etag-{event['sequence']}"
        event["change_key"] = f"demo-change-{event['sequence']}"
        event["content_hash"] = event_content_hash(event)
        data["changes"].append({"sequence": data["sequence"], "event": dict(event)})
        return event

    def list_calendars(self, account: dict[str, Any]) -> list[dict[str, Any]]:
        data = self._load()
        key = self._calendar_key(account)
        if key not in data["calendars"]:
            data["calendars"][key] = {
                "id": key,
                "provider_calendar_id": key,
                "name": "Calendario demo IUSENTRA",
                "role": "completo",
                "direction": "bidirectional",
                "enabled": True,
            }
            self._save(data)
        return [dict(item) for item in data["calendars"].values()]

    def pull_changes(
        self,
        account: dict[str, Any],
        calendar: dict[str, Any],
        cursor: str = "",
    ) -> dict[str, Any]:
        data = self._load()
        calendar_key = self._calendar_key(account, calendar)
        cursor_num = int(cursor or 0) if str(cursor or "").isdigit() else 0
        if cursor_num <= 0:
            events = [
                dict(item)
                for item in data["events"].values()
                if item.get("calendar_id") == calendar_key and not item.get("deleted")
            ]
        else:
            events = [
                dict(change["event"])
                for change in data["changes"]
                if int(change.get("sequence") or 0) > cursor_num
                and change.get("event", {}).get("calendar_id") == calendar_key
            ]
        return {
            "ok": True,
            "events": [normalise_provider_event(item) for item in events],
            "cursor": str(data.get("sequence") or 0),
            "full_snapshot": cursor_num <= 0,
        }

    def push_event(
        self,
        account: dict[str, Any],
        calendar: dict[str, Any],
        event: dict[str, Any],
    ) -> dict[str, Any]:
        data = self._load()
        calendar_key = self._calendar_key(account, calendar)
        binding = event.get("binding") if isinstance(event.get("binding"), dict) else {}
        event_id = str(binding.get("external_event_id") or event.get("external_event_id") or "").strip()
        if not event_id:
            event_id = f"demo_evt_{uuid.uuid4().hex[:16]}"
        uid = str(binding.get("external_uid") or event.get("uid") or f"{event_id}@iusentra.demo")
        remote = dict(data["events"].get(event_id) or {})
        remote.update(
            {
                "id": event_id,
                "uid": uid,
                "calendar_id": calendar_key,
                "account_id": str(account.get("id") or ""),
                "title": str(event.get("title") or "Evento IUSENTRA"),
                "description": str(event.get("description") or ""),
                "location": str(event.get("location") or ""),
                "start": str(event.get("start") or ""),
                "end": str(event.get("end") or event.get("start") or ""),
                "all_day": bool(event.get("all_day")),
                "status": str(event.get("status") or "confirmed"),
                "categories": list(event.get("categories") or []),
                "deleted": False,
            }
        )
        remote = self._record_change(data, remote)
        data["events"][event_id] = remote
        self._save(data)
        return {"ok": True, "event": normalise_provider_event(remote)}

    def delete_event(
        self,
        account: dict[str, Any],
        calendar: dict[str, Any],
        binding: dict[str, Any],
    ) -> dict[str, Any]:
        data = self._load()
        event_id = str(binding.get("external_event_id") or "")
        if event_id not in data["events"]:
            return {"ok": True, "deleted": True, "missing": True}
        event = dict(data["events"][event_id])
        event["deleted"] = True
        event["status"] = "cancelled"
        event = self._record_change(data, event)
        data["events"][event_id] = event
        self._save(data)
        return {"ok": True, "deleted": True, "event": normalise_provider_event(event)}

    def create_remote_event(self, account_id: str, calendar_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return self.push_event({"id": account_id}, {"provider_calendar_id": calendar_id}, event)["event"]

    def update_remote_event(self, event_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        if event_id not in data["events"]:
            raise KeyError(f"Evento demo '{event_id}' non trovato.")
        event = dict(data["events"][event_id])
        event.update(updates)
        event = self._record_change(data, event)
        data["events"][event_id] = event
        self._save(data)
        return normalise_provider_event(event)

    def delete_remote_event(self, event_id: str) -> dict[str, Any]:
        data = self._load()
        if event_id not in data["events"]:
            raise KeyError(f"Evento demo '{event_id}' non trovato.")
        event = dict(data["events"][event_id])
        event["deleted"] = True
        event["status"] = "cancelled"
        event = self._record_change(data, event)
        data["events"][event_id] = event
        self._save(data)
        return normalise_provider_event(event)

    def get_event(self, event_id: str) -> dict[str, Any] | None:
        return dict(self._load()["events"].get(event_id) or {}) or None
