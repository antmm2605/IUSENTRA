"""Fatti restituiti dai verificatori nativi, senza confondere creazione e incasso.

Questi parser non autenticano notifiche. Il chiamante deve avere già verificato
la firma o consultato il gestore con le credenziali dello studio.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, DecimalException
from typing import Mapping
from zoneinfo import ZoneInfo


def exact_cents(value):
    if isinstance(value, bool):
        raise ValueError('Importo del gestore non valido.')
    try:
        amount = Decimal(str(value))
        if not amount.is_finite() or not 0 < amount <= Decimal(9007199254740991) / 100:
            raise ValueError('Importo del gestore fuori intervallo.')
        minor = amount * 100
        if not amount.is_finite() or minor != minor.to_integral_value() or not 0 < minor <= 9007199254740991:
            raise ValueError('Importo del gestore non rappresentabile in centesimi.')
        return int(minor)
    except (DecimalException, TypeError) as exc:
        raise ValueError('Importo del gestore non valido.') from exc


def _value(source, field, default=None):
    return source.get(field, default) if isinstance(source, Mapping) else getattr(source, field, default)


def _timestamp(value, *, epoch=False):
    if value is None or value == '':
        return None, 'Data effettiva non presente nella conferma del gestore.'
    try:
        if epoch:
            if type(value) is not int or value <= 0:
                raise ValueError('Timestamp non valido')
            parsed = datetime.fromtimestamp(value, timezone.utc)
        else:
            if not isinstance(value, str):
                raise ValueError('Data non testuale')
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError('Fuso orario assente')
        if parsed > datetime.now(timezone.utc):
            raise ValueError('Data futura')
        return parsed.astimezone(timezone.utc).isoformat(), ''
    except (ValueError, OverflowError, OSError):
        return None, 'Data effettiva del gestore non valida: verifica della fonte necessaria.'


@dataclass(frozen=True)
class ProviderPaymentFacts:
    provider: str
    transaction_id: str
    link_id: str
    invoice_id: str
    client_id: str
    amount_cents: int
    currency: str
    paid_at: str | None
    date_origin: str
    date_issue: str
    source_json: str
    paid_on: str | None = None
    observed_at: str = ''

    @property
    def source_sha256(self):
        return hashlib.sha256(self.source_json.encode('utf-8')).hexdigest()

    def cash_date(self):
        if self.paid_on is None:
            raise ValueError(self.date_issue)
        return self.paid_on


def _facts(provider, transaction_id, link, amount, currency, source, *, timestamp=None, origin='', epoch=False,
           lower_bound=None, lower_epoch=False, observed_at=None):
    if not isinstance(transaction_id, str) or not transaction_id.strip() or len(transaction_id) > 200:
        raise ValueError('Identificativo della transazione del gestore assente o non valido.')
    cents = exact_cents(amount)
    if cents != exact_cents(link.importo):
        raise ValueError('Importo del gestore discordante dal collegamento.')
    if not isinstance(currency, str) or currency.upper() != str(link.valuta).upper():
        raise ValueError('Valuta del gestore discordante dal collegamento.')
    paid_at, issue = _timestamp(timestamp, epoch=epoch)
    observed, observed_issue = _timestamp(observed_at or datetime.now(timezone.utc).isoformat())
    if observed is None:
        raise ValueError(observed_issue)
    day = None
    if paid_at:
        created, _ = _timestamp(lower_bound, epoch=lower_epoch)
        if lower_bound is not None and lower_bound != '' and created is None:
            issue = 'Data di creazione del gestore non valida: verifica della fonte necessaria.'
        elif created and datetime.fromisoformat(paid_at) < datetime.fromisoformat(created):
            issue = 'La conferma precede la creazione del pagamento: verifica della fonte necessaria.'
        elif datetime.fromisoformat(paid_at) <= datetime.fromisoformat(observed):
            day = datetime.fromisoformat(paid_at).astimezone(ZoneInfo('Europe/Rome')).date().isoformat()
        else:
            issue = 'Data del gestore successiva alla conferma osservata: verifica necessaria.'
    elif timestamp is None or timestamp == '':
        created, _ = _timestamp(lower_bound, epoch=lower_epoch)
        if created:
            lower = datetime.fromisoformat(created)
            upper = datetime.fromisoformat(observed)
            lower_day = lower.astimezone(ZoneInfo('Europe/Rome')).date()
            upper_day = upper.astimezone(ZoneInfo('Europe/Rome')).date()
            if lower <= upper and lower_day == upper_day:
                day, origin, issue = lower_day.isoformat(), 'verified_same_day_interval', ''
            else:
                issue = 'Data effettiva non specificata: creazione e conferma non delimitano un unico giorno.'
    return ProviderPaymentFacts(provider, transaction_id, link.id, link.id_parcella, link.id_cliente,
        cents, currency.upper(), paid_at, origin if day else '', issue,
        json.dumps(source, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False), day, observed)


def stripe_facts(session, link, *, verified_event_created=None, observed_at=None,
                 verified_event_id=None, verified_event_type=None):
    raw_metadata = _value(session, 'metadata') or {}
    if not isinstance(raw_metadata, Mapping):
        raise ValueError('Riferimenti Stripe non validi.')
    metadata = dict(raw_metadata)
    amount = _value(session, 'amount_total')
    if (_value(session, 'payment_status') != 'paid' or metadata.get('link_id') != link.id
            or metadata.get('parcella', link.id_parcella) != link.id_parcella
            or type(amount) is not int or amount <= 0):
        raise ValueError('Sessione Stripe non concordante con il collegamento.')
    source = {key: _value(session, key) for key in ('id', 'payment_status', 'amount_total', 'currency', 'created')}
    source['metadata'] = {key: metadata[key] for key in ('link_id', 'parcella') if key in metadata}
    source['verified_event_created'] = verified_event_created
    if verified_event_id is not None or verified_event_type is not None:
        if (not isinstance(verified_event_id, str) or not verified_event_id.startswith('evt_') or len(verified_event_id) > 200
                or verified_event_type not in {'checkout.session.completed', 'checkout.session.async_payment_succeeded'}):
            raise ValueError('Identità dell’evento Stripe non valida per il pagamento.')
        source['verified_event_id'] = verified_event_id
        source['verified_event_type'] = verified_event_type
    return _facts('stripe', source['id'], link, Decimal(amount) / 100, source['currency'], source,
                  timestamp=verified_event_created, origin='stripe.event.created', epoch=True,
                  lower_bound=source['created'], lower_epoch=True, observed_at=observed_at)


def paypal_capture_facts(capture, capture_id, link, *, observed_at=None):
    if (not isinstance(capture, dict) or capture.get('status') != 'COMPLETED'
            or capture.get('id') != capture_id or capture.get('custom_id') != link.id):
        raise ValueError('Cattura PayPal non concordante con il collegamento.')
    amount = capture.get('amount') or {}
    if not isinstance(amount, dict):
        raise ValueError('Importo della cattura PayPal non valido.')
    source = {key: capture.get(key) for key in ('id', 'status', 'custom_id', 'create_time', 'update_time')}
    source['amount'] = {key: amount.get(key) for key in ('value', 'currency_code')}
    # La creazione non sostituisce update_time: può solo delimitare un
    # intervallo verificato. L'ordine non sostituisce l'identità della cattura.
    return _facts('paypal', capture_id, link, amount.get('value'), amount.get('currency_code'), source,
                  timestamp=capture.get('update_time'), origin='paypal.capture.update_time',
                  lower_bound=capture.get('create_time'), observed_at=observed_at)


def satispay_facts(payment, payment_id, link, *, observed_at=None):
    if not isinstance(payment, dict):
        raise ValueError('Conferma Satispay non valida.')
    metadata = payment.get('metadata') or {}
    if not isinstance(metadata, dict):
        raise ValueError('Riferimenti Satispay non validi.')
    units = payment.get('amount_unit')
    if (payment.get('id') != payment_id or payment.get('type') != 'TO_BUSINESS'
            or payment.get('status') != 'ACCEPTED' or metadata.get('link_id') != link.id
            or type(units) is not int or units <= 0):
        raise ValueError('Pagamento Satispay non concordante con il collegamento.')
    source = {key: payment.get(key) for key in ('id', 'type', 'status', 'amount_unit', 'currency', 'insert_date')}
    source['metadata'] = {'link_id': metadata['link_id']}
    # insert_date da sola non dimostra l'accettazione. Insieme alla conferma
    # autenticata può delimitare un giorno, senza inventare l'ora dell'incasso.
    return _facts('satispay', payment_id, link, Decimal(units) / 100, payment.get('currency'), source,
                  lower_bound=payment.get('insert_date'), observed_at=observed_at)


def paypal_order_capture_facts(response, verified_order, link, *, observed_at=None):
    """Cattura nel relativo ordine autenticato; non inventare custom_id nella cattura."""
    if (not isinstance(response, dict) or not isinstance(verified_order, dict)
            or not verified_order.get('id') or response.get('id') != verified_order['id']
            or response.get('status') != 'COMPLETED'):
        raise ValueError('Risposta di cattura PayPal non concordante con l’ordine verificato.')
    original_units, units = verified_order.get('purchase_units'), response.get('purchase_units')
    if (not isinstance(original_units, list) or len(original_units) != 1 or not isinstance(original_units[0], dict)
            or not isinstance(units, list) or len(units) != 1 or not isinstance(units[0], dict)):
        raise ValueError('Unità dell’ordine PayPal non determinata.')
    original, unit = original_units[0], units[0]
    amount = original.get('amount') or {}
    if (original.get('custom_id') != link.id or not isinstance(amount, dict)
            or exact_cents(amount.get('value')) != exact_cents(link.importo)
            or amount.get('currency_code') != link.valuta):
        raise ValueError('Ordine PayPal di un altro collegamento o importo.')
    payments = unit.get('payments') or {}
    captures = payments.get('captures') if isinstance(payments, dict) else None
    if not isinstance(captures, list) or len(captures) != 1 or not isinstance(captures[0], dict):
        raise ValueError('Cattura univoca non presente nell’ordine PayPal.')
    capture = captures[0]
    if (capture.get('status') != 'COMPLETED' or capture.get('custom_id', link.id) != link.id
            or unit.get('custom_id', link.id) != link.id):
        raise ValueError('Cattura PayPal non completata o discordante.')
    capture_amount = capture.get('amount') or {}
    if not isinstance(capture_amount, dict):
        raise ValueError('Importo della cattura PayPal non valido.')
    source = {'order_id': verified_order['id'], 'verified_order_custom_id': original['custom_id'],
              'verified_order_amount': {key: amount.get(key) for key in ('value', 'currency_code')},
              'capture': {key: capture.get(key) for key in ('id', 'status', 'custom_id', 'create_time', 'update_time')}}
    source['capture']['amount'] = {key: capture_amount.get(key) for key in ('value', 'currency_code')}
    return _facts('paypal', capture.get('id'), link, capture_amount.get('value'), capture_amount.get('currency_code'),
                  source, timestamp=capture.get('update_time'), origin='paypal.capture.update_time',
                  lower_bound=capture.get('create_time'), observed_at=observed_at)


def sumup_checkout_facts(checkout, checkout_id, link, *, observed_at=None):
    if (not isinstance(checkout, dict) or checkout.get('id') != checkout_id
            or checkout.get('status') != 'PAID' or checkout.get('checkout_reference') != link.id):
        raise ValueError('Checkout SumUp non concordante con il collegamento.')
    transactions = checkout.get('transactions') or []
    if not isinstance(transactions, list) or any(not isinstance(item, dict) for item in transactions):
        raise ValueError('Riscontri della transazione SumUp non validi.')
    if any(item.get('status') in {'REFUNDED', 'PARTIALLY_REFUNDED', 'CHARGEBACK'} for item in transactions):
        raise ValueError('La fonte SumUp indica un rimborso o uno storno da riconciliare.')
    source = {key: checkout.get(key) for key in ('id', 'status', 'checkout_reference', 'amount', 'currency', 'date')}
    source['transactions'] = [{key: item.get(key) for key in ('id', 'status', 'amount', 'currency', 'timestamp')}
                              for item in transactions]
    return _facts('sumup', checkout_id, link, checkout.get('amount'), checkout.get('currency'), source,
                  lower_bound=checkout.get('date'), observed_at=observed_at)
