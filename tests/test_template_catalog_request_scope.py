"""Una consultazione del catalogo non deve inventariare archivi estranei."""
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('catalog', [[], [dict(codice='CONTROLLED', titolo='Modello controllato')]])
def test_catalogo_consultivo_non_avvia_inventario_globale(monkeypatch, catalog):
    from pct import template_atti_inventory
    from web.services import react_template_atti_bridge as bridge

    original = template_atti_inventory.build_template_inventory
    calls = []

    def packaged_only(*args, **kwargs):
        assert kwargs.get('include_runtime_sources') is False, 'Inventario runtime non richiesto'
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(template_atti_inventory, 'build_template_inventory', packaged_only)
    monkeypatch.setattr(bridge, '_safe_catalog_rows', lambda warnings: catalog)
    bridge._safe_inventory_stats.cache_clear()
    bridge._safe_inventory_by_code.cache_clear()
    result = bridge.build_react_template_atti_payload(
        get_template_manager=lambda: SimpleNamespace(tutti=lambda: []))
    assert result['contracts']['writes'] == 'none'
    assert calls


def test_catalogo_distribuito_non_enumera_directory_dati(monkeypatch, tmp_path):
    from pathlib import Path

    from pct.template_atti_inventory import build_template_inventory

    def forbidden(*args, **kwargs):
        pytest.fail('Il catalogo distribuito sta enumerando i dati degli studi')

    monkeypatch.setattr(Path, 'glob', forbidden)
    records = build_template_inventory(tmp_path, include_runtime_sources=False)
    assert len(records) == 1320
    assert all(record['tenant_scope'] == 'global' for record in records)
