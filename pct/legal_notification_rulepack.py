"""Rulepack governato per riconoscimento e tempi delle notifiche legali.

Il modulo non esegue rete e non decide dal cutoff interno quale legge applicare.
Il caricamento JSON e la compilazione delle regex avvengono una sola volta per
processo; la pipeline richiama il motore durante la materializzazione worker.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

RULEPACK_PATH = Path(__file__).with_name("data") / "legal_notification_detection_rules_v1.json"
SOURCE_REGISTRY_PATH = Path(__file__).with_name("data") / "legal_sources_registry.json"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ROME = ZoneInfo("Europe/Rome")
MANDATORY_EVENT_TYPES = frozenset(
    {
        "EXPLICIT_NOTIFICATION_ORDER",
        "PROCEDURE_RULE_CANDIDATE",
        "STRATEGIC_NOTIFICATION_REVIEW",
        "COMMUNICATION_ONLY",
        "SENT_NOTIFICATION",
        "RAC",
        "RdAC",
        "DELIVERY_FAILURE",
        "PROOF_DEPOSIT",
        "PROOF_DEPOSIT_ACCEPTED",
        "NON_LEGAL_NOTIFICATION",
    }
)
REQUIRED_RULE_FIELDS = frozenset(
    {
        "id",
        "version",
        "procedural_family",
        "event_type",
        "trigger_mode",
        "positive_patterns",
        "negative_patterns",
        "source_requirements",
        "notification_case",
        "recommended_template_id",
        "portal_original_required",
        "default_priority",
        "legal_sources",
        "human_review_required",
        "effective_from",
        "effective_to",
    }
)
EVENT_TYPE_ALIASES = {
    "office_communication_not_l53_notification": "COMMUNICATION_ONLY",
    "office_communication": "COMMUNICATION_ONLY",
    "non_legal_message": "NON_LEGAL_NOTIFICATION",
    "notification_delivery_failure": "DELIVERY_FAILURE",
    "notification_rdac": "RdAC",
    "notification_rac": "RAC",
    "notification_l53_sent": "SENT_NOTIFICATION",
    "notification_to_prepare": "EXPLICIT_NOTIFICATION_ORDER",
    "notification_strategic_review": "STRATEGIC_NOTIFICATION_REVIEW",
}


def _clean(value: Any, limit: int = 0) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\x00", " ")).strip()
    return text[:limit].rstrip() if limit and len(text) > limit else text


@lru_cache(maxsize=4)
def _load_json(resolved_path: str) -> dict[str, Any]:
    return json.loads(Path(resolved_path).read_text(encoding="utf-8"))


def load_notification_rulepack(path: str | Path | None = None) -> dict[str, Any]:
    return _load_json(str(Path(path or RULEPACK_PATH).resolve()))


def load_legal_source_registry(path: str | Path | None = None) -> dict[str, Any]:
    return _load_json(str(Path(path or SOURCE_REGISTRY_PATH).resolve()))


def _normalise_detection_rule(raw: dict[str, Any]) -> dict[str, Any]:
    """Accetta il JSON storico già versionato e lo porta al contratto runtime."""

    rule = dict(raw)
    rule["match_priority"] = int(rule.get("match_priority") or rule.get("priority") or 0)
    rule["version"] = str(rule.get("version") or str(rule.get("id") or "v1").rsplit(".", 1)[-1] or "v1")
    rule["procedural_family"] = str(rule.get("procedural_family") or "civil_notification")
    rule["trigger_mode"] = str(rule.get("trigger_mode") or "deterministic")
    rule["positive_patterns"] = list(rule.get("positive_patterns") or rule.get("positive_any") or [])
    rule["negative_patterns"] = list(rule.get("negative_patterns") or rule.get("negative_any") or [])
    rule["source_requirements"] = rule.get("source_requirements") or {
        "source_types": list(rule.get("source_types") or [])
    }
    rule["recommended_template_id"] = str(
        rule.get("recommended_template_id")
        or ("relata_pec_base_l53" if rule.get("creates_notification_candidate") else "")
    )
    rule["portal_original_required"] = rule.get("portal_original_required", rule.get("portal_original", "never"))
    rule["default_priority"] = str(rule.get("default_priority") or rule.get("result_priority") or "P2")
    rule["effective_from"] = str(rule.get("effective_from") or "2026-07-20")
    rule["effective_to"] = rule.get("effective_to", "")
    rule["event_type"] = EVENT_TYPE_ALIASES.get(str(rule.get("event_type") or ""), str(rule.get("event_type") or ""))
    return rule


@lru_cache(maxsize=4)
def _compiled_rules(resolved_path: str) -> tuple[dict[str, Any], ...]:
    payload = _load_json(resolved_path)
    compiled: list[dict[str, Any]] = []
    rules = payload.get("detection_rules") or []
    for raw_rule in sorted(rules, key=lambda item: -int(item.get("match_priority") or item.get("priority") or 0)):
        rule = _normalise_detection_rule(raw_rule)
        missing = sorted(REQUIRED_RULE_FIELDS.difference(rule))
        if missing:
            raise ValueError(f"Regola {rule.get('id') or '<senza id>'}: campi mancanti: {', '.join(missing)}")
        if rule["event_type"] not in MANDATORY_EVENT_TYPES:
            raise ValueError(f"Regola {rule['id']}: event_type non governato: {rule['event_type']}")
        compiled.append(
            {
                "rule": rule,
                "positive": tuple(re.compile(pattern, re.IGNORECASE) for pattern in rule["positive_patterns"]),
                "negative": tuple(re.compile(pattern, re.IGNORECASE) for pattern in rule["negative_patterns"]),
            }
        )
    return tuple(compiled)


def compiled_notification_rules(path: str | Path | None = None) -> tuple[dict[str, Any], ...]:
    return _compiled_rules(str(Path(path or RULEPACK_PATH).resolve()))


def validate_source_registry(
    path: str | Path | None = None,
    *,
    require_snapshots: bool = True,
) -> dict[str, Any]:
    """Valida hash reali; le fonti mancanti falliscono con istruzione acquisizione."""

    registry = load_legal_source_registry(path)
    errors: list[str] = []
    for source in registry.get("notification_sources") or []:
        snapshot = source.get("snapshot") if isinstance(source.get("snapshot"), dict) else {}
        status = str(snapshot.get("status") or "")
        instruction = str(snapshot.get("acquisition_instruction") or "")
        if status == "acquisition_required":
            if require_snapshots:
                errors.append(f"{source.get('id')}: {instruction or 'Acquisire lo snapshot dalla fonte ufficiale.'}")
            continue
        local_path = str(snapshot.get("local_path") or "")
        expected = str(snapshot.get("sha256") or "").lower()
        if status != "verified" or not local_path or not re.fullmatch(r"[0-9a-f]{64}", expected):
            errors.append(f"{source.get('id')}: metadati snapshot incompleti o non governati")
            continue
        candidate = REPOSITORY_ROOT / local_path
        if not candidate.is_file():
            errors.append(f"{source.get('id')}: snapshot assente: {local_path}")
            continue
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if digest != expected:
            errors.append(f"{source.get('id')}: SHA-256 diverso per {local_path}")
    for bundle in registry.get("source_bundles") or []:
        for component in bundle.get("components") or []:
            local_path = str(component.get("local_path") or "")
            expected = str(component.get("sha256") or "").lower()
            candidate = REPOSITORY_ROOT / local_path
            if not local_path or not re.fullmatch(r"[0-9a-f]{64}", expected):
                errors.append(f"{bundle.get('id')}: componente senza path/hash governato")
            elif not candidate.is_file():
                errors.append(f"{bundle.get('id')}: componente assente: {local_path}")
            elif hashlib.sha256(candidate.read_bytes()).hexdigest() != expected:
                errors.append(f"{bundle.get('id')}: SHA-256 diverso per {local_path}")
    if errors:
        raise ValueError("Registro fonti notifiche non validato:\n- " + "\n- ".join(errors))
    return registry


def _parse_date(value: Any) -> date | None:
    raw = _clean(value, 40)
    if not raw:
        return None
    for parser in (
        lambda: date.fromisoformat(raw[:10]),
        lambda: datetime.strptime(raw[:10], "%d/%m/%Y").date(),
    ):
        try:
            return parser()
        except ValueError:
            pass
    return None


def _parse_datetime(value: Any) -> datetime | None:
    raw = _clean(value, 80)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        for pattern in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                parsed = datetime.strptime(raw, pattern)
                break
            except ValueError:
                continue
    if parsed is None:
        return None
    return parsed.replace(tzinfo=ROME) if parsed.tzinfo is None else parsed.astimezone(ROME)


def _fmt_it(value: datetime | None) -> str:
    return value.astimezone(ROME).strftime("%d/%m/%Y %H:%M:%S") if value else ""


def resolve_procedural_regime(
    proceeding_commenced_on: Any = "",
    *,
    context_kind: str = "proceeding",
    notification_event_at: Any = "",
    rulepack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Seleziona il regime legale; il cutoff di migrazione non entra nel calcolo."""

    rules = rulepack or load_notification_rulepack()
    transition = _parse_date((rules.get("procedural_resolvers") or {}).get("cartabia_civil_transition"))
    transition = transition or date(2023, 2, 28)
    kind = _clean(context_kind).lower() or "proceeding"
    commenced = _parse_date(proceeding_commenced_on)
    event_day = _parse_datetime(notification_event_at)
    reference = commenced if kind == "proceeding" else (event_day.date() if event_day else _parse_date(notification_event_at))
    if reference is None:
        return {
            "regime_id": "needs_review",
            "reason": "Data di introduzione del procedimento non disponibile: selezione normativa da confermare.",
            "human_review_required": True,
            "source_ids": [],
            "policy_used_for_selection": False,
        }
    current = reference > transition if kind == "proceeding" else reference >= transition + timedelta(days=1)
    regime_id = "cartabia_current" if current else "pre_cartabia_historical"
    regime = (rules.get("legal_regimes") or {}).get(regime_id) or {}
    return {
        "regime_id": regime_id,
        "reason": str(regime.get("reason") or ""),
        "human_review_required": bool(regime.get("human_review_required", not current)),
        "source_ids": list(regime.get("source_ids") or []),
        "reference_date": reference.isoformat(),
        "policy_used_for_selection": False,
    }


