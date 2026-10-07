"""Adapter Flask per le letture SQL; nessun invio PEC e nessun esito legale mutato."""
import logging
from pct.controllo_studio.letture import LettureControllo
from pct.email_sql_client import GestioneEmailSQL, MailboxMirrorError
from web.services.registro_letture_runtime import registro_corrente, tenant_corrente, utente_corrente_id

def repository():
    from flask import current_app
    tenant = tenant_corrente()
    if tenant in {'default', 'single-studio'} and not current_app.config.get('MULTI_TENANT'):
        tenant = 'installazione-locale'
    return LettureControllo(registro_corrente(),tenant)

def marca_pec(ids):
    from web.helpers import get_email_pec
    from pct.email_client import CartellaEmail, StatoEmail
    if not isinstance(ids,list) or not ids or len(ids)>2000 or any(not isinstance(i,str) or not i for i in ids):
        raise ValueError('Seleziona le comunicazioni da segnare come lette.')
    gestore = get_email_pec()
    if isinstance(gestore, GestioneEmailSQL):
        selected = list(dict.fromkeys(ids))
        warning = ''
        try:
            result = gestore.marca_lette_multipla(selected)
        except MailboxMirrorError as exc:
            result, warning = exc.operation_result, str(exc)
        changed = result['updated']
        message = ('1 comunicazione segnata come letta.' if changed == 1
                   else f'{changed} comunicazioni segnate come lette.' if changed
                   else 'Le comunicazioni selezionate risultano già lette.')
        return selected, message + (' ' + warning if warning else '')
    db = gestore._carica()
    if any(eid not in db or db[eid].cartella != CartellaEmail.INBOX for eid in ids):
        raise ValueError('La selezione contiene comunicazioni non disponibili nella posta in arrivo.')
    selected, now = repository().segna_pec(utente_corrente_id(),ids)
    # Il commit SQL precede il mirror; un errore del mirror resta esplicito.
    try:
        for eid in selected:
            db[eid].stato, db[eid].letta_il = StatoEmail.LETTA, now
        gestore._salva()
    except Exception:
        logging.getLogger(__name__).exception('Lettura PEC SQL salvata; mirror storico non aggiornato')
        return selected, 'Lettura salvata. Il mirror storico della casella richiede riallineamento.'
    return selected, f'{len(selected)} comunicazioni segnate come lette.'
