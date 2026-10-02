"""Un solo presidio per lo stesso originale ministeriale e gli stessi destinatari.

La correlazione conserva i presidi sorgente, le PEC e le catene di audit.
Non prende decisioni sull'obbligo di notificare e non registra invii eseguiti.
"""
from collections import defaultdict
from .models import canonical_json, json_load, utc_now_iso, validate_transition

EARLY = ('DETECTED', 'NEEDS_REVIEW', 'ORIGINAL_TO_ACQUIRE', 'ORIGINAL_ACQUIRED')
PREFIX = 'DUPLICATE_OF:'


def _groups(conn, tenant_id):
    rows = [dict(r) for r in conn.execute(
        'SELECT * FROM pec_legal_notification_presidia WHERE tenant_id=? AND status IN (?,?,?,?) AND confirmed_at IS NULL',
        (tenant_id, *EARLY)).fetchall()]
    groups = defaultdict(list)
    for row in rows:
        pid = row['id']
        docs = [dict(d) for d in conn.execute(
            "SELECT * FROM pec_legal_notification_documents WHERE tenant_id=? AND presidio_id=? AND document_role='portal_original' AND authoritative=TRUE",
            (tenant_id, pid)).fetchall()]
        originals = {(d['portal_document_id'], d['content_sha256'], d['document_version']) for d in docs
                     if d['portal_document_id'] and len(d['content_sha256'] or '') == 64}
        if len(originals) != 1:
            continue
        copies = [dict(d) for d in conn.execute(
            "SELECT content_sha256 FROM pec_legal_notification_documents WHERE tenant_id=? AND presidio_id=? AND document_role='office_pec_copy'",
            (tenant_id, pid)).fetchall()]
        copy_hashes = tuple(sorted({str(d['content_sha256'] or '') for d in copies}))
        if any(len(value) != 64 for value in copy_hashes):
            continue
        recipients = [dict(r) for r in conn.execute(
            'SELECT * FROM pec_legal_notification_recipients WHERE tenant_id=? AND presidio_id=?',
            (tenant_id, pid)).fetchall()]
        # Prove, invii, PEC verificate o decisioni di operatori devono restare distinti.
        if not recipients or any(r['sent_message_id'] or r['rac_message_id'] or r['rdac_message_id']
                                 or r['public_register_verified_at'] or r['failure_reason']
                                 or r['send_status'] != 'pending' or r['rac_status'] != 'pending'
                                 or r['delivery_status'] != 'pending' for r in recipients):
            continue
        key = (row['fascicolo_id'], row['notification_case'], row['channel'], row['status'],
               row['explicit_due_at'], row['assigned_user_id'], tuple(sorted(originals)), copy_hashes,
               row['rulepack_version'], canonical_json(json_load(row['legal_basis_json'], default=[])), bool(row['proof_deposit_required']),
               row['priority'], bool(row['human_review_required']), row['legacy_policy_id'],
               tuple(sorted((r['recipient_identity_key'], bool(r['required'])) for r in recipients)))
        groups[key].append(row)
    return [sorted(items, key=lambda r: (r['created_at'], r['id'])) for items in groups.values() if len(items) > 1]


def reconcile_document_duplicates(repo, *, apply=False):
    """Da pipeline/job, mai dalla consultazione della coda; transazione tenant-aware."""
    mapping = {}
    with repo.connection() as conn:
        if apply and repo.backend_kind == 'sqlite':
            conn.execute('BEGIN IMMEDIATE')
        elif apply:
            # Blocca gli stessi candidati in ordine stabile prima della rivalutazione.
            conn.execute('SELECT id FROM pec_legal_notification_presidia WHERE tenant_id=? AND status IN (?,?,?,?) ORDER BY id FOR UPDATE', (repo.tenant_id, *EARLY)).fetchall()
            for table in ('pec_legal_notification_documents', 'pec_legal_notification_recipients'):
                conn.execute(f'SELECT id FROM {table} WHERE tenant_id=? AND presidio_id IN (SELECT id FROM pec_legal_notification_presidia WHERE tenant_id=? AND status IN (?,?,?,?)) ORDER BY id FOR UPDATE',
                             (repo.tenant_id, repo.tenant_id, *EARLY)).fetchall()
        groups = _groups(conn, repo.tenant_id)
        for group in groups:
            primary = group[0]
            for duplicate in group[1:]:
                mapping[duplicate['id']] = primary['id']
                if not apply:
                    continue
                now = utc_now_iso()
                reason = 'Stesso originale ministeriale, versione e destinatari: attività riunita al presidio già presente. PEC e prove conservate; nessuna notifica registrata come eseguita.'
                evidence = {'event': 'document_duplicate_consolidation', 'canonical_presidio_id': primary['id'],
                            'duplicate_presidio_id': duplicate['id'], 'source_message_id': duplicate['source_message_id']}
                validate_transition(duplicate['status'], 'CANCELLED', reason=reason)
                repo._append_transition_row(conn, presidio_id=duplicate['id'], previous_status=duplicate['status'],
                    next_status='CANCELLED', actor='verificatore-duplicati', reason=reason, evidence=evidence,
                    idempotency_key='document-duplicate:' + primary['id'], occurred_at=now)
                repo._append_transition_row(conn, presidio_id=primary['id'], previous_status=primary['status'],
                    next_status=primary['status'], actor='verificatore-duplicati', reason=reason, evidence=evidence,
                    idempotency_key='correlated-source:' + duplicate['id'], occurred_at=now)
                conn.execute('UPDATE pec_legal_notification_presidia SET status=?,resolution_code=?,resolution_reason=?,resolved_at=?,updated_at=? WHERE tenant_id=? AND id=?',
                    ('CANCELLED', PREFIX + primary['id'], reason, now, now, repo.tenant_id, duplicate['id']))
                conn.execute('UPDATE pec_legal_notification_presidia SET updated_at=? WHERE tenant_id=? AND id=?',
                    (now, repo.tenant_id, primary['id']))
    return {'source_of_truth': repo.backend_kind, 'mapping': mapping, 'applied': bool(apply)}


def canonical_presidio_ids(repo, ids):
    """Risolve anche correlazioni già consolidate per i job su un singolo evento."""
    selected = set(ids)
    with repo.connection() as conn:
        for pid in tuple(selected):
            row = conn.execute('SELECT resolution_code FROM pec_legal_notification_presidia WHERE tenant_id=? AND id=?', (repo.tenant_id, pid)).fetchone()
            code = str(row['resolution_code'] or '') if row else ''
            if code.startswith(PREFIX):
                selected.remove(pid)
                selected.add(code[len(PREFIX):])
    return tuple(sorted(selected))
