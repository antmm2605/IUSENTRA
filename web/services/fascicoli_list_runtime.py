"""Consultazione primaria paginata, senza inizializzare gestori o cataloghi."""
import json
from pathlib import Path
from contextlib import contextmanager

from flask import current_app, g

from pct.fascicoli import GestioneFascicoli
from pct.fascicoli_list_query import FascicoliListQuery, FascicoliListNotReady, assert_registry_ready
from pct.fatturazione import Parcella
from pct.fascicolo_document_presidio import duplicate_practice_groups
from web.services.document_intelligence_runtime import document_ai_tenant_id
from web.services.fascicoli_list_payload import build_sql_list_payload
from web.services.registro_letture_runtime import registro_corrente, registro_consultivo, connessione_registro
from web.services.studio_readonly import request_studio_reader, borrowed_studio_backend
from web.services.tenant_paths import tenant_data_path


def catalog_exists(conn, table, *, postgres=False):
    if table not in {'fascicoli_list_owner', 'fascicoli_list_registry_owner', 'fascicoli_list_clock'}:
        raise ValueError('Catalogo non previsto.')
    sql = ('SELECT 1 FROM information_schema.tables WHERE table_schema=current_schema() AND table_name=?'
           if postgres else "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?")
    return conn.execute(sql, (table,)).fetchone() is not None


def registry_ready(tenant):
    try:
        registry = registro_corrente(sola_lettura=True)
    except FileNotFoundError as exc:
        raise FascicoliListNotReady('Catalogo delle fonti non preparato: recupero governato necessario.') from exc
    with connessione_registro(registry) as conn:
        if not catalog_exists(conn, 'fascicoli_list_registry_owner', postgres=registry.backend_kind == 'postgres'):
            raise FascicoliListNotReady('Catalogo delle fonti non preparato: recupero governato necessario.')
        assert_registry_ready(conn, tenant)


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
    from web.services.react_fascicoli_bridge import enrich_economic_list_items
    keys = {item['id'] for item in items}
    placeholders = ','.join('?' for _ in keys)
    duplicate_keys = [row[0] for row in database.conn.execute('SELECT DISTINCT duplicate_key '
        'FROM fascicoli_list_identity WHERE tenant_key=? AND record_key IN (' + placeholders + ") AND duplicate_key<>''",
        (tenant, *sorted(keys))).fetchall()]
    for duplicate_key in duplicate_keys:
        keys.update(str(row[0]) for row in database.conn.execute('SELECT record_key FROM fascicoli_list_identity '
            'WHERE tenant_key=? AND archived=0 AND duplicate_key=?', (tenant, duplicate_key)).fetchall())
    native = native_list_repository(database, anchor)
    ordered_keys = sorted(keys)
    models = []
    for start in range(0, len(ordered_keys), 100):
        models.extend(native.elenco_per_ids(ordered_keys[start:start + 100]))
    models.sort(key=lambda value: value.numero, reverse=True)
    invoices = {}
    for start in range(0, len(ordered_keys), 100):
        block = ordered_keys[start:start + 100]
        rows = database.conn.execute('SELECT id,id_fascicolo,dati_json FROM parcelle WHERE id_fascicolo IN ('
            + ','.join('?' for _ in block) + ')', tuple(block)).fetchall()
        for row in rows:
            invoice = Parcella.from_dict(json.loads(row['dati_json']))
            if invoice.id != row['id'] or invoice.id_fascicolo != row['id_fascicolo']:
                raise FascicoliListNotReady('Collegamento della parcella da riallineare alla fonte SQL.')
            invoices.setdefault(invoice.id_fascicolo, []).append(invoice)
    groups = {value['key']: value for value in duplicate_practice_groups(models)}
    missing = object()
    names = ('_fascicoli', '_fascicoli_elenco', '_fascicoli_mirato')
    previous = {name: getattr(g, name, missing) for name in names}
    for name in names:
        setattr(g, name, native)
    try:
        with borrowed_studio_backend(database, anchor), registro_consultivo():
            return enrich_economic_list_items(items, gf=native, fascicoli_for_summary=models,
                duplicate_groups_by_key=groups, parcelle_by_fasc=invoices)
    finally:
        for name, value in previous.items():
            if value is missing:
                g.pop(name, None)
            else:
                setattr(g, name, value)


def build_fascicoli_list_request(**params):
    anchor = tenant_data_path('FASCICOLI_DB', current_app.config.get('FASCICOLI_DB', ''), require_tenant=True)
    tenant = document_ai_tenant_id()
    with request_studio_reader(anchor) as database:
        postgres = getattr(database, 'backend_kind', '') == 'postgresql'
        registry_ready(tenant)
        repository = FascicoliListQuery(database, tenant)
        with catalog_snapshot(database):
            if not catalog_exists(database.conn, 'fascicoli_list_owner', postgres=postgres):
                raise FascicoliListNotReady('Catalogo fascicoli non preparato: recupero governato necessario.')
            payload = build_sql_list_payload(repository,
                enrich_economic=lambda items: enrich_economic_page(database, tenant, anchor, items), **params)
        repository._ready()
        registry_ready(tenant)
        return payload
