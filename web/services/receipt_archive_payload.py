"""DTO delle prove archiviate: collegamenti nativi, senza effetti legali."""
from urllib.parse import quote

from pct.registro_letture.ricevute_query import ReceiptArchiveQuery
from web.services.registro_letture_runtime import connessione_registro, registro_corrente, tenant_corrente


def archived_receipt_page(*, tenant, ranges=(), kind='', limit=20, cursor=None):
    if tenant != tenant_corrente():
        raise PermissionError('Studio discordante per le prove archiviate.')
    registry = registro_corrente(sola_lettura=True)
    with connessione_registro(registry) as conn:
        page = ReceiptArchiveQuery(conn, tenant).list_page(ranges=ranges, kind=kind, limit=limit, cursor=cursor)
    for row in page['rows']:
        links = []
        for source in row['sources']:
            if source['tipo'] == 'documento':
                href = '/fascicoli/' + quote(row['fascicolo_id'], safe='') + '/documenti/' + quote(source['oggetto_id'], safe='') + '/visualizza'
            elif source['tipo'] == 'pec':
                from web.services.pec_source_links import pec_source_href
                href = pec_source_href(source['oggetto_id'], '')
            else:
                href = '/fascicoli/' + quote(row['fascicolo_id'], safe='') + '#documenti'
            links.append(dict(id=source['id'], title=source['nome'], href=href,
                              source_sha256=source['sha256'], source_type=source['tipo']))
        row.update(tenant_id=tenant, titolo=row['title'], data=row['event_at'],
                   stato='Prova di trasporto archiviata', action_url=links[0]['href'], evidence_sources=links)
    return page
