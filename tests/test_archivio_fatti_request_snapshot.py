"""Snapshot consultivo limitato alla richiesta e senza dati obsoleti."""
from types import SimpleNamespace
import os
import pytest

from flask import Flask, g

from pct.registro_letture import RegistroLetture, Oggetto, Fatto
from web.services import registro_letture_runtime as runtime
from web.services.archivio_fatti_precaricati import istantanea_dettaglio, fatti_precaricati


def test_profili_storage_riusano_ancore_alternate_solo_nella_richiesta(tmp_path, monkeypatch):
    from web.services import storage_runtime as storage
    app = Flask(__name__)
    app.config['STORAGE_MODE_DEFAULT'] = 'SQLITE'
    original = storage.resolve_storage_runtime
    calls = []
    def resolve(**kwargs):
        calls.append(kwargs['anchor_path'])
        return original(**kwargs)
    monkeypatch.setattr(storage, 'resolve_storage_runtime', resolve)
    first_path = str(tmp_path / 'clienti' / 'anagrafica.json')
    second_path = str(tmp_path / 'fascicoli' / 'fascicoli.json')
    with app.test_request_context('/'):
        class TenantWithFreshConfig:
            slug = 'studio'
            @property
            def database(self):
                return SimpleNamespace(mode='SQLITE')
        g.tenant = TenantWithFreshConfig()
        first = storage.get_request_storage_runtime(first_path)
        second = storage.get_request_storage_runtime(second_path)
        assert storage.get_request_storage_runtime(first_path) is first
        assert g._storage_runtime_profile is first
        assert storage.get_request_storage_runtime(second_path) is second
        assert g._storage_runtime_profile is second
        assert first.data_anchor_path != second.data_anchor_path
    with app.test_request_context('/'):
        assert storage.get_request_storage_runtime(first_path) is not first
    assert len(calls) == 3


def test_profili_storage_invalidano_modalita_tenant_e_connessione(tmp_path):
    from web.services import storage_runtime as storage
    app = Flask(__name__)
    app.config['STORAGE_MODE_DEFAULT'] = 'SQLITE'
    anchor = str(tmp_path / 'fascicoli' / 'fascicoli.json')
    with app.test_request_context('/'):
        sqlite = storage.get_request_storage_runtime(anchor)
        app.config['STORAGE_MODE_DEFAULT'] = 'JSON'
        assert storage.get_request_storage_runtime(anchor).effective_mode == storage.DbMode.JSON
        database = SimpleNamespace(mode='POSTGRESQL', connessione_ok=False, core_runtime_enabled=True)
        g.tenant = SimpleNamespace(slug='prima', database=database)
        staging = storage.get_request_storage_runtime(anchor)
        assert staging.effective_mode == storage.DbMode.SQLITE
        database.connessione_ok = True
        postgres = storage.get_request_storage_runtime(anchor)
        assert postgres.effective_mode == storage.DbMode.POSTGRESQL
        g.tenant = SimpleNamespace(slug='seconda', database=database)
        second = storage.get_request_storage_runtime(anchor)
        assert second is not postgres and second.tenant_slug == 'seconda'
        database.mode = 'JSON'
        assert storage.get_request_storage_runtime(anchor).effective_mode == storage.DbMode.JSON
        assert sqlite.uses_sqlite and staging.uses_sqlite


def test_profili_storage_risolvono_di_nuovo_il_collegamento_fisico(tmp_path):
    from web.services import storage_runtime as storage
    app = Flask(__name__)
    app.config['STORAGE_MODE_DEFAULT'] = 'SQLITE'
    first_root = tmp_path / 'prima'
    second_root = tmp_path / 'seconda'
    first_root.mkdir()
    second_root.mkdir()
    link = tmp_path / 'corrente'
    link.symlink_to(first_root, target_is_directory=True)
    anchor = str(link / 'fascicoli' / 'fascicoli.json')
    with app.test_request_context('/'):
        first = storage.get_request_storage_runtime(anchor)
        link.unlink()
        link.symlink_to(second_root, target_is_directory=True)
        second = storage.get_request_storage_runtime(anchor)
        assert second is not first
        assert first.studio_db_path != second.studio_db_path
        assert second.data_anchor_path.startswith(str(second_root))


