"""Compatibilita': la regola firma vive nel dominio pct."""

from pct.document_signature_state import (  # noqa: F401
    SIGNED_CONTAINER_SUFFIXES,
    document_has_real_digital_signature,
    document_has_signed_container,
    is_signed_container_name,
)
