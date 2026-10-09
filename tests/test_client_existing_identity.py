from types import SimpleNamespace as S

import pytest

from web.services import client_document_reader as reader


def test_existing_identity_uses_client_cases_and_preserves_source(monkeypatch):
    doc = S(id='d1', nome='Carta identità.pdf', nome_originale='', hash_contenuto_sha256='')
    case = S(id='case1', id_cliente='c1', documenti=[doc])
    calls = []
    manager = S(cerca=lambda **kwargs: calls.append(kwargs) or [case])
    repo = S(list_catalog_assignments=lambda *_: [])
    monkeypatch.setattr(reader, 'read_client_case_document', lambda *args, **kwargs: {'source': args[3:6]})
    result = reader.read_client_existing_document(manager, repo, 'tenant', 'c1')
    assert calls == [{'id_cliente': 'c1', 'archiviati': True}]
    assert result['source'] == ('case1', 'c1', 'd1')


def test_existing_identity_never_selects_other_client(monkeypatch):
    doc = S(id='d1', nome='Carta identità.pdf', nome_originale='', hash_contenuto_sha256='')
    manager = S(cerca=lambda **_: [S(id='case1', id_cliente='other', documenti=[doc])])
    repo = S(list_catalog_assignments=lambda *_: pytest.fail('Altri clienti non devono essere consultati'))
    with pytest.raises(reader.ClientDocumentReaderError):
        reader.read_client_existing_document(manager, repo, 'tenant', 'c1')


def test_existing_identity_deduplicates_same_current_bytes(monkeypatch):
    def case(fid):
        return S(id=fid, id_cliente='c1', documenti=[S(id='d', nome='Carta.pdf', nome_originale='', hash_contenuto_sha256='sha')])
    assignment = S(document_id='d', document_sha256='sha', document_nature='documento_identita',
                   metadata={'identity_client_id': 'c1', 'identity_holder': 'Mario Rossi'})
    manager = S(cerca=lambda **_: [case('f1'), case('f2')])
    repo = S(list_catalog_assignments=lambda *_: [assignment])
    monkeypatch.setattr(reader, 'read_client_case_document', lambda *args, **kwargs: args[3])
    assert reader.read_client_existing_document(manager, repo, 'tenant', 'c1') == 'f1'


def test_existing_identity_requires_choice_for_distinct_documents():
    docs = [S(id=did, nome='Carta identità.pdf', nome_originale='', hash_contenuto_sha256='') for did in ('a', 'b')]
    manager = S(cerca=lambda **_: [S(id='f1', id_cliente='c1', documenti=docs)])
    repo = S(list_catalog_assignments=lambda *_: [])
    with pytest.raises(reader.ClientDocumentReaderError, match='più documenti'):
        reader.read_client_existing_document(manager, repo, 'tenant', 'c1')


def test_archived_cie_mrz_single_line_survives_unreadable_heading():
    from pct.document_intelligence.catalog_identita_personale import documento_identita_personale
    text = ("REPUBBLICA ITALIANA\nCRTA D DENTTA/IDENTY CARD\nCognome Nome\n"
            "C<ITACA12345AA7<<<<<<<<<<<<<<< 8001014m3001019ITA<<<<<<<<<<<8 ROSSI<<MARIO<<<<<<<<<<<<<<<<<<")
    identity = documento_identita_personale(text, cliente='Rossi Mario')
    assert identity['titolare'] == 'Rossi Mario'
    patch = reader.parse_client_document_text(text)['patch']
    assert patch['nome'] == 'Mario'
    assert patch['cognome'] == 'Rossi'
    assert patch['doc_numero'] == 'CA12345AA'
    assert patch['data_nascita'] == '1980-01-01'


def test_existing_identity_does_not_fill_discordant_fiscal_code():
    client = S(nome='Mario', cognome='Rossi', nome_completo='Rossi Mario', codice_fiscale='RSSMRA80A01H501U')
    text = "CARTA D'IDENTITA\nCOGNOME ROSSI\nNOME MARIO\nCODICE FISCALE RSSMRA80A01H501U"
    result = reader.parse_client_document_text(text)
    result['patch']['codice_fiscale'] = 'DIFFERENT'
    with pytest.raises(reader.ClientDocumentReaderError, match='discordante'):
        reader._verify_client_identity(text, result, client)


def test_matching_fiscal_code_never_overwrites_names_from_confused_ocr_labels():
    client = S(nome='Mario', cognome='Rossi', nome_completo='Rossi Mario', codice_fiscale='RSSMRA80A01H501U')
    text = "CARTA D'IDENTITA\nCOGNOME ROSSI\nNOME MARIO\nCODICE FISCALE RSSMRA80A01H501U"
    result = reader.parse_client_document_text(text)
    result['patch']['nome'] = 'Nome Mario'
    reader._verify_client_identity(text, result, client)
    assert 'nome' not in result['patch'] and 'cognome' not in result['patch']
    assert not any(field['name'] in ('nome', 'cognome') for field in result['fields'])
    assert result['patch']['codice_fiscale'] == client.codice_fiscale
    assert any('conservati' in warning for warning in result['warnings'])