def resolve_legacy_policy(
    event_at: Any = "",
    rulepack: dict[str, Any] | None = None,
    *,
    explicit_action_at: Any = "",
    official_delivery_at: Any = "",
    event_order_at: Any = "",
    portal_release_at: Any = "",
    document_at: Any = "",
    filesystem_at: Any = "",
) -> dict[str, Any]:
    """Applica solo la policy di migrazione, con precedenza temporale governata.

    Il cutoff non seleziona mai il regime legale. Una scadenza/azione esplicita
    futura prevale quindi sulla data di arrivo di una PEC storica.
    """

    rules = rulepack or load_notification_rulepack()
    overlay = (rules.get("policy_overlays") or {}).get("legacy_migration_cutoff") or {}
    historical_cutoff = _parse_datetime(overlay.get("historical_cutoff"))
    strict_from = _parse_datetime(overlay.get("strict_tracking_from"))
    historical_cutoff = historical_cutoff or datetime(2026, 7, 19, 23, 59, 59, tzinfo=ROME)
    strict_from = strict_from or datetime(2026, 7, 20, 0, 0, 0, tzinfo=ROME)
    candidates = (
        ("explicit_action_at", explicit_action_at),
        ("official_delivery_at", official_delivery_at),
        ("event_order_at", event_order_at),
        ("portal_release_at", portal_release_at),
        ("document_at", document_at),
        ("event_at", event_at),
        ("filesystem_at", filesystem_at),
    )
    reference_source = ""
    reference: datetime | None = None
    for source, raw in candidates:
        parsed = _parse_datetime(raw)
        if parsed is not None:
            reference_source, reference = source, parsed
            break
    applies = bool(reference and reference < strict_from)
    filesystem_fallback = reference_source == "filesystem_at"
    return {
        "policy_id": "legacy_migration_cutoff",
        "historical_cutoff": historical_cutoff.isoformat(),
        "strict_tracking_from": strict_from.isoformat(),
        "reference_at": reference.isoformat() if reference else None,
        "reference_source": reference_source or None,
        "applies": applies,
        "effect": "migration_review" if applies else "strict_tracking" if reference else "needs_review",
        "human_review_required": reference is None or filesystem_fallback,
        "legal_regime_selector": False,
    }


