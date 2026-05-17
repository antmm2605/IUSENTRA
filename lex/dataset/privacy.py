"""Classificazione privacy leggera per dataset Lex."""

from __future__ import annotations

import re
from typing import Any

from .models import PrivacyClassification


_CF_RE = re.compile(r"\b[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]\b", re.IGNORECASE)
_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_IBAN_RE = re.compile(r"\bIT\d{2}[A-Z]\d{10}[0-9A-Z]{12}\b", re.IGNORECASE)
_RG_RE = re.compile(r"\b(?:RG|R\.G\.|N\.?\s*R\.?\s*G\.?)\s*\d{1,7}/\d{2,4}\b", re.IGNORECASE)
_PHONE_RE = re.compile(r"(?<!\d)(?:\+39\s*)?(?:0\d{1,3}[\s.-]?\d{5,8}|3\d{2}[\s.-]?\d{6,7})(?!\d)")


def _count_sensitive_hits(text: str) -> int:
    value = str(text or "")
    return sum(
        len(pattern.findall(value))
        for pattern in (_CF_RE, _EMAIL_RE, _IBAN_RE, _RG_RE, _PHONE_RE)
    )


def classify_privacy(text: Any, *, default: PrivacyClassification = "studio_internal") -> PrivacyClassification:
    value = str(text or "")
    if not value.strip():
        return default
    hits = _count_sensitive_hits(value)
    if hits >= 3:
        return "highly_sensitive"
    if hits > 0:
        return "sensitive"
    return default


def redact_sensitive_for_dataset(text: Any) -> str:
    value = str(text or "")
    value = _CF_RE.sub("[CODICE_FISCALE_OSCURATO]", value)
    value = _EMAIL_RE.sub("[EMAIL_OSCURATA]", value)
    value = _IBAN_RE.sub("[IBAN_OSCURATO]", value)
    value = _RG_RE.sub("[RG_OSCURATO]", value)
    value = _PHONE_RE.sub("[TELEFONO_OSCURATO]", value)
    return value
