"""Nessuna anagrafica composta scegliendo frammenti personali discordanti."""

import pytest

from web.services.client_document_reader import parse_client_document_text


PAPER = "COMUNE DI ROMA\nCARTA D'IDENTITA\nN. AB1234567\n"
FIRST = 'COGNOME ROSSI\nNOME MARIO\nNATO IL 01/01/1980\n'
SECOND = 'COGNOME VERDI\nNOME LUCA\nNATO IL 02/02/1970\n'


@pytest.mark.parametrize('separator', ['', "CARTA D'IDENTITA\n"])
def test_distinct_named_fronts_without_second_number_or_cf_do_not_mix(separator):
    result = parse_client_document_text(PAPER + FIRST + separator + SECOND)
    assert result['patch'] == {} and result['fields'] == [] and not result['ok']
    assert 'titolari distinti' in result['message']


def test_single_cf_on_only_one_front_does_not_prove_the_second_holder():
    result = parse_client_document_text(PAPER + FIRST + 'CODICE FISCALE RSSMRA80A01H501U\n'
                                        + "CARTA D'IDENTITA\n" + SECOND)
    assert result['patch'] == {} and 'titolari distinti' in result['message']


def test_same_person_repeated_or_split_across_pages_is_preserved():
    result = parse_client_document_text(FIRST + PAPER + FIRST + 'SCADE IL 01/01/2030\n')
    assert result['patch']['nome'] == 'Mario'
    assert result['patch']['cognome'] == 'Rossi'
    assert result['patch']['data_nascita'] == '1980-01-01'
    assert result['patch']['doc_data_scadenza'] == '2030-01-01'
    assert not any('discordanti' in warning for warning in result['warnings'])


def test_conflicting_expiry_never_silently_selects_the_first_date():
    result = parse_client_document_text(PAPER + FIRST + 'SCADE IL 01/01/2030\nSCADE IL 02/02/2031\n')
    assert 'doc_data_scadenza' not in result['patch']
    assert all(row['name'] != 'doc_data_scadenza' for row in result['fields'])
    assert result['patch']['nome'] == 'Mario'
    assert any('discordanti per data scadenza' in warning for warning in result['warnings'])


def test_repeated_equal_expiry_with_different_printed_separators_is_not_conflicting():
    result = parse_client_document_text(PAPER + FIRST + 'SCADE IL 01/01/2030\nSCADE IL 01.01.2030\n')
    assert result['patch']['doc_data_scadenza'] == '2030-01-01'
    assert not any('discordanti per data scadenza' in warning for warning in result['warnings'])


@pytest.mark.parametrize('identity', [PAPER, 'CARTA DI IDENTITA / IDENTITY CARD\nCA12345AA\n'])
def test_health_card_expiry_is_not_identity_card_expiry(identity):
    result = parse_client_document_text(identity + FIRST + 'SCADENZA 01/01/2030\n'
        'TESSERA SANITARIA\nCOGNOME ROSSI\nNOME MARIO\nSCADENZA 02/02/2031\n')
    assert result['patch']['doc_data_scadenza'] == '2030-01-01'
    assert result['patch']['nome'] == 'Mario'
    assert not any('discordanti per data scadenza' in warning for warning in result['warnings'])


def test_shared_cf_does_not_turn_conflicting_names_into_verified_names():
    code = 'CODICE FISCALE RSSMRA80A01H501U\n'
    result = parse_client_document_text(PAPER + FIRST + code + "CARTA D'IDENTITA\n" + SECOND + code)
    assert result['patch']['codice_fiscale'] == 'RSSMRA80A01H501U'
    assert 'nome' not in result['patch'] and 'cognome' not in result['patch']
    assert 'data_nascita' not in result['patch']
    assert any('discordanti per cognome' in warning for warning in result['warnings'])


def test_literal_name_disagreement_is_not_repaired_by_similarity():
    result = parse_client_document_text(PAPER + FIRST + "CARTA D'IDENTITA\n" + FIRST.replace('ROSSI', 'ROSSO'))
    assert result['patch'] == {} and 'titolari distinti' in result['message']


@pytest.mark.parametrize('second', [
    'EMISSIONE / ISSUING SCADENZA / EXPIRY\n01/01/2020 02/02/2031\n',
    'SCADENZA 02/02/2031\n',
])
def test_cie_paired_fields_keep_real_expiry_disagreements_visible(second):
    source = ('CARTA DI IDENTITA / IDENTITY CARD\nCA12345AA\n' + FIRST
        + 'EMISSIONE / ISSUING SCADENZA / EXPIRY\n01/01/2020 01/01/2030\n')
    baseline = parse_client_document_text(source)
    assert baseline['patch']['doc_data_rilascio'] == '2020-01-01'
    assert baseline['patch']['doc_data_scadenza'] == '2030-01-01'
    result = parse_client_document_text(source + second)
    assert 'doc_data_scadenza' not in result['patch']
    assert result['patch']['doc_data_rilascio'] == '2020-01-01'
    assert any('discordanti per data scadenza' in warning for warning in result['warnings'])
