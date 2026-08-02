"""Repository materializzato del piano del giorno (SQLite + PostgreSQL).

Segue il pattern canonico di ``pct/workspace_intelligence_repository.py`` e
``pct/notifications/repository.py``: schema versionato in ``pct/sql/``,
backend PostgreSQL opzionale via ``PostgresRepositoryBackend``, isolamento
tenant fail-closed (``tenant_id`` legato al costruttore e presente in ogni
WHERE). Transazioni brevi, upsert batch, query parametrizzate.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pct.postgres_runtime_support import PostgresRepositoryBackend

from .clock import Clock, system_clock
from .models import (
    HUMAN_STATUSES,
    ITEM_STATUS_TRANSITIONS,
    DailyWorkItem,
    OperationalSignal,
    SignalEvidence,
    redact_text,
)

SCHEMA_DAILY_PLAN = Path(__file__).resolve().parents[1] / "sql" / "20260711_daily_plan.sql"
POSTGRES_SCHEMA_DAILY_PLAN = (
    Path(__file__).resolve().parents[1] / "sql" / "20260711_daily_plan_postgres.sql"
)

_ITEM_COLUMNS = (
    "id, tenant_id, target_date, assigned_user_id, assigned_lawyer_label, plan_version, "
    "priority, item_rank, action_kind, sector, status, title, reason, priority_reason, "
    "priority_rule, fascicolo_id, fascicolo_label, cliente_id, cliente_label, due_at, "
    "blocking, peremptory, confidence, review_required, scheduled_start, estimated_minutes, "
    "in_backlog, source_signal_ids_json, evidence_json, available_actions_json, href, "
    "snoozed_until, status_actor, status_note, status_updated_at, dedupe_key, created_at, updated_at"
)

_SQLITE_REQUIRED_SCHEMA_OBJECTS = frozenset(
    {
        "operational_signals",
        "daily_plan_items",
        "daily_plan_snapshots",
        "daily_plan_source_watermarks",
        "daily_plan_jobs",
        "dirty_entities",
        "daily_plan_action_log",
        "idx_dp_signals_tenant_dedupe",
        "idx_dp_signals_tenant_status_due",
        "idx_dp_signals_tenant_fascicolo",
        "idx_dp_signals_tenant_source",
        "idx_dp_items_tenant_date_dedupe",
        "idx_dp_items_tenant_user_date_prio",
        "idx_dp_items_tenant_status_due",
        "idx_dp_items_tenant_fascicolo",
        "idx_dp_snapshots_tenant_date_user",
        "idx_dp_jobs_tenant_status",
        "idx_dp_jobs_tenant_idem",
        "idx_dp_dirty_pending",
        "idx_dp_action_idem",
        "idx_dp_action_item",
    }
)

# Il budget dichiarato per una richiesta manuale e' breve, ma la
# riconciliazione completa di uno studio puo' richiedere piu' tempo. Il
# margine evita di interrompere un'elaborazione lecita e, al riavvio, evita
# che un job rimasto ``running`` blocchi per sempre la coda dello studio.
STALE_RUNNING_JOB_SECONDS = 45 * 60


def derive_daily_plan_db_path(anchor: str) -> str:
    """Percorso del DB piano del giorno accanto a un file dati del tenant."""
    target = Path(str(anchor or "./intelligence/anchor.json")).resolve()
    return str(target.with_name("daily_plan.db"))


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


class TenantMismatchError(PermissionError):
    """Accesso a dati di un tenant diverso da quello legato al repository."""


class InvalidStatusTransition(ValueError):
    """Transizione di stato non ammessa dalla state machine delle attività."""


class DailyPlanRepository:
    def __init__(
        self,
        db_path: str,
        *,
        tenant_id: str,
        postgres_dsn: str = "",
        postgres_schema_path: Path | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.db_path = str(db_path or "").strip()
        self.tenant_id = str(tenant_id or "").strip()
        if not self.tenant_id:
            raise ValueError("tenant_id obbligatorio per DailyPlanRepository")
        self.postgres_dsn = str(postgres_dsn or "").strip()
        self.postgres_schema_path = Path(postgres_schema_path or POSTGRES_SCHEMA_DAILY_PLAN)
        self.backend_kind = "postgresql" if self.postgres_dsn else "sqlite"
        self._postgres_backend = (
            PostgresRepositoryBackend(self.postgres_dsn, self.postgres_schema_path)
            if self.postgres_dsn
            else None
        )
        self.clock = clock or system_clock()
        self._ensure_schema()

    # ------------------------------------------------------------- infra

    def _connect(self):
        if self._postgres_backend is not None:
            return self._postgres_backend.connection()
        target = Path(self.db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(target), timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    @staticmethod
    def _sqlite_schema_ready(conn: sqlite3.Connection) -> bool:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
        ).fetchall()
        present = {str(row[0]) for row in rows}
        return _SQLITE_REQUIRED_SCHEMA_OBJECTS.issubset(present)

    def _ensure_schema(self) -> None:
        if self._postgres_backend is not None:
            schema = self.postgres_schema_path.read_text(encoding="utf-8")
            with self._connect() as conn:
                conn.executescript(schema)
                conn.commit()
            return

        with self._connect() as conn:
            if self._sqlite_schema_ready(conn):
                return
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            conn.executescript(SCHEMA_DAILY_PLAN.read_text(encoding="utf-8"))
            conn.commit()

    def _now_iso(self) -> str:
        return self.clock.now().isoformat(timespec="seconds")

    # ----------------------------------------------------------- signals

    def upsert_signals(self, signals: Iterable[OperationalSignal]) -> dict[str, int]:
        """Upsert batch per dedupe_key. Conserva created_at della prima vista."""
        now = self._now_iso()
        inserted = 0
        updated = 0
        rows = []
        for sig in signals:
            if sig.tenant_id and sig.tenant_id != self.tenant_id:
                raise TenantMismatchError("segnale di un altro tenant rifiutato")
            rows.append(sig)
        with self._connect() as conn:
            for sig in rows:
                existing = conn.execute(
                    "SELECT id FROM operational_signals WHERE tenant_id = ? AND dedupe_key = ?",
                    (self.tenant_id, sig.dedupe_key),
                ).fetchone()
                if existing:
                    updated += 1
                    # L'identificativo tecnico dei collector può essere
                    # deterministico (es. stessa sorgente importata due volte
                    # con chiavi di deduplica diverse). Conserviamo quindi
                    # sempre l'ID già materializzato per la medesima chiave.
                    signal_id = str(existing["id"] or "")
                else:
                    inserted += 1
                    # ``id`` è PK globale anche quando la deduplica è
                    # tenant-aware. Un ID proposto da una sorgente non deve
                    # mai impedire il piano del giorno: se è già occupato da
                    # un altro segnale, assegniamo un ID interno nuovo e
                    # lasciamo invariata la chiave di deduplica operativa.
                    signal_id = str(sig.id or new_id("sig"))
                    while conn.execute(
                        "SELECT 1 FROM operational_signals WHERE id = ?", (signal_id,)
                    ).fetchone():
                        signal_id = new_id("sig")
                # I successivi passaggi costruiscono le attività usando gli
                # oggetti raccolti: mantenerli allineati evita riferimenti a
                # un ID tecnico che è stato sostituito per collisione.
                sig.id = signal_id
                conn.execute(
                    """
                    INSERT INTO operational_signals (
                        id, tenant_id, source_type, source_id, source_version,
                        fascicolo_id, cliente_id, lawyer_hint, responsible_user_id,
                        kind, title, description, reason, event_at, due_at,
                        legal_risk, priority_hint, blocking, peremptory, confidence,
                        status, evidence_json, href, dedupe_key, metadata_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tenant_id, dedupe_key) DO UPDATE SET
                        source_type = excluded.source_type,
                        source_id = excluded.source_id,
                        source_version = excluded.source_version,
                        fascicolo_id = excluded.fascicolo_id,
                        cliente_id = excluded.cliente_id,
                        lawyer_hint = excluded.lawyer_hint,
                        responsible_user_id = excluded.responsible_user_id,
                        kind = excluded.kind,
                        title = excluded.title,
                        description = excluded.description,
                        reason = excluded.reason,
                        event_at = excluded.event_at,
                        due_at = excluded.due_at,
                        legal_risk = excluded.legal_risk,
                        priority_hint = excluded.priority_hint,
                        blocking = excluded.blocking,
                        peremptory = excluded.peremptory,
                        confidence = excluded.confidence,
                        status = excluded.status,
                        evidence_json = excluded.evidence_json,
                        href = excluded.href,
                        metadata_json = excluded.metadata_json,
                        updated_at = excluded.updated_at
                    """,
                    (
                        signal_id,
                        self.tenant_id,
                        sig.source_type,
                        sig.source_id,
                        sig.source_version,
                        sig.fascicolo_id,
                        sig.cliente_id,
                        sig.lawyer_hint,
                        sig.responsible_user_id,
                        sig.kind,
                        sig.title,
                        sig.description,
                        sig.reason,
                        sig.event_at,
                        sig.due_at,
                        sig.legal_risk,
                        sig.priority_hint,
                        1 if sig.blocking else 0,
                        1 if sig.peremptory else 0,
                        float(sig.confidence or 0.0),
                        sig.status or "active",
                        json.dumps([e.to_dict() for e in sig.evidence], ensure_ascii=False),
                        sig.href,
                        sig.dedupe_key,
                        json.dumps(sig.metadata, ensure_ascii=False),
                        sig.created_at or now,
                        now,
                    ),
                )
            conn.commit()
        return {"inserted": inserted, "updated": updated}

    def list_active_signals(
        self,
        *,
        source_type: str = "",
        fascicolo_id: str = "",
        limit: int = 2000,
    ) -> list[OperationalSignal]:
        query = "SELECT * FROM operational_signals WHERE tenant_id = ? AND status = 'active'"
        params: list[Any] = [self.tenant_id]
        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)
        if fascicolo_id:
            query += " AND fascicolo_id = ?"
            params.append(fascicolo_id)
        query += " ORDER BY due_at, dedupe_key LIMIT ?"
        params.append(max(int(limit), 1))
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._signal_from_row(row) for row in rows]

    def resolve_signals_not_in(
        self, source_type: str, keep_dedupe_keys: Iterable[str]
    ) -> int:
        """Dopo una scansione completa di una fonte, marca 'resolved' i segnali
        di quella fonte non più riemessi."""
        keep = set(keep_dedupe_keys)
        now = self._now_iso()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT dedupe_key FROM operational_signals "
                "WHERE tenant_id = ? AND source_type = ? AND status = 'active'",
                (self.tenant_id, source_type),
            ).fetchall()
            stale = [r["dedupe_key"] for r in rows if r["dedupe_key"] not in keep]
            for key in stale:
                conn.execute(
                    "UPDATE operational_signals SET status = 'resolved', updated_at = ? "
                    "WHERE tenant_id = ? AND dedupe_key = ?",
                    (now, self.tenant_id, key),
                )
            conn.commit()
        return len(stale)

    def _signal_from_row(self, row: Any) -> OperationalSignal:
        data = dict(row)
        data["evidence"] = [
            SignalEvidence.from_dict(e)
            for e in json.loads(data.pop("evidence_json", "[]") or "[]")
        ]
        data["metadata"] = json.loads(data.pop("metadata_json", "{}") or "{}")
        data["blocking"] = bool(data.get("blocking"))
        data["peremptory"] = bool(data.get("peremptory"))
        return OperationalSignal(**{
            k: v for k, v in data.items() if k in OperationalSignal.__dataclass_fields__
        })

    # ------------------------------------------------------------- items

    def replace_items_for_date(
        self,
        target_date: str,
        items: Iterable[DailyWorkItem],
        *,
        plan_version: str,
    ) -> dict[str, int]:
        """Upsert degli item del giorno preservando gli stati decisi da persone.

        Gli item esistenti non riemessi diventano ``obsolete`` (mai cancellati).
        """
        now = self._now_iso()
        new_items = list(items)
        seen_keys = {i.dedupe_key for i in new_items}
        stats = {"inserted": 0, "updated": 0, "obsoleted": 0, "preserved_status": 0}
        with self._connect() as conn:
            existing_rows = conn.execute(
                "SELECT id, dedupe_key, status, status_actor, status_note, "
                "status_updated_at, snoozed_until, created_at "
                "FROM daily_plan_items WHERE tenant_id = ? AND target_date = ?",
                (self.tenant_id, target_date),
            ).fetchall()
            existing = {r["dedupe_key"]: r for r in existing_rows}

            for item in new_items:
                if item.tenant_id and item.tenant_id != self.tenant_id:
                    raise TenantMismatchError("item di un altro tenant rifiutato")
                prev = existing.get(item.dedupe_key)
                status = item.status
                status_actor = item.status_actor
                status_note = item.status_note
                status_updated_at = item.status_updated_at
                snoozed_until = item.snoozed_until
                created_at = item.created_at or now
                item_id = item.id or new_id("dpi")
                if prev is not None:
                    item_id = prev["id"]
                    created_at = prev["created_at"] or created_at
                    if prev["status"] in HUMAN_STATUSES:
                        status = prev["status"]
                        status_actor = prev["status_actor"]
                        status_note = prev["status_note"]
                        status_updated_at = prev["status_updated_at"]
                        snoozed_until = prev["snoozed_until"]
                        stats["preserved_status"] += 1
                    stats["updated"] += 1
                else:
                    stats["inserted"] += 1
                conn.execute(
                    f"""
                    INSERT INTO daily_plan_items ({_ITEM_COLUMNS})
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(tenant_id, target_date, dedupe_key) DO UPDATE SET
                        assigned_user_id = excluded.assigned_user_id,
                        assigned_lawyer_label = excluded.assigned_lawyer_label,
                        plan_version = excluded.plan_version,
                        priority = excluded.priority,
                        item_rank = excluded.item_rank,
                        action_kind = excluded.action_kind,
                        sector = excluded.sector,
                        status = excluded.status,
                        title = excluded.title,
                        reason = excluded.reason,
                        priority_reason = excluded.priority_reason,
                        priority_rule = excluded.priority_rule,
                        fascicolo_id = excluded.fascicolo_id,
                        fascicolo_label = excluded.fascicolo_label,
                        cliente_id = excluded.cliente_id,
                        cliente_label = excluded.cliente_label,
                        due_at = excluded.due_at,
                        blocking = excluded.blocking,
                        peremptory = excluded.peremptory,
                        confidence = excluded.confidence,
                        review_required = excluded.review_required,
                        scheduled_start = excluded.scheduled_start,
                        estimated_minutes = excluded.estimated_minutes,
                        in_backlog = excluded.in_backlog,
                        source_signal_ids_json = excluded.source_signal_ids_json,
                        evidence_json = excluded.evidence_json,
                        available_actions_json = excluded.available_actions_json,
                        href = excluded.href,
                        snoozed_until = excluded.snoozed_until,
                        status_actor = excluded.status_actor,
                        status_note = excluded.status_note,
                        status_updated_at = excluded.status_updated_at,
                        updated_at = excluded.updated_at
                    """,
                    (
                        item_id,
                        self.tenant_id,
                        target_date,
                        item.assigned_user_id,
                        item.assigned_lawyer_label,
                        plan_version,
                        item.priority,
                        int(item.item_rank),
                        item.action_kind,
                        item.sector,
                        status,
                        item.title,
                        item.reason,
                        item.priority_reason,
                        item.priority_rule,
                        item.fascicolo_id,
                        item.fascicolo_label,
                        item.cliente_id,
                        item.cliente_label,
                        item.due_at,
                        1 if item.blocking else 0,
                        1 if item.peremptory else 0,
                        float(item.confidence or 0.0),
                        1 if item.review_required else 0,
                        item.scheduled_start,
                        int(item.estimated_minutes or 0),
                        1 if item.in_backlog else 0,
                        json.dumps(item.source_signal_ids, ensure_ascii=False),
                        json.dumps([e.to_dict() for e in item.evidence], ensure_ascii=False),
                        json.dumps(item.available_actions, ensure_ascii=False),
                        item.href,
                        snoozed_until,
                        status_actor,
                        status_note,
                        status_updated_at,
                        item.dedupe_key,
                        created_at,
                        now,
                    ),
                )

            for key, prev in existing.items():
                if key not in seen_keys and prev["status"] not in ("obsolete",):
                    conn.execute(
                        "UPDATE daily_plan_items SET status = 'obsolete', updated_at = ? "
                        "WHERE tenant_id = ? AND target_date = ? AND dedupe_key = ?",
                        (now, self.tenant_id, target_date, key),
                    )
                    stats["obsoleted"] += 1
            conn.commit()
        return stats

    def list_items(
        self,
        target_date: str,
        *,
        assigned_user_id: str | None = None,
        include_backlog: bool = False,
        include_obsolete: bool = False,
        limit: int = 500,
    ) -> list[DailyWorkItem]:
        query = "SELECT * FROM daily_plan_items WHERE tenant_id = ? AND target_date = ?"
        params: list[Any] = [self.tenant_id, target_date]
        if assigned_user_id is not None:
            query += " AND assigned_user_id = ?"
            params.append(assigned_user_id)
        if not include_backlog:
            query += " AND in_backlog = 0"
        if not include_obsolete:
            query += " AND status <> 'obsolete'"
        query += " ORDER BY priority, item_rank, dedupe_key LIMIT ?"
        params.append(max(int(limit), 1))
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._item_from_row(row) for row in rows]

    def list_backlog_page(
        self,
        target_date: str,
        *,
        assigned_user_id: str | None = None,
        cursor: str = "",
        limit: int = 50,
    ) -> dict[str, Any]:
        """Paginazione keyset del backlog su (priority, item_rank)."""
        limit = max(min(int(limit), 200), 1)
        query = (
            "SELECT * FROM daily_plan_items WHERE tenant_id = ? AND target_date = ? "
            "AND in_backlog = 1 AND status <> 'obsolete'"
        )
        params: list[Any] = [self.tenant_id, target_date]
        if assigned_user_id is not None:
            query += " AND assigned_user_id = ?"
            params.append(assigned_user_id)
        count_query = query.replace("SELECT *", "SELECT COUNT(*)", 1)
        if cursor:
            try:
                cur_priority, cur_rank = cursor.split(":", 1)
                query += " AND (priority > ? OR (priority = ? AND item_rank > ?))"
                params.extend([cur_priority, cur_priority, int(cur_rank)])
            except Exception:
                pass
        query += " ORDER BY priority, item_rank, dedupe_key LIMIT ?"
        with self._connect() as conn:
            total = conn.execute(count_query, tuple(params[: 3 if assigned_user_id is not None else 2])).fetchone()
            rows = conn.execute(query, tuple(params) + (limit + 1,)).fetchall()
        items = [self._item_from_row(row) for row in rows[:limit]]
        has_more = len(rows) > limit
        next_cursor = ""
        if has_more and items:
            last = items[-1]
            next_cursor = f"{last.priority}:{last.item_rank}"
        total_matching = int((total or [0])[0] or 0)
        return {
            "items": items,
            "next_cursor": next_cursor,
            "total_matching": total_matching,
            "truncated": has_more,
        }

    def get_item(self, item_id: str) -> DailyWorkItem | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_plan_items WHERE tenant_id = ? AND id = ?",
                (self.tenant_id, item_id),
            ).fetchone()
        return self._item_from_row(row) if row else None

    def update_item_status(
        self,
        item_id: str,
        new_status: str,
        *,
        actor: str = "",
        note: str = "",
        snoozed_until: str = "",
        assigned_user_id: str | None = None,
    ) -> DailyWorkItem:
        item = self.get_item(item_id)
        if item is None:
            raise KeyError(f"attivita non trovata: {item_id}")
        allowed = ITEM_STATUS_TRANSITIONS.get(item.status, ())
        if new_status not in allowed:
            raise InvalidStatusTransition(
                f"transizione non ammessa: {item.status} -> {new_status}"
            )
        now = self._now_iso()
        with self._connect() as conn:
            if assigned_user_id is not None:
                conn.execute(
                    "UPDATE daily_plan_items SET status = ?, status_actor = ?, status_note = ?, "
                    "status_updated_at = ?, snoozed_until = ?, assigned_user_id = ?, updated_at = ? "
                    "WHERE tenant_id = ? AND id = ?",
                    (
                        new_status,
                        actor,
                        redact_text(note),
                        now,
                        snoozed_until,
                        assigned_user_id,
                        now,
                        self.tenant_id,
                        item_id,
                    ),
                )
            else:
                conn.execute(
                    "UPDATE daily_plan_items SET status = ?, status_actor = ?, status_note = ?, "
                    "status_updated_at = ?, snoozed_until = ?, updated_at = ? "
                    "WHERE tenant_id = ? AND id = ?",
                    (
                        new_status,
                        actor,
                        redact_text(note),
                        now,
                        snoozed_until,
                        now,
                        self.tenant_id,
                        item_id,
                    ),
                )
            conn.commit()
        refreshed = self.get_item(item_id)
        assert refreshed is not None
        return refreshed

    def _item_from_row(self, row: Any) -> DailyWorkItem:
        data = dict(row)
        data["source_signal_ids"] = json.loads(data.pop("source_signal_ids_json", "[]") or "[]")
        data["evidence"] = [
            SignalEvidence.from_dict(e)
            for e in json.loads(data.pop("evidence_json", "[]") or "[]")
        ]
        data["available_actions"] = json.loads(data.pop("available_actions_json", "[]") or "[]")
        for flag in ("blocking", "peremptory", "review_required", "in_backlog"):
            data[flag] = bool(data.get(flag))
        return DailyWorkItem(**{
            k: v for k, v in data.items() if k in DailyWorkItem.__dataclass_fields__
        })

    # --------------------------------------------------------- snapshots

    def save_snapshot(
        self,
        *,
        target_date: str,
        user_id: str,
        plan_version: str,
        generation_mode: str,
        freshness: dict[str, Any],
        coverage: dict[str, Any],
        summary: dict[str, Any],
        fixed_agenda: list[dict[str, Any]],
        warnings: list[str],
        lex_summary: str = "",
        lex_summary_version: str = "",
    ) -> None:
        now = self._now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_plan_snapshots (
                    id, tenant_id, target_date, user_id, plan_version, generated_at,
                    generation_mode, freshness_json, coverage_json, summary_json,
                    fixed_agenda_json, warnings_json, lex_summary, lex_summary_version,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, target_date, user_id) DO UPDATE SET
                    plan_version = excluded.plan_version,
                    generated_at = excluded.generated_at,
                    generation_mode = excluded.generation_mode,
                    freshness_json = excluded.freshness_json,
                    coverage_json = excluded.coverage_json,
                    summary_json = excluded.summary_json,
                    fixed_agenda_json = excluded.fixed_agenda_json,
                    warnings_json = excluded.warnings_json,
                    lex_summary = CASE
                        WHEN excluded.lex_summary <> '' THEN excluded.lex_summary
                        WHEN excluded.plan_version = daily_plan_snapshots.plan_version
                            THEN daily_plan_snapshots.lex_summary
                        ELSE ''
                    END,
                    lex_summary_version = CASE
                        WHEN excluded.lex_summary <> '' THEN excluded.lex_summary_version
                        WHEN excluded.plan_version = daily_plan_snapshots.plan_version
                            THEN daily_plan_snapshots.lex_summary_version
                        ELSE ''
                    END,
                    updated_at = excluded.updated_at
                """,
                (
                    new_id("dps"),
                    self.tenant_id,
                    target_date,
                    user_id,
                    plan_version,
                    now,
                    generation_mode,
                    json.dumps(freshness, ensure_ascii=False),
                    json.dumps(coverage, ensure_ascii=False),
                    json.dumps(summary, ensure_ascii=False),
                    json.dumps(fixed_agenda, ensure_ascii=False),
                    json.dumps([redact_text(w) for w in warnings], ensure_ascii=False),
                    lex_summary,
                    lex_summary_version,
                    now,
                    now,
                ),
            )
            conn.commit()

    def get_snapshot(self, target_date: str, user_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_plan_snapshots "
                "WHERE tenant_id = ? AND target_date = ? AND user_id = ?",
                (self.tenant_id, target_date, user_id),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        for key, default in (
            ("freshness_json", "{}"),
            ("coverage_json", "{}"),
            ("summary_json", "{}"),
            ("fixed_agenda_json", "[]"),
            ("warnings_json", "[]"),
        ):
            target = key.replace("_json", "")
            try:
                data[target] = json.loads(data.pop(key) or default)
            except Exception:
                data[target] = json.loads(default)
        return data

    def snapshot_user_ids(self, target_date: str) -> set[str]:
        """Utenti con snapshot per la data del tenant corrente."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT user_id FROM daily_plan_snapshots "
                "WHERE tenant_id = ? AND target_date = ?",
                (self.tenant_id, target_date),
            ).fetchall()
        return {str(row["user_id"] or "") for row in rows}

    def save_lex_summary(
        self, *, target_date: str, user_id: str, plan_version: str, summary: str
    ) -> bool:
        """Salva la sintesi Lex solo se la plan_version corrisponde ancora."""
        now = self._now_iso()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE daily_plan_snapshots SET lex_summary = ?, lex_summary_version = ?, "
                "updated_at = ? WHERE tenant_id = ? AND target_date = ? AND user_id = ? "
                "AND plan_version = ?",
                (summary, plan_version, now, self.tenant_id, target_date, user_id, plan_version),
            )
            conn.commit()
            return bool(cur.rowcount)

    # -------------------------------------------------------- watermarks

    def get_watermarks(self) -> dict[str, dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_plan_source_watermarks WHERE tenant_id = ?",
                (self.tenant_id,),
            ).fetchall()
        return {row["source_type"]: dict(row) for row in rows}

    def set_watermark(
        self,
        source_type: str,
        *,
        watermark: str = "",
        status: str = "ok",
        error: str = "",
    ) -> None:
        now = self._now_iso()
        last_success = now if status == "ok" else ""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO daily_plan_source_watermarks (
                    tenant_id, source_type, watermark, last_success_at, last_error,
                    last_status, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, source_type) DO UPDATE SET
                    watermark = CASE WHEN excluded.watermark <> ''
                        THEN excluded.watermark
                        ELSE daily_plan_source_watermarks.watermark END,
                    last_success_at = CASE WHEN excluded.last_success_at <> ''
                        THEN excluded.last_success_at
                        ELSE daily_plan_source_watermarks.last_success_at END,
                    last_error = excluded.last_error,
                    last_status = excluded.last_status,
                    updated_at = excluded.updated_at
                """,
                (
                    self.tenant_id,
                    source_type,
                    watermark,
                    last_success,
                    redact_text(error),
                    status,
                    now,
                ),
            )
            conn.commit()

    # -------------------------------------------------------------- jobs

    def recover_stale_running_jobs(
        self, *, max_age_seconds: int = STALE_RUNNING_JOB_SECONDS
    ) -> int:
        """Chiude in modo terminale i job rimasti ``running`` dopo un crash.

        Non esiste una lease persistente nelle versioni precedenti dello
        schema. Perciò un job senza ``started_at`` valido o oltre la soglia
        viene marcato fallito e liberato dalla relativa idempotency key: una
        nuova richiesta puo' essere accodata e il recupero automatico della
        giornata non resta ostaggio di una riga zombie.
        """
        try:
            age_seconds = max(60, int(max_age_seconds or STALE_RUNNING_JOB_SECONDS))
        except (TypeError, ValueError):
            age_seconds = STALE_RUNNING_JOB_SECONDS
        now = self.clock.now()
        cutoff = now - timedelta(seconds=age_seconds)
        stale_ids: list[tuple[str, str]] = []

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, started_at FROM daily_plan_jobs "
                "WHERE tenant_id = ? AND status = 'running'",
                (self.tenant_id,),
            ).fetchall()
            for row in rows:
                raw_started = str(row["started_at"] or "").strip()
                stale = not raw_started
                if raw_started:
                    try:
                        parsed = datetime.fromisoformat(
                            raw_started[:-1] + "+00:00"
                            if raw_started.endswith("Z")
                            else raw_started
                        )
                        if parsed.tzinfo is None:
                            parsed = parsed.replace(tzinfo=now.tzinfo)
                        stale = parsed <= cutoff
                    except (TypeError, ValueError):
                        stale = True
                if stale:
                    stale_ids.append((str(row["id"] or ""), raw_started))

            recovered = 0
            report = json.dumps(
                {
                    "ok": False,
                    "code": "stale_running_recovered",
                },
                ensure_ascii=False,
            )
            finished_at = self._now_iso()
            for job_id, started_at in stale_ids:
                if not job_id:
                    continue
                updated = conn.execute(
                    "UPDATE daily_plan_jobs "
                    "SET status = 'failed', finished_at = ?, report_json = ?, idempotency_key = '' "
                    "WHERE tenant_id = ? AND id = ? AND status = 'running' AND started_at = ?",
                    (finished_at, report, self.tenant_id, job_id, started_at),
                )
                if int(updated.rowcount or 0) > 0:
                    recovered += 1
            conn.commit()
        return recovered

    def enqueue_job(
        self,
        job_type: str,
        *,
        requested_by: str = "",
        idempotency_key: str = "",
        payload: dict[str, Any] | None = None,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.recover_stale_running_jobs()
        now = self._now_iso()
        with self._connect() as conn:
            if idempotency_key:
                row = conn.execute(
                    "SELECT id, status FROM daily_plan_jobs "
                    "WHERE tenant_id = ? AND idempotency_key = ?",
                    (self.tenant_id, idempotency_key),
                ).fetchone()
                if row:
                    return {"job_id": row["id"], "status": row["status"], "replayed": True}
            open_rows = conn.execute(
                "SELECT id, status, payload_json FROM daily_plan_jobs "
                "WHERE tenant_id = ? AND job_type = ? AND status IN ('queued', 'running') "
                "ORDER BY created_at",
                (self.tenant_id, job_type),
            ).fetchall()
            requested_payload = payload or {}
            for open_row in open_rows:
                try:
                    raw_payload = open_row["payload_json"] or "{}"
                    existing_payload = (
                        raw_payload
                        if isinstance(raw_payload, dict)
                        else json.loads(raw_payload)
                    )
                except Exception:
                    existing_payload = {}
                if existing_payload == requested_payload:
                    return {
                        "job_id": open_row["id"],
                        "status": open_row["status"],
                        "replayed": True,
                    }
            job_id = new_id("dpj")
            conn.execute(
                "INSERT INTO daily_plan_jobs (id, tenant_id, job_type, status, requested_by, "
                "idempotency_key, payload_json, budget_json, created_at) "
                "VALUES (?, ?, ?, 'queued', ?, ?, ?, ?, ?)",
                (
                    job_id,
                    self.tenant_id,
                    job_type,
                    requested_by,
                    idempotency_key,
                    json.dumps(requested_payload, ensure_ascii=False),
                    json.dumps(budget or {}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
        return {"job_id": job_id, "status": "queued", "replayed": False}

    def claim_next_job(self, job_type: str = "") -> dict[str, Any] | None:
        self.recover_stale_running_jobs()
        now = self._now_iso()
        with self._connect() as conn:
            query = (
                "SELECT * FROM daily_plan_jobs WHERE tenant_id = ? AND status = 'queued'"
            )
            params: list[Any] = [self.tenant_id]
            if job_type:
                query += " AND job_type = ?"
                params.append(job_type)
            query += " ORDER BY created_at LIMIT 1"
            row = conn.execute(query, tuple(params)).fetchone()
            if not row:
                return None
            claimed = conn.execute(
                "UPDATE daily_plan_jobs SET status = 'running', started_at = ? "
                "WHERE tenant_id = ? AND id = ? AND status = 'queued'",
                (now, self.tenant_id, row["id"]),
            )
            conn.commit()
            if int(claimed.rowcount or 0) <= 0:
                return None
            data = dict(row)
            data["status"] = "running"
            data["payload"] = json.loads(data.pop("payload_json", "{}") or "{}")
            data["budget"] = json.loads(data.pop("budget_json", "{}") or "{}")
            return data

    def finish_job(
        self, job_id: str, *, status: str = "done", report: dict[str, Any] | None = None
    ) -> None:
        now = self._now_iso()
        with self._connect() as conn:
            conn.execute(
                "UPDATE daily_plan_jobs SET status = ?, finished_at = ?, report_json = ? "
                "WHERE tenant_id = ? AND id = ? AND status IN ('queued', 'running')",
                (
                    status,
                    now,
                    json.dumps(report or {}, ensure_ascii=False),
                    self.tenant_id,
                    job_id,
                ),
            )
            conn.commit()

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """Restituisce lo stato di un job della coda del tenant corrente.

        La lettura e' intenzionalmente piccola e tenant-scoped: serve alla UI
        soltanto per distinguere in coda, in lavorazione, concluso o fallito,
        senza interrogare collettori o dati di dominio.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_plan_jobs WHERE tenant_id = ? AND id = ?",
                (self.tenant_id, job_id),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        for column, key in (
            ("payload_json", "payload"),
            ("budget_json", "budget"),
            ("report_json", "report"),
        ):
            try:
                raw = data.pop(column, "{}") or "{}"
                decoded = raw if isinstance(raw, dict) else json.loads(raw)
            except Exception:
                decoded = {}
            data[key] = decoded if isinstance(decoded, dict) else {}
        return data

    # -------------------------------------------------------------- dirty

    def mark_dirty(
        self, entity_type: str, entity_ids: Iterable[str], *, reason: str = ""
    ) -> int:
        now = self._now_iso()
        count = 0
        with self._connect() as conn:
            for entity_id in entity_ids:
                if not str(entity_id or "").strip():
                    continue
                conn.execute(
                    """
                    INSERT INTO dirty_entities (
                        tenant_id, entity_type, entity_id, reason, marked_at, consumed_at
                    ) VALUES (?, ?, ?, ?, ?, '')
                    ON CONFLICT(tenant_id, entity_type, entity_id) DO UPDATE SET
                        reason = excluded.reason,
                        marked_at = excluded.marked_at,
                        consumed_at = ''
                    """,
                    (self.tenant_id, entity_type, str(entity_id), redact_text(reason, max_len=120), now),
                )
                count += 1
            conn.commit()
        return count

    def consume_dirty(self, *, limit: int = 200) -> list[dict[str, Any]]:
        now = self._now_iso()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT tenant_id, entity_type, entity_id, reason, marked_at "
                "FROM dirty_entities WHERE tenant_id = ? AND consumed_at = '' "
                "ORDER BY marked_at LIMIT ?",
                (self.tenant_id, max(int(limit), 1)),
            ).fetchall()
            for row in rows:
                conn.execute(
                    "UPDATE dirty_entities SET consumed_at = ? "
                    "WHERE tenant_id = ? AND entity_type = ? AND entity_id = ?",
                    (now, self.tenant_id, row["entity_type"], row["entity_id"]),
                )
            conn.commit()
        return [dict(row) for row in rows]

    def pending_dirty_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM dirty_entities WHERE tenant_id = ? AND consumed_at = ''",
                (self.tenant_id,),
            ).fetchone()
        return int((row or [0])[0] or 0)

    # --------------------------------------------------------- action log

    def get_action_by_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        if not idempotency_key:
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM daily_plan_action_log "
                "WHERE tenant_id = ? AND idempotency_key = ?",
                (self.tenant_id, idempotency_key),
            ).fetchone()
        if not row:
            return None
        data = dict(row)
        data["result"] = json.loads(data.pop("result_json", "{}") or "{}")
        return data

    def record_action(
        self,
        *,
        item_id: str,
        action: str,
        actor: str = "",
        idempotency_key: str = "",
        result: dict[str, Any] | None = None,
    ) -> str:
        now = self._now_iso()
        action_id = new_id("dpa")
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO daily_plan_action_log (id, tenant_id, item_id, action, actor, "
                "idempotency_key, result_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    action_id,
                    self.tenant_id,
                    item_id,
                    action,
                    actor,
                    idempotency_key,
                    json.dumps(result or {}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
        return action_id

    # -------------------------------------------------------------- stats

    def storage_stats(self) -> dict[str, Any]:
        with self._connect() as conn:
            signals = conn.execute(
                "SELECT COUNT(*) FROM operational_signals WHERE tenant_id = ?",
                (self.tenant_id,),
            ).fetchone()
            items = conn.execute(
                "SELECT COUNT(*) FROM daily_plan_items WHERE tenant_id = ?",
                (self.tenant_id,),
            ).fetchone()
        return {
            "backend_kind": self.backend_kind,
            "tenant_id": self.tenant_id,
            "operational_signals": int((signals or [0])[0] or 0),
            "daily_plan_items": int((items or [0])[0] or 0),
        }


__all__ = [
    "DailyPlanRepository",
    "InvalidStatusTransition",
    "POSTGRES_SCHEMA_DAILY_PLAN",
    "SCHEMA_DAILY_PLAN",
    "TenantMismatchError",
    "derive_daily_plan_db_path",
    "new_id",
]
