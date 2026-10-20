"""Preparazione nativa dei soli archivi controllati dei test di pagamento."""
import hashlib
import json
from pathlib import Path


def prepare_empty_receipts(database, tenant, paths, root):
    from pct.prima_nota_repository import PrimaNotaRepository
    from pct.parcella_incassi_preparation import prepare_invoice_receipts
    from pct.prima_nota_transition import prima_nota_source_lock, prepare_transition_locked, commit_transition_locked
    root = Path(root)
    source = Path(paths['PRIMA_NOTA_DB'])
    assert source.resolve().is_relative_to(root.resolve())
    source.parent.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        source.write_text('{}', encoding='utf-8')
    assert json.loads(source.read_text(encoding='utf-8')) == {}
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    backup = root / (tenant + '-cash-source.json')
    backup.write_bytes(source.read_bytes())
    cash = PrimaNotaRepository(database, tenant, actor_key='controlled-preparation')
    cash.ensure_schema()
    with prima_nota_source_lock(source):
        prepare_transition_locked(source, tenant=tenant, source_sha256=digest)
        cash.initialize({}, source_sha256=digest, backup_reference=str(backup))
        commit_transition_locked(source, tenant=tenant, source_sha256=digest)
    prepare_invoice_receipts(database, tenant, root / (tenant + '-receipt-backup'))
