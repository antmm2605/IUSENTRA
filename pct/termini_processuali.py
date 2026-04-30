"""Motore spiegabile per termini processuali italiani.

Il modulo e' separato dallo scadenziario CRUD: espone template versionati,
calcolo, spiegazione, audit immutabile e repository JSON/SQLite. PostgreSQL e'
governato dagli schemi SQL dedicati e puo' usare gli stessi payload canonici.
"""

from __future__ import annotations

import calendar
import csv
import hashlib
import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


ENGINE_VERSION = "1.0.0"
RULESET_VERSION = "IT-CPC-155-L742-2026.1"
CALENDAR_VERSION = "IT-FESTIVITA-NAZIONALI-2026.1"
DEFAULT_REMINDER_THRESHOLDS = (30, 15, 7, 1, 0)

LEGAL_SOURCES = (
    {
        "code": "art_155_cpc",
        "label": "Art. 155 c.p.c. - computo dei termini",
        "url": "https://def.giustiziatributaria.gov.it/DocTribFrontend/executePrintArticolo.do?articolo=Articolo+155",
    },
    {
        "code": "legge_742_1969",
        "label": "Legge 7 ottobre 1969, n. 742 - sospensione feriale",
        "url": "https://www.normattiva.it/eli/id/1969/11/06/069U0742/CONSOLIDATED/20241015",
    },
    {
        "code": "agid_conservazione",
        "label": "AgID - conservazione: autenticita, integrita, affidabilita, leggibilita e reperibilita",
        "url": "https://www.agid.gov.it/it/piattaforme/conservazione",
    },
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Data iniziale obbligatoria")
    return date.fromisoformat(raw[:10])


def _parse_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or value == "":
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on", "si"}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _easter(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def national_holidays(year: int) -> set[date]:
    easter = _easter(year)
    return {
        date(year, 1, 1),
        date(year, 1, 6),
        easter + timedelta(days=1),
        date(year, 4, 25),
        date(year, 5, 1),
        date(year, 6, 2),
        date(year, 8, 15),
        date(year, 11, 1),
        date(year, 12, 8),
        date(year, 12, 25),
        date(year, 12, 26),
    }


def _add_months(day: date, months: int) -> date:
    total = (day.month - 1) + months
    year = day.year + total // 12
    month = total % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


@dataclass(frozen=True)
class DeadlineTemplate:
    code: str
    name: str
    matter_type: str = "civil"
    base_value: int = 30
    period_type: str = "days"
    direction: str = "forward"
    suspend_august: bool = True
    ferial_suspension_policy: str = "applies"
    free_term: bool = False
    urgent: bool = False
    extend_saturday: bool = True
    extend_holiday: bool = True
    reference_law: str = ""
    cartabia_compliant: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(payload: Mapping[str, Any]) -> "DeadlineTemplate":
        data = dict(payload or {})
        allowed = DeadlineTemplate.__dataclass_fields__.keys()
        return DeadlineTemplate(**{key: data[key] for key in allowed if key in data})


@dataclass(frozen=True)
class DeadlineAuditRecord:
    id: str
    template_code: str
    template_version: int
    case_reference: str
    user_id: str
    input_date: str
    calculated_deadline: str
    rules_applied: list[str]
    engine_version: str
    ruleset_version: str
    calendar_version: str
    is_override: bool = False
    override_reason: str = ""
    raw_input: dict[str, Any] = field(default_factory=dict)
    raw_output: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now)
    immutable_hash: str = ""

    def with_hash(self) -> "DeadlineAuditRecord":
        payload = asdict(self)
        payload.pop("immutable_hash", None)
        return DeadlineAuditRecord(**{**payload, "immutable_hash": canonical_sha256(payload)})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


