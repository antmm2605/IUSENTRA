"""Eccezioni tipizzate del Legal Skills Engine."""

from __future__ import annotations


class LegalSkillsError(RuntimeError):
    code = "legal_skills_error"
    status_code = 400

    def __init__(self, message: str = "", *, code: str = "", status_code: int | None = None) -> None:
        super().__init__(message or "Operazione Legal Skills non riuscita.")
        if code:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class FeatureDisabledError(LegalSkillsError):
    code = "feature_disabled"
    status_code = 403


class PermissionDeniedError(LegalSkillsError):
    code = "permission_denied"
    status_code = 403


class ProfileIncompleteError(LegalSkillsError):
    code = "profile_incomplete"
    status_code = 409


class SkillNotFoundError(LegalSkillsError):
    code = "skill_not_found"
    status_code = 404


class TrustRefusedError(LegalSkillsError):
    code = "trust_refused"
    status_code = 422


class StorageError(LegalSkillsError):
    code = "storage_error"
    status_code = 500


__all__ = [
    "FeatureDisabledError",
    "LegalSkillsError",
    "PermissionDeniedError",
    "ProfileIncompleteError",
    "SkillNotFoundError",
    "StorageError",
    "TrustRefusedError",
]
