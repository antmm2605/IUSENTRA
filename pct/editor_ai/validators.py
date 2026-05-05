"""Validazioni per Editor AI."""

from __future__ import annotations

import re
from typing import Any

from .models import (
    ATTO_AI_EDIT_OPERATIONS,
    ATTO_AI_EDIT_STATUSES,
    ATTO_AI_STATUSES,
    ATTO_AI_VERSION_SOURCES,
    AttoDraftPlan,
)


FORBIDDEN_ENGLISH_HEADINGS = (
    "case summary",
    "key points",
    "relevant documents",
    "legal basis",
    "in essence",
    "claimant",
    "dispute",
    "breakdown",
)


class EditorAIError(Exception):
    code = "editor_ai_error"


class EditorAIValidationError(EditorAIError):
    code = "validation_error"


class EditorAINotFound(EditorAIError):
    code = "not_found"


class EditorAIPermissionDenied(EditorAIError):
    code = "permission_denied"


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def user_id_from_context(user_context: object) -> str:
    if isinstance(user_context, dict):
        explicit = clean_text(user_context.get("user_id"))
        if explicit:
            return explicit
        user = user_context.get("user")
    else:
        user = user_context
    for attr in ("id", "email", "username", "nome"):
        value = clean_text(getattr(user, attr, ""))
        if value:
            return value
    return "sistema"


def has_user_permission(user_context: object, permission: str) -> bool:
    if isinstance(user_context, dict):
        if user_context.get("skip_permission_check"):
            return True
        user = user_context.get("user")
    else:
        user = user_context
    checker = getattr(user, "ha_permesso", None)
    return bool(callable(checker) and checker(permission))


def assert_user_can_read(user_context: object) -> None:
    if not has_user_permission(user_context, "fascicoli.leggi"):
        raise EditorAIPermissionDenied("Operazione non autorizzata")


def assert_user_can_write(user_context: object) -> None:
    if not has_user_permission(user_context, "fascicoli.scrivi"):
        raise EditorAIPermissionDenied("Operazione non autorizzata")


def validate_status(status: str) -> str:
    value = clean_text(status)
    if value not in ATTO_AI_STATUSES:
        raise EditorAIValidationError("Stato atto AI non valido.")
    return value


def validate_version_source(source: str) -> str:
    value = clean_text(source)
    if value not in ATTO_AI_VERSION_SOURCES:
        raise EditorAIValidationError("Origine versione atto AI non valida.")
    return value


def validate_edit_status(status: str) -> str:
    value = clean_text(status)
    if value not in ATTO_AI_EDIT_STATUSES:
        raise EditorAIValidationError("Stato proposta modifica non valido.")
    return value


def validate_edit_operation(operation_type: str) -> str:
    value = clean_text(operation_type)
    if value not in ATTO_AI_EDIT_OPERATIONS:
        raise EditorAIValidationError("Operazione modifica non valida.")
    return value


def detect_english_headings(text: str) -> list[str]:
    lowered = str(text or "").lower()
    return [phrase for phrase in FORBIDDEN_ENGLISH_HEADINGS if phrase in lowered]


def validate_italian_text(text: str, *, field_name: str = "testo") -> list[str]:
    warnings: list[str] = []
    forbidden = detect_english_headings(text)
    if forbidden:
        raise EditorAIValidationError(
            f"{field_name} contiene intestazioni inglesi non consentite: {', '.join(forbidden)}."
        )
    if re.search(r"\b(okay,? here's|do you have any specific questions)\b", str(text or ""), re.IGNORECASE):
        raise EditorAIValidationError(f"{field_name} contiene formule inglesi non consentite.")
    if str(text or "").strip() and len(re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ]", str(text))) < 20:
        warnings.append(f"{field_name} troppo breve per una bozza professionale.")
    return warnings


def validate_plan(plan: AttoDraftPlan) -> list[str]:
    warnings: list[str] = []
    if not clean_text(plan.title):
        raise EditorAIValidationError("Titolo del piano mancante.")
    if not plan.sections:
        raise EditorAIValidationError("Il piano non contiene sezioni.")
    warnings.extend(validate_italian_text(plan.title, field_name="titolo piano"))
    seen: set[str] = set()
    for section in plan.sections:
        heading = clean_text(section.heading)
        if not heading:
            raise EditorAIValidationError("Una sezione del piano non ha titolo.")
        if section.level < 1 or section.level > 4:
            raise EditorAIValidationError("Livello sezione non valido.")
        warnings.extend(validate_italian_text(heading, field_name="titolo sezione"))
        key = heading.casefold()
        if key in seen:
            warnings.append(f"Sezione duplicata: {heading}.")
        seen.add(key)
    return warnings


def require_existing_source(source_id: str, available_ids: set[str]) -> None:
    clean = clean_text(source_id)
    if clean and clean not in available_ids:
        raise EditorAIValidationError("Fonte documentale non presente nel fascicolo.")