@pytest.mark.parametrize('field,value', [('db_name', 'seconda'), ('host', 'altro'),
                                       ('utente', 'secondo'), ('password', 'altra sintetica'),
                                       ('porta_effettiva', 5433), ('ssl', True)])
def test_backend_storage_non_riusa_connessione_dopo_cambio_configurazione(tmp_path, monkeypatch, field, value):
    from web.services import storage_runtime as storage
    app = Flask(__name__)
    database = SimpleNamespace(mode='POSTGRESQL', connessione_ok=True,
                               core_runtime_enabled=True, db_name='prima', host='localhost',
                               utente='studio', password='sintetica', porta_effettiva=5432, ssl=False)
    created = []
    def backend(_anchor, _profile):
        value = SimpleNamespace(backend_kind='postgresql', owner=database.db_name)
        created.append(value)
        return value
    monkeypatch.setattr(storage, '_postgres_runtime_backend', backend)
    with app.test_request_context('/'):
        g.tenant = SimpleNamespace(slug='studio', database=database)
        anchor = str(tmp_path / 'fascicoli' / 'fascicoli.json')
        first = storage.get_request_studio_db(anchor)
        assert storage.get_request_studio_db(anchor) is first
        setattr(database, field, value)
        second = storage.get_request_studio_db(anchor)
        assert second is not first and second.owner == database.db_name
        assert storage.get_request_studio_db(anchor) is second
    assert len(created) == 2


def test_link_pubblico_azzera_anche_le_nuove_cache_dello_studio():
    from web.services.token_pubblici_tenant import _imposta_studio
    app = Flask(__name__)
    with app.test_request_context('/'):
        g._storage_runtime_profiles = {'precedente': object()}
        g._runtime_studio_db_key = ('precedente',)
        _imposta_studio(SimpleNamespace(slug='seconda'), {'FASCICOLI_DB': '/seconda/fascicoli.json'})
        assert '_storage_runtime_profiles' not in g
        assert '_runtime_studio_db_key' not in g
        assert g.tenant.slug == 'seconda'


def test_rinomina_con_impronta_identica_non_avvia_motori(snapshot_registry, monkeypatch):
    registry = snapshot_registry
    source = Oggetto(tipo='documento', oggetto_id='D1', nome='prima.pdf', sha256='a' * 64,
                     sha256_archivio='b' * 64, cliente='Anna Bianchi', numero_rg='77', anno_rg='2026')
    other = Oggetto(tipo='documento', oggetto_id='D2', nome='altro.pdf', sha256='c' * 64)
    registry.registra_inventario('studio', 'F1', [source, other])
    registry.registra_fatti('studio', 'F1', source, 'documenti', [
        Fatto(categoria='importo', campo='liquidazione_giudice', valore='1300', verifica='verificata')])
    facts_before = registry.fatti('studio', 'F1')
    monkeypatch.setattr(runtime, 'registro_corrente', lambda: registry)
    monkeypatch.setattr(runtime, 'tenant_corrente', lambda: 'studio')
    def forbidden(*_):
        raise AssertionError('La sola rinomina non deve caricare inventari o avviare lettori')
    monkeypatch.setattr(runtime, '_fascicolo', forbidden)
    monkeypatch.setattr(runtime, '_lettura_dopo_evento', forbidden)
    invalidated = []
    monkeypatch.setattr(runtime, 'invalida_lettura', invalidated.append)
    document = SimpleNamespace(id='D1', nome='dopo.pdf', hash_sha256='b' * 64)
    for _ in range(2):
        runtime.documento_aggiornato('F1', document, solo_nome=True)
    saved = registry.oggetto('studio', 'F1', 'documento', 'D1')
    assert saved.nome == 'dopo.pdf'
    assert (saved.sha256, saved.sha256_archivio, saved.cliente, saved.numero_rg, saved.anno_rg) == (
        source.sha256, source.sha256_archivio, source.cliente, source.numero_rg, source.anno_rg)
    assert registry.oggetto('studio', 'F1', 'documento', 'D2') == other
    assert registry.fatti('studio', 'F1') == facts_before
    assert registry.oggetti('altro-studio', 'F1') == []
    assert invalidated == ['F1', 'F1']


