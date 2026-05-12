"""Repository e utility per i conflitti calendario."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pct import cache as _cache


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class CalendarConflictRepository:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        data = _cache.load(self.path, default={"conflicts": []})
        if not isinstance(data, dict) or not isinstance(data.get("conflicts"), list):
            return {"conflicts": []}
        return data

    def _save(self, data: dict[str, Any]) -> None:
        _cache.save(self.path, data)

    def list_conflicts(self, tenant_id: str = "", *, status: str = "open") -> list[dict[str, Any]]:
        rows = [dict(item) for item in self._load()["conflicts"]]
        if tenant_id:
            rows = [item for item in rows if str(item.get("tenant_id") or "") == tenant_id]
        if status:
            rows = [item for item in rows if str(item.get("status") or "") == status]
        return sorted(rows, key=lambda item: str(item.get("created_at") or ""), reverse=True)

    def get(self, conflict_id: str, tenant_id: str = "") -> dict[str, Any] | None:
        for item in self.list_conflicts(tenant_id, status=""):
            if item.get("id") == conflict_id:
                return dict(item)
        return None

    def create_conflict(
        self,
        *,
        tenant_id: str,
        local_type: str,
        local_id: str,
        provider: str,
        conflict_type: str,
        local_snapshot: dict[str, Any],
        remote_snapshot: dict[str, Any],
        proposed_resolution: str = "revisione_manuale",
    ) -> dict[str, Any]:
        data = self._load()
        for item in data["conflicts"]:
            if (
                item.get("status") == "open"
                and item.get("tenant_id") == tenant_id
                and item.get("local_type") == local_type
                and item.get("local_id") == local_id
                and item.get("provider") == provider
                and item.get("conflict_type") == conflict_type
            ):
                item["local_snapshot"] = local_snapshot
                item["remote_snapshot"] = remote_snapshot
                item["updated_at"] = now_iso()
                self._save(data)
                return dict(item)
        now = now_iso()
        conflict = {
            "id": f"calconf_{uuid.uuid4().hex[:16]}",
            "tenant_id": tenant_id or "default",
            "local_type": local_type,
            "local_id": local_id,
            "provider": provider,
            "conflict_type": conflict_type,
            "local_snapshot": local_snapshot,
            "remote_snapshot": remote_snapshot,
            "proposed_resolution": proposed_resolution,
            "status": "open",
            "created_at": now,
            "updated_at": now,
            "resolved_at": "",
        }
        data["conflicts"].append(conflict)
        self._save(data)
        return dict(conflict)

    def resolve(self, conflict_id: str, *, status: str = "resolved", resolution: str = "") -> dict[str, Any]:
        data = self._load()
        for item in data["conflicts"]:
            if item.get("id") == conflict_id:
                item["status"] = status
                item["resolution"] = resolution
                item["resolved_at"] = now_iso()
                item["updated_at"] = item["resolved_at"]
                self._save(data)
                return dict(item)
        raise KeyError(f"Conflitto calendario '{conflict_id}' non trovato.")
