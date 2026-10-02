"""Indicizzazione Lex di un documento appena entrato nel fascicolo.

Il wiring delle rotte non deve contenere la regia dell'indicizzazione: qui la
stessa funzione serve il caricamento manuale e l'import dai portali, in modo
bloccante o in sfondo secondo chi la chiama.
"""

from __future__ import annotations

import threading
from typing import Any

from flask import g, has_request_context

from pct.document_intelligence.sources import source_from_uploaded_document


def indicizza_documento_lex(
    app: Any,
    *,
    id_fasc: str,
    document_id: str,
    filename: str,
    content: bytes,
    source_type: str,
    metadata: dict[str, Any] | None = None,
    blocking: bool = True,
) -> None:
    try:
        from web.services.document_intelligence_runtime import (
            build_document_ai_service,
            document_ai_tenant_id,
            document_ai_user_context,
        )
        tenant_id = document_ai_tenant_id()
        user_context = document_ai_user_context()
        app_obj = app._get_current_object() if hasattr(app, "_get_current_object") else app
        # Copiare solo il contesto autenticato, mai connessioni SQL o cache di g.
        # Un nuovo app_context perdeva i percorsi e leggeva l'archivio globale.
        context_keys = (
            "tenant", "tenant_context_slug", "tenant_context_required",
            "tenant_context_missing", "multi_tenant_enabled", "utente_corrente",
            "api_tenant_authenticated", "api_tenant_slug",
        )
        request_context = {
            key: getattr(g, key) for key in context_keys if hasattr(g, key)
        } if has_request_context() else {}
        paths = dict(getattr(g, "data_paths", {}) or {}) if has_request_context() else {}
        if app_obj.config.get("MULTI_TENANT") and (not paths or not request_context.get("tenant")):
            raise RuntimeError("Contesto studio non disponibile per l’indicizzazione.")

        def _process() -> None:
            try:
                with app_obj.test_request_context("/__internal/lex-index-document"):
                    for key, value in request_context.items():
                        setattr(g, key, value)
                    g.data_paths = dict(paths)
                    if document_ai_tenant_id() != tenant_id:
                        raise RuntimeError("Contesto studio non coerente per l’indicizzazione.")
                    source = source_from_uploaded_document(
                        tenant_id=tenant_id,
                        fascicolo_id=id_fasc,
                        document_id=document_id,
                        filename=filename,
                        content=content,
                        source_type=source_type,
                        metadata=metadata or {},
                    )
                    service = build_document_ai_service()
                    result = service.process_lex_indexing_sources(
                        tenant_id,
                        id_fasc,
                        [source],
                        user_context,
                        retry_errors=True,
                    )
                    for error in result.errors:
                        app_obj.logger.warning("Indicizzazione Lex: %s", error)
            except Exception as exc:
                app.logger.warning("Indicizzazione Lex non completata per %s/%s: %s", id_fasc, filename, exc)

        if blocking:
            _process()
        else:
            threading.Thread(
                target=_process,
                name=f"lex-index-document-{id_fasc}-{document_id}",
                daemon=True,
            ).start()
    except Exception as exc:
        app.logger.warning("Indicizzazione Lex non completata per %s/%s: %s", id_fasc, filename, exc)


__all__ = ["indicizza_documento_lex"]
