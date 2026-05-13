"""Exceptions for legal-grade audit evidence."""

from __future__ import annotations


class AuditError(RuntimeError):
    """Base class for controlled audit failures."""

    code = "audit_error"


class AuditConfigError(AuditError):
    code = "audit_config_error"


class AuditValidationError(AuditError):
    code = "audit_validation_error"


class AuditWormError(AuditError):
    code = "audit_worm_error"


class AuditSignatureError(AuditError):
    code = "audit_signature_error"


class AuditChainError(AuditError):
    code = "audit_chain_error"


class AuditIndexError(AuditError):
    code = "audit_index_error"


class AuditTimestampError(AuditError):
    code = "audit_timestamp_error"


class AuditVerificationError(AuditError):
    code = "audit_verification_error"
