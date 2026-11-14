"""Consultazione primaria paginata, senza inizializzare gestori o cataloghi."""
from pathlib import Path
from contextlib import contextmanager

from flask import current_app

from pct.fascicoli import GestioneFascicoli
from pct.fascicoli_list_query import FascicoliListQuery, FascicoliListNotReady, assert_registry_ready
from web.services.document_intelligence_runtime import document_ai_tenant_id
from web.services.fascicoli_list_payload import build_sql_list_payload
from web.services.registro_letture_runtime import registro_corrente, connessione_registro
from web.services.studio_readonly import request_studio_reader
from web.services.tenant_paths import tenant_data_path


def catalog_exists(conn, table, *, postgres=False):
    if table not in {'fascicoli_list_owner', 'fascicoli_list_registry_owner', 'fascicoli_list_clock'}:
        raise ValueError('Catalogo non previsto.')
    sql = ('SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?'
           if postgres else "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?")
    return conn.execute(sql, (table,)).fetchone() is not None


def registry_ready(tenant, *, in_corso_ammessi=False):
    try:
        registry = registro_corrente(sola_lettura=True)
    except FileNotFoundError as exc:
        raise FascicoliListNotReady('Catalogo delle fonti non preparato: recupero governato necessario.') from exc
    with connessione_registro(registry) as conn:
        if not catalog_exists(conn, 'fascicoli_list_registry_owner', postgres=registry.backend_kind == 'postgres'):
            raise FascicoliListNotReady('Catalogo delle fonti non preparato: recupero governato necessario.')
        return assert_registry_ready(conn, tenant, in_corso_ammessi=in_corso_ammessi)


def native_list_repository(database, anchor):
    return GestioneFascicoli(anchor,
        documents_dir=tenant_data_path('FASCICOLI_DOCS', current_app.config.get('FASCICOLI_DOCS')
            or str(Path(anchor).parent / 'documenti'), require_tenant=True),
        archive_dir=tenant_data_path('FASCICOLI_ARCH', current_app.config.get('FASCICOLI_ARCH')
            or str(Path(anchor).parent / 'archivio'), require_tenant=True),
        studio_db=database, carica_tutto=False, senza_documenti=True, prepara_cartelle=False)


@contextmanager
def catalog_snapshot(database):
    """Pagina e conteggi provengono dalla stessa istantanea consultiva."""
    if not getattr(database, '_readonly_only', False):
        raise RuntimeError('La pagina richiede una connessione SQL consultiva.')
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    target = database.raw_conn if postgres else database.conn
    if postgres:
        target.set_session(readonly=True, isolation_level='REPEATABLE READ')
    else:
        target.execute('BEGIN')
    try:
        before = database.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()
        if before is None:
            raise FascicoliListNotReady('Revisione del catalogo non preparata.')
        yield
    finally:
        target.rollback()
    after = database.conn.execute("SELECT revision FROM operational_live_revisions WHERE domain='fascicoli'").fetchone()
    if before is None or after is None or before[0] != after[0]:
        raise FascicoliListNotReady('I fascicoli sono cambiati durante il caricamento: aggiornamento necessario.')


def enrich_economic_page(database, tenant, anchor, items):
    """Vista economica: le righe salvate dal writer, senza ricalcolo.

    Riepilogo economico e prossima scadenza sono decisi una sola volta, dal writer della riga
    (``FascicoliListWriter.project_case``), con lo stesso motore e le stesse fonti (doppioni compresi) per la
    vista operativa e per quella economica: due controllori per lo stesso dato davano risultati difformi.
    """
    del database, tenant, anchor
    return items


def build_fascicoli_list_request(**params):
    anchor = tenant_data_path('FASCICOLI_DB', current_app.config.get('FASCICOLI_DB', ''), require_tenant=True)
    tenant = document_ai_tenant_id()
    with request_studio_reader(anchor) as database:
        postgres = getattr(database, 'backend_kind', '') == 'postgresql'
        in_aggiornamento = set(registry_ready(tenant, in_corso_ammessi=True))
        repository = FascicoliListQuery(database, tenant)
        repository.in_corso_ammessi = True
        with catalog_snapshot(database):
            if not catalog_exists(database.conn, 'fascicoli_list_owner', postgres=postgres):
                raise FascicoliListNotReady('Catalogo fascicoli non preparato: recupero governato necessario.')
            payload = build_sql_list_payload(repository,
                enrich_economic=lambda items: enrich_economic_page(database, tenant, anchor, items), **params)
        repository._ready()
        in_aggiornamento |= repository.in_aggiornamento
        in_aggiornamento |= set(registry_ready(tenant, in_corso_ammessi=True))
        return segna_in_aggiornamento(payload, in_aggiornamento)


def segna_in_aggiornamento(payload, in_aggiornamento):
    """Le righe con un aggiornamento puntuale ancora in corso sono dichiarate, non nascoste."""
    for item in payload.get('items') or []:
        if isinstance(item, dict) and str(item.get('id') or '') in in_aggiornamento:
            item['refreshPending'] = True
    payload['refreshPending'] = {'count': len(in_aggiornamento),
                                 'onPage': sum(1 for item in payload.get('items') or [] if isinstance(item, dict) and item.get('refreshPending'))}
    return payload
