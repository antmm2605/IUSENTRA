"""Timer operativo per la top bar e salvataggio finale nel timesheet."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ACTIVITY_TYPES = {
    "call",
    "drafting",
    "research",
    "hearing",
    "meeting",
    "email",
    "filing",
    "other",
}
ACTIVE_STATUSES = {"running", "paused"}


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.now(UTC)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


@dataclass
class TimeTrackingTimer:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    user_id: str = ""
    username: str = ""
    case_id: str = ""
    client_id: str = ""
    activity_type: str = "other"
    description: str = ""
    started_at: str = field(default_factory=utc_now_iso)
    paused_at: str = ""
    ended_at: str = ""
    elapsed_seconds: int = 0
    status: str = "running"
    timesheet_entry_id: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> TimeTrackingTimer:
        data = dict(payload or {})
        data["elapsed_seconds"] = int(data.get("elapsed_seconds", 0) or 0)
        data["activity_type"] = str(data.get("activity_type") or "other")
        if data["activity_type"] not in ACTIVITY_TYPES:
            data["activity_type"] = "other"
        data["status"] = str(data.get("status") or "running")
        if data["status"] not in {"running", "paused", "stopped"}:
            data["status"] = "stopped"
        fields = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in data.items() if key in fields})

    def current_elapsed(self, now: datetime | None = None) -> int:
        base = max(0, int(self.elapsed_seconds or 0))
        if self.status != "running":
            return base
        current = now or datetime.now(UTC)
        started = parse_iso(self.started_at)
        delta = int((current - started).total_seconds())
        return max(0, base + delta)


class GestioneTimeTracking:
    """Repository JSON/SQLite per il timer attivo della top bar."""

    def __init__(self, db_path: str = "./timesheet/time_tracking.json", studio_db=None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._studio_db = studio_db
        self._timers: dict[str, TimeTrackingTimer] = {}
        self._carica()

    def _carica(self) -> None:
        if self._studio_db is not None:
            rows = self._studio_db.carica_tabella("time_tracking_timers")
            self._timers = {}
            for row in rows:
                try:
                    timer = TimeTrackingTimer.from_dict(row)
                except Exception:
                    continue
                self._timers[timer.id] = timer
            return

        if not self.db_path.exists():
            self._timers = {}
            return
        try:
            raw = json.loads(self.db_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        values = raw.values() if isinstance(raw, dict) else raw if isinstance(raw, list) else []
        self._timers = {}
        for item in values:
            if not isinstance(item, dict):
                continue
            timer = TimeTrackingTimer.from_dict(item)
            self._timers[timer.id] = timer

    def _salva(self) -> None:
        if self._studio_db is not None:

            def _insert(conn, timer: TimeTrackingTimer) -> None:
                payload = timer.to_dict()
                conn.execute(
                    """
                    INSERT INTO time_tracking_timers
                    (id, user_id, username, id_fascicolo, id_cliente, activity_type,
                     description, started_at, paused_at, ended_at, elapsed_seconds,
                     status, created_at, updated_at, dati_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        timer.id,
                        timer.user_id or None,
                        timer.username,
                        timer.case_id or None,
                        timer.client_id or None,
                        timer.activity_type,
                        timer.description,
                        timer.started_at,
                        timer.paused_at or None,
                        timer.ended_at or None,
                        int(timer.elapsed_seconds or 0),
                        timer.status,
                        timer.created_at,
                        timer.updated_at,
                        json.dumps(payload, ensure_ascii=False),
                    ),
                )

            self._studio_db.salva_tabella("time_tracking_timers", list(self._timers.values()), _insert)
            return

        from pct import cache as _cache

        _cache.save(self.db_path, {key: value.to_dict() for key, value in self._timers.items()})

    @staticmethod
    def _normalize_activity(activity_type: str) -> str:
        candidate = str(activity_type or "other").strip().lower()
        return candidate if candidate in ACTIVITY_TYPES else "other"

    def active_for_user(self, user_id: str) -> TimeTrackingTimer | None:
        user = str(user_id or "").strip()
        candidates = [
            timer
            for timer in self._timers.values()
            if timer.user_id == user and timer.status in ACTIVE_STATUSES
        ]
        candidates.sort(key=lambda item: item.updated_at or item.started_at, reverse=True)
        return candidates[0] if candidates else None

    def get(self, timer_id: str) -> TimeTrackingTimer | None:
        return self._timers.get(str(timer_id or "").strip())

    def start(
        self,
        *,
        user_id: str,
        username: str = "",
        case_id: str = "",
        client_id: str = "",
        activity_type: str = "other",
        description: str = "",
    ) -> TimeTrackingTimer:
        if self.active_for_user(user_id):
            raise RuntimeError("timer_concorrente")
        now = utc_now_iso()
        timer = TimeTrackingTimer(
            user_id=str(user_id or "").strip(),
            username=str(username or "").strip(),
            case_id=str(case_id or "").strip(),
            client_id=str(client_id or "").strip(),
            activity_type=self._normalize_activity(activity_type),
            description=str(description or "").strip()[:500],
            started_at=now,
            created_at=now,
            updated_at=now,
        )
        self._timers[timer.id] = timer
        self._salva()
        return timer

    def pause(self, timer_id: str, user_id: str) -> TimeTrackingTimer:
        timer = self._owned_timer(timer_id, user_id)
        if timer.status != "running":
            return timer
        now_dt = datetime.now(UTC)
        timer.elapsed_seconds = timer.current_elapsed(now_dt)
        timer.paused_at = now_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        timer.status = "paused"
        timer.updated_at = timer.paused_at
        self._salva()
        return timer

    def resume(self, timer_id: str, user_id: str) -> TimeTrackingTimer:
        timer = self._owned_timer(timer_id, user_id)
        if timer.status != "paused":
            return timer
        now = utc_now_iso()
        timer.started_at = now
        timer.paused_at = ""
        timer.status = "running"
        timer.updated_at = now
        self._salva()
        return timer

    def stop(self, timer_id: str, user_id: str) -> TimeTrackingTimer:
        timer = self._owned_timer(timer_id, user_id)
        if timer.status == "stopped":
            return timer
        now_dt = datetime.now(UTC)
        timer.elapsed_seconds = timer.current_elapsed(now_dt)
        timer.ended_at = now_dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        timer.paused_at = ""
        timer.status = "stopped"
        timer.updated_at = timer.ended_at
        self._salva()
        return timer

    def collega_timesheet(self, timer_id: str, user_id: str, entry_id: str) -> TimeTrackingTimer:
        timer = self._owned_timer(timer_id, user_id)
        timer.timesheet_entry_id = str(entry_id or "").strip()
        timer.updated_at = utc_now_iso()
        self._salva()
        return timer

    def _owned_timer(self, timer_id: str, user_id: str) -> TimeTrackingTimer:
        timer = self.get(timer_id)
        if timer is None:
            raise KeyError("timer_non_trovato")
        if timer.user_id != str(user_id or "").strip():
            raise PermissionError("timer_non_autorizzato")
        return timer