def calculate_notification_effects(
    *,
    rac_at: Any = "",
    rdac_at: Any = "",
    proceeding_commenced_on: Any = "",
    context_kind: str = "proceeding",
) -> dict[str, Any]:
    rac = _parse_datetime(rac_at)
    rdac = _parse_datetime(rdac_at)
    regime = resolve_procedural_regime(
        proceeding_commenced_on,
        context_kind=context_kind,
        notification_event_at=rdac or rac or "",
    )
    recipient_effect = rdac
    deferred = False
    if rdac and regime["regime_id"] in {"cartabia_current", "pre_cartabia_historical"}:
        local = rdac.astimezone(ROME)
        if local.time() < time(7, 0):
            recipient_effect = datetime.combine(local.date(), time(7, 0), tzinfo=ROME)
            deferred = True
        elif local.time() >= time(21, 0):
            recipient_effect = datetime.combine(local.date() + timedelta(days=1), time(7, 0), tzinfo=ROME)
            deferred = True
    historical_night_review = bool(
        regime["regime_id"] == "pre_cartabia_historical"
        and ((rac and rac.astimezone(ROME).time() < time(7, 0)) or (rdac and rdac.astimezone(ROME).time() < time(7, 0)))
    )
    return {
        "legal_regime": regime,
        "rac_at": rac.isoformat() if rac else None,
        "rdac_at": rdac.isoformat() if rdac else None,
        "sender_effect_at": rac.isoformat() if rac else None,
        "recipient_effect_at": recipient_effect.isoformat() if recipient_effect else None,
        "sender_effect_label": _fmt_it(rac) if rac else "In attesa della RAC effettiva.",
        "recipient_effect_label": _fmt_it(recipient_effect) if recipient_effect else "In attesa della RdAC effettiva.",
        "recipient_effect_deferred": deferred,
        "delivery_proven": rdac is not None,
        "complete": rac is not None and rdac is not None,
        "human_review_required": bool(regime["human_review_required"] or historical_night_review),
    }


