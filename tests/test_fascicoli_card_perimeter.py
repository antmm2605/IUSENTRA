"""Guardrail sui conteggi e sui filtri, non sostituisce la prova UI reale."""
from tests.test_fascicoli_pagination import _seed_fascicoli
from tests.test_react_shell import _app
from web.services import react_fascicoli_bridge as bridge
from pathlib import Path
from tempfile import TemporaryDirectory


def test_card_counts_keep_common_search_when_category_has_no_rows(tmp_path):
    app = _app(tmp_path)
    _seed_fascicoli(app, 11)
    headers = {"X-API-Key": "react-test-key"}
    with app.test_client() as client:
        empty = client.get('/api/v1/ui/fascicoli?q=Pratica+paginata&duplicates_only=1', headers=headers)
        active = client.get('/api/v1/ui/fascicoli?q=Pratica+paginata', headers=headers)
        current = client.get('/api/v1/ui/fascicoli?q=Pratica+paginata&status=in_corso', headers=headers)
        closed = client.get('/api/v1/ui/fascicoli?q=Pratica+paginata&status=definito', headers=headers)
    assert empty.status_code == active.status_code == current.status_code == closed.status_code == 200
    cards = empty.get_json()['cardSummary']
    assert empty.get_json()['pagination']['total'] == 0
    assert cards['active'] == active.get_json()['pagination']['total'] == 11
    assert cards['inProgress'] == current.get_json()['pagination']['total']
    assert cards['toArchive'] == closed.get_json()['pagination']['total'] == 3
    assert active.get_json()['cardSummary'] == cards


def test_card_counts_honor_common_search_and_type(tmp_path):
    app = _app(tmp_path)
    _seed_fascicoli(app, 11)
    with app.test_client() as client:
        response = client.get('/api/v1/ui/fascicoli?q=Cliente+01&type=civile&duplicates_only=1', headers={"X-API-Key": "react-test-key"})
    assert response.status_code == 200
    assert response.get_json()['pagination']['total'] == 0
    assert response.get_json()['cardSummary']['active'] == 1


def test_communications_filter_does_not_include_document_alerts():
    document_alert = {'alerts': 2, 'unreadCommunications': 0}
    unread_message = {'alerts': 0, 'unreadCommunications': 2}
    assert bridge._matches_list_filters(document_alert, alerts_only=True)
    assert not bridge._matches_list_filters(document_alert, communications_only=True)
    assert bridge._matches_list_filters(unread_message, communications_only=True)
    assert bridge._matches_list_filters(unread_message, alerts_only=True)


def test_card_units_count_matters_separately_from_work_items():
    rows = [
        {'status': 'in_corso', 'unreadCommunications': 2, 'paymentSummary': {'parcelleDaEmettere': 2}},
        {'status': 'in_corso', 'unreadCommunications': 0, 'paymentSummary': {'proformaPresidio': {'existingDraftCount': 1}}},
        {'status': 'in_corso', 'unreadCommunications': 0, 'paymentSummary': {}},
    ]
    cards = bridge._summary(rows)
    assert cards['invoiceWorkTotal'] == 3
    assert cards['invoiceMattersToReview'] == sum(bridge._matches_list_filters(row, payment_filters={'parcella': 'da_emettere'}) for row in rows) == 2
    assert cards['unreadCommunications'] == 2
    assert cards['communicationMatters'] == sum(bridge._matches_list_filters(row, communications_only=True) for row in rows) == 1


def test_communications_category_has_distinct_server_cache_key(tmp_path):
    common = dict(query='', client_filter='', rg_filter='', type_filter='', status_filter='', court='', sort='rg', secondary_sort='', group_by='', view='', alerts_only=False, payments_only=False, missing_rg_only=False, duplicates_only=False, payment_filters={}, field_filters={})
    app = _app(tmp_path)
    with app.app_context():
        assert bridge._fascicoli_base_cache_key(**common, communications_only=False) != bridge._fascicoli_base_cache_key(**common, communications_only=True)


if __name__ == '__main__':
    tests = [test_card_counts_keep_common_search_when_category_has_no_rows,
             test_card_counts_honor_common_search_and_type,
             test_communications_category_has_distinct_server_cache_key]
    for test in tests:
        with TemporaryDirectory(prefix='iusentra-card-guard-') as directory:
            test(Path(directory))
    test_communications_filter_does_not_include_document_alerts()
    test_card_units_count_matters_separately_from_work_items()
    print('5 controlli indicatori/filtri superati su dati isolati; prova UI distinta.')
