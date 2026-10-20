"""Presentazione dei movimenti verificati, distinta dallo stato della fattura."""
from pct.formatting import format_date_it, format_euro_it


def receipt_rows(parcelle, clienti, legacy_record):
    rows = []
    for invoice in parcelle:
        balance = getattr(invoice, '_incassi_projection', None)
        if not isinstance(balance, dict):
            if getattr(getattr(invoice, 'stato', None), 'value', '') == 'PAGATA':
                rows.append((str(invoice.data_pagamento or ''), legacy_record(invoice, clienti)))
            continue
        for receipt in balance['receipts']:
            row = legacy_record(invoice, clienti)
            reverse = receipt['direction'] == -1
            row.update(id=receipt['movement_id'],
                amountDisplay=format_euro_it(receipt['amount_cents'] * receipt['direction'] / 100),
                paidAt=format_date_it(receipt['paid_on']),
                method=receipt['method'].capitalize(),
                state='STORNO' if reverse else 'PAGATA',
                stateLabel='Storno incasso' if reverse else 'Incasso poi stornato' if receipt['reversed'] else 'Incasso registrato',
                stateTone='warning' if reverse else 'success')
            rows.append((receipt['paid_on'], row))
    rows.sort(key=lambda value: (value[0], value[1]['id']), reverse=True)
    return [row for _, row in rows]