@pytest.mark.parametrize('stored_hash', ['', 'c' * 64])
def test_rinomina_senza_prova_della_stessa_fonte_conserva_recupero(snapshot_registry, monkeypatch, stored_hash):
    registry = snapshot_registry
    registry.registra_inventario('studio', 'F1', [
        Oggetto(tipo='documento', oggetto_id='D1', sha256_archivio='b' * 64)])
    monkeypatch.setattr(runtime, 'registro_corrente', lambda: registry)
    monkeypatch.setattr(runtime, 'tenant_corrente', lambda: 'studio')
    monkeypatch.setattr(runtime, '_fascicolo', lambda _: SimpleNamespace(id='F1'))
    recovered = []
    monkeypatch.setattr(runtime, 'aggiorna_inventario', lambda *_, **__: recovered.append('inventario'))
    monkeypatch.setattr(runtime, '_lettura_dopo_evento', lambda _: recovered.append('lettori'))
    monkeypatch.setattr(runtime, 'invalida_lettura', lambda _: None)
    runtime.documento_aggiornato('F1', SimpleNamespace(id='D1', nome='dopo.pdf', hash_sha256=stored_hash), solo_nome=True)
    assert recovered == ['inventario', 'lettori']


def test_repository_richiesta_separa_studio_percorso_e_modalita(tmp_path, monkeypatch):
    app = Flask(__name__)
    made = []
    def factory(path, **options):
        made.append((path, options))
        return SimpleNamespace(path=path, options=options)
    monkeypatch.setattr(runtime, 'RegistroLetture', factory)
    monkeypatch.setattr(runtime, '_dsn_postgres', lambda: '')
    monkeypatch.setattr(runtime, 'tenant_corrente', lambda: g.studio)
    with app.test_request_context('/detail'):
        g.studio = 'a'; g.data_paths = {'REGISTRO_LETTURE_DB': str(tmp_path / 'a.db')}
        first = runtime.registro_corrente()
        assert runtime.registro_corrente() is first
        assert runtime.registro_corrente(sola_lettura=True) is not first
        g.studio = 'b'
        assert runtime.registro_corrente() is not first
        g.data_paths['REGISTRO_LETTURE_DB'] = str(tmp_path / 'b.db')
        assert runtime.registro_corrente().path.endswith('b.db')
    with app.test_request_context('/detail'):
        g.studio = 'a'; g.data_paths = {'REGISTRO_LETTURE_DB': str(tmp_path / 'a.db')}
        assert runtime.registro_corrente() is not first
    assert len(made) == 5


@pytest.fixture(params=['sqlite', 'postgresql'])
def snapshot_registry(tmp_path, request):
    from tests.test_condivisioni_sql_repository import SQLFactory
    if request.param == 'postgresql' and not os.environ.get('AUDIT_POSTGRES_PASSWORD'):
        pytest.skip('Database PostgreSQL controllato non configurato')
    factory = SQLFactory(request.param)
    registry = None
    try:
        dsn = ''
        if request.param == 'postgresql':
            from psycopg2.extensions import make_dsn
            dsn = make_dsn(**factory.pg_parameters, options=f'-c search_path={factory.schema}')
        registry = RegistroLetture(tmp_path / 'facts.db', postgres_dsn=dsn)
        yield registry
    finally:
        if registry is not None:
            registry.close()
        factory.close()


