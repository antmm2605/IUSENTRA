from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .models import canonical_json, required_text, sha256_text


_SPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9@._+-]+")


def _text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    return _SPACE_RE.sub(" ", normalized)


def normalize_pec(value: Any) -> str:
    return _text(value).replace(" ", "")


def _token(value: Any) -> str:
    return _NON_ALNUM_RE.sub("", _text(value))


def _sha(value: Any) -> str:
    candidate = _token(value)
    if re.fullmatch(r"[a-f0-9]{64}", candidate):
        return candidate
    return ""


@dataclass(frozen=True, slots=True)
class IdentityDecision:
    key: str
    basis: str
    confidence: float
    human_review_required: bool
    components: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CorrelationDecision:
    score: float
    reasons: tuple[str, ...]
    auto_link_allowed: bool
    human_review_required: bool


def recipient_identity_key(recipient: Mapping[str, Any]) -> str:
    pec = normalize_pec(recipient.get("pec_address") or recipient.get("pec"))
    fiscal_id = _token(recipient.get("fiscal_id") or recipient.get("codice_fiscale"))
    role = _text(recipient.get("role"))
    name = _text(recipient.get("name") or recipient.get("nome"))
    if not pec and not fiscal_id and not name:
        raise ValueError("Identità destinatario insufficiente")
    return sha256_text(canonical_json([pec, fiscal_id, role, name]))


def canonical_document_identity(document: Mapping[str, Any]) -> IdentityDecision:
    portal_id = _token(document.get("portal_document_id"))
    portal_ref = _text(document.get("portal_reference"))
    content_sha = _sha(document.get("content_sha256") or document.get("extracted_content_sha256"))
    outer_sha = _sha(document.get("outer_sha256") or document.get("container_sha256"))
    zip_sha = _sha(document.get("zip_sha256") or document.get("zip_member_sha256"))
    member_path = _text(document.get("zip_member_path"))
    source_message = _text(document.get("source_message_id"))

    basis = ""
    confidence = 0.0
    review = False
    components: list[str] = []
    if portal_id or portal_ref:
        basis, confidence = "portal_reference", 0.99
        components = [portal_id, portal_ref, content_sha]
    elif content_sha:
        basis, confidence = "content_sha256", 0.98
        components = [content_sha]
    elif outer_sha:
        basis, confidence = "outer_sha256", 0.95
        components = [outer_sha]
    elif zip_sha and member_path:
        basis, confidence = "zip_member", 0.94
        components = [zip_sha, member_path]
    elif source_message and member_path:
        basis, confidence = "source_message_member", 0.90
        components = [source_message, member_path]
    else:
        office = _text(document.get("office") or document.get("ufficio"))
        rg = _token(document.get("rg"))
        number = _token(document.get("document_number") or document.get("numero"))
        document_date = _text(document.get("document_date") or document.get("data"))
        if rg and (office or number or document_date):
            basis, confidence, review = "legal_semantic_fingerprint", 0.80, True
            components = [office, rg, number, document_date]
        else:
            filename = _text(document.get("original_filename") or document.get("filename"))
            size = str(document.get("size") or "").strip()
            if not filename:
                raise ValueError("Identità documentale insufficiente")
            basis, confidence, review = "filename_size_weak", 0.40, True
            components = [filename, size]

    vector = ["canonical-document-v1", basis, *components]
    return IdentityDecision(
        key=sha256_text(canonical_json(vector)),
        basis=basis,
        confidence=confidence,
        human_review_required=review,
        components=tuple(components),
    )


def notification_instance_identity(
    *,
    tenant_id: str,
    fascicolo_id: str,
    canonical_document_key: str,
    document_version: str,
    notification_case: str,
    source_order_or_event_id: str,
    recipients: Iterable[Mapping[str, Any]],
    channel: str,
) -> str:
    tenant = required_text(tenant_id, "tenant_id")
    recipient_keys = sorted({recipient_identity_key(item) for item in recipients})
    if not recipient_keys:
        raise ValueError("Almeno un destinatario è obbligatorio")
    vector = {
        "v": 1,
        "tenant": tenant,
        "fascicolo": required_text(fascicolo_id, "fascicolo_id"),
        "document": required_text(canonical_document_key, "canonical_document_key"),
        "document_version": str(document_version or "1").strip(),
        "notification_case": required_text(notification_case, "notification_case"),
        "source_order_or_event": required_text(
            source_order_or_event_id, "source_order_or_event_id"
        ),
        "recipients": recipient_keys,
        "channel": required_text(channel, "channel").lower(),
    }
    return sha256_text(canonical_json(vector))


def correlation_score(left: Mapping[str, Any], right: Mapping[str, Any]) -> CorrelationDecision:
    reasons: list[str] = []
    score = 0.0
    left_message = _text(left.get("original_message_id") or left.get("message_id"))
    right_message = _text(right.get("original_message_id") or right.get("message_id"))
    if left_message and left_message == right_message:
        return CorrelationDecision(1.0, ("exact_original_message_id",), True, False)

    if _token(left.get("portal_document_id")) and _token(left.get("portal_document_id")) == _token(
        right.get("portal_document_id")
    ):
        return CorrelationDecision(0.99, ("exact_portal_document_id",), True, False)

    same_recipient = normalize_pec(left.get("pec_address")) == normalize_pec(right.get("pec_address"))
    same_case = _token(left.get("fascicolo_id") or left.get("rg")) == _token(
        right.get("fascicolo_id") or right.get("rg")
    )
    left_content = _sha(left.get("content_sha256"))
    right_content = _sha(right.get("content_sha256"))
    if left_content and left_content == right_content and same_case and same_recipient:
        return CorrelationDecision(
            0.98, ("exact_content_hash", "same_case", "same_recipient"), True, False
        )

    left_outer = _sha(left.get("outer_sha256"))
    right_outer = _sha(right.get("outer_sha256"))
    if left_outer and left_outer == right_outer and same_case and same_recipient:
        return CorrelationDecision(
            0.95, ("exact_outer_hash", "same_case", "same_recipient"), True, False
        )

    for key, weight in (("rg", 0.30), ("office", 0.20), ("document_date", 0.15), ("document_number", 0.15)):
        left_value = _text(left.get(key))
        right_value = _text(right.get(key))
        if left_value and left_value == right_value:
            score += weight
            reasons.append(f"same_{key}")
    if same_recipient:
        score += 0.10
        reasons.append("same_recipient")
    if _text(left.get("filename")) and _text(left.get("filename")) == _text(right.get("filename")):
        score = min(score + 0.10, 0.40 if not reasons[:-1] else 0.80)
        reasons.append("same_filename")
    score = min(score, 0.80)
    return CorrelationDecision(score, tuple(reasons), False, True)
