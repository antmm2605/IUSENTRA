"""Validazioni e primitive di sicurezza per Documenti AI Fascicolo."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path


ALLOWED_DOCUMENT_AI_EXTENSIONS = {"pdf", "docx", "doc"}
DEFAULT_MAX_DOCUMENT_AI_BYTES = 25 * 1024 * 1024


class DocumentAIError(Exception):
    code = "document_ai_error"


class DocumentAIValidationError(DocumentAIError):
    code = "validation_error"


class DocumentAISecurityError(DocumentAIValidationError):
    code = "security_error"


class DocumentAIPermissionDenied(DocumentAIError):
    code = "permission_denied"


class DocumentAINotFound(DocumentAIError):
    code = "not_found"


def _extension(filename: str) -> str:
    suffix = Path(str(filename or "")).suffix.lower().lstrip(".")
    return suffix


def detect_file_type(filename: str) -> str:
    safe_name = sanitize_filename(filename)
    file_type = _extension(safe_name)
    if not file_type:
        raise DocumentAIValidationError("Estensione file mancante.")
    return file_type


def validate_document_file_type(filename: str, mime_type: str | None = None) -> str:
    file_type = detect_file_type(filename)
    assert_allowed_document_ai_extension(file_type)
    return file_type


def sanitize_filename(filename: str) -> str:
    raw = str(filename or "").strip()
    if not raw:
        raise DocumentAIValidationError("Nome file mancante.")
    if "/" in raw or "\\" in raw:
        raise DocumentAIValidationError("Il nome file non puo' contenere percorsi.")
    if raw in {".", ".."} or ".." in Path(raw).parts:
        raise DocumentAIValidationError("Nome file non valido.")
    stem = Path(raw).stem.strip()
    suffix = Path(raw).suffix.lower()
    if not stem or not suffix:
        raise DocumentAIValidationError("Nome file o estensione mancante.")
    normalized = unicodedata.normalize("NFKD", stem)
    ascii_stem = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_stem).strip("._-")
    if not ascii_stem:
        ascii_stem = "documento"
    safe = f"{ascii_stem[:120]}{suffix}"
    if "/" in safe or "\\" in safe or safe in {".", ".."}:
        raise DocumentAIValidationError("Nome file non valido.")
    return safe


def assert_allowed_document_ai_extension(file_type: str) -> None:
    value = str(file_type or "").lower().lstrip(".")
    if value not in ALLOWED_DOCUMENT_AI_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_DOCUMENT_AI_EXTENSIONS))
        raise DocumentAIValidationError(f"Formato non supportato. Formati ammessi: {allowed}.")


def compute_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def compute_sha256_bytes(content: bytes) -> str:
    return compute_sha256(content)


def ensure_allowed_size(size_bytes: int, max_size_bytes: int | None = None) -> None:
    limit = int(max_size_bytes or DEFAULT_MAX_DOCUMENT_AI_BYTES)
    if int(size_bytes or 0) <= 0:
        raise DocumentAIValidationError("File vuoto o non leggibile.")
    if int(size_bytes) > limit:
        raise DocumentAIValidationError("File superiore al limite configurato per i documenti AI.")


def safe_join_under_root(root: str | Path, *parts: str) -> Path:
    root_path = Path(root).resolve()
    candidate = root_path.joinpath(*[str(part) for part in parts]).resolve()
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise DocumentAISecurityError("Percorso documento non valido.") from exc
    return candidate


def user_id_from_context(user_context: object) -> str:
    if isinstance(user_context, dict):
        explicit = str(user_context.get("user_id") or "").strip()
        if explicit:
            return explicit
        user = user_context.get("user")
    else:
        user = user_context
    for attr in ("id", "email", "username", "nome"):
        value = str(getattr(user, attr, "") or "").strip()
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
        raise DocumentAIPermissionDenied("Operazione non autorizzata")


def assert_user_can_write(user_context: object) -> None:
    if not has_user_permission(user_context, "fascicoli.scrivi"):
        raise DocumentAIPermissionDenied("Operazione non autorizzata")
