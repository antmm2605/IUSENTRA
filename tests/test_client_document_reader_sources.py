"""Provenienza della lettura distinta dai pesi delle regole del parser."""

from datetime import date
import hashlib
from types import SimpleNamespace

import pytest

from web.services import client_document_reader as reader


PAPER = "CARTA D'IDENTITA\nN. AB1234567\n"
PERSON = 'COGNOME ROSSI\nNOME MARIO\n'
CODE = 'RSSMRA80A01H501U'


def source(text, mode='ocr', page=1):
    return {'text': text, 'mode': mode, 'page_number': page}


def test_isolated_ocr_name_is_visible_for_review_but_not_applied():
    text = PAPER + 'NOME MARLO\n'
    result = reader.parse_client_document_text(text, identity_sources=[source(text)])
    assert 'nome' not in result['patch']
    name = next(row for row in result['fields'] if row['name'] == 'nome')
    assert name['value'] == 'Marlo' and name['status'] == 'da verificare'
    assert any('riscontro del titolare' in warning for warning in result['warnings'])


def test_generic_parser_and_native_single_name_keep_their_contract():
    text = 'NOME MARIO\n'
    assert reader.parse_client_document_text(text)['patch']['nome'] == 'Mario'
    assert reader.parse_client_document_text(text, identity_sources=[source(text, 'native')])['patch']['nome'] == 'Mario'
    assert 'nome' not in reader.parse_client_document_text(text, identity_sources=[])['patch']


def test_complete_raw_pair_different_from_recovery_keeps_holder_ambiguous():
    raw = PAPER + 'COGNOME ROSSO\nNOME MARLO\n'
    checked = PAPER + PERSON
    result = reader.parse_client_document_text(raw + checked,
        identity_sources=[source(raw), source(checked, 'recovery')])
    assert result['patch'] == {}
    assert any('variante OCR grezza' in warning for warning in result['warnings'])
    assert any('titolari distinti' in warning for warning in result['warnings'])


def test_complete_recovery_can_corroborate_a_single_raw_name():
    raw = PAPER + 'NOME MARLO\n'
    checked = PAPER + PERSON
    result = reader.parse_client_document_text(raw + checked,
        identity_sources=[source(raw), source(checked, 'recovery')])
    assert result['patch']['nome'] == 'Mario' and result['patch']['cognome'] == 'Rossi'


def test_other_raw_front_never_donates_birthdate_to_qualified_holder():
    raw = 'COGNOME BIANCHI\nNOME ANNA\nNATO IL 02/02/1990\n'
    checked = PAPER + PERSON
    for front in (raw, PAPER + raw):
        result = reader.parse_client_document_text(front + '\n' + checked,
            identity_sources=[source(front), source(checked, 'recovery', 2)])
        assert result['patch'] == {}
        assert any('titolari distinti' in warning for warning in result['warnings'])


def test_repeated_concordant_raw_pair_is_not_a_second_holder():
    raw = PAPER + PERSON + 'NATO IL 01/01/1980\n'
    checked = PAPER + PERSON
    result = reader.parse_client_document_text(raw + checked,
        identity_sources=[source(raw), source(checked, 'recovery', 2)])
    assert result['patch']['nome'] == 'Mario'
    assert result['patch']['cognome'] == 'Rossi'
    assert result['patch']['data_nascita'] == '1980-01-01'
    assert not any('titolari distinti' in warning for warning in result['warnings'])


def test_distinct_qualified_holders_without_codes_still_block_every_field():
    first = PAPER + PERSON
    second = PAPER + 'COGNOME BIANCHI\nNOME ANNA\n'
    result = reader.parse_client_document_text(first + second,
        identity_sources=[source(first, 'recovery'), source(second, 'recovery', 2)])
    assert result['patch'] == {} and 'titolari distinti' in result['message']


