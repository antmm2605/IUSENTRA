"""Preparazione esplicita del catalogo nei soli studi sintetici dei test."""
from pathlib import Path


def prepare_list_catalog(app, *, owner=None):
    from pct.tenant import GestioneTenant
    from web.services.document_intelligence_runtime import document_ai_tenant_id
    from web.services.fascicoli_list_preparation import prepare_catalog
    from web.services.fascicoli_presidi_runtime import _attach_tenant_context
    from web.services.registro_letture_runtime import registro_corrente
    from web.services.storage_runtime import get_request_studio_db
    from web.services.studio_readonly import worker_studio_writer
    from web.services.tenant_paths import tenant_data_path

    assert app.testing, 'Preparazione riservata a dati sintetici.'
    with app.test_request_context('/__prepare-test-list'):
        if owner is not None:
            _attach_tenant_context(GestioneTenant(app.config['TENANTS_REGISTRY']), owner)
        anchor=tenant_data_path('FASCICOLI_DB',app.config['FASCICOLI_DB'],require_tenant=True)
        get_request_studio_db(anchor)
        registro_corrente()
        with worker_studio_writer(anchor) as database:
            result=prepare_catalog(database,tenant=document_ai_tenant_id(),anchor=anchor,
                destination=Path(anchor).parent.parent/'backup'/'test-list-catalog')
            assert result['phase']=='COMPLETED'
