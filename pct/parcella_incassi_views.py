"""Letture a lotti degli stessi saldi verificati, senza query per singola riga."""
from collections import defaultdict


def invoice_cash_year(invoice, year):
    """Somma dei fatti di cassa nell'anno, anche per fatture di anni precedenti."""
    summary = getattr(invoice, '_incassi_projection', None)
    if isinstance(summary, dict):
        return sum(row['amount_cents'] * row['direction'] for row in summary['receipts']
                   if str(row['paid_on']).startswith(f'{year}-')) / 100
    if (getattr(invoice.stato, 'value', '') == 'PAGATA'
            and str(getattr(invoice, 'data_pagamento', '') or '').startswith(f'{year}-')):
        return invoice.totale
    return 0


def balance_amount(invoice, balances, field, legacy_amount):
    summary = balances.get(invoice.id)
    if summary is None:
        return legacy_amount
    value = summary[field]
    if value is None:
        raise ValueError(summary.get('reason') or 'Saldo economico da riscontrare: nessun importo presunto.')
    return value / 100


def receipts_in_period(invoices, balances, start, end):
    from datetime import date
    from pct.parcella_incassi_repository import _cents
    if date.fromisoformat(start) >= date.fromisoformat(end):
        raise ValueError('Intervallo degli incassi non valido.')
    total, count = 0, 0
    for invoice in invoices.values():
        summary = balances.get(invoice.id)
        if summary is not None:
            for receipt in summary['receipts']:
                if start <= receipt['paid_on'] < end:
                    total += receipt['amount_cents'] * receipt['direction']
                    count += 1
        elif (getattr(invoice.stato, 'value', '') == 'PAGATA'
              and start <= str(invoice.data_pagamento or '')[:10] < end):
            # Riscontro storico già presente nel gestionale: non si crea né
            # si retrodata una nuova prova di cassa a partire da questo dato.
            total += _cents(invoice.totale)
            count += 1
    return {'importo': total / 100, 'movimenti': count}


def balances_for_invoices(database, invoices):
    from pct.fatturazione import ParcellaConcurrentUpdate, parcella_revision
    from pct.parcella_incassi_repository import ParcellaIncassiRepository
    if database is None or not invoices:
        return {}
    conn = database.conn
    postgres = getattr(database, 'backend_kind', '') == 'postgresql'
    present = (conn.execute("SELECT to_regclass('parcella_incassi_state')").fetchone()[0] if postgres else
        conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='parcella_incassi_state'").fetchone())
    if not present:
        return {}
    result, owners = {}, {}
    keys = list(invoices)
    for offset in range(0, len(keys), 400):
        page = keys[offset:offset + 400]
        rows = conn.execute('SELECT tenant_key,parcella_id FROM parcella_incassi_state WHERE parcella_id IN ('
            + ','.join('?' for _ in page) + ')', page).fetchall()
        groups = defaultdict(list)
        for row in rows:
            tenant, invoice_id = row[0], row[1]
            if invoice_id in owners and owners[invoice_id] != tenant:
                raise ValueError('Proprietà del saldo economico discordante: verifica necessaria.')
            owners[invoice_id] = tenant
            invoices[invoice_id]._incassi_projection = {
                'status': 'REVIEW', 'paid_cents': None, 'residual_cents': None, 'receipts': [],
                'reason': 'Riscontro dei movimenti SQL non confermato: aggiorna o verifica il documento.',
            }
            groups[tenant].append(invoice_id)
        for tenant, ids in groups.items():
            repo = ParcellaIncassiRepository(database, tenant, actor_key='consultazione-incassi')
            batch = repo.summaries(ids)
            if set(batch) != set(ids):
                raise ParcellaConcurrentUpdate('Documento cambiato durante la lettura degli incassi: aggiorna la pagina.')
            for invoice_id, summary in batch.items():
                if parcella_revision(invoices[invoice_id]) != summary['revision']:
                    raise ParcellaConcurrentUpdate('Saldi aggiornati da un altro operatore: aggiorna la pagina.')
                result[invoice_id] = summary
                # Proiezione della sola consultazione corrente; non entra nel
                # dataclass né nel JSON persistito della parcella.
                invoices[invoice_id]._incassi_projection = summary
    return result
