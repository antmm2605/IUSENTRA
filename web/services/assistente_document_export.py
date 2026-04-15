"""Facciata compatibile per l'export documentale di Lex.

Il modulo reale vive in ``lex.formatting.document_export``.
"""

from lex.formatting.document_export import (
    build_docx_bytes,
    build_export_filename,
    format_dataora_italiana,
    infer_export_title,
    sanitize_export_title,
)

__all__ = [
    "build_docx_bytes",
    "build_export_filename",
    "format_dataora_italiana",
    "infer_export_title",
    "sanitize_export_title",
]