DEFAULT_TEMPLATES: tuple[DeadlineTemplate, ...] = (
    DeadlineTemplate(
        code="CIV_APPELLO_BREVE",
        name="Appello civile - termine breve",
        base_value=30,
        period_type="days",
        reference_law="Art. 325 c.p.c.",
        metadata={"source_event": "notifica_sentenza"},
    ),
    DeadlineTemplate(
        code="CIV_APPELLO_LUNGO",
        name="Appello civile - termine lungo",
        base_value=6,
        period_type="months",
        suspend_august=False,
        extend_saturday=True,
        reference_law="Art. 327 c.p.c.",
        metadata={"source_event": "deposito_sentenza"},
    ),
    DeadlineTemplate(
        code="CIV_CASSAZIONE_BREVE",
        name="Ricorso per Cassazione - termine breve",
        base_value=60,
        reference_law="Art. 325 c.p.c.",
        metadata={"source_event": "notifica_sentenza"},
    ),
    DeadlineTemplate(
        code="CIV_OPPOSIZIONE_DI",
        name="Opposizione a decreto ingiuntivo",
        base_value=40,
        reference_law="Art. 641 c.p.c.",
        metadata={"source_event": "notifica_decreto"},
    ),
    DeadlineTemplate(
        code="CIV_MEMORIA_171_TER_1",
        name="Memoria art. 171-ter n. 1",
        base_value=40,
        direction="backward",
        free_term=True,
        reference_law="Art. 171-ter c.p.c.",
        metadata={"source_event": "udienza"},
    ),
    DeadlineTemplate(
        code="CIV_MEMORIA_171_TER_2",
        name="Memoria art. 171-ter n. 2",
        base_value=20,
        direction="backward",
        free_term=True,
        reference_law="Art. 171-ter c.p.c.",
        metadata={"source_event": "udienza"},
    ),
    DeadlineTemplate(
        code="CIV_MEMORIA_171_TER_3",
        name="Memoria art. 171-ter n. 3",
        base_value=10,
        direction="backward",
        free_term=True,
        reference_law="Art. 171-ter c.p.c.",
        metadata={"source_event": "udienza"},
    ),
    DeadlineTemplate(
        code="CUSTOM_PROCESSUALE",
        name="Termine processuale personalizzato",
        base_value=30,
        reference_law="Configurazione studio",
        cartabia_compliant=False,
        metadata={"manual": True},
    ),
)


