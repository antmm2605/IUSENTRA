"""Contesto dell'editor limitato alle impostazioni dello studio corrente."""
from dataclasses import asdict


def studio_context_for_editor():
    from flask import g
    from pct.postgres_runtime_support import database_config_to_dsn, resolve_runtime_postgres_dsn
    from web.blueprints.template_atti import _get_config_studio_manager, _cfg_path
    from pct.studio_timbro import build_studio_timbro
    manager = _get_config_studio_manager()
    config = manager.config
    tenant = getattr(g, 'tenant', None)
    dsn = database_config_to_dsn(getattr(tenant, 'database', None)) if tenant is not None else resolve_runtime_postgres_dsn()
    if tenant is not None and not dsn and resolve_runtime_postgres_dsn():
        raise RuntimeError('Archivio timbro dello studio non disponibile')
    studio = asdict(config.studio)
    studio['citta'] = studio.get('city', '')
    studio['provincia'] = studio.get('province', '')
    # Nessun SMTP_FROM o dato professionale globale come ripiego.
    context = {'studio': studio, 'pec': {'indirizzo': config.pec.indirizzo}}
    return {'config': context, 'studio_timbro': build_studio_timbro(
        db_path=_cfg_path('STUDIO_TIMBRO_DB', './config/studio_timbro.db'),
        config_studio=config, app_config={}, postgres_dsn=dsn,
    )}