def test_distinct_qualified_fiscal_codes_still_block_every_field():
    first = PAPER + PERSON + 'CODICE FISCALE ' + CODE
    second = PAPER + 'COGNOME BIANCHI\nNOME ANNA\nCODICE FISCALE BNCNNA90C41H501X'
    result = reader.parse_client_document_text(first + '\n' + second,
        identity_sources=[source(first, 'recovery'), source(second, 'recovery', 2)])
    assert result['patch'] == {} and 'codici fiscali di più titolari' in result['message']


def test_birthdate_requires_literal_qualified_date_and_matching_holder_cf():
    raw = PAPER + PERSON + 'NATO IL 01/01/2020\n'
    checked = ('TESSERA SANITARIA\n' + PERSON + '01/01/1980' + CODE
               + '\nData di nascita\nCODICE FISCALE ' + CODE)
    result = reader.parse_client_document_text(raw + checked,
        identity_sources=[source(raw), source(checked, 'recovery', 2)])
    assert result['patch']['data_nascita'] == '1980-01-01'
    assert any('variante OCR grezza' in warning for warning in result['warnings'])
    for changed in (checked.replace('01/01/1980', '02/01/1980'), checked.replace('01/01/1980', ''),
                    checked.replace('01/01/1980', '01/01/19805')):
        result = reader.parse_client_document_text(raw + changed,
            identity_sources=[source(raw), source(changed, 'recovery', 2)])
        assert 'data_nascita' not in result['patch']
        assert any('incompatibile con il codice fiscale' in warning for warning in result['warnings'])


def test_fiscal_birthdate_check_does_not_choose_a_century():
    raw = PAPER + PERSON + 'NATO IL 01/01/1880\n'
    checked = 'TESSERA SANITARIA\n' + PERSON + 'DATA DI NASCITA\nCODICE FISCALE ' + CODE
    result = reader.parse_client_document_text(raw + checked,
        identity_sources=[source(raw), source(checked, 'recovery', 2)])
    assert result['patch']['data_nascita'] == '1880-01-01'


def test_residence_label_is_not_a_second_nationality():
    text = PAPER + PERSON + 'CITTADINANZA ITALIANA\n' + PAPER + PERSON + 'CITTADINANZA ITALIANA ROMA(RM) Residenra\n'
    result = reader.parse_client_document_text(text)
    assert result['patch']['nazionalita'] == 'Italiana'
    assert not any('discordanti per nazionalità' in warning for warning in result['warnings'])


def test_qualified_expiry_disagreement_is_not_silently_resolved():
    first = PAPER + PERSON + 'SCADE IL 01/01/2030\n'
    second = PAPER + PERSON + 'SCADE IL 02/02/2031\n'
    result = reader.parse_client_document_text(first + second,
        identity_sources=[source(first, 'native'), source(second, 'recovery')])
    assert 'doc_data_scadenza' not in result['patch']
    assert any('discordanti per data scadenza' in warning for warning in result['warnings'])


def test_upload_transports_sources_and_keeps_legacy_extractor_test_contract(monkeypatch):
    text = PAPER + 'NOME MARLO\n'
    monkeypatch.setattr(reader, '_extract_text', lambda *_: (text, '', [source(text)]))
    assert 'nome' not in reader.read_client_document_bytes(b'controlled', 'document.pdf')['patch']
    monkeypatch.setattr(reader, '_extract_text', lambda *_: (text, ''))
    assert reader.read_client_document_bytes(b'controlled', 'document.pdf')['patch']['nome'] == 'Marlo'


def test_archived_sources_are_preserved_and_never_invented():
    item = source(PAPER + PERSON, 'recovery')
    for page in ({'identity_sources': [item]}, SimpleNamespace(identity_sources=[item])):
        assert reader._archived_identity_sources(SimpleNamespace(pages=[page])) == [item]
    assert reader._archived_identity_sources(SimpleNamespace(text=PAPER)) == []