class ItalianDeadlineCalculator:
    """Calcolatore termini processuali con output spiegabile."""

    def __init__(
        self,
        *,
        engine_version: str = ENGINE_VERSION,
        ruleset_version: str = RULESET_VERSION,
        calendar_version: str = CALENDAR_VERSION,
    ) -> None:
        self.engine_version = engine_version
        self.ruleset_version = ruleset_version
        self.calendar_version = calendar_version

    def calculate(self, input_date: date, base_value: int, direction: str = "forward", **options: Any) -> dict[str, Any]:
        template = DeadlineTemplate(
            code=str(options.get("template_code") or "AD_HOC"),
            name=str(options.get("template_name") or "Termine ad hoc"),
            matter_type=str(options.get("matter_type") or "civil"),
            base_value=max(int(base_value), 1),
            period_type=str(options.get("period_type") or "days"),
            direction=direction,
            suspend_august=_parse_bool(options.get("suspend_august"), False),
            ferial_suspension_policy=str(options.get("ferial_suspension_policy") or "applies"),
            free_term=_parse_bool(options.get("free_term"), False),
            urgent=_parse_bool(options.get("urgent"), False),
            extend_saturday=_parse_bool(options.get("extend_saturday"), True),
            extend_holiday=_parse_bool(options.get("extend_holiday"), True),
            reference_law=str(options.get("reference_law") or ""),
            cartabia_compliant=_parse_bool(options.get("cartabia_compliant"), True),
            version=_safe_int(options.get("template_version"), 1),
            metadata=dict(options.get("metadata") or {}),
        )
        return self.calculate_template(input_date, template, case_reference=str(options.get("case_reference") or ""))

    def calculate_months(self, input_date: date, months: int, **options: Any) -> date:
        step = -1 if str(options.get("direction") or "forward") == "backward" else 1
        return _add_months(input_date, step * max(int(months), 1))

    def calculate_template(
        self,
        input_date: date,
        template: DeadlineTemplate,
        *,
        case_reference: str = "",
        overrides: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        effective = DeadlineTemplate.from_dict({**template.to_dict(), **dict(overrides or {})})
        if effective.period_type not in {"days", "months"}:
            raise ValueError("Tipo periodo non supportato")
        if effective.direction not in {"forward", "backward"}:
            raise ValueError("Direzione calcolo non valida")
        step = 1 if effective.direction == "forward" else -1
        rules: list[str] = ["dies_a_quo_excluded"]
        steps: list[dict[str, str]] = [
            {"code": "input_date", "label": "Data evento generatore", "date": input_date.isoformat()}
        ]
        if effective.free_term:
            rules.append("free_term")
        if self._ferial_active(effective):
            rules.append("ferial_suspension_1_31_august")
        if effective.urgent:
            rules.append("urgent_matter_ferial_bypass")
        if effective.extend_saturday:
            rules.append("saturday_extension_out_of_hearing")
        if effective.extend_holiday:
            rules.append("holiday_extension")

        raw = self._raw_deadline(input_date, effective, step, steps)
        adjusted = self._adjust_final(raw, effective, step, steps)
        review = self._requires_review(effective)
        confidence = "bassa" if effective.ferial_suspension_policy in {"manual_review", "partial"} else "media" if review else "alta"
        explanation = self._explain(input_date, raw, adjusted, effective, rules)
        result = {
            "calculationId": str(uuid.uuid4()),
            "deadline": adjusted.isoformat(),
            "rawDeadline": raw.isoformat(),
            "inputDate": input_date.isoformat(),
            "direction": effective.direction,
            "confidence": confidence,
            "requiresLegalReview": review,
            "template": effective.to_dict(),
            "templateVersion": effective.version,
            "rulesetVersion": self.ruleset_version,
            "calendarVersion": self.calendar_version,
            "engineVersion": self.engine_version,
            "rulesApplied": rules,
            "steps": steps,
            "explanation": explanation,
            "caseReference": case_reference,
            "legalSources": list(LEGAL_SOURCES),
            "notificationPlan": self.notification_plan(adjusted, case_reference, effective.code),
        }
        result["resultHash"] = canonical_sha256(result)
        return result

    def notification_plan(self, deadline: date, case_reference: str, template_code: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for days in DEFAULT_REMINDER_THRESHOLDS:
            reminder_date = deadline - timedelta(days=days)
            key = canonical_sha256({
                "deadline": deadline.isoformat(),
                "case_reference": case_reference,
                "template_code": template_code,
                "days_left": days,
            })
            rows.append({
                "daysLeft": days,
                "date": reminder_date.isoformat(),
                "channel": "PEC",
                "status": "pianificabile",
                "idempotencyKey": key,
            })
        return rows

    def _ferial_active(self, template: DeadlineTemplate) -> bool:
        return bool(
            template.suspend_august
            and not template.urgent
            and template.ferial_suspension_policy == "applies"
        )

    def _is_suspended(self, day: date, template: DeadlineTemplate) -> bool:
        return self._ferial_active(template) and day.month == 8

    def _raw_deadline(self, input_date: date, template: DeadlineTemplate, step: int, steps: list[dict[str, str]]) -> date:
        if template.period_type == "months":
            raw = _add_months(input_date, step * template.base_value)
            steps.append({"code": "calendar_months", "label": "Computo a mesi secondo calendario comune", "date": raw.isoformat()})
            if self._ferial_active(template):
                raw = self._shift_for_august_span(input_date, raw, step, steps)
            if template.free_term:
                raw = self._move_one_clear_day(raw, step, template, steps)
            return raw

        cursor = input_date + timedelta(days=step)
        counted = 0
        while counted < template.base_value:
            if self._is_suspended(cursor, template):
                if counted in {0, template.base_value - 1}:
                    steps.append({"code": "ferial_skip", "label": "Giorno non computato per sospensione feriale", "date": cursor.isoformat()})
            else:
                counted += 1
                if counted in {1, template.base_value}:
                    steps.append({"code": "day_count", "label": f"Giorno computato n. {counted}", "date": cursor.isoformat()})
            if counted < template.base_value:
                cursor += timedelta(days=step)
        if template.free_term:
            cursor = self._move_one_clear_day(cursor, step, template, steps)
        return cursor

    def _move_one_clear_day(self, day: date, step: int, template: DeadlineTemplate, steps: list[dict[str, str]]) -> date:
        cursor = day + timedelta(days=step)
        while self._is_suspended(cursor, template):
            cursor += timedelta(days=step)
        steps.append({"code": "free_term_clear_day", "label": "Escluso anche il dies ad quem del termine libero", "date": cursor.isoformat()})
        return cursor

    def _shift_for_august_span(self, start: date, raw: date, step: int, steps: list[dict[str, str]]) -> date:
        if step < 0:
            span = self._august_days(raw, start)
            shifted = raw - timedelta(days=span)
        else:
            span = self._august_days(start, raw)
            shifted = raw + timedelta(days=span)
        if span:
            steps.append({"code": "ferial_month_shift", "label": f"Aggiunti {span} giorni di sospensione feriale", "date": shifted.isoformat()})
        return shifted

    def _august_days(self, start: date, end: date) -> int:
        if end < start:
            start, end = end, start
        cursor = start + timedelta(days=1)
        total = 0
        while cursor <= end:
            if cursor.month == 8:
                total += 1
            cursor += timedelta(days=1)
        return total

    def _adjust_final(self, raw: date, template: DeadlineTemplate, step: int, steps: list[dict[str, str]]) -> date:
        cursor = raw
        while self._is_blocked_final(cursor, template):
            code = "final_extension" if step > 0 else "final_anticipation"
            label = "Proroga al primo giorno seguente non festivo"
            if step < 0:
                label = "Calcolo a ritroso: anticipo al giorno utile precedente"
            steps.append({"code": code, "label": label, "date": cursor.isoformat()})
            cursor += timedelta(days=step)
        if cursor != raw:
            steps.append({"code": "legal_deadline", "label": "Scadenza legale finale", "date": cursor.isoformat()})
        return cursor

    def _is_blocked_final(self, day: date, template: DeadlineTemplate) -> bool:
        if self._is_suspended(day, template):
            return True
        if template.extend_saturday and day.weekday() == 5:
            return True
        if template.extend_holiday and (day.weekday() == 6 or day in national_holidays(day.year)):
            return True
        return False

    def _requires_review(self, template: DeadlineTemplate) -> bool:
        return bool(
            template.urgent
            or template.direction == "backward"
            or template.free_term
            or template.ferial_suspension_policy in {"partial", "manual_review"}
            or template.matter_type not in {"civil", "admin", "labor", "tax", "penal"}
            or not template.cartabia_compliant
        )

    def _explain(self, input_date: date, raw: date, adjusted: date, template: DeadlineTemplate, rules: Iterable[str]) -> str:
        parts = [f"Il termine decorre dal giorno successivo all'evento del {input_date.isoformat()}."]
        if template.period_type == "months":
            parts.append("Il periodo e' computato a mesi secondo calendario comune.")
        if "ferial_suspension_1_31_august" in rules:
            parts.append("I giorni dal 1 al 31 agosto sono esclusi dal computo.")
        if template.urgent:
            parts.append("La materia urgente esclude la sospensione feriale nel calcolo automatico.")
        if template.free_term:
            parts.append("Il termine libero esclude anche il giorno finale.")
        if adjusted != raw:
            action = "prorogata" if template.direction == "forward" else "anticipata"
            parts.append(f"La scadenza grezza {raw.isoformat()} e' stata {action} a {adjusted.isoformat()}.")
        else:
            parts.append(f"La scadenza finale e' {adjusted.isoformat()}.")
        return " ".join(parts)


class DeadlinePracticeRepository:
    """Repository template/audit per JSON o SQLite."""

    def __init__(self, path: str | Path, *, backend: str = "json") -> None:
        self.path = Path(path)
        self.backend = backend
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if backend == "sqlite":
            self._init_sqlite()
        else:
            self._init_json()

    @classmethod
    def json(cls, path: str | Path) -> "DeadlinePracticeRepository":
        return cls(path, backend="json")

    @classmethod
    def sqlite(cls, path: str | Path) -> "DeadlinePracticeRepository":
        return cls(path, backend="sqlite")

    def _init_json(self) -> None:
        if self.path.exists():
            payload = self._read_json()
        else:
            payload = {}
        if not payload.get("templates"):
            payload["templates"] = [template.to_dict() for template in DEFAULT_TEMPLATES]
        payload.setdefault("audit_logs", [])
        payload.setdefault("notification_logs", [])
        payload.setdefault("calendar_versions", [{"version": CALENDAR_VERSION, "source": "builtin", "imported_at": _utc_now()}])
        payload.setdefault("official_holidays", [])
        self._write_json(payload)

    def _init_sqlite(self) -> None:
        with sqlite3.connect(self.path) as conn:
            conn.executescript(SQLITE_SCHEMA)
            count = conn.execute("SELECT COUNT(*) FROM deadline_templates").fetchone()[0]
            if not count:
                for template in DEFAULT_TEMPLATES:
                    self._insert_template_sqlite(conn, template)
            conn.commit()

    def _read_json(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_json(self, payload: Mapping[str, Any]) -> None:
        self.path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_templates(self) -> list[dict[str, Any]]:
        if self.backend == "sqlite":
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute("SELECT * FROM deadline_templates ORDER BY matter_type, name").fetchall()
                return [self._template_from_row(row).to_dict() for row in rows]
        return list(self._read_json().get("templates", []))

    def get_template(self, code: str) -> DeadlineTemplate:
        normalized = str(code or "").strip() or "CUSTOM_PROCESSUALE"
        for item in self.list_templates():
            if item.get("code") == normalized:
                return DeadlineTemplate.from_dict(item)
        raise ValueError("Template termine non trovato")

    def save_audit(self, record: DeadlineAuditRecord) -> DeadlineAuditRecord:
        hashed = record.with_hash()
        if self.backend == "sqlite":
            with sqlite3.connect(self.path) as conn:
                conn.execute(
                    """
                    INSERT INTO deadline_audit_logs
                    (id, template_code, template_version, case_reference, user_id, input_date,
                     calculated_deadline, rules_applied_json, engine_version, ruleset_version,
                     calendar_version, is_override, override_reason, raw_input_json,
                     raw_output_json, created_at, immutable_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        hashed.id,
                        hashed.template_code,
                        hashed.template_version,
                        hashed.case_reference,
                        hashed.user_id,
                        hashed.input_date,
                        hashed.calculated_deadline,
                        json.dumps(hashed.rules_applied, ensure_ascii=False),
                        hashed.engine_version,
                        hashed.ruleset_version,
                        hashed.calendar_version,
                        1 if hashed.is_override else 0,
                        hashed.override_reason,
                        json.dumps(hashed.raw_input, ensure_ascii=False),
                        json.dumps(hashed.raw_output, ensure_ascii=False),
                        hashed.created_at,
                        hashed.immutable_hash,
                    ),
                )
                conn.commit()
            return hashed
        payload = self._read_json()
        payload.setdefault("audit_logs", []).append(hashed.to_dict())
        self._write_json(payload)
        return hashed

    def list_audit(self, limit: int = 20) -> list[dict[str, Any]]:
        if self.backend == "sqlite":
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM deadline_audit_logs ORDER BY created_at DESC LIMIT ?",
                    (max(1, int(limit)),),
                ).fetchall()
                return [dict(row) for row in rows]
        rows = list(self._read_json().get("audit_logs", []))
        rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        return rows[: max(1, int(limit))]

    def save_notification_plan(
        self,
        *,
        deadline_id: str,
        case_reference: str,
        user_id: str,
        notification_plan: Iterable[Mapping[str, Any]],
    ) -> int:
        rows = []
        now = _utc_now()
        for item in notification_plan:
            days_left = _safe_int(item.get("daysLeft") or item.get("days_left"), 0)
            due_at = str(item.get("date") or item.get("scheduled_at") or "").strip()
            idempotency_key = str(item.get("idempotencyKey") or item.get("idempotency_key") or "").strip()
            if not due_at or not idempotency_key:
                continue
            rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "deadline_id": deadline_id,
                    "case_reference": case_reference,
                    "user_id": user_id,
                    "channel": str(item.get("channel") or "PEC"),
                    "days_left": days_left,
                    "scheduled_at": due_at,
                    "status": str(item.get("status") or "pianificabile"),
                    "idempotency_key": idempotency_key,
                    "message_id": "",
                    "receipt_status": "",
                    "created_at": now,
                    "updated_at": now,
                }
            )
        if not rows:
            return 0
        if self.backend == "sqlite":
            with sqlite3.connect(self.path) as conn:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO deadline_notification_logs
                    (id, deadline_id, case_reference, user_id, channel, days_left,
                     scheduled_at, status, idempotency_key, message_id,
                     receipt_status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row["id"],
                            row["deadline_id"],
                            row["case_reference"],
                            row["user_id"],
                            row["channel"],
                            row["days_left"],
                            row["scheduled_at"],
                            row["status"],
                            row["idempotency_key"],
                            row["message_id"],
                            row["receipt_status"],
                            row["created_at"],
                            row["updated_at"],
                        )
                        for row in rows
                    ],
                )
                conn.commit()
                return int(conn.total_changes)
        payload = self._read_json()
        existing = {
            str(row.get("idempotency_key") or "")
            for row in payload.setdefault("notification_logs", [])
        }
        inserted = [row for row in rows if row["idempotency_key"] not in existing]
        payload["notification_logs"].extend(inserted)
        self._write_json(payload)
        return len(inserted)

    def list_notification_logs(self, limit: int = 20) -> list[dict[str, Any]]:
        if self.backend == "sqlite":
            with sqlite3.connect(self.path) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM deadline_notification_logs ORDER BY scheduled_at ASC LIMIT ?",
                    (max(1, int(limit)),),
                ).fetchall()
                return [dict(row) for row in rows]
        rows = list(self._read_json().get("notification_logs", []))
        rows.sort(key=lambda row: str(row.get("scheduled_at") or ""))
        return rows[: max(1, int(limit))]

    def import_holidays(
        self,
        rows: Iterable[Mapping[str, Any]],
        *,
        source_year: int,
        source: str = "CSV ufficiale",
        source_url: str = "",
        checksum_sha256: str = "",
        calendar_version: str | None = None,
        notes: str = "",
    ) -> dict[str, Any]:
        imported_at = _utc_now()
        version = calendar_version or f"IT-FESTIVITA-{source_year}.1"
        normalized: list[dict[str, Any]] = []
        for row in rows:
            raw_day = str(row.get("date") or row.get("day") or row.get("data") or "").strip()
            if not raw_day:
                continue
            try:
                day = date.fromisoformat(raw_day[:10])
            except ValueError:
                continue
            normalized.append(
                {
                    "day": day.isoformat(),
                    "description": str(row.get("description") or row.get("descrizione") or "Festivita ufficiale").strip(),
                    "type": str(row.get("type") or row.get("tipo") or "national").strip(),
                    "source_year": int(source_year),
                    "source_url": source_url,
                    "checksum_sha256": checksum_sha256,
                    "imported_at": imported_at,
                }
            )
        if self.backend == "sqlite":
            with sqlite3.connect(self.path) as conn:
                conn.executemany(
                    """
                    INSERT OR REPLACE INTO official_holidays
                    (day, description, type, source_year, source_url, checksum_sha256, imported_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            row["day"],
                            row["description"],
                            row["type"],
                            row["source_year"],
                            row["source_url"],
                            row["checksum_sha256"],
                            row["imported_at"],
                        )
                        for row in normalized
                    ],
                )
                conn.execute(
                    """
                    INSERT OR REPLACE INTO calendar_versions
                    (version, source, source_url, checksum_sha256, imported_at, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (version, source, source_url, checksum_sha256, imported_at, notes),
                )
                conn.commit()
        else:
            payload = self._read_json()
            current = {
                str(row.get("day")): dict(row)
                for row in payload.setdefault("official_holidays", [])
            }
            for row in normalized:
                current[row["day"]] = row
            payload["official_holidays"] = sorted(current.values(), key=lambda row: row["day"])
            versions = {
                str(row.get("version")): dict(row)
                for row in payload.setdefault("calendar_versions", [])
            }
            versions[version] = {
                "version": version,
                "source": source,
                "source_url": source_url,
                "checksum_sha256": checksum_sha256,
                "imported_at": imported_at,
                "notes": notes,
            }
            payload["calendar_versions"] = sorted(versions.values(), key=lambda row: str(row.get("version") or ""))
            self._write_json(payload)
        return {
            "imported": len(normalized),
            "sourceYear": int(source_year),
            "calendarVersion": version,
            "checksumSha256": checksum_sha256,
        }

    def _insert_template_sqlite(self, conn: sqlite3.Connection, template: DeadlineTemplate) -> None:
        conn.execute(
            """
            INSERT INTO deadline_templates
            (id, code, name, matter_type, base_value, period_type, direction,
             suspend_august, ferial_suspension_policy, free_term, urgent,
             extend_saturday, extend_holiday, reference_law, cartabia_compliant,
             metadata_json, version, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                template.code,
                template.name,
                template.matter_type,
                template.base_value,
                template.period_type,
                template.direction,
                1 if template.suspend_august else 0,
                template.ferial_suspension_policy,
                1 if template.free_term else 0,
                1 if template.urgent else 0,
                1 if template.extend_saturday else 0,
                1 if template.extend_holiday else 0,
                template.reference_law,
                1 if template.cartabia_compliant else 0,
                json.dumps(template.metadata, ensure_ascii=False),
                template.version,
                _utc_now(),
                _utc_now(),
            ),
        )

    def _template_from_row(self, row: sqlite3.Row) -> DeadlineTemplate:
        return DeadlineTemplate(
            code=str(row["code"]),
            name=str(row["name"]),
            matter_type=str(row["matter_type"]),
            base_value=int(row["base_value"]),
            period_type=str(row["period_type"]),
            direction=str(row["direction"]),
            suspend_august=bool(row["suspend_august"]),
            ferial_suspension_policy=str(row["ferial_suspension_policy"]),
            free_term=bool(row["free_term"]),
            urgent=bool(row["urgent"]),
            extend_saturday=bool(row["extend_saturday"]),
            extend_holiday=bool(row["extend_holiday"]),
            reference_law=str(row["reference_law"] or ""),
            cartabia_compliant=bool(row["cartabia_compliant"]),
            metadata=json.loads(row["metadata_json"] or "{}"),
            version=int(row["version"] or 1),
        )


def calculate_and_audit(
    payload: Mapping[str, Any],
    *,
    repository: DeadlinePracticeRepository,
    user_id: str = "",
    is_override: bool = False,
    override_reason: str = "",
) -> dict[str, Any]:
    template = repository.get_template(str(payload.get("template_code") or payload.get("templateCode") or "CUSTOM_PROCESSUALE"))
    overrides = {
        key: payload[key]
        for key in (
            "base_value",
            "period_type",
            "direction",
            "suspend_august",
            "ferial_suspension_policy",
            "free_term",
            "urgent",
            "extend_saturday",
            "extend_holiday",
            "matter_type",
        )
        if key in payload
    }
    input_date = _parse_date(payload.get("input_date") or payload.get("inputDate"))
    case_reference = str(payload.get("case_reference") or payload.get("caseReference") or "").strip()
    calculator = ItalianDeadlineCalculator()
    result = calculator.calculate_template(input_date, template, case_reference=case_reference, overrides=overrides)
    if is_override:
        override_deadline = str(payload.get("override_deadline") or payload.get("overrideDeadline") or "").strip()
        if override_deadline:
            result["overrideDeadline"] = _parse_date(override_deadline).isoformat()
            result["deadline"] = result["overrideDeadline"]
            result["requiresLegalReview"] = True
            result["confidence"] = "bassa"
            result["rulesApplied"] = list(result["rulesApplied"]) + ["manual_override"]
            result["explanation"] += " E' stato registrato un override manuale motivato."
    record = DeadlineAuditRecord(
        id=str(uuid.uuid4()),
        template_code=result["template"]["code"],
        template_version=int(result["templateVersion"]),
        case_reference=case_reference,
        user_id=user_id,
        input_date=input_date.isoformat(),
        calculated_deadline=str(result["deadline"]),
        rules_applied=list(result["rulesApplied"]),
        engine_version=str(result["engineVersion"]),
        ruleset_version=str(result["rulesetVersion"]),
        calendar_version=str(result["calendarVersion"]),
        is_override=is_override,
        override_reason=override_reason,
        raw_input=dict(payload),
        raw_output=result,
    )
    audit = repository.save_audit(record)
    result["audit"] = {
        "id": audit.id,
        "createdAt": audit.created_at,
        "immutableHash": audit.immutable_hash,
        "isOverride": audit.is_override,
    }
    return result


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS deadline_templates (
    id TEXT PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    matter_type TEXT NOT NULL DEFAULT 'civil',
    base_value INTEGER NOT NULL CHECK (base_value > 0),
    period_type TEXT NOT NULL DEFAULT 'days' CHECK (period_type IN ('days', 'months')),
    direction TEXT NOT NULL DEFAULT 'forward' CHECK (direction IN ('forward', 'backward')),
    suspend_august INTEGER NOT NULL DEFAULT 1,
    ferial_suspension_policy TEXT NOT NULL DEFAULT 'applies',
    free_term INTEGER NOT NULL DEFAULT 0,
    urgent INTEGER NOT NULL DEFAULT 0,
    extend_saturday INTEGER NOT NULL DEFAULT 1,
    extend_holiday INTEGER NOT NULL DEFAULT 1,
    reference_law TEXT NOT NULL DEFAULT '',
    cartabia_compliant INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS deadline_audit_logs (
    id TEXT PRIMARY KEY,
    template_code TEXT NOT NULL,
    template_version INTEGER NOT NULL,
    case_reference TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    input_date TEXT NOT NULL,
    calculated_deadline TEXT NOT NULL,
    rules_applied_json TEXT NOT NULL DEFAULT '[]',
    engine_version TEXT NOT NULL,
    ruleset_version TEXT NOT NULL,
    calendar_version TEXT NOT NULL,
    is_override INTEGER NOT NULL DEFAULT 0,
    override_reason TEXT NOT NULL DEFAULT '',
    raw_input_json TEXT NOT NULL DEFAULT '{}',
    raw_output_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    immutable_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deadline_audit_deadline ON deadline_audit_logs(calculated_deadline);
CREATE INDEX IF NOT EXISTS idx_deadline_audit_case ON deadline_audit_logs(case_reference);
CREATE INDEX IF NOT EXISTS idx_deadline_template_matter ON deadline_templates(matter_type, urgent);

CREATE TABLE IF NOT EXISTS official_holidays (
    day TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'national',
    source_year INTEGER NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    checksum_sha256 TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS calendar_versions (
    version TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL DEFAULT '',
    checksum_sha256 TEXT NOT NULL DEFAULT '',
    imported_at TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS deadline_notification_logs (
    id TEXT PRIMARY KEY,
    deadline_id TEXT NOT NULL,
    case_reference TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL DEFAULT 'PEC',
    days_left INTEGER NOT NULL,
    scheduled_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    idempotency_key TEXT NOT NULL UNIQUE,
    message_id TEXT NOT NULL DEFAULT '',
    receipt_status TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_deadline_notification_due ON deadline_notification_logs(scheduled_at, status);
"""


def holidays_from_csv(filepath: str | Path) -> list[dict[str, str]]:
    with Path(filepath).open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]
