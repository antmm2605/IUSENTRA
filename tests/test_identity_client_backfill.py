from types import SimpleNamespace as S

from scripts.associa_documenti_identita_clienti import associate_case


def fixtures():
    text = "CARTA D'IDENTITA\nCOMUNE DI ROMA\nCognome ROSSI\nNome MARIO\nCodice fiscale RSSMRA80A01H501U\nScadenza 01/01/2030"
    case = S(id='case', id_cliente='client', documenti=[S(id='doc', nome='Carta.pdf', nome_originale='')])
    client = S(id='client', nome='Mario', cognome='Rossi', nome_completo='Rossi Mario', codice_fiscale='RSSMRA80A01H501U')
    record = S(id='record', sha256='current', status='ready', current_version_id='v', safe_filename='Carta.pdf',
               file_type='pdf', mime_type='application/pdf', size_bytes=100, updated_at='2026-10-08T00:00:00Z')
    repo = S(list_documents=lambda *_: [record], list_catalog_assignments=lambda *_: [],
             get_extracted_text=lambda *_: S(text=text))
    objects = [S(oggetto_id='doc', tipo='documento', presente=True, sha256='current', sha256_archivio='')]
    return case, client, repo, objects


def test_backfill_rejects_changed_source_fingerprint():
    case, client, repo, objects = fixtures()
    objects[0].sha256 = 'different'
    result = associate_case(case, client, repo, objects, 'tenant')
    assert result['candidates'] == []


def test_backfill_reports_identity_named_document_with_unrecognized_current_text():
    case, client, repo, objects = fixtures()
    case.documenti[0].nome = "Carta d'identità.pdf"
    repo.get_extracted_text = lambda *_: S(text='Testo incompleto non riconosciuto')
    result = associate_case(case, client, repo, objects, 'tenant')
    assert result['candidates'] == []
    assert 'non riconosciuto' in result['unresolved'][0]['reason']


def test_backfill_rejects_different_valid_client_cf():
    case, client, repo, objects = fixtures()
    client.codice_fiscale = 'VRDLRA82B41H501U'
    result = associate_case(case, client, repo, objects, 'tenant')
    assert result['candidates'] == []
    assert result['unresolved'][0]['documento_id'] == 'doc'


def test_backfill_preserves_manual_assignment():
    case, client, repo, objects = fixtures()
    repo.list_catalog_assignments = lambda *_: [S(document_id='doc', document_sha256='current',
        metadata={}, status='confirmed', source_state='verified_snapshot')]
    result = associate_case(case, client, repo, objects, 'tenant')
    assert result['candidates'] == []
    assert result['unresolved'][0]['reason'] == 'Decisione manuale conservata.'
