"""Prepara i contatori di revisione dei pannelli pronti (trigger SQL) con backup verificato, studio per studio.

Uso: python -m scripts.pannelli_pronti_prepara --tenant all [--apply --backup-dir /data/backup/pannelli-pronti]
Senza --apply dice soltanto quali database vanno preparati.
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    if args.apply and args.backup_dir is None:
        parser.error('Serve una cartella di backup persistente per applicare.')
    from scripts.backfill_archivio_batches import _targets, _tenant_context
    from web.app import create_app
    from flask import g
    from pct.pannelli_pronti.preparazione import prepara_database
    from web.services.pannelli_pronti_fonti import TABELLE_PEC, TABELLE_REGISTRO, TABELLE_STUDIO, percorso_pec
    from web.services.registro_letture_runtime import percorso_registro

    app = create_app({'SCHEDULER_ONLY': True, 'DISABLE_SCHEDULER': True})
    manager, owners = _targets(app, '' if args.tenant == 'all' else args.tenant)
    for slug, owner in owners.items():
        with _tenant_context(app, manager, owner, slug):
            paths = dict(getattr(g, 'data_paths', {}) or {})
            studio_db = paths.get('STUDIO_DB') or ''
            registro = percorso_registro(paths)
        destinazione = (args.backup_dir / slug) if args.backup_dir else None
        for percorso, tabelle, condivise in (
            (studio_db, TABELLE_STUDIO, False),
            (registro, TABELLE_REGISTRO, False),
            (percorso_pec(paths), TABELLE_PEC, True),
        ):
            if not percorso:
                continue
            esito = prepara_database(percorso, tabelle_senza_fascicolo=tabelle, backup_dir=destinazione,
                                     applica=args.apply, sole_tabelle_condivise=condivise)
            print(json.dumps({'tenant': slug, **esito}, ensure_ascii=False))


if __name__ == '__main__':
    main()
