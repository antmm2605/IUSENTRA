"""Pubblica un solo modello revisionato; nessuna copia di archivi tenant."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data-root', required=True)
    parser.add_argument('--bundle', required=True)
    parser.add_argument('--reviewed-sha256', required=True)
    parser.add_argument('--publisher', required=True)
    args = parser.parse_args()
    from pct.editor_shared_models import publish_shared_model
    from pct.template_atti_repository import GestioneTemplateRepository
    root = Path(args.data_root).resolve()
    target = root / 'editor_shared_models' / 'template_repository.db'
    dsn = os.getenv('EDITOR_SHARED_MODELS_POSTGRES_DSN', '')
    # Il catalogo PostgreSQL usa un database di piattaforma dedicato.
    # Il backup coerente PostgreSQL va predisposto dalla procedura di deploy.
    if dsn and not os.getenv('EDITOR_SHARED_MODELS_POSTGRES_BACKUP_CONFIRMED'):
        raise ValueError('Backup PostgreSQL di piattaforma non confermato.')
    if target.is_file() and not dsn:
        backup = root / 'backups' / 'editor-shared-models' / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        backup.mkdir(parents=True)
        with sqlite3.connect(str(target)) as source, sqlite3.connect(str(backup / target.name)) as output:
            source.backup(output)
            if output.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Backup del catalogo non integro.')
    bundle = json.loads(Path(args.bundle).read_text(encoding='utf-8'))
    # Un catalogo pubblicato deve essere leggibile dall'app senza scrivere
    # sidecar WAL nella directory amministrativa, che resta protetta.
    repo = GestioneTemplateRepository(str(target), postgres_dsn=dsn, journal_mode='DELETE')
    receipt = publish_shared_model(repo, bundle['payload'], font_source=bundle.get('font_source', ''), reviewed_sha256=args.reviewed_sha256, publisher=args.publisher)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    main()