def test_snapshot_sql_filtri_identici_e_aggiornamento_successivo(snapshot_registry, monkeypatch):
    app = Flask(__name__)
    registry = snapshot_registry
    source = Oggetto(tipo='documento', oggetto_id='D1', sha256='a' * 64)
    registry.registra_inventario('a', 'F1', [source])
    registry.registra_fatti('a', 'F1', source, 'documenti', [
        Fatto(categoria='importo', campo='liquidazione_giudice', valore='1300', verifica='verificata'),
        Fatto(categoria='data', campo='udienza', valore='2026-10-14', verifica='plausibile')])
    monkeypatch.setattr(runtime, 'registro_corrente', lambda: registry)
    monkeypatch.setattr(runtime, 'tenant_corrente', lambda: g.studio)
    monkeypatch.setattr(runtime, 'percorso_registro', lambda: g.path)
    repo = SimpleNamespace(get=lambda _: SimpleNamespace(id='F1'))
    @istantanea_dettaglio
    def projection(**_):
        for filters in ({}, {'categoria': 'importo'}, {'campo': 'udienza'},
                        {'motore': 'documenti', 'verifiche': None}, {'tipo': 'documento'}):
            assert fatti_precaricati('F1', filters, False) == registry.fatti('a', 'F1', **filters)
        result = fatti_precaricati('F1', {'categoria': 'importo'}, False)
        result[0].valore = 'alterato'
        assert fatti_precaricati('F1', {'categoria': 'importo'}, False)[0].valore == '1300'
        g.studio = 'b'
        assert fatti_precaricati('F1', {}, False) is None
        g.studio = 'a'; g.path = 'changed'
        assert fatti_precaricati('F1', {}, False) is None
        return True
    with app.test_request_context('/detail'):
        g.studio = 'a'; g.path = 'facts.db'
        assert projection(get_fascicoli=lambda: repo, id_fasc='F1')
        assert fatti_precaricati('F1', {}, False) is None
    assert registry.fatti('a', 'F1', categoria='importo')[0].valore == '1300'


def test_fine_richiesta_chiude_gestore_una_volta():
    from web.services.observability_runtime import register_observability_runtime
    app = Flask(__name__)
    register_observability_runtime(app)
    closed = []
    @app.get('/probe')
    def probe():
        g._registri_letture_richiesta = {'owned': SimpleNamespace(close=lambda: closed.append(True))}
        return 'ok'
    with app.test_client() as client:
        assert client.get('/probe').status_code == 200
        assert len(closed) == 1
        assert client.get('/probe').status_code == 200
        assert len(closed) == 2
    assert len(closed) == 2


def test_elenco_riusa_fatti_grezzi_senza_perdere_filtri_o_decisioni(snapshot_registry, monkeypatch):
    from web.services.archivio_fatti_precaricati import precaricati
    app = Flask(__name__)
    registry = snapshot_registry
    for fid in ('F1', 'F2'):
        source = Oggetto(tipo='documento', oggetto_id=f'D-{fid}', sha256='a' * 64)
        registry.registra_inventario('studio', fid, [source])
        registry.registra_fatti('studio', fid, source, 'documenti', [
            Fatto(categoria='importo', campo='liquidazione_giudice', valore='1300', verifica='verificata'),
            Fatto(categoria='importo', campo='fondo_spese', valore='200', verifica='ignorata')])
    filters = ({'categoria': 'importo'}, {'categoria': 'importo', 'verifiche': None},
               {'categoria': 'importo', 'campo': 'fondo_spese', 'verifiche': None},
               {'categoria': 'importo', 'motore': 'documenti'},
               {'categoria': 'importo', 'tipo': 'documento'})
    expected = {(fid, n): registry.fatti('studio', fid, **flt)
                for fid in ('F1', 'F2') for n, flt in enumerate(filters)}
    from pct.archivio_letture import fatti_canonici
    monkeypatch.setattr(runtime, 'registro_corrente', lambda: registry)
    monkeypatch.setattr(runtime, 'tenant_corrente', lambda: g.studio)
    monkeypatch.setattr(runtime, 'percorso_registro', lambda: g.path)
    def unexpected_single_read(*args, **kwargs):
        pytest.fail('Il precarico deve rispondere senza altre interrogazioni per fascicolo')
    monkeypatch.setattr(registry, 'fatti', unexpected_single_read)
    with app.test_request_context('/list'):
        g.studio = 'studio'; g.path = 'facts.db'
        with precaricati([SimpleNamespace(id='F1'), SimpleNamespace(id='F2')], ('importo', 'evento')):
            for fid in ('F1', 'F2'):
                for n, flt in enumerate(filters):
                    assert fatti_precaricati(fid, flt, False) == expected[fid, n]
                    canonical = fatti_canonici(expected[fid, n]) if not flt.get('motore') and not flt.get('tipo') else expected[fid, n]
                    assert fatti_precaricati(fid, flt, True) == canonical
            values = fatti_precaricati('F1', {'categoria': 'importo'}, False)
            values[0].valore = 'alterato'
            assert fatti_precaricati('F1', {'categoria': 'importo'}, False)[0].valore == '1300'
            assert fatti_precaricati('F3', {'categoria': 'importo'}, False) is None
            assert fatti_precaricati('F1', {'categoria': 'data'}, False) is None
            g.studio = 'altro'
            assert fatti_precaricati('F1', {'categoria': 'importo'}, False) is None
            g.studio = 'studio'; g.path = 'altro.db'
            assert fatti_precaricati('F1', {'categoria': 'importo'}, False) is None
        g.studio = 'studio'
        assert fatti_precaricati('F1', {'categoria': 'importo'}, False) is None


