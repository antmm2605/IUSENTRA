"""Guardrail dei fatti del gestore, senza chiamate esterne o movimenti reali."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from pct.payment_evidence import exact_cents, stripe_facts, paypal_capture_facts, satispay_facts, sumup_checkout_facts, paypal_order_capture_facts


@pytest.fixture
def link():
    return SimpleNamespace(id='LINK-1', id_parcella='INVOICE-1', id_cliente='CLIENT-1', importo=600, valuta='EUR')


@pytest.mark.parametrize('value', [True, False, None, 'NaN', 'Infinity', '-1', '0', '0.001', '600.004', '1e999999999'])
def test_amount_never_rounds_or_coerces_invalid_provider_values(value):
    with pytest.raises(ValueError):
        exact_cents(value)


def test_stripe_paid_confirmation_uses_verified_event_not_checkout_creation(link):
    session = dict(id='cs_controlled', payment_status='paid', amount_total=60000, currency='eur',
                   created=1704067200, client_secret='NEVER-STORE',
                   metadata={'link_id': link.id, 'parcella': link.id_parcella, 'secret': 'NEVER-STORE'})
    missing = stripe_facts(session, link)
    assert missing.paid_at is None and missing.date_issue
    with pytest.raises(ValueError):
        missing.cash_date()
    timestamp = int(datetime(2026, 10, 19, 22, 30, tzinfo=timezone.utc).timestamp())
    assert stripe_facts(session, link, verified_event_created=timestamp).paid_on is None
    session['created'] = timestamp - 60
    facts = stripe_facts(session, link, verified_event_created=timestamp)
    assert facts.paid_at is None
    assert facts.amount_cents == 60000 and facts.cash_date() == '2026-10-20'
    assert facts.date_origin == 'verified_event_same_day_interval'
    assert 'NEVER-STORE' not in facts.source_json
    assert facts.source_sha256 == stripe_facts(session, link, verified_event_created=timestamp).source_sha256


@pytest.mark.parametrize('change', [{'currency': 'usd'}, {'amount_total': 59999}, {'amount_total': True},
                                  {'payment_status': 'unpaid'}, {'payment_status': 'no_payment_required'},
                                  {'metadata': {'link_id': 'FOREIGN'}}])
def test_stripe_foreign_or_unpaid_session_cannot_supply_cash_facts(link, change):
    source = dict(id='cs_controlled', payment_status='paid', amount_total=60000, currency='eur',
                  metadata={'link_id': link.id, 'parcella': link.id_parcella})
    with pytest.raises(ValueError):
        stripe_facts({**source, **change}, link)


def test_paypal_order_does_not_replace_capture_identity_or_its_effective_date(link):
    capture = dict(id='CAPTURE-1', status='COMPLETED', custom_id=link.id,
                   amount={'value': '600.00', 'currency_code': 'EUR'}, create_time='2025-12-31T22:00:00Z')
    assert paypal_capture_facts(capture, 'CAPTURE-1', link).cash_date() == '2025-12-31'
    with pytest.raises(ValueError):
        paypal_capture_facts(capture, 'ORDER-1', link)
    facts = paypal_capture_facts({**capture, 'update_time': '2026-10-19T23:30:00Z'}, 'CAPTURE-1', link)
    assert facts.transaction_id == 'CAPTURE-1' and facts.cash_date() == '2025-12-31'
    assert facts.date_origin == 'paypal.capture.create_time'


@pytest.mark.parametrize('created', ['not-a-date', '2099-01-01T00:00:00Z', '2026-10-19T13:00:00Z'])
def test_explicit_source_chronology_conflict_cannot_prove_a_cash_date(link, created):
    capture = dict(id='CAPTURE-1', status='COMPLETED', custom_id=link.id,
                   amount={'value': '600.00', 'currency_code': 'EUR'},
                   create_time=created, update_time='2026-10-19T12:00:00Z')
    facts = paypal_capture_facts(capture, 'CAPTURE-1', link, observed_at='2026-10-19T14:00:00Z')
    assert facts.paid_on is None and facts.date_issue
    with pytest.raises(ValueError):
        facts.cash_date()


def test_satispay_creation_is_not_acceptance_date_and_refund_is_not_income(link):
    payment = dict(id='PAYMENT-1', type='TO_BUSINESS', status='ACCEPTED', amount_unit=60000,
                   currency='EUR', metadata={'link_id': link.id}, insert_date='2026-10-19T10:00:00Z')
    facts = satispay_facts(payment, 'PAYMENT-1', link)
    assert facts.paid_at is None and facts.date_issue and facts.amount_cents == 60000
    with pytest.raises(ValueError):
        satispay_facts({**payment, 'type': 'REFUND_TO_BUSINESS'}, 'PAYMENT-1', link)


@pytest.mark.parametrize(('created', 'observed', 'expected'), [
    ('2026-10-19T10:00:00Z', '2026-10-19T12:00:00Z', '2026-10-19'),
    ('2026-10-19T23:30:00Z', '2026-10-20T00:30:00Z', '2026-10-20'),
    ('2026-10-19T21:59:00Z', '2026-10-19T22:01:00Z', None),
    ('2026-10-19T13:00:00Z', '2026-10-19T12:00:00Z', None),
])
def test_accepted_payment_day_must_be_proven_by_the_whole_interval(link, created, observed, expected):
    payment = dict(id='PAYMENT-1', type='TO_BUSINESS', status='ACCEPTED', amount_unit=60000,
                   currency='EUR', metadata={'link_id': link.id}, insert_date=created)
    facts = satispay_facts(payment, 'PAYMENT-1', link, observed_at=observed)
    assert facts.paid_at is None  # Nessun orario di esecuzione inventato.
    assert facts.paid_on == expected
    if expected:
        assert facts.cash_date() == expected and facts.date_origin == 'verified_same_day_interval'
    else:
        with pytest.raises(ValueError):
            facts.cash_date()


def test_sumup_paid_checkout_has_a_day_only_when_creation_and_observation_prove_it(link):
    checkout = dict(id='CHECKOUT-1', status='PAID', checkout_reference=link.id, amount=600,
                    currency='EUR', date='2026-10-19T10:00:00Z', transactions=[])
    facts = sumup_checkout_facts(checkout, 'CHECKOUT-1', link, observed_at='2026-10-19T12:00:00Z')
    assert facts.cash_date() == '2026-10-19' and facts.paid_at is None
    with pytest.raises(ValueError, match='rimborso'):
        sumup_checkout_facts({**checkout, 'transactions': [{'status': 'REFUNDED'}]}, 'CHECKOUT-1', link)


@pytest.mark.parametrize('provider', ['paypal', 'sumup', 'satispay'])
@pytest.mark.parametrize('wrong_currency', [False, True])
def test_existing_verifier_uses_one_authenticated_response(link, monkeypatch, provider, wrong_currency):
    import requests
    from pct import pagamenti_verifica as verification
    currency = 'USD' if wrong_currency else 'EUR'
    source = {
        'paypal': dict(id='TX-1', status='COMPLETED', custom_id=link.id,
                       amount={'value': '600.00', 'currency_code': currency}, update_time='2026-10-19T12:00:00Z'),
        'sumup': dict(id='TX-1', status='PAID', checkout_reference=link.id,
                      amount='600.00', currency=currency, date='2026-10-19T12:00:00Z'),
        'satispay': dict(id='TX-1', type='TO_BUSINESS', status='ACCEPTED',
                        amount_unit=60000, currency=currency, metadata={'link_id': link.id},
                        insert_date='2026-10-19T12:00:00Z'),
    }[provider]
    calls = []

    def get(url, *, headers, timeout):
        calls.append((url, headers, timeout))
        return SimpleNamespace(status_code=200, json=lambda: source)

    monkeypatch.setattr(requests, 'get', get)
    monkeypatch.setattr(verification, '_firma_satispay', lambda *args: {'Authorization': 'CONTROLLED-SIGNATURE'})
    gp = SimpleNamespace(paypal_token=lambda: 'CONTROLLED-TOKEN', config=SimpleNamespace(
        paypal=SimpleNamespace(base_url='https://api-m.sandbox.paypal.com'),
        sumup=SimpleNamespace(api_key='CONTROLLED-KEY'),
        satispay=SimpleNamespace(base_url='https://staging.authservices.satispay.com',
                                 key_id='CONTROLLED-KEY', private_key_pem='CONTROLLED-PEM')))
    verify = getattr(verification, provider + '_pagamento_confermato')
    if wrong_currency:
        with pytest.raises(ValueError):
            verify(gp, 'TX-1', link, evidence=True)
    else:
        facts = verify(gp, 'TX-1', link, evidence=True)
        assert facts.provider == provider and facts.transaction_id == 'TX-1'
        assert facts.amount_cents == 60000 and facts.currency == 'EUR'
        assert 'CONTROLLED-TOKEN' not in facts.source_json and 'CONTROLLED-KEY' not in facts.source_json
    assert len(calls) == 1 and calls[0][2] == verification.TIMEOUT
    assert calls[0][1].get('Authorization')


@pytest.mark.parametrize('amount,expected', [(1.13, 113), (19.99, 1999), (600.01, 60001)])
def test_stripe_creation_does_not_truncate_binary_floating_point_cents(tmp_path, monkeypatch, amount, expected):
    import sys
    from pct.pagamenti import GestionePagamenti
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(url='https://checkout.stripe.com/controlled')

    monkeypatch.setitem(sys.modules, 'stripe', SimpleNamespace(checkout=SimpleNamespace(
        Session=SimpleNamespace(create=create))))
    gp = GestionePagamenti(str(tmp_path / 'controlled-links'))
    payment = gp.crea_link('INVOICE-1', 'CLIENT-1', amount, 'CONTROLLED')
    assert gp.stripe_crea_sessione(payment, 'https://example.test/success', 'https://example.test/cancel')
    assert len(calls) == 1
    assert calls[0]['line_items'][0]['price_data']['unit_amount'] == expected


def test_paypal_capture_from_authenticated_order_keeps_its_real_identity(link):
    order = {'id': 'ORDER-1', 'status': 'APPROVED', 'purchase_units': [
        {'custom_id': link.id, 'amount': {'value': '600.00', 'currency_code': 'EUR'}}]}
    capture = {'id': 'CAPTURE-1', 'status': 'COMPLETED', 'amount': {'value': '600.00', 'currency_code': 'EUR'},
               'create_time': '2026-10-19T10:00:00Z', 'update_time': '2026-10-19T10:00:01Z'}
    response = {'id': 'ORDER-1', 'status': 'COMPLETED', 'purchase_units': [{'payments': {'captures': [capture]}}]}
    facts = paypal_order_capture_facts(response, order, link)
    assert facts.transaction_id == 'CAPTURE-1' and facts.cash_date() == '2026-10-19'
    assert 'verified_order_custom_id' in facts.source_json
    assert '"custom_id":null' in facts.source_json  # Non inventarlo nella cattura che lo omette.
    with pytest.raises(ValueError):
        paypal_order_capture_facts({**response, 'id': 'ANOTHER-ORDER'}, order, link)
    with pytest.raises(ValueError):
        paypal_order_capture_facts({**response, 'status': 'APPROVED'}, order, link)
    altered = {**capture, 'amount': {'value': '599.00', 'currency_code': 'EUR'}}
    with pytest.raises(ValueError):
        paypal_order_capture_facts({**response, 'purchase_units': [{'payments': {'captures': [altered]}}]}, order, link)


@pytest.mark.parametrize('expiry,valid', [
    ('2000-01-01T12:00:00+02:00', False),
    ('2999-01-01T12:00:00+02:00', True),
    ('2000-01-01T12:00:00', False),
    ('data-non-valida', False),
])
def test_link_expiration_respects_timezone_and_rejects_invalid_dates(expiry, valid):
    from pct.pagamenti import LinkPagamento
    payment = LinkPagamento('L', 'T', 'I', 'C', 10, 'Controllato', scade_il=expiry)
    assert payment.is_valido is valid


@pytest.mark.parametrize(('created', 'confirmed', 'expected'), [
    ('2026-10-19T23:30:00+00:00', '2026-10-20T00:30:00+00:00', '2026-10-20'),
    ('2026-10-19T21:59:00+00:00', '2026-10-19T22:01:00+00:00', None),
    ('2026-10-18T10:00:00+00:00', '2026-10-19T10:00:00+00:00', None),
])
def test_stripe_delayed_notification_never_substitutes_event_time_for_payment(link, created, confirmed, expected):
    session = {'id': 'cs_day', 'payment_status': 'paid', 'amount_total': 60000, 'currency': 'eur',
               'created': int(datetime.fromisoformat(created).timestamp()), 'metadata': {'link_id': link.id}}
    facts = stripe_facts(session, link, verified_event_created=int(datetime.fromisoformat(confirmed).timestamp()),
                         observed_at='2026-10-20T06:00:00Z')
    assert facts.paid_on == expected and facts.paid_at is None
    if expected:
        assert facts.cash_date() == expected
    else:
        with pytest.raises(ValueError): facts.cash_date()



def test_sumup_reuses_the_relevant_successful_transaction_without_checkout_date_assumptions(link):
    transaction = {'id': 'TX-REAL', 'status': 'SUCCESSFUL', 'amount': 600, 'currency': 'EUR',
                   'timestamp': '2026-10-20T06:00:00Z'}
    checkout = {'id': 'CHECKOUT-1', 'status': 'PAID', 'checkout_reference': link.id, 'amount': 600,
                'currency': 'EUR', 'date': '2026-10-18T10:00:00Z', 'transactions': [transaction]}
    facts = sumup_checkout_facts(checkout, 'CHECKOUT-1', link, observed_at='2026-10-20T07:00:00Z')
    assert facts.cash_date() == '2026-10-20' and facts.paid_at is None
    for invalid in ([{**transaction, 'amount': 599}], [transaction, {**transaction, 'id': 'ANOTHER'}],
                    [{**transaction, 'status': 'PENDING'}]):
        with pytest.raises(ValueError):
            sumup_checkout_facts({**checkout, 'transactions': invalid}, 'CHECKOUT-1', link)
