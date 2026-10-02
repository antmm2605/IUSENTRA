"""Fonti PEC correlate: identificativi audit e allegati propri di ciascuna PEC."""
from urllib.parse import quote


def correlated_sources(repo, row):
    with repo.connection() as conn:
        duplicates = [dict(r) for r in conn.execute(
            'SELECT id,source_message_id,source_effective_at FROM pec_legal_notification_presidia WHERE tenant_id=? AND fascicolo_id=? AND resolution_code=? ORDER BY source_effective_at,id',
            (repo.tenant_id, row['fascicolo_id'], 'DUPLICATE_OF:' + row['id'])).fetchall()]
        rows = [row, *duplicates]
        result = []
        for source in rows:
            document = conn.execute(
                "SELECT original_filename FROM pec_legal_notification_documents WHERE tenant_id=? AND presidio_id=? AND document_role='office_pec_copy' AND original_filename<>'' ORDER BY created_at,id LIMIT 1",
                (repo.tenant_id, source['id'])).fetchone()
            name = str(document['original_filename']) if document else ''
            message = str(source.get('source_message_id') or '')
            result.append({'id': source['id'], 'received_at': source.get('source_effective_at'),
                'name': name, 'href': f'/api/v1/ui/email/source/{quote(message, safe="")}?name={quote(name, safe="")}' if name and message else ''})
    return result
