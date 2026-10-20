"""Consultazione e comandi atomici per gli incassi del documento selezionato."""
from __future__ import annotations

from flask import g, jsonify, request


def register_invoice_receipts_routes(app):
    from web.blueprints.api_v1_react import _richiedi_auth
    from pct.parcella_incassi_repository import ParcellaIncassoConflict, ParcellaIncassoCommandConflict
    from web.services.invoice_receipts_runtime import current_invoice_receipts, receipt_command_scope
    from web.services.fascicolo_bonifico_ricevuto import _data_iso

    def allowed(write=False):
        user = g.get('utente_corrente')
        return bool(user and user.ha_permesso('fatturazione.leggi')
                    and (not write or user.ha_permesso('fatturazione.scrivi')))

    def snapshot(repo, invoice_id, source=None):
        from pct.prima_nota import METODI
        from pct.payment_confirmations import for_invoice
        labels = {'banca': 'Conto corrente', 'cassa': 'Contanti', 'pos': 'POS', 'altro': 'Altro'}
        summary = repo.summary(invoice_id) if source is None else {key: value for key, value in source.items()
            if key not in {'movement_id', 'already_present'}}
        return {**summary, 'command_scope': receipt_command_scope(repo, invoice_id),
                'provider_confirmations': for_invoice(repo.db, repo.tenant, invoice_id),
                'can_write': allowed(True), 'methods': [{'value': key, 'label': labels[key]} for key in METODI]}

    @app.get('/api/fatturazione/<invoice_id>/incassi')
    @_richiedi_auth
    def invoice_receipts_read(invoice_id):
        if not allowed():
            return jsonify(ok=False, message='Permesso insufficiente.'), 403
        try:
            repo = current_invoice_receipts(readonly=True)
            return jsonify(ok=True, summary=snapshot(repo, invoice_id))
        except KeyError:
            return jsonify(ok=False, message='Documento non trovato.'), 404
        except Exception:
            app.logger.exception('Consultazione incassi non confermata')
            return jsonify(ok=False, message='Incassi non disponibili. I dati esistenti sono conservati.'), 503

    @app.post('/api/fatturazione/<invoice_id>/incassi')
    @_richiedi_auth
    def invoice_receipts_write(invoice_id):
        if not allowed(True):
            return jsonify(ok=False, message='Permesso insufficiente.'), 403
        payload = request.get_json(silent=True)
        base = {'operation', 'command_key', 'expected_revision', 'paid_on', 'scope'}
        if not isinstance(payload, dict) or payload.get('operation') not in {'receipt', 'reversal'}:
            return jsonify(ok=False, code='validation', message='Comando di incasso non valido.'), 400
        fields = base | ({'amount_cents', 'method', 'note'} if payload['operation'] == 'receipt' else {'movement_id', 'reason'})
        if set(payload) != fields:
            return jsonify(ok=False, code='validation', message='Dati del comando incompleti o non previsti.'), 400
        repo = None
        try:
            repo = current_invoice_receipts()
            if payload['scope'] != receipt_command_scope(repo, invoice_id):
                return jsonify(ok=False, code='context_changed', message='Contesto del comando cambiato. Controlla il documento prima di proseguire.'), 409
            if not isinstance(payload['paid_on'], str) or not payload['paid_on'].strip():
                raise ValueError('Indica la data effettiva del movimento.')
            paid_on, date_error = _data_iso(payload['paid_on'])
            if date_error:
                raise ValueError(date_error)
            common = dict(invoice_id=invoice_id, paid_on=paid_on, command_key=payload['command_key'],
                          expected_revision=payload['expected_revision'])
            if payload['operation'] == 'receipt':
                result = repo.register(**common, amount_cents=payload['amount_cents'],
                    method=payload['method'], note=payload['note'])
            else:
                result = repo.reverse(**common, movement_id=payload['movement_id'], reason=payload['reason'])
            # Il commit comprende già audit e outbox nativi. La consegna esterna
            # resta riprendibile dallo scheduler anche se la risposta si perde.
            return jsonify(ok=True, movement_id=result['movement_id'],
                already_present=result['already_present'], summary=snapshot(repo, invoice_id, result),
                confirmed_command={'scope': payload['scope'], 'command_key': payload['command_key'],
                    'invoice_id': invoice_id, 'expected_revision': payload['expected_revision']},
                message='Movimento già registrato: nessun doppione.' if result['already_present'] else 'Movimento registrato.'), 200
        except ParcellaIncassoCommandConflict as exc:
            return jsonify(ok=False, code='command_conflict', message=str(exc), conflict=True), 409
        except ParcellaIncassoConflict as exc:
            return jsonify(ok=False, code='revision_conflict', message=str(exc), conflict=True), 409
        except KeyError:
            return jsonify(ok=False, message='Documento o movimento non trovato.'), 404
        except ValueError as exc:
            try:
                if repo is not None and repo.command_exists(payload.get('command_key')):
                    return jsonify(ok=False, code='command_conflict', message='Il comando è già presente: recupera i dati originali prima di proseguire.'), 409
            except Exception:
                app.logger.exception('Riscontro del comando non disponibile dopo la validazione')
                return jsonify(ok=False, code='outcome_not_confirmed', message='Esito da recuperare con lo stesso comando.'), 503
            return jsonify(ok=False, code='validation', message=str(exc)), 400
        except Exception:
            app.logger.exception('Esito incasso non confermato: recuperare lo stesso comando')
            return jsonify(ok=False, code='outcome_not_confirmed', message=
                'Esito da verificare. Conserva la bozza e verifica il salvataggio con lo stesso comando.'), 503
