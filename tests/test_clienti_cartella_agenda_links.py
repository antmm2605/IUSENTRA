from types import SimpleNamespace

import pytest

from web.services.react_cliente_agenda import appuntamenti_cartella


def _case(**values):
    return SimpleNamespace(**dict(id='F1', numero_rg='821', anno_rg=2024,
                                 source_external_id='quickorganizer:93',
                                 id_cliente='C1', nome_cliente='Alessi Giovanna',
                                 tribunale='Tribunale di Brescia', **values))


def _appointment(**values):
    data = dict(id='A1', id_cliente='', procedimento='RG 821/2024',
                cliente='Alessi Giovanna', tribunale='Tribunale di Brescia',
                data_ora='2026-10-06T09:00:00')
    data.update(values)
    return SimpleNamespace(**data)


def _linked(*items):
    agenda = SimpleNamespace(tutti=lambda: list(items),
                             per_cliente=lambda cid: [a for a in items if a.id_cliente == cid])
    return appuntamenti_cartella(agenda, [_case()], 'C1')


@pytest.mark.parametrize('rg', ['RG 1821/2024', 'RG 13821/2024', 'RG 806/2026'])
def test_substrings_and_random_identifiers_are_not_case_links(rg):
    app = _appointment(procedimento=rg, cliente='Altra persona',
                       tribunale='Tribunale di Palmi', note='Citazione 821',
                       external_uid='PEC:ab821cd', external_source_url='/pec/ab821cd')
    assert _linked(app) == []


def test_complete_rg_and_client_name_are_kept_without_client_id():
    app = _appointment(cliente='ALESSI GIOVANNA', tribunale='Ufficio giudiziario civile')
    assert _linked(app) == [app]


def test_complete_rg_and_exact_court_are_kept():
    app = _appointment(cliente='')
    assert _linked(app) == [app]


def test_same_rg_at_different_court_and_client_is_not_a_link():
    assert _linked(_appointment(cliente='Altra persona', tribunale='Tribunale di Palmi')) == []


def test_conflicting_explicit_client_id_is_not_reassigned():
    assert _linked(_appointment(id_cliente='OTHER')) == []


def test_existing_client_relationship_is_preserved_for_non_case_appointments():
    app = _appointment(id_cliente='C1', procedimento='', titolo='Consultazione cliente')
    assert _linked(app) == [app]


@pytest.mark.parametrize('link', [dict(external_profile_id='fascicolo:F1'),
                                  dict(external_source_url='quickorganizer:93')])
def test_exact_case_identifiers_are_preserved(link):
    app = _appointment(procedimento='', cliente='', tribunale='', **link)
    assert _linked(app) == [app]


def test_another_explicit_case_profile_is_not_associated_by_text():
    assert _linked(_appointment(external_profile_id='fascicolo:OTHER')) == []


def test_appointment_linked_by_client_and_rg_is_not_duplicated():
    app = _appointment(id_cliente='C1')
    assert _linked(app) == [app]
