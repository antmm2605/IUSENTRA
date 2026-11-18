"""Crea il registro consultato dai soli comandi di preparazione del rilascio."""
import argparse
import json
import os
from pathlib import Path

from pct.storage import StudioDB
from pct.tenant import GestioneTenant, StatoTenant
from tools.prepare_operational_query_indexes import _tenant_core
from web.services.storage_runtime import resolve_storage_runtime


def prepare(source: Path, target: Path) -> int:
    source = source.resolve(strict=True)
    if target.parent.resolve(strict=True) != source.parent or not target.name.startswith('.tenants-preflight-'):
        raise ValueError('Percorso temporaneo del preflight non valido.')
    raw = source.read_bytes()
    original = json.loads(raw)
    registry = GestioneTenant(registry_path=str(source))
    resolved = {}
    for owner in registry.lista():
        if owner.stato == StatoTenant.SOSPESO:
            continue
        paths = registry.percorsi_dati(owner.slug, reconcile_aliases=False, ensure_baseline=False)
        profile = resolve_storage_runtime(anchor_path=paths['FASCICOLI_DB'], tenant=owner)
        if not profile.uses_sqlite or profile.external_sql_configured:
            continue
        database = StudioDB(profile.studio_db_path, initialize_schema=False, readonly=True)
        try:
            tenant = _tenant_core(database, owner, registry, paths['STORAGE_CONFIG'])
        finally:
            database.chiudi()
        if tenant != owner.slug:
            resolved[owner.slug] = tenant

    if source.read_bytes() != raw:
        raise RuntimeError('Registro degli studi cambiato durante la verifica del preflight.')
    for entry in original.values():
        if entry['slug'] in resolved:
            entry['slug'] = resolved[entry['slug']]
    identities = [entry['slug'] for entry in original.values()]
    if len(identities) != len(set(identities)):
        raise ValueError('Identità duplicata nel registro di preparazione.')
    with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w', encoding='utf-8') as stream:
        json.dump(original, stream, ensure_ascii=False)
    return len(resolved)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant-registry', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(f'Studi con chiave storica verificata per il preflight: {prepare(args.tenant_registry, args.output)}')
