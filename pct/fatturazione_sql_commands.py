"""Comandi puntuali che preservano le altre parcelle e i collegamenti SQL."""
import json


class ParcellaPaymentRequiresReceipt(ValueError):
    """Il pagamento richiede il comando nativo che aggiorna anche la cassa."""


def guard_managed_payment(database, invoice_id, *, target='PAGATA'):
    """Un'etichetta di stato non costituisce un nuovo movimento di cassa."""
    conn = database.conn
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    present = (conn.execute("SELECT to_regclass('parcella_incassi_state')").fetchone()[0] if postgres else
        conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='parcella_incassi_state'").fetchone())
    if present and conn.execute('SELECT 1 FROM parcella_incassi_state WHERE parcella_id=? LIMIT 1', (invoice_id,)).fetchone():
        if target == 'BOZZA':
            row = conn.execute('SELECT stato FROM parcelle WHERE id=?', (invoice_id,)).fetchone()
            if row and row[0] == 'BOZZA':
                return
            raise ParcellaPaymentRequiresReceipt('Il documento ha incassi registrati e non può tornare in bozza. Gestisci lo storno o l’annullamento dal documento.')
        raise ParcellaPaymentRequiresReceipt('Il saldo di questo documento deriva dagli incassi registrati. Registra il pagamento effettivo nella sezione Incassi.')
    if target == 'PAGATA':
        from pct.fatturazione import Parcella, StatoParcella
        row = conn.execute('SELECT dati_json FROM parcelle WHERE id=?', (invoice_id,)).fetchone()
        item = Parcella.from_dict(json.loads(row[0])) if row else None
        if item and item.stato != StatoParcella.PAGATA:
            raise ParcellaPaymentRequiresReceipt('Registra il pagamento effettivo nella sezione Incassi: lo stato da solo non costituisce un movimento di cassa.')


def delete_draft(database, invoice_id, expected_revision):
    from pct.fatturazione import Parcella, ParcellaConcurrentUpdate, StatoParcella, parcella_revision
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    writable = getattr(database, '_conn_per_scrittura', None)
    conn = writable() if callable(writable) else database.conn
    target = database.raw_conn if postgres else conn
    if not postgres and conn.in_transaction:
        raise RuntimeError('Transazione estranea alla cancellazione della bozza.')
    try:
        if not postgres:
            conn.execute('PRAGMA foreign_keys=ON')
            if conn.execute('PRAGMA foreign_keys').fetchone()[0] != 1:
                raise RuntimeError('Vincoli SQL della bozza non attivi.')
            conn.execute('BEGIN IMMEDIATE')
        row = conn.execute('SELECT dati_json,stato FROM parcelle WHERE id=?'
            + (' FOR UPDATE' if postgres else ''), (invoice_id,)).fetchone()
        if row is None:
            raise ParcellaConcurrentUpdate('Il documento non è più presente: aggiorna la scheda.')
        invoice = Parcella.from_dict(json.loads(row[0]))
        if parcella_revision(invoice) != expected_revision:
            raise ParcellaConcurrentUpdate('La bozza è cambiata: confronta la versione aggiornata prima di eliminarla.')
        if invoice.stato != StatoParcella.BOZZA or row[1] != StatoParcella.BOZZA.value:
            raise ValueError('Solo una bozza mai emessa può essere eliminata.')
        if conn.execute('SELECT 1 FROM payment_links WHERE id_parcella=? LIMIT 1', (invoice_id,)).fetchone():
            raise ValueError('La bozza ha collegamenti di pagamento: annulla il documento per conservarne la provenienza.')
        removed = conn.execute('DELETE FROM parcelle WHERE id=? AND dati_json=? RETURNING id',
                               (invoice_id, row[0])).fetchone()
        if removed is None:
            raise ParcellaConcurrentUpdate('La bozza è cambiata durante la cancellazione.')
        target.commit()
    except Exception:
        target.rollback()
        raise
