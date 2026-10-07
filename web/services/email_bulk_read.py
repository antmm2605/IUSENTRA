"""Lettura massiva primaria: selezione valida, transazione SQL e risposta esplicita."""
from pct.email_mailbox_repository import MailboxNotInitialized
from pct.email_sql_client import GestioneEmailSQL, MailboxMirrorError
from web.services.email_storage_runtime import create_email_mailbox


def mark_selected_mail_read(db_path, ids):
    if (not isinstance(ids, list) or not ids or len(ids) > 5000
            or any(not isinstance(key, str) or not key.strip() or len(key) > 200 for key in ids)):
        raise ValueError('Seleziona da 1 a 5.000 messaggi validi.')
    keys = list(dict.fromkeys(key.strip() for key in ids))
    manager = create_email_mailbox(db_path, load_catalog=False)
    if not isinstance(manager, GestioneEmailSQL):
        raise MailboxNotInitialized('La lettura massiva richiede l’archivio strutturato dello studio.')
    # Non cambiare inviate/cestino né uno stato già lavorato. La scelta massiva
    # deve contenere esclusivamente la posta in arrivo mostrata all’avvocato.
    warning = ''
    try:
        result = manager.marca_lette_multipla(keys)
    except MailboxMirrorError as exc:
        result = exc.operation_result
        warning = str(exc)
    updated = list(result['message_keys'])
    updated_keys = set(updated)
    message = ('1 messaggio segnato come letto.' if len(updated) == 1
               else f'{len(updated)} messaggi segnati come letti.' if updated
               else 'I messaggi selezionati risultano già letti.')
    return {
        'ok': True, 'message': message + (' ' + warning if warning else ''),
        'updated': updated, 'selected': len(keys), 'warning': bool(warning),
        'primary_committed': True, 'missing': [],
        'skipped': [key for key in keys if key not in updated_keys],
    }
