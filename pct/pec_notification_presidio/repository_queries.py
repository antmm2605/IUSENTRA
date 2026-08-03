from __future__ import annotations

from typing import Any, Mapping

from .models import (
    PresidioProjection,
    PresidioStatus,
    Priority,
    ProjectionPage,
    canonical_json,
    canonical_timestamp,
    json_load,
    required_text,
    utc_now_iso,
)


class NotificationPresidioQueryMixin:

    def list_presidia(
        self,
        *,
        status: str = "",
        priority: str = "",
        fascicolo_id: str = "",
        assigned_user_id: str = "",
        channel: str = "",
        recipient_identity_key: str = "",
        legacy_assumed_handled: bool | None = None,
        needs_review: bool | None = None,
        date_from: str = "",
        date_to: str = "",
        cursor: tuple[str, str] | None = None,
        limit: int = 50,
    ) -> ProjectionPage:
        page_size = max(1, min(int(limit or 50), 100))
        where = ["p.tenant_id=?"]
        params: list[Any] = [self.tenant_id]
        if status:
            status_values = [
                PresidioStatus(item.strip()).value
                for item in str(status).split(",")
                if item.strip()
            ]
            if len(status_values) == 1:
                where.append("p.status=?")
                params.append(status_values[0])
            elif status_values:
                where.append("p.status IN (" + ",".join("?" for _ in status_values) + ")")
                params.extend(status_values)
        if priority:
            where.append("p.priority=?")
            params.append(Priority(priority).value)
        if fascicolo_id:
            where.append("p.fascicolo_id=?")
            params.append(fascicolo_id)
        if assigned_user_id:
            where.append("p.assigned_user_id=?")
            params.append(assigned_user_id)
        if channel:
            where.append("p.channel=?")
            params.append(channel.strip().lower())
        if recipient_identity_key:
            recipient_filter = str(recipient_identity_key).strip()
            if len(recipient_filter) == 64 and all(ch in "0123456789abcdef" for ch in recipient_filter.lower()):
                where.append(
                    "EXISTS (SELECT 1 FROM pec_legal_notification_recipients rf "
                    "WHERE rf.tenant_id=p.tenant_id AND rf.presidio_id=p.id "
                    "AND rf.recipient_identity_key=?)"
                )
                params.append(recipient_filter)
            else:
                where.append(
                    "EXISTS (SELECT 1 FROM pec_legal_notification_recipients rf "
                    "WHERE rf.tenant_id=p.tenant_id AND rf.presidio_id=p.id "
                    "AND (LOWER(rf.name) LIKE ? OR LOWER(rf.pec_address) LIKE ? "
                    "OR LOWER(rf.fiscal_id) LIKE ? OR LOWER(rf.recipient_identity_key) LIKE ?))"
                )
                needle = f"%{recipient_filter.lower()}%"
                params.extend((needle, needle, needle, needle))
        if legacy_assumed_handled is not None:
            where.append("p.legacy_assumed_handled=?")
            params.append(bool(legacy_assumed_handled))
        if needs_review is not None:
            where.append("p.human_review_required=?")
            params.append(bool(needs_review))
        if date_from:
            where.append("p.source_effective_at>=?")
            params.append(canonical_timestamp(date_from))
        if date_to:
            where.append("p.source_effective_at<=?")
            params.append(canonical_timestamp(date_to))
        if cursor:
            where.append("(p.updated_at<? OR (p.updated_at=? AND p.id<?))")
            cursor_at = canonical_timestamp(cursor[0])
            params.extend((cursor_at, cursor_at, cursor[1]))
        params.append(page_size + 1)
        sql = f"""
            SELECT p.id, p.fascicolo_id, p.status, p.priority, p.confidence,
                   p.human_review_required, p.trigger_type, p.notification_case,
                   p.channel, p.assigned_user_id, p.legacy_assumed_handled,
                   p.proof_deposit_required, p.resolution_code,
                   p.source_effective_at, p.explicit_due_at,
                   p.created_at, p.updated_at,
                   SUM(CASE WHEN r.required=TRUE THEN 1 ELSE 0 END) AS recipients_total,
                   SUM(CASE WHEN r.required=TRUE AND r.send_status='sent' THEN 1 ELSE 0 END) AS recipients_sent,
                   SUM(CASE WHEN r.required=TRUE AND r.rac_status='received' THEN 1 ELSE 0 END) AS recipients_rac,
                   SUM(
                       CASE WHEN r.required=TRUE AND r.delivery_status='delivered' THEN 1 ELSE 0 END
                   ) AS recipients_delivered,
                   SUM(CASE WHEN r.required=TRUE AND r.delivery_status='failed' THEN 1 ELSE 0 END) AS recipients_failed
            FROM pec_legal_notification_presidia p
            LEFT JOIN pec_legal_notification_recipients r
              ON r.tenant_id=p.tenant_id AND r.presidio_id=p.id
            WHERE {' AND '.join(where)}
            GROUP BY p.id, p.fascicolo_id, p.status, p.priority, p.confidence,
                     p.human_review_required, p.trigger_type, p.notification_case,
                     p.channel, p.assigned_user_id, p.legacy_assumed_handled,
                     p.proof_deposit_required, p.resolution_code,
                     p.source_effective_at, p.explicit_due_at,
                     p.created_at, p.updated_at
            ORDER BY p.updated_at DESC, p.id DESC
            LIMIT ?
        """
        with self.connection() as conn:
            rows = [self._row(row) for row in conn.execute(sql, tuple(params)).fetchall()]
        has_more = len(rows) > page_size
        selected = rows[:page_size]
        next_cursor = None
        if has_more and selected:
            next_cursor = (
                canonical_timestamp(selected[-1]["updated_at"]),
                str(selected[-1]["id"]),
            )
        return ProjectionPage(tuple(PresidioProjection.from_row(row) for row in selected), next_cursor)

    def get_config(self) -> dict[str, Any]:
        with self.connection() as conn:
            row = conn.execute(
                "SELECT * FROM pec_legal_notification_config WHERE tenant_id=?",
                (self.tenant_id,),
            ).fetchone()
        if row is None:
            return {
                "tenant_id": self.tenant_id,
                "policy_id": "policy.studio.notification_legacy_cutoff.2026-07-19.v1",
                "historical_cutoff": "2026-07-19T23:59:59+02:00",
                "strict_tracking_from": "2026-07-20T00:00:00+02:00",
                "rulepack_version": "",
                "correlation_thresholds": {"auto": 0.95, "review": 0.80},
                "backfill_status": "not_started",
                "backfill_cursor": {},
                # Studio senza configurazione esplicita: il registro dei presidi
                # e' visibile in sola lettura. Restava spento, e siccome vale
                # come un AND con il flag globale lo studio non vedeva mai i
                # presidi che la pipeline PEC stava gia' scrivendo. Modalita'
                # `shadow`: il registro si legge, ma l'esperienza primaria della
                # pagina Notifiche Legali non cambia senza una scelta esplicita.
                "rollout_enabled": True,
                "rollout_mode": "shadow",
                "version": 0,
            }
        result = self._row(row)
        result["correlation_thresholds"] = json_load(
            result.pop("correlation_thresholds_json", None), default={}
        )
        result["backfill_cursor"] = json_load(result.pop("backfill_cursor_json", None), default={})
        result["historical_cutoff"] = canonical_timestamp(result["historical_cutoff"])
        result["strict_tracking_from"] = canonical_timestamp(result["strict_tracking_from"])
        result["rollout_enabled"] = bool(result.get("rollout_enabled"))
        result["rollout_mode"] = str(result.get("rollout_mode") or "off")
        return result

    def save_config(self, config: Mapping[str, Any], *, actor: str) -> dict[str, Any]:
        now = utc_now_iso()
        rollout_mode = str(config.get("rollout_mode") or "off").strip().lower()
        if rollout_mode not in {"off", "shadow", "primary"}:
            rollout_mode = "off"
        with self.connection() as conn:
            conn.execute(
                """
                INSERT INTO pec_legal_notification_config
                (tenant_id, policy_id, historical_cutoff, strict_tracking_from,
                 legacy_declaration, rulepack_version, correlation_thresholds_json,
                 backfill_status, backfill_cursor_json, rollout_enabled, rollout_mode,
                 version, updated_by, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    policy_id=excluded.policy_id,
                    historical_cutoff=excluded.historical_cutoff,
                    strict_tracking_from=excluded.strict_tracking_from,
                    legacy_declaration=excluded.legacy_declaration,
                    rulepack_version=excluded.rulepack_version,
                    correlation_thresholds_json=excluded.correlation_thresholds_json,
                    backfill_status=excluded.backfill_status,
                    backfill_cursor_json=excluded.backfill_cursor_json,
                    rollout_enabled=excluded.rollout_enabled,
                    rollout_mode=excluded.rollout_mode,
                    version=pec_legal_notification_config.version+1,
                    updated_by=excluded.updated_by,
                    updated_at=excluded.updated_at
                """,
                (
                    self.tenant_id,
                    str(config.get("policy_id") or "policy.studio.notification_legacy_cutoff.2026-07-19.v1"),
                    canonical_timestamp(
                        config.get("historical_cutoff") or "2026-07-19T23:59:59+02:00"
                    ),
                    canonical_timestamp(
                        config.get("strict_tracking_from") or "2026-07-20T00:00:00+02:00"
                    ),
                    str(config.get("legacy_declaration") or ""),
                    str(config.get("rulepack_version") or ""),
                    canonical_json(config.get("correlation_thresholds") or {"auto": 0.95, "review": 0.80}),
                    str(config.get("backfill_status") or "not_started"),
                    canonical_json(config.get("backfill_cursor") or {}),
                    bool(config.get("rollout_enabled")) and rollout_mode != "off",
                    rollout_mode,
                    max(1, int(config.get("version") or 1)),
                    required_text(actor, "actor"),
                    now,
                ),
            )
        return self.get_config()
