"""Repository persistente per account, calendari collegati, binding e job sync."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pct import cache as _cache


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class CalendarSyncRepository:
    """Archivio JSON tenant-aware per il nuovo motore calendario."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _empty(self) -> dict[str, list[dict[str, Any]]]:
        return {"accounts": [], "calendars": [], "bindings": [], "jobs": []}

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        data = _cache.load(self.path, default=self._empty())
        if not isinstance(data, dict):
            data = self._empty()
        for key in self._empty():
            if not isinstance(data.get(key), list):
                data[key] = []
        return data

    def _save(self, data: dict[str, Any]) -> None:
        _cache.save(self.path, data)

    def list_accounts(self, tenant_id: str = "", *, include_disconnected: bool = False) -> list[dict[str, Any]]:
        tenant = str(tenant_id or "").strip()
        rows = [dict(item) for item in self._load()["accounts"]]
        if tenant:
            rows = [item for item in rows if str(item.get("tenant_id") or "") == tenant]
        if not include_disconnected:
            rows = [item for item in rows if str(item.get("status") or "") != "disconnected"]
        return sorted(rows, key=lambda item: (str(item.get("provider") or ""), str(item.get("display_name") or "")))

    def get_account(self, account_id: str, tenant_id: str = "") -> dict[str, Any] | None:
        for item in self.list_accounts(tenant_id, include_disconnected=True):
            if item.get("id") == account_id:
                return dict(item)
        return None

    def find_account(self, *, tenant_id: str, provider: str, email: str = "", display_name: str = "") -> dict[str, Any] | None:
        for item in self.list_accounts(tenant_id, include_disconnected=True):
            if str(item.get("provider") or "") != provider:
                continue
            if email and str(item.get("email") or "").lower() == email.lower():
                return dict(item)
            if display_name and str(item.get("display_name") or "").lower() == display_name.lower():
                return dict(item)
        return None

    def upsert_account(self, account: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        now = now_iso()
        payload = dict(account)
        payload.setdefault("id", new_id("calacc"))
        payload.setdefault("tenant_id", "default")
        payload.setdefault("provider", "demo")
        payload.setdefault("display_name", "Calendario")
        payload.setdefault("email", "")
        payload.setdefault("auth_type", payload.get("provider", "demo"))
        payload.setdefault("encrypted_credentials", "")
        payload.setdefault("scopes", [])
        payload.setdefault("status", "active")
        payload.setdefault("sync_cursor", "")
        payload.setdefault("webhook_channel_id", "")
        payload.setdefault("webhook_expires_at", "")
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        replaced = False
        for index, item in enumerate(data["accounts"]):
            if item.get("id") == payload["id"]:
                data["accounts"][index] = {**item, **payload}
                payload = data["accounts"][index]
                replaced = True
                break
        if not replaced:
            data["accounts"].append(payload)
        self._save(data)
        return dict(payload)

    def disconnect_account(self, account_id: str, tenant_id: str = "") -> dict[str, Any]:
        account = self.get_account(account_id, tenant_id)
        if not account:
            raise KeyError(f"Account calendario '{account_id}' non trovato.")
        account["status"] = "disconnected"
        account["encrypted_credentials"] = ""
        updated = self.upsert_account(account)
        data = self._load()
        for calendar in data["calendars"]:
            if calendar.get("account_id") == account_id:
                calendar["enabled"] = False
                calendar["updated_at"] = now_iso()
        self._save(data)
        return updated

    def list_calendars(self, tenant_id: str = "", account_id: str = "") -> list[dict[str, Any]]:
        tenant = str(tenant_id or "").strip()
        rows = [dict(item) for item in self._load()["calendars"]]
        if tenant:
            rows = [item for item in rows if str(item.get("tenant_id") or "") == tenant]
        if account_id:
            rows = [item for item in rows if str(item.get("account_id") or "") == account_id]
        return sorted(rows, key=lambda item: (str(item.get("name") or ""), str(item.get("role") or "")))

    def get_calendar(self, calendar_id: str, tenant_id: str = "") -> dict[str, Any] | None:
        for item in self.list_calendars(tenant_id):
            if item.get("id") == calendar_id:
                return dict(item)
        return None

    def upsert_calendar(self, calendar: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        now = now_iso()
        payload = dict(calendar)
        payload.setdefault("id", new_id("cal"))
        payload.setdefault("tenant_id", "default")
        payload.setdefault("account_id", "")
        payload.setdefault("provider_calendar_id", payload["id"])
        payload.setdefault("name", "Calendario")
        payload.setdefault("role", "completo")
        payload.setdefault("direction", "bidirectional")
        payload.setdefault("enabled", True)
        payload.setdefault("privacy_level", "professional_reduced")
        payload.setdefault("last_sync_at", "")
        payload.setdefault("last_error", "")
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        replaced = False
        for index, item in enumerate(data["calendars"]):
            if item.get("id") == payload["id"]:
                data["calendars"][index] = {**item, **payload}
                payload = data["calendars"][index]
                replaced = True
                break
        if not replaced:
            data["calendars"].append(payload)
        self._save(data)
        return dict(payload)

    def list_bindings(
        self,
        tenant_id: str = "",
        *,
        account_id: str = "",
        calendar_id: str = "",
        local_type: str = "",
        local_id: str = "",
    ) -> list[dict[str, Any]]:
        rows = [dict(item) for item in self._load()["bindings"]]
        if tenant_id:
            rows = [item for item in rows if str(item.get("tenant_id") or "") == tenant_id]
        if account_id:
            rows = [item for item in rows if str(item.get("account_id") or "") == account_id]
        if calendar_id:
            rows = [item for item in rows if str(item.get("calendar_id") or "") == calendar_id]
        if local_type:
            rows = [item for item in rows if str(item.get("local_type") or "") == local_type]
        if local_id:
            rows = [item for item in rows if str(item.get("local_id") or "") == local_id]
        return rows

    def find_binding(
        self,
        *,
        tenant_id: str,
        account_id: str,
        calendar_id: str,
        local_type: str = "",
        local_id: str = "",
        external_event_id: str = "",
        external_uid: str = "",
    ) -> dict[str, Any] | None:
        for item in self.list_bindings(tenant_id, account_id=account_id, calendar_id=calendar_id):
            if local_type and local_id and item.get("local_type") == local_type and item.get("local_id") == local_id:
                return dict(item)
            if external_event_id and str(item.get("external_event_id") or "") == external_event_id:
                return dict(item)
            if external_uid and str(item.get("external_uid") or "") == external_uid:
                return dict(item)
        return None

    def upsert_binding(self, binding: dict[str, Any]) -> dict[str, Any]:
        data = self._load()
        now = now_iso()
        payload = dict(binding)
        payload.setdefault("id", new_id("calbind"))
        payload.setdefault("tenant_id", "default")
        payload.setdefault("local_type", "agenda")
        payload.setdefault("local_id", "")
        payload.setdefault("provider", "")
        payload.setdefault("account_id", "")
        payload.setdefault("calendar_id", "")
        payload.setdefault("external_event_id", "")
        payload.setdefault("external_uid", "")
        payload.setdefault("etag", "")
        payload.setdefault("change_key", "")
        payload.setdefault("sequence", 0)
        payload.setdefault("content_hash", "")
        payload.setdefault("remote_content_hash", "")
        payload.setdefault("last_pushed_at", "")
        payload.setdefault("last_pulled_at", "")
        payload.setdefault("deleted_remote_at", "")
        payload.setdefault("deleted_local_at", "")
        payload.setdefault("created_at", now)
        payload["updated_at"] = now
        replaced = False
        for index, item in enumerate(data["bindings"]):
            if item.get("id") == payload["id"]:
                data["bindings"][index] = {**item, **payload}
                payload = data["bindings"][index]
                replaced = True
                break
        if not replaced:
            data["bindings"].append(payload)
        self._save(data)
        return dict(payload)

    def create_job(self, *, tenant_id: str, account_id: str, action: str, status: str = "queued", error: str = "") -> dict[str, Any]:
        data = self._load()
        now = now_iso()
        job = {
            "id": new_id("caljob"),
            "tenant_id": tenant_id or "default",
            "account_id": account_id,
            "action": action,
            "status": status,
            "attempts": 0,
            "error": error,
            "created_at": now,
            "updated_at": now,
        }
        data["jobs"].append(job)
        self._save(data)
        return dict(job)

    def update_job(self, job_id: str, **fields: Any) -> dict[str, Any]:
        data = self._load()
        for item in data["jobs"]:
            if item.get("id") == job_id:
                item.update(fields)
                item["updated_at"] = now_iso()
                self._save(data)
                return dict(item)
        raise KeyError(f"Job calendario '{job_id}' non trovato.")

    def list_jobs(self, tenant_id: str = "", *, status: str = "") -> list[dict[str, Any]]:
        rows = [dict(item) for item in self._load()["jobs"]]
        if tenant_id:
            rows = [item for item in rows if str(item.get("tenant_id") or "") == tenant_id]
        if status:
            rows = [item for item in rows if str(item.get("status") or "") == status]
        return rows