def calculate_recipients_effects(
    recipients: Iterable[dict[str, Any]],
    *,
    proceeding_commenced_on: Any = "",
    context_kind: str = "proceeding",
) -> dict[str, Any]:
    """Calcola ricevute ed esito separatamente per ciascun destinatario."""

    rows: list[dict[str, Any]] = []
    for index, recipient in enumerate(recipients):
        if not isinstance(recipient, dict):
            continue
        effects = calculate_notification_effects(
            rac_at=recipient.get("rac_at"),
            rdac_at=recipient.get("rdac_at"),
            proceeding_commenced_on=proceeding_commenced_on,
            context_kind=context_kind,
        )
        sent_at = _parse_datetime(recipient.get("sent_at"))
        failure_at = _parse_datetime(recipient.get("failure_at"))
        failed = bool(failure_at or recipient.get("delivery_failure"))
        failure_attribution = _clean(
            recipient.get("failure_attribution")
            or recipient.get("failure_classification")
            or ("uncertain" if failed else ""),
            80,
        )
        if failure_attribution not in {
            "",
            "attributable_to_recipient",
            "not_attributable_to_recipient",
            "uncertain",
        }:
            failure_attribution = "uncertain"
        if failed:
            status, priority = "DELIVERY_FAILURE", "P0"
        elif effects["delivery_proven"]:
            status, priority = "DELIVERY_COMPLETE", "P1"
        elif effects["rac_at"]:
            status, priority = "RAC_RECEIVED", "P1"
        elif sent_at:
            status, priority = "SENT_WAITING_RAC", "P1"
        else:
            status, priority = "NOT_SENT", "P2"
        rows.append(
            {
                "recipient_id": _clean(recipient.get("recipient_id") or recipient.get("address") or f"destinatario-{index + 1}", 320),
                "status": status,
                "priority": priority,
                "sent_at": sent_at.isoformat() if sent_at else None,
                "failure_at": failure_at.isoformat() if failure_at else None,
                "failure_attribution": failure_attribution,
                **effects,
            }
        )
    delivered = sum(row["status"] == "DELIVERY_COMPLETE" for row in rows)
    failed_count = sum(row["status"] == "DELIVERY_FAILURE" for row in rows)
    if rows and delivered == len(rows):
        aggregate_status, priority = "DELIVERY_COMPLETE", "P1"
    elif delivered:
        aggregate_status = "PARTIAL_DELIVERY"
        priority = "P0" if failed_count else "P1"
    elif failed_count:
        aggregate_status, priority = "DELIVERY_FAILED", "P0"
    elif any(row["status"] == "RAC_RECEIVED" for row in rows):
        aggregate_status, priority = "RAC_RECEIVED", "P1"
    elif any(row["status"] == "SENT_WAITING_RAC" for row in rows):
        aggregate_status, priority = "SENT_WAITING_RAC", "P1"
    else:
        aggregate_status, priority = "NOT_SENT", "P2"
    return {
        "status": aggregate_status,
        "priority": priority,
        "complete": bool(rows and delivered == len(rows)),
        "delivery_proven_for_all": bool(rows and delivered == len(rows)),
        "delivered_recipients": delivered,
        "failed_recipients": failed_count,
        "human_review_required": any(
            row["status"] == "DELIVERY_FAILURE" and row["failure_attribution"] == "uncertain"
            for row in rows
        ),
        "recipient_count": len(rows),
        "recipients": rows,
    }


