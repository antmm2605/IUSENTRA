from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from zoneinfo import ZoneInfo

from .models import PresidioStatus, Priority


ROME = ZoneInfo("Europe/Rome")
HISTORICAL_POLICY_ID = "policy.studio.notification_legacy_cutoff.2026-07-19.v1"
HISTORICAL_CUTOFF = datetime(2026, 7, 19, 23, 59, 59, tzinfo=ROME)
STRICT_TRACKING_FROM = datetime(2026, 7, 20, 0, 0, 0, tzinfo=ROME)
LEGACY_DECLARATION = "Dichiarazione dello studio: pratiche gestite fino al 19/07/2026"


@dataclass(frozen=True, slots=True)
class HistoricalDecision:
    status: PresidioStatus
    priority: Priority
    effective_at: str
    date_basis: str
    legacy_assumed_handled: bool
    human_review_required: bool
    reason: str
    policy_id: str = HISTORICAL_POLICY_ID


def _parse(value: Any, *, filesystem_fallback: bool = False) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        if filesystem_fallback:
            return parsed.replace(tzinfo=ROME)
        return None
    return parsed.astimezone(ROME)


def _effective_date(payload: Mapping[str, Any]) -> tuple[datetime | None, str, bool]:
    ordered = (
        ("explicit_due_at", False),
        ("pec_official_delivery_at", False),
        ("event_or_order_at", False),
        ("source_effective_at", False),
        ("portal_release_at", False),
        ("document_date", False),
        ("filesystem_date", True),
    )
    for key, filesystem in ordered:
        parsed = _parse(payload.get(key), filesystem_fallback=filesystem)
        if parsed is not None:
            return parsed, key, filesystem
    return None, "missing", True


def classify_historical_record(payload: Mapping[str, Any]) -> HistoricalDecision:
    complete_proof = bool(payload.get("complete_proof"))
    negative_delivery = bool(payload.get("negative_delivery"))
    partial_delivery = bool(payload.get("partial_delivery"))
    notification_case = str(payload.get("notification_case") or "")
    trigger_type = str(payload.get("trigger_type") or "").strip().upper()
    live_operational_event = bool(payload.get("live_pec_operational_event"))
    explicit_notification_request = trigger_type in {
        "EXPLICIT_NOTIFICATION_ORDER",
        "PROCEDURE_RULE_CANDIDATE",
        "NOTIFICATION_TO_PREPARE",
    }
    explicit_due = _parse(payload.get("explicit_due_at"))
    effective, basis, weak_basis = _effective_date(payload)

    if complete_proof and not negative_delivery and not partial_delivery:
        return HistoricalDecision(
            PresidioStatus.CLOSED,
            Priority.P3,
            effective.isoformat() if effective else "",
            basis,
            False,
            False,
            "Workflow storico verificato con prova completa.",
        )
    if negative_delivery or partial_delivery:
        return HistoricalDecision(
            PresidioStatus.LEGACY_REVIEW_REQUIRED,
            Priority.P0 if negative_delivery else Priority.P1,
            effective.isoformat() if effective else "",
            basis,
            False,
            True,
            "Esito negativo o parziale: revisione obbligatoria anche prima del cutoff.",
        )
    # Il cutoff del 19/07/2026 e' una dichiarazione di migrazione dello storico,
    # non una prova giuridica di esecuzione. Un evento PEC ancora operativo o una
    # richiesta espressa di notifica resta quindi aperto finche' non esiste una
    # catena probatoria completa e correlata.
    if live_operational_event or explicit_notification_request:
        requires_review = bool(
            payload.get("human_review_required")
            or effective is None
            or effective < STRICT_TRACKING_FROM
        )
        return HistoricalDecision(
            PresidioStatus.DETECTED,
            Priority.P1,
            effective.isoformat() if effective else "",
            basis,
            False,
            requires_review,
            "Evento PEC operativo o richiesta espressa senza prova completa: presidio attivo.",
        )
    if explicit_due is not None and explicit_due >= STRICT_TRACKING_FROM:
        return HistoricalDecision(
            PresidioStatus.DETECTED,
            Priority.P1,
            explicit_due.isoformat(),
            "explicit_due_at",
            False,
            False,
            "Attività esplicita dal 20/07/2026: presidio attivo.",
        )
    if effective is not None and effective >= STRICT_TRACKING_FROM:
        return HistoricalDecision(
            PresidioStatus.DETECTED,
            Priority.P1,
            effective.isoformat(),
            basis,
            False,
            weak_basis,
            "Evento successivo al cutoff operativo: presidio attivo.",
        )
    if effective is not None and effective <= HISTORICAL_CUTOFF and not weak_basis:
        return HistoricalDecision(
            PresidioStatus.LEGACY_ASSUMED_HANDLED,
            Priority.P3,
            effective.isoformat(),
            basis,
            True,
            False,
            LEGACY_DECLARATION,
        )
    return HistoricalDecision(
        PresidioStatus.LEGACY_REVIEW_REQUIRED,
        Priority.P1,
        effective.isoformat() if effective else "",
        basis,
        False,
        True,
        "Data assente o basata sul filesystem: verifica umana obbligatoria.",
    )
