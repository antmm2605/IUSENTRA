"""Facciata compatibile per le guardie legali di Lex.

Il modulo reale vive in ``lex.guards.legal_reference_guard``.
"""

from lex.guards.legal_reference_guard import (
    build_case_law_guard_prompt,
    build_unverified_pdf_reply,
    collect_verified_legal_references,
    has_verified_legal_reference,
    has_verified_pdf_reference,
    is_case_law_lookup,
    is_pdf_download_request,
)

__all__ = [
    "build_case_law_guard_prompt",
    "build_unverified_pdf_reply",
    "collect_verified_legal_references",
    "has_verified_legal_reference",
    "has_verified_pdf_reference",
    "is_case_law_lookup",
    "is_pdf_download_request",
]