@pytest.mark.parametrize('with_metadata', [False, True])
def test_case_reading_uses_provenance_and_does_not_repeat_finished_recovery(monkeypatch, with_metadata):
    from legal_ocr.motore.identita import RECUPERO_IDENTITA_VERSIONE
    from pct.document_intelligence.service import IDENTITY_PROVENANCE_MARKER
    from web.services import fascicolo_documento_ocr

    raw = b'controlled identity source'
    text = PAPER + 'NOME MARLO\nCITTADINANZA ITALIANA\n'
    page = SimpleNamespace(identity_sources=[source(text)] if with_metadata else [])
    extracted = SimpleNamespace(text=text, pages=[page], warnings=[
        f'Recupero identità {RECUPERO_IDENTITA_VERSIONE}: tentativi finiti.', IDENTITY_PROVENANCE_MARKER])
    doc = SimpleNamespace(id='d', nome='carta.pdf', nome_originale='')
    case = SimpleNamespace(id='f', id_cliente='c', documenti=[doc])
    record = SimpleNamespace(status='ready', original_filename='carta.pdf', id='r',
                             current_version_id='v', sha256=hashlib.sha256(raw).hexdigest())
    manager = SimpleNamespace(get=lambda _: case)
    repository = SimpleNamespace(list_documents=lambda *_: [record], get_extracted_text=lambda *_: extracted)
    service = SimpleNamespace(reacquire_existing_version=lambda *_args, **_kwargs: pytest.fail('Recupero già concluso'))
    monkeypatch.setattr(fascicolo_documento_ocr, 'leggi_documento', lambda *_: ('carta.pdf', raw))
    result = reader.read_client_case_document(manager, repository, 'tenant', 'f', 'c', 'd', service=service)
    assert 'nome' not in result['patch']
    assert next(row for row in result['fields'] if row['name'] == 'nome')['status'] == 'da verificare'
    assert result['source_document']['sha256'] == record.sha256


@pytest.fixture
def fixed_today(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 10, 9)
    monkeypatch.setattr(reader, 'date', FixedDate)


@pytest.mark.parametrize(('label', 'field'), [('NATO IL', 'data_nascita'), ('DATA RILASCIO', 'doc_data_rilascio')])
def test_future_birth_and_issue_are_excluded_without_changing_the_year(fixed_today, label, field):
    result = reader.parse_client_document_text(PAPER + PERSON + label + ' 10/10/2026')
    assert field not in result['patch'] and not any(row['name'] == field for row in result['fields'])
    assert any('futura rispetto a oggi' in warning for warning in result['warnings'])
    assert reader.parse_client_document_text(PAPER + PERSON + label + ' 09/10/2026')['patch'][field] == '2026-10-09'


def test_issue_after_expiry_does_not_choose_which_date_is_right(fixed_today):
    result = reader.parse_client_document_text(PAPER + PERSON + 'DATA RILASCIO 01/01/2020\nSCADENZA 01/01/2013')
    assert 'doc_data_rilascio' not in result['patch'] and 'doc_data_scadenza' not in result['patch']
    assert any('entrambe le letture' in warning for warning in result['warnings'])
    expired = reader.parse_client_document_text(PAPER + PERSON + 'DATA RILASCIO 01/01/2001\nSCADENZA 01/01/2013')
    assert expired['patch']['doc_data_scadenza'] == '2013-01-01'


def test_invalid_variant_does_not_erase_concordant_valid_date(fixed_today):
    text = ('CARTA DI IDENTITA / IDENTITY CARD\nCA12345AA\n' + PERSON
        + 'EMISSIONE / ISSUING SCADENZA / EXPIRY\n01/01/2020 01/01/2030\n'
        + 'EMISSIONE / ISSUING SCADENZA / EXPIRY\n31/02/2020 01/01/2030\n')
    result = reader.parse_client_document_text(text)
    assert result['patch']['doc_data_rilascio'] == '2020-01-01'
    assert result['patch']['doc_data_scadenza'] == '2030-01-01'
    assert any('calendario valida' in warning for warning in result['warnings'])
