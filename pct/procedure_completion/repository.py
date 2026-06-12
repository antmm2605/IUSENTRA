"""Repository SQLite del Procedure Completion Engine.

Pattern allineato a pct/procedure_lifecycle_repository: connessione con
context manager, schema idempotente da pct/sql, audit con payload sanificato
(sanitize_audit_payload) ed event_hash deterministico. Il tenant_id e' sempre
passato dal layer server (mai dal client).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from pct.procedure_completion.models import (
    ProcedureCompletionCard,
    new_id,
    now_iso,
)
from pct.procedure_lifecycle_repository import (
    json_dumps,
    json_loads,
    row_to_dict,
    sanitize_audit_payload,
    stable_event_hash,
)

_SCHEMA_FILE = Path(__file__).resolve().parent.parent / "sql" / "20260606_procedure_completion_engine.sql"


class ProcedureCompletionRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        script = _SCHEMA_FILE.read_text(encoding="utf-8")
        with self.connect() as conn:
            conn.executescript(script)

    # ------------------------------------------------------------------ audit

    def audit_log(
        self,
        entity_type: str,
        entity_id: Any,
        action: str,
        *,
        payload: dict[str, Any] | None = None,
        actor: str = "",
        tenant_id: str = "",
    ) -> str:
        sanitized = sanitize_audit_payload(payload or {})
        event = {
            "entity_type": entity_type,
            "entity_id": str(entity_id or ""),
            "action": action,
            "actor": sanitize_audit_payload(actor),
            "payload": sanitized,
        }
        event_hash = stable_event_hash(event)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO procedure_completion_audit_log
                    (tenant_id, entity_type, entity_id, action, actor, payload_json, event_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tenant_id or None,
                    entity_type,
                    str(entity_id or ""),
                    action,
                    str(sanitize_audit_payload(actor) or ""),
                    json_dumps(sanitized),
                    event_hash,
                    now_iso(),
                ),
            )
        return event_hash

    def list_audit_log(self, *, entity_type: str = "", entity_id: str = "", tenant_id: str = "") -> list[dict[str, Any]]:
        query = "SELECT * FROM procedure_completion_audit_log WHERE 1=1"
        params: list[Any] = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id = ?"
            params.append(str(entity_id))
        if tenant_id:
            query += " AND (tenant_id = ? OR tenant_id IS NULL)"
            params.append(tenant_id)
        query += " ORDER BY id DESC LIMIT 500"
        with self.connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [row_to_dict(row) or {} for row in rows]

    # ------------------------------------------------------------------ runs

    def create_run(
        self,
        *,
        procedure_code: str,
        request_payload: dict[str, Any],
        tenant_id: str = "",
        requested_by: str = "",
        mode: str = "preview",
        xsd_code: str = "",
        template_code: str = "",
    ) -> str:
        run_id = new_id("run")
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO procedure_completion_runs
                    (id, tenant_id, procedure_code, xsd_code, template_code, mode, status,
                     requested_by, request_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'completed', ?, ?, ?, ?)
                """,
                (
                    run_id,
                    tenant_id or None,
                    procedure_code,
                    xsd_code or None,
                    template_code or None,
                    mode,
                    requested_by or None,
                    json_dumps(sanitize_audit_payload(request_payload or {})),
                    now_iso(),
                    now_iso(),
                ),
            )
        self.audit_log("procedure_completion_run", run_id, "create", payload={"procedure_code": procedure_code, "mode": mode}, actor=requested_by, tenant_id=tenant_id)
        return run_id

    def get_run(self, run_id: str, *, tenant_id: str = "") -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM procedure_completion_runs WHERE id = ?", (str(run_id),)).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        if tenant_id and record.get("tenant_id") not in (None, "", tenant_id):
            return None
        record["request"] = json_loads(record.pop("request_json", "{}"), {})
        return record

    # ------------------------------------------------------------------ cards

    def save_card(self, card: ProcedureCompletionCard, *, actor: str = "") -> str:
        payload = card.to_dict()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO procedure_completion_cards
                    (id, run_id, tenant_id, procedure_code, xsd_code, template_code, status,
                     risk_level, confidence, payload_json, validation_report_json,
                     source_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    risk_level = excluded.risk_level,
                    confidence = excluded.confidence,
                    payload_json = excluded.payload_json,
                    template_code = excluded.template_code,
                    source_hash = excluded.source_hash,
                    updated_at = excluded.updated_at
                """,
                (
                    card.id,
                    card.run_id or None,
                    card.tenant_id or None,
                    card.codice,
                    card.xsd_code or None,
                    str(card.template_selected.get("template_id") or "") or None,
                    card.status,
                    card.risk_level,
                    card.confidence,
                    json_dumps(payload),
                    json_dumps({}),
                    stable_event_hash({"sources": card.source_hashes}),
                    now_iso(),
                    now_iso(),
                ),
            )
        self.audit_log(
            "procedure_completion_card",
            card.id,
            "save",
            payload={"procedure_code": card.codice, "status": card.status, "confidence": card.confidence},
            actor=actor,
            tenant_id=card.tenant_id,
        )
        return card.id

    def _row_to_card(self, record: dict[str, Any]) -> ProcedureCompletionCard:
        payload = json_loads(record.get("payload_json"), {})
        payload.setdefault("id", record.get("id"))
        card = ProcedureCompletionCard.from_dict(payload)
        card.status = str(record.get("status") or card.status)
        card.confidence = str(record.get("confidence") or card.confidence)
        card.risk_level = str(record.get("risk_level") or card.risk_level)
        if record.get("reviewer"):
            card.review_avvocato = {
                "reviewer": record.get("reviewer") or "",
                "reviewed_at": record.get("reviewed_at") or "",
                "reason": record.get("review_reason") or "",
                "esito": "approved" if card.status in {"approved", "published"} else "",
            }
        return card

    def get_card(self, card_id: str, *, tenant_id: str = "") -> Optional[ProcedureCompletionCard]:
        with self.connect() as conn:
            row = conn.execute("SELECT * FROM procedure_completion_cards WHERE id = ?", (str(card_id),)).fetchone()
        record = row_to_dict(row)
        if record is None:
            return None
        if tenant_id and record.get("tenant_id") not in (None, "", tenant_id):
            return None
        return self._row_to_card(record)

    def get_card_validation_report(self, card_id: str) -> dict[str, Any]:
        with self.connect() as conn:
            row = conn.execute(
                "SELECT validation_report_json FROM procedure_completion_cards WHERE id = ?",
                (str(card_id),),
            ).fetchone()
        if row is None:
            return {}
        return json_loads(row["validation_report_json"], {})

    def save_validation_report(self, card_id: str, report: dict[str, Any]) -> None:
        with self.connect() as conn:
            conn.execute(
                "UPDATE procedure_completion_cards SET validation_report_json = ?, updated_at = ? WHERE id = ?",
                (json_dumps(report or {}), now_iso(), str(card_id)),
            )

    def list_cards(
        self,
        *,
        tenant_id: str = "",
        procedure_code: str = "",
        status: str = "",
        query: str = "",
        limit: int = 50,
    ) -> list[ProcedureCompletionCard]:
        sql = "SELECT * FROM procedure_completion_cards WHERE 1=1"
        params: list[Any] = []
        if tenant_id:
            sql += " AND (tenant_id = ? OR tenant_id IS NULL)"
            params.append(tenant_id)
        if procedure_code:
            sql += " AND procedure_code = ?"
            params.append(procedure_code)
        if status:
            sql += " AND status = ?"
            params.append(status)
        if query:
            sql += " AND payload_json LIKE ?"
            params.append(f"%{query}%")
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(max(1, min(int(limit or 50), 200)))
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_card(row_to_dict(row) or {}) for row in rows]

    # -------------------------------------------------------- sources / gaps

    def add_source(self, card_id: str, source: dict[str, Any], *, tenant_id: str = "") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO procedure_completion_sources
                    (card_id, tenant_id, source_type, title, url, authority, trust_class,
                     copyright_policy, excerpt, origin, source_hash, last_checked_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(card_id),
                    tenant_id or None,
                    str(source.get("source_type") or "technical"),
                    str(source.get("title") or ""),
                    str(source.get("url") or ""),
                    str(source.get("authority") or ""),
                    str(source.get("trust_class") or ""),
                    str(source.get("copyright_policy") or "metadata_only"),
                    str(source.get("excerpt") or ""),
                    str(source.get("origin") or ""),
                    str(source.get("source_hash") or ""),
                    str(source.get("last_checked_at") or ""),
                    now_iso(),
                ),
            )
            source_id = int(cursor.lastrowid or 0)
        return source_id

    def add_citation(self, card_id: str, citation: dict[str, Any], *, tenant_id: str = "") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO procedure_completion_citations
                    (card_id, tenant_id, riferimento, atto_normativo, articolo, comma,
                     versione, url, source_id, snippet, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(card_id),
                    tenant_id or None,
                    str(citation.get("riferimento") or ""),
                    str(citation.get("atto_normativo") or ""),
                    str(citation.get("articolo") or ""),
                    str(citation.get("comma") or ""),
                    str(citation.get("versione") or ""),
                    str(citation.get("url") or ""),
                    str(citation.get("source_id") or ""),
                    str(citation.get("snippet") or "")[:500],
                    now_iso(),
                ),
            )
            citation_id = int(cursor.lastrowid or 0)
        return citation_id

    def add_gap(self, card_id: str, gap: dict[str, Any], *, tenant_id: str = "") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO procedure_completion_gaps
                    (card_id, tenant_id, codice_gap, descrizione, severita, azione_suggerita, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(card_id),
                    tenant_id or None,
                    str(gap.get("codice_gap") or ""),
                    str(gap.get("descrizione") or ""),
                    str(gap.get("severita") or "warning"),
                    str(gap.get("azione_suggerita") or ""),
                    now_iso(),
                ),
            )
            gap_id = int(cursor.lastrowid or 0)
        return gap_id

    def list_gaps(self, *, tenant_id: str = "", severita: str = "", card_id: str = "", limit: int = 100) -> list[dict[str, Any]]:
        sql = "SELECT * FROM procedure_completion_gaps WHERE risolto = 0"
        params: list[Any] = []
        if tenant_id:
            sql += " AND (tenant_id = ? OR tenant_id IS NULL)"
            params.append(tenant_id)
        if severita:
            sql += " AND severita = ?"
            params.append(severita)
        if card_id:
            sql += " AND card_id = ?"
            params.append(str(card_id))
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(max(1, min(int(limit or 100), 500)))
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [row_to_dict(row) or {} for row in rows]

    def link_template(self, card_id: str, candidate: dict[str, Any], *, selezionato: bool = False, tenant_id: str = "") -> int:
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO procedure_completion_template_links
                    (card_id, tenant_id, template_id, titolo, score, selezionato, motivi_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(card_id),
                    tenant_id or None,
                    str(candidate.get("template_id") or ""),
                    str(candidate.get("titolo") or ""),
                    int(candidate.get("score") or 0),
                    1 if selezionato else 0,
                    json_dumps(list(candidate.get("motivi") or [])),
                    now_iso(),
                ),
            )
            link_id = int(cursor.lastrowid or 0)
        return link_id

    # ----------------------------------------------------- review transitions

    def _record_review_event(
        self,
        card_id: str,
        *,
        evento: str,
        reviewer: str,
        reason: str,
        from_status: str,
        to_status: str,
        tenant_id: str = "",
    ) -> str:
        event_hash = stable_event_hash(
            sanitize_audit_payload(
                {"card_id": card_id, "evento": evento, "from": from_status, "to": to_status, "reviewer": reviewer}
            )
        )
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO procedure_completion_review_events
                    (card_id, tenant_id, evento, reviewer, reason, from_status, to_status, event_hash, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(card_id),
                    tenant_id or None,
                    evento,
                    str(sanitize_audit_payload(reviewer) or ""),
                    str(sanitize_audit_payload(reason) or "")[:500],
                    from_status,
                    to_status,
                    event_hash,
                    now_iso(),
                ),
            )
        return event_hash

    def _transition(
        self,
        card_id: str,
        *,
        to_status: str,
        evento: str,
        reviewer: str = "",
        reason: str = "",
        tenant_id: str = "",
        set_review: bool = False,
        set_published: bool = False,
    ) -> ProcedureCompletionCard:
        card = self.get_card(card_id, tenant_id=tenant_id)
        if card is None:
            raise ValueError("Scheda non trovata o non accessibile dal contesto corrente.")
        from_status = card.status
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE procedure_completion_cards
                SET status = ?,
                    reviewer = CASE WHEN ? THEN ? ELSE reviewer END,
                    reviewed_at = CASE WHEN ? THEN ? ELSE reviewed_at END,
                    review_reason = CASE WHEN ? THEN ? ELSE review_reason END,
                    published_at = CASE WHEN ? THEN ? ELSE published_at END,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    to_status,
                    1 if set_review else 0, reviewer or None,
                    1 if set_review else 0, now_iso() if set_review else None,
                    1 if set_review else 0, reason or None,
                    1 if set_published else 0, now_iso() if set_published else None,
                    now_iso(),
                    str(card_id),
                ),
            )
        self._record_review_event(
            card_id,
            evento=evento,
            reviewer=reviewer,
            reason=reason,
            from_status=from_status,
            to_status=to_status,
            tenant_id=tenant_id,
        )
        self.audit_log(
            "procedure_completion_card",
            card_id,
            evento,
            payload={"from": from_status, "to": to_status, "reason": reason},
            actor=reviewer,
            tenant_id=tenant_id,
        )
        aggiornata = self.get_card(card_id, tenant_id=tenant_id)
        if aggiornata is None:
            raise ValueError("Scheda non rileggibile dopo la transizione.")
        # Persistiamo lo stato anche dentro il payload per coerenza di lettura.
        aggiornata.status = to_status
        if set_review:
            aggiornata.review_avvocato = {
                "reviewer": reviewer,
                "reviewed_at": now_iso(),
                "reason": reason,
                "esito": "approved" if to_status in {"approved", "published"} else to_status,
            }
        self.save_card(aggiornata, actor=reviewer)
        return aggiornata

    def submit_for_review(self, card_id: str, *, requested_by: str = "", reason: str = "", tenant_id: str = "") -> ProcedureCompletionCard:
        return self._transition(
            card_id,
            to_status="needs_review",
            evento="submit_review",
            reviewer=requested_by,
            reason=reason or "Invio in revisione avvocato.",
            tenant_id=tenant_id,
        )

    def approve_card(self, card_id: str, *, reviewer: str, reason: str = "", tenant_id: str = "") -> ProcedureCompletionCard:
        if not str(reviewer or "").strip():
            raise ValueError("L'approvazione richiede il revisore (avvocato).")
        return self._transition(
            card_id,
            to_status="approved",
            evento="approve",
            reviewer=reviewer,
            reason=reason or "Scheda approvata dall'avvocato.",
            tenant_id=tenant_id,
            set_review=True,
        )

    def publish_card(self, card_id: str, *, reviewer: str = "", tenant_id: str = "") -> ProcedureCompletionCard:
        return self._transition(
            card_id,
            to_status="published",
            evento="publish",
            reviewer=reviewer,
            reason="Pubblicazione scheda approvata.",
            tenant_id=tenant_id,
            set_published=True,
        )


__all__ = ["ProcedureCompletionRepository"]
