"""Indicizzazione nativa del solo documento salvato nell'editor."""
from __future__ import annotations

from flask import current_app


def indicizza_salvataggio_editor(*, id_fasc: str, document_id: str, filename: str, content: bytes) -> None:
    try:
        from pct.document_intelligence.sources import source_from_uploaded_document
        from web.services.document_intelligence_runtime import (
            build_document_ai_service,
            document_ai_tenant_id,
            document_ai_user_context,
        )

        tenant_id = document_ai_tenant_id()
        source = source_from_uploaded_document(
            tenant_id=tenant_id,
            fascicolo_id=id_fasc,
            document_id=document_id,
            filename=filename,
            content=content,
            source_type="editor_professionale",
            metadata={"trigger": "editor_salva"},
        )
        build_document_ai_service().process_lex_indexing_sources(
            tenant_id,
            id_fasc,
            [source],
            document_ai_user_context(),
            retry_errors=True,
        )
    except Exception as exc:
        current_app.logger.warning("Indicizzazione Lex editor non completata per %s/%s: %s", id_fasc, filename, exc)