def _payload_value(payload: dict[str, Any], *paths: str) -> Any:
    for path in paths:
        current: Any = payload
        for segment in path.split("."):
            current = current.get(segment) if isinstance(current, dict) else None
        if current not in (None, ""):
            return current
    return ""


def build_notification_timing_plan(payload: dict[str, Any]) -> dict[str, Any]:
    raw = _payload_value(payload, "notifica.invio_programmato", "notifica.data_ora_invio", "invio_programmato", "data_ora_invio_pec", "pec_send_at")
    planned = _parse_datetime(raw)
    commenced = _payload_value(payload, "notifica.data_inizio_procedimento", "procedimento.data_introduzione", "data_inizio_procedimento", "proceeding_commenced_on")
    context_kind = _clean(_payload_value(payload, "notifica.contesto_regime", "context_kind"))
    if not context_kind:
        has_proceeding_context = bool(
            commenced
            or isinstance(payload.get("procedimento"), dict)
            or _payload_value(payload, "notifica.procedimento_id", "procedimento_id", "fascicolo_id")
        )
        context_kind = "proceeding" if has_proceeding_context else "standalone_notification"
    regime = resolve_procedural_regime(commenced, context_kind=context_kind, notification_event_at=planned or "")
    policy = resolve_legacy_policy(planned or "", explicit_action_at=planned or "")
    night_overlay = (load_notification_rulepack().get("policy_overlays") or {}).get("night_send_prudential") or {}
    night_mode = _clean(_payload_value(payload, "notifica.policy_fascia_notturna", "policy_fascia_notturna"))
    night_mode = night_mode or str(night_overlay.get("default_mode") or "warning")
    policy["night_send_prudential"] = {
        "mode": night_mode,
        "configurable": True,
        "legal_rule": False,
    }
    common = {"legalRegime": regime, "policy": policy, "legalSourceIds": regime["source_ids"]}
    if planned is None:
        return {
            "plannedAt": _clean(raw), "ready": True, "status": "da_pianificare",
            "senderEffect": "Il perfezionamento del notificante sarà determinato dalla RAC effettiva.",
            "recipientEffect": "Il perfezionamento del destinatario sarà determinato dalla RdAC effettiva.",
            "warning": "Data del procedimento da confermare." if regime["human_review_required"] else "", **common,
        }
    local_time = planned.astimezone(ROME).time()
    historical_block = regime["regime_id"] == "pre_cartabia_historical" and local_time < time(7, 0)
    prudential_block = regime["regime_id"] == "cartabia_current" and local_time < time(7, 0) and night_mode == "block"
    if local_time < time(7, 0) or local_time >= time(21, 0):
        status = "fuori_fascia_storica" if historical_block else "policy_prudenziale_notturna" if prudential_block else "fascia_con_differimento_destinatario"
        warning = (
            "Regime storico: fascia 00:00-06:59 da sottoporre a verifica professionale."
            if historical_block else "Policy interna configurata: invio notturno sospeso; non è un divieto del regime vigente."
            if prudential_block else
            "Nessun divieto corrente di invio; l'effetto per il destinatario dipende dalla RdAC effettiva e può essere differito alle 07:00."
        )
        return {
            "plannedAt": _fmt_it(planned), "ready": not historical_block and not prudential_block, "status": status,
            "senderEffect": "In attesa della RAC effettiva; l'orario pianificato non prova il perfezionamento.",
            "recipientEffect": "In attesa della RdAC effettiva; tra le 21:00 e le 06:59 l'effetto è differito alle 07:00.",
            "warning": warning, **common,
        }
    return {
        "plannedAt": _fmt_it(planned), "ready": regime["regime_id"] != "needs_review", "status": "fascia_ordinaria",
        "senderEffect": "In attesa della RAC effettiva.", "recipientEffect": "In attesa della RdAC effettiva.",
        "warning": "Data del procedimento da confermare." if regime["human_review_required"] else "", **common,
    }


