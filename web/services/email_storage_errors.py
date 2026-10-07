"""Errori SQL della posta espliciti, senza falsi conteggi o successi di invio."""
from flask import jsonify, request

from pct.email_mailbox_repository import MailboxConflict, MailboxNotInitialized
from pct.email_sql_client import MailboxMirrorError

MAILBOX_STORAGE_ERRORS = (MailboxConflict, MailboxNotInitialized, MailboxMirrorError)


def register_mailbox_errors(blueprint):
    def conflict(error):
        response = jsonify(ok=False, message=str(error), refresh_required=True)
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response, 409

    def unavailable(error):
        response = jsonify(ok=False, message=str(error), refresh_required=True)
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response, 503

    def mirror_pending(error):
        # Una presa visione non ha azioni successive al commit del catalogo.
        # Non estendere questa certezza a invii, allegati o eliminazioni fisiche.
        endpoint = str(request.endpoint or '').rsplit('.', 1)[-1]
        acknowledged = request.method == 'POST' and endpoint in {
            'segna_letta', 'segna_non_letta', 'cestino', 'ripristina',
        }
        response = jsonify(ok=acknowledged, warning=True, primary_committed=True,
                           refresh_required=True, message=str(error))
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        return response, 200 if acknowledged else 503

    blueprint.register_error_handler(MailboxConflict, conflict)
    blueprint.register_error_handler(MailboxNotInitialized, unavailable)
    blueprint.register_error_handler(MailboxMirrorError, mirror_pending)
