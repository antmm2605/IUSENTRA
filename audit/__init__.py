"""Legal-grade append-only audit evidence for IUSENTRA.

The package keeps the legal evidence in immutable WORM objects. Database
tables are indexes only and can be rebuilt from the WORM source of truth.
"""

from .models import AuditEmitResult, AuditVerificationResult
from .schemas import ActorContext, AuditFileRef, AuditKind, SourceContext
from .service import AuditService, emit_event

__all__ = [
    "ActorContext",
    "AuditEmitResult",
    "AuditFileRef",
    "AuditKind",
    "AuditService",
    "AuditVerificationResult",
    "SourceContext",
    "emit_event",
]