def test_elenco_errore_sql_non_diventa_dato_vuoto_o_raffica_di_letture(monkeypatch):
    from web.services.archivio_fatti_precaricati import precaricati
    app = Flask(__name__)
    calls = []
    def failed(*args, **kwargs):
        calls.append(True)
        raise OSError('Errore sintetico del database')
    monkeypatch.setattr(runtime, 'registro_corrente', lambda: SimpleNamespace(fatti_per_fascicoli=failed))
    monkeypatch.setattr(runtime, 'tenant_corrente', lambda: 'studio')
    monkeypatch.setattr(runtime, 'percorso_registro', lambda: 'facts.db')
    with app.test_request_context('/list'):
        with pytest.raises(RuntimeError, match='Archivio delle letture non disponibile'):
            with precaricati([SimpleNamespace(id='F1')], ('importo',)):
                pytest.fail('Non deve costruire righe da una lettura SQL fallita')
    assert len(calls) == 1


@pytest.mark.parametrize('archive_changed', [False, True])
def test_presidio_non_riscrive_orario_in_attesa_ma_reagisce_a_nuovi_fatti(monkeypatch, archive_changed):
    from web.services import react_fascicoli_bridge as bridge
    marker = {'analysisVersion': bridge.ECONOMIC_DOCUMENT_ANALYSIS_VERSION,
              'economicFactsFingerprint': 'prima', 'updated_at': '2026-10-14T12:00:00Z'}
    case = SimpleNamespace(id='F1', pagamenti={'_presidio_documentale': marker})
    monkeypatch.setattr(bridge, '_payment_source_needs_automatic_value', lambda *args: True)
    monkeypatch.setattr(bridge, '_presidio_documentale_marker_is_current', lambda *args: True)
    monkeypatch.setattr(bridge, '_economic_archive_fingerprint', lambda *args: 'dopo' if archive_changed else 'prima')
    monkeypatch.setattr(bridge, '_presidio_documenti_da_leggere', lambda *args: ['D2', 'D3'])
    monkeypatch.setattr(bridge, '_indicizzazione_consentita_qui', lambda: True)
    class ProjectionReached(Exception):
        pass
    def projection(*args, **kwargs):
        if not archive_changed:
            pytest.fail('Nessun fatto cambiato: non deve ripetere la proiezione economica')
        assert kwargs['force_revalidate_auto'] is True
        raise ProjectionReached()
    monkeypatch.setattr(bridge, '_automatic_payment_sources_for_fascicolo', projection)
    def write(*args, **kwargs):
        pytest.fail('Non deve salvare un semplice stato di attesa invariato')
    repository = SimpleNamespace(aggiorna=write)
    if archive_changed:
        with pytest.raises(ProjectionReached):
            bridge._ensure_contributo_unificato_for_fascicolo(
                fascicoli_repository=repository, fascicolo=case)
    else:
        result = bridge._ensure_contributo_unificato_for_fascicolo(
            fascicoli_repository=repository, fascicolo=case)
        assert result['analysisUpdated'] is False
        assert result['status'] == 'existing'
        assert 'readComplete' not in result and 'documentIds' not in result
        assert case.pagamenti['_presidio_documentale'] == marker