def _source_type(filename: str) -> str:
    lowered = filename.lower()
    if lowered.endswith("comunicazione.xml"):
        return "comunicazione_xml"
    if lowered.endswith("daticert.xml"):
        return "daticert_xml"
    if lowered.endswith("postacert.eml") or lowered.endswith(".eml"):
        return "eml"
    return "attachment"


def _text_sources(parsed: dict[str, Any], report: dict[str, Any], attachments: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    headers = parsed.get("headers") if isinstance(parsed.get("headers"), dict) else {}
    procedural_rule = (
        report.get("procedural_notification_rule")
        or report.get("notification_rule")
        or parsed.get("procedural_notification_rule")
        or parsed.get("notification_rule")
    )
    procedural_text = (
        json.dumps(procedural_rule, ensure_ascii=False, sort_keys=True)
        if isinstance(procedural_rule, dict)
        else procedural_rule
    )
    sources = [
        {"source_type": "message_subject", "source_file": "PEC", "text": _clean(headers.get("subject") or parsed.get("subject"), 1000)},
        {"source_type": "message_body", "source_file": "PEC", "text": _clean(parsed.get("body_text") or parsed.get("text") or parsed.get("body"), 50000)},
        {"source_type": "validation_report", "source_file": "report", "text": _clean(report.get("summary") or report.get("message"), 10000)},
        {"source_type": "procedural_rule", "source_file": "regola-procedurale", "text": _clean(procedural_text, 10000)},
    ]
    all_attachments = [*(parsed.get("attachments") or []), *list(attachments or [])]
    for index, item in enumerate(all_attachments):
        if not isinstance(item, dict):
            continue
        filename = _clean(item.get("filename") or item.get("name") or item.get("nome_file") or f"allegato-{index + 1}", 260)
        text_value = _clean(item.get("ocr_text") or item.get("extracted_text") or item.get("text") or item.get("content_text"), 50000)
        sources.append({"source_type": _source_type(filename), "source_file": filename, "text": text_value})
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for source in sources:
        key = (source["source_type"], source["source_file"], source["text"])
        if source["text"] and key not in seen:
            seen.add(key)
            unique.append(source)
    return unique


def _is_verified_portal_original(item: dict[str, Any]) -> bool:
    filename = _clean(item.get("filename") or item.get("name") or item.get("original_filename")).lower()
    text_value = _clean(item.get("ocr_text") or item.get("extracted_text") or item.get("text") or item.get("content_text"), 5000).lower()
    role = _clean(item.get("document_role") or item.get("role")).lower()
    origin = _clean(item.get("source") or item.get("origin")).lower()
    verification = _clean(item.get("verification_status") or item.get("status")).lower()
    declared_original = bool(
        item.get("portal_original") is True
        or role in {"portal_original", "duplicato_informatico", "authoritative_original"}
    )
    governed_origin = bool(
        origin in {"pst", "polisweb", "portal", "ministerial_portal"}
        or item.get("portal_document_id")
        or item.get("portal_reference")
    )
    verified = bool(
        item.get("verified") is True
        or verification in {"verified", "hash_verified", "signature_verified"}
    )
    professional_attachment = bool(
        filename
        and not filename.endswith(("comunicazione.xml", "daticert.xml", "postacert.eml"))
        and filename.endswith((".pdf", ".p7m", ".pdf.p7m", ".doc", ".docx", ".odt"))
        and (text_value or item.get("content_sha256") or item.get("sha256"))
    )
    return (declared_original and governed_origin and verified) or professional_attachment


def portal_original_requirement(
    parsed: dict[str, Any],
    attachments: Iterable[dict[str, Any]] = (),
    *,
    _sources: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    attachment_rows = [*(parsed.get("attachments") or []), *list(attachments or [])]
    sources = _sources if _sources is not None else _text_sources(parsed, {}, attachments)
    joined = "\n".join(source["text"] for source in sources).lower()
    secure_notice = "avviso di disponibilità" in joined or "area download" in joined or "pst.giustizia.it" in joined
    original_present = any(
        _is_verified_portal_original(item)
        for item in attachment_rows
        if isinstance(item, dict)
    )
    required = secure_notice and not original_present
    return {
        "required": required,
        "reason": "Acquisire l'originale dal portale indicato prima dell'uso probatorio." if required else "Originale allegato o avviso portale non rilevato.",
        "conditional": True,
        "original_present": original_present,
    }


def detect_notification_candidates(
    parsed: dict[str, Any],
    report: dict[str, Any] | None = None,
    *,
    attachments: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Classifica evidenze già estratte; non apre portali e non analizza su GET."""

    pack = load_notification_rulepack()
    sources = _text_sources(parsed, report or {}, attachments)
    portal = portal_original_requirement(parsed, attachments, _sources=sources)
    findings: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for source in sources:
        for compiled in compiled_notification_rules():
            rule = compiled["rule"]
            allowed = (rule.get("source_requirements") or {}).get("source_types") or []
            if allowed and source["source_type"] not in allowed:
                continue
            text_value = source["text"]
            if compiled["negative"] and any(pattern.search(text_value) for pattern in compiled["negative"]):
                continue
            match = None
            for pattern in compiled["positive"]:
                match = pattern.search(text_value)
                if match:
                    break
            if not match:
                continue
            key = (str(rule["id"]), source["source_file"])
            if key in seen:
                continue
            seen.add(key)
            start = max(0, match.start() - 90)
            excerpt = _clean(text_value[start : match.end() + 180], 360)
            findings.append(
                {
                    "event_type": rule["event_type"], "confidence": float(rule["confidence"]),
                    "evidence": [{"source_file": source["source_file"], "source_locator": source["source_type"], "text_excerpt": excerpt}],
                    "source_file": source["source_file"], "source_locator": source["source_type"], "text_excerpt": excerpt,
                    "rule_id": rule["id"], "rulepack_version": pack["version"], "reason": rule["reason"],
                    "proposed_action": rule["proposed_action"],
                    "creates_notification_candidate": bool(rule["creates_notification_candidate"]),
                    "human_review_required": bool(rule["human_review_required"]),
                    "notification_case": rule["notification_case"], "priority": rule["default_priority"],
                    "legal_sources": list(rule.get("legal_sources") or []),
                    "recommended_template_id": rule.get("recommended_template_id"),
                    "portal_original_required": bool(portal["required"] and rule.get("portal_original_required") == "conditional"),
                }
            )
            if rule.get("terminal_for_source"):
                break
    return findings


__all__ = [
    "build_notification_timing_plan", "calculate_notification_effects", "calculate_recipients_effects",
    "compiled_notification_rules",
    "detect_notification_candidates", "load_legal_source_registry", "load_notification_rulepack",
    "portal_original_requirement", "resolve_legacy_policy", "resolve_procedural_regime", "validate_source_registry",
]
