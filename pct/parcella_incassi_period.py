"""Incassi del periodo: indice temporale e riscontro della sola cassa richiesta."""
from collections import defaultdict
from datetime import date

from pct.parcella_incassi_proofs import _cents, verified_receipt


def period_totals(database, invoices, start, end):
    if date.fromisoformat(start) >= date.fromisoformat(end):
        raise ValueError('Intervallo degli incassi non valido.')
    owners, total, count = {}, 0, 0
    if database is not None and invoices:
        conn = database.conn
        postgres = getattr(database, 'backend_kind', '') == 'postgresql'
        present = (conn.execute("SELECT to_regclass('parcella_incassi_state')").fetchone()[0] if postgres else
            conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='parcella_incassi_state'").fetchone())
        if present:
            from pct.parcella_incassi_preparation import require_receipt_indexes
            require_receipt_indexes(database)
            keys = list(invoices)
            for offset in range(0, len(keys), 400):
                page = keys[offset:offset + 400]
                rows = conn.execute('SELECT tenant_key,parcella_id FROM parcella_incassi_state WHERE parcella_id IN ('
                    + ','.join('?' for _ in page) + ')', page).fetchall()
                groups = defaultdict(list)
                for row in rows:
                    tenant, invoice_id = row[0], row[1]
                    if invoice_id in owners and owners[invoice_id] != tenant:
                        raise ValueError('Proprietà degli incassi discordante: nessun totale presunto.')
                    owners[invoice_id] = tenant
                    groups[tenant].append(invoice_id)
                for tenant, ids in groups.items():
                    movements = conn.execute(
                        'SELECT p.parcella_id,p.movement_id,p.amount_cents,p.direction,p.cash_sha256,'
                        'c.payload_json,p.reverses_movement_id,p.paid_on FROM parcella_incassi_proofs p '
                        'LEFT JOIN prima_nota_records c ON c.tenant_key=p.tenant_key AND c.record_key=p.movement_id '
                        'WHERE p.tenant_key=? AND p.paid_on>=? AND p.paid_on<? AND p.parcella_id IN ('
                        + ','.join('?' for _ in ids) + ')', (tenant, start, end, *ids)).fetchall()
                    for row in movements:
                        receipt = verified_receipt(*(row[index] for index in range(8)))
                        total += receipt['amount_cents'] * receipt['direction']
                        count += 1
    for invoice in invoices.values():
        if (invoice.id not in owners and getattr(invoice.stato, 'value', '') == 'PAGATA'
                and start <= str(invoice.data_pagamento or '')[:10] < end):
            # Conserva il dato storico dichiarato; non crea nuove prove SQL.
            total += _cents(invoice.totale)
            count += 1
    return {'importo': total / 100, 'movimenti': count}