def test_backend_sql_verificato_una_volta_per_richiesta(tmp_path, monkeypatch):
    from web.services import storage_runtime as storage
    app = Flask(__name__)
    app.config['STORAGE_MODE_DEFAULT'] = 'sqlite'
    checked = []
    created = []
    monkeypatch.setattr(storage, '_sqlite_runtime_is_unseeded',
                        lambda path, anchor: checked.append(str(path)) or False)
    monkeypatch.setattr(storage, 'ensure_core_storage_backend_contract', lambda db: db)
    def make(path):
        created.append(path)
        return SimpleNamespace(db_path=path)
    monkeypatch.setattr(storage.StudioDB, 'get', make)
    anchor = str(tmp_path / 'a' / 'clienti' / 'clienti.json')
    with app.test_request_context('/detail'):
        first = storage.get_request_studio_db(anchor)
        assert storage.get_request_studio_db(anchor) is first
        assert storage.get_request_studio_db(str(tmp_path / 'b' / 'clienti' / 'clienti.json')) is not first
    with app.test_request_context('/detail'):
        assert storage.get_request_studio_db(anchor) is not first
    assert len(checked) == len(created) == 3


def test_servizio_documenti_consultivo_non_si_estende_ai_comandi(monkeypatch):
    from web.services import document_intelligence_runtime as docs
    app = Flask(__name__)
    app.add_url_rule('/detail', endpoint='api_v1_react.fascicolo_react_dettaglio', view_func=lambda: '', methods=['GET', 'POST'])
    backend = object()
    made = []
    monkeypatch.setattr(docs, 'fascicoli_db_path', lambda: g.anchor)
    monkeypatch.setattr(docs, 'document_ai_tenant_id', lambda: g.studio)
    monkeypatch.setattr(docs, 'get_request_studio_db', lambda _: backend)
    monkeypatch.setattr(docs, 'get_fascicoli', lambda: object())
    def repository(anchor, **_):
        made.append(anchor)
        return object()
    monkeypatch.setattr(docs.DocumentAIRepository, 'from_fascicoli_db', repository)
    monkeypatch.setattr(docs, 'DocumentAIService', lambda repo, manager, **_: SimpleNamespace(repository=repo))
    with app.test_request_context('/detail'):
        g.anchor = '/a/fascicoli.json'; g.studio = 'a'
        first = docs.build_document_ai_service()
        assert docs.build_document_ai_service() is first
        g.studio = 'b'; g.anchor = '/b/fascicoli.json'
        assert docs.build_document_ai_service() is not first
    with app.test_request_context('/detail', method='POST'):
        g.anchor = '/a/fascicoli.json'; g.studio = 'a'
        assert docs.build_document_ai_service() is not docs.build_document_ai_service()
    with app.test_request_context('/detail'):
        g.anchor = '/a/fascicoli.json'; g.studio = 'a'
        assert docs.build_document_ai_service() is not first
    assert len(made) == 5


def test_backend_postgresql_richiesta_non_riusa_un_altro_tenant(monkeypatch):
    from web.services import storage_runtime as storage
    app = Flask(__name__)
    created = []
    def profile(_):
        return storage.StorageRuntimeProfile(storage.DbMode.POSTGRESQL, storage.DbMode.POSTGRESQL, False,
                                             '/shared/studio.db', '/shared/fascicoli.json', tenant_slug=g.studio)
    def backend(anchor, selected):
        created.append(selected.tenant_slug)
        return SimpleNamespace(backend_kind='postgresql', studio=selected.tenant_slug)
    monkeypatch.setattr(storage, 'get_request_storage_runtime', profile)
    monkeypatch.setattr(storage, '_postgres_runtime_backend', backend)
    with app.test_request_context('/detail'):
        g.studio = 'a'
        first = storage.get_request_studio_db('anchor')
        assert storage.get_request_studio_db('anchor') is first
        g.studio = 'b'
        second = storage.get_request_studio_db('anchor')
        assert second is not first and second.studio == 'b'
    assert created == ['a', 'b']


def test_tempi_ui_coprono_salvataggi_errori_e_header_esistenti():
    from web.services.observability_runtime import register_observability_runtime
    app = Flask(__name__)
    register_observability_runtime(app)
    @app.route('/api/v1/ui/probe', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'])
    def probe():
        from flask import request
        return 'esito', 503 if request.method == 'DELETE' else 200, {'Server-Timing': 'database;dur=1'}
    with app.test_client() as client:
        for method in ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']:
            result = client.open('/api/v1/ui/probe', method=method)
            assert result.status_code == (503 if method == 'DELETE' else 200)
            assert result.data == b'esito'
            assert result.headers['Server-Timing'].startswith('database;dur=1, iusentra;dur=')
