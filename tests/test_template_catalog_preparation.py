"""Adozione puntuale con originali preservati e consultazioni senza migrazioni."""
import json

import pytest

from pct.template_atti import GestioneTemplateAtti
from pct.template_atti_preparation import catalog_ready, prepare_catalog
from pct.template_atti_repository import GestioneTemplateRepository, derive_template_repository_db_path


def test_catalogo_assente_non_crea_file_e_richiede_scrittori_fermi(tmp_path):
    source = tmp_path / 'templates.json'
    assert not catalog_ready(source)
    with pytest.raises(RuntimeError, match='scrittori'):
        prepare_catalog(source, backup_dir=tmp_path / 'backup')
    assert list(tmp_path.iterdir()) == []


def test_preparazione_conserva_originale_stile_metadati_e_riapertura(tmp_path):
    source = tmp_path / 'templates.json'
    payload = {'personal': dict(id='personal', titolo='È personale', categoria='Civile',
        corpo='<p style="font-size:14pt"><strong>Cliente</strong></p>',
        creato_il='2026-10-10T09:10:00', modificato_il='2026-10-11T10:15:00',
        extra={'font': 'Times New Roman', 'interlinea': 1.5})}
    original = json.dumps(payload, ensure_ascii=False).encode()
    source.write_bytes(original)
    # Archivio SQL già presente, ma non ancora adottato come fonte primaria.
    repository = GestioneTemplateRepository(derive_template_repository_db_path(str(source)))
    assert repository.read_runtime_snapshot() == ([], None)
    result = prepare_catalog(source, backup_dir=tmp_path / 'backup', writers_drained=True)
    assert result['changed']
    assert (tmp_path / 'backup' / 'templates-original.json').read_bytes() == original
    assert (tmp_path / 'backup' / 'sql' / 'manifest.json').is_file()
    assert catalog_ready(source)
    stored, revision = repository.read_runtime_snapshot()
    assert stored[0]['extra'] == payload['personal']['extra']
    assert stored[0]['corpo'] == payload['personal']['corpo']
    assert stored[0]['creato_il'] == payload['personal']['creato_il']
    reader = GestioneTemplateAtti(str(source), read_only=True, postgres_dsn='')
    assert reader.get('personal').corpo == payload['personal']['corpo']
    assert prepare_catalog(source, backup_dir=tmp_path / 'backup') == dict(changed=False)
    assert repository.read_runtime_snapshot()[1] == revision


def test_originale_non_valido_non_viene_sostituito(tmp_path):
    source = tmp_path / 'templates.json'
    source.write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError, match='storico'):
        prepare_catalog(source, backup_dir=tmp_path / 'backup', writers_drained=True)
    assert source.read_text() == '[]'
    assert not catalog_ready(source)


def test_nuovo_studio_ha_catalogo_pronto_e_isolato(tmp_path):
    from pct.tenant import GestioneTenant

    registry = GestioneTenant(str(tmp_path / 'tenants.json'))
    first = registry.crea('Studio controllato uno', 'controlled-one')
    second = registry.crea('Studio controllato due', 'controlled-two')
    paths = [registry.percorsi_dati(item.slug, ensure_baseline=False, reconcile_aliases=False)
             for item in (first, second)]
    assert paths[0]['TEMPLATE_ATTI_DB'] != paths[1]['TEMPLATE_ATTI_DB']
    assert all(catalog_ready(item['TEMPLATE_ATTI_DB']) for item in paths)
    manager = GestioneTemplateAtti(paths[0]['TEMPLATE_ATTI_DB'], postgres_dsn='')
    custom = manager.crea('Solo primo studio', 'Civile', '<p>Controllato</p>')
    other = GestioneTemplateAtti(paths[1]['TEMPLATE_ATTI_DB'], postgres_dsn='', read_only=True)
    assert other.get(custom.id) is None
