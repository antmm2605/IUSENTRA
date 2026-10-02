"""Link originali associati da SQL alla precisa copia PDF/A visualizzata."""
import hashlib
import io

from flask import current_app


def original_link_layers(display_bytes, fascicolo_id, document_id):
    """Non cambia un byte del PDF/A: riusa solo provenienze e impronte esatte."""
    from pct.document_intelligence.security import safe_join_under_root
    from web.services.document_intelligence_runtime import build_document_ai_service, document_ai_tenant_id, document_ai_user_context
    from web.services.pdf_reader_links import page_links
    import pdfplumber

    display_hash = hashlib.sha256(display_bytes).hexdigest()
    try:
        tenant = document_ai_tenant_id()
        context = document_ai_user_context()
        service = build_document_ai_service()
        repository = service.repository
        assignments = repository.list_reader_source_assignments(tenant, fascicolo_id, document_id)
        for assignment in assignments:
            if assignment.document_id != document_id or assignment.metadata.get('source_display_sha256') != display_hash:
                continue
            if not assignment.document_ai_id or not assignment.document_version_id or assignment.document_sha256 == display_hash:
                continue
            service.get_fascicolo_document(tenant, fascicolo_id, assignment.document_ai_id, context)
            version = repository.get_version(tenant, fascicolo_id, assignment.document_ai_id, assignment.document_version_id)
            if not version or version.sha256 != assignment.document_sha256:
                continue
            path = safe_join_under_root(repository.storage_root, version.storage_path)
            if path.stat().st_size > 40_000_000:
                continue
            source = path.read_bytes()
            if hashlib.sha256(source).hexdigest() != version.sha256 or not source.startswith(b'%PDF'):
                continue
            with pdfplumber.open(io.BytesIO(display_bytes)) as shown, pdfplumber.open(io.BytesIO(source)) as original:
                if len(shown.pages) != len(original.pages):
                    continue
                layers = []
                for page, source_page in zip(shown.pages, original.pages):
                    if abs(page.width - source_page.width) > .1 or abs(page.height - source_page.height) > .1:
                        raise ValueError('Geometria del documento originale diversa dalla copia visualizzata.')
                    layers.append(page_links(source_page, original))
                return layers
    except Exception as exc:
        current_app.logger.warning('Link originali non riassociati: %s', type(exc).__name__)
    return None
