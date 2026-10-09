import pytest

from legal_ocr.motore.identita import _identita_riquadri


def _read(text, profile):
    return text, [], profile


def test_two_faces_link_by_literal_document_number_and_icao_digit():
    rows = [_read('IDENTITY CARD CA12345AA', ('cie', 'CA12345AA')),
            _read('CODICE FISCALE\n## C<ITACA12345AA7<<<<<<<<<<<<<<<', ('cie_rear', 'RSSMRA80A01H501U'))]
    assert _identita_riquadri(rows) == {('cie', 'CA12345AA')}


def test_adjacent_rear_without_number_proof_is_not_linked():
    rows = [_read('CA12345AA', ('cie', 'CA12345AA')),
            _read('CODICE FISCALE RSSMRA80A01H501U', ('cie_rear', 'RSSMRA80A01H501U'))]
    assert len(_identita_riquadri(rows)) == 2


def test_bad_digit_or_different_number_does_not_join_faces():
    for line in ('C<ITACA12345AA8<<<<<<<<<<<<<<<', 'C<ITACA19377QY5<<<<<<<<<<<<<<<'):
        rows = [_read('CA12345AA', ('cie', 'CA12345AA')),
                _read(line, ('cie_rear', 'RSSMRA80A01H501U'))]
        assert len(_identita_riquadri(rows)) == 2


def test_two_verified_distinct_cards_remain_distinct():
    rows = [_read('CA12345AA', ('cie', 'CA12345AA')),
            _read('CA19377QY', ('cie', 'CA19377QY'))]
    assert len(_identita_riquadri(rows)) == 2


def test_unreadable_nationality_does_not_block_verified_mrz_fields():
    from web.services.client_document_reader import parse_client_document_text

    result = parse_client_document_text(
        'C<ITACA12345AA7<<<<<<<<<<<<<<< '
        '8001014M30010191TA<<<<<<<<<<<8 '
        'ROSSI<<MARIO<<<<<<<<<<<<<<<<<<')
    assert 'nazionalita' not in result['patch']
    assert result['patch']['cognome'] == 'Rossi'
    assert result['patch']['nome'] == 'Mario'
    assert result['patch']['doc_numero'] == 'CA12345AA'
    assert result['patch']['data_nascita'] == '1980-01-01'
    assert result['patch']['doc_data_scadenza'] == '2030-01-01'
    assert result['warnings']


@pytest.mark.parametrize(('accepted_size', 'preserve', 'expected_calls'), [
    ((372, 88), False, [((93, 22), True), ((372, 88), True), ((372, 88), False)]),
    ((93, 38), True, [((93, 22), True), ((372, 88), True), ((372, 88), False), ((93, 38), True)]),
])
def test_issue_date_retries_finite_regions_and_stops_after_verified_value(monkeypatch, accepted_size, preserve, expected_calls):
    from types import SimpleNamespace
    from PIL import Image
    import legal_ocr.motore.identita as reader
    import legal_ocr.motore.immagine as preparation

    monkeypatch.setattr(preparation, 'diagnostica_zona_testo', lambda _: SimpleNamespace(escursione=1))
    monkeypatch.setattr(preparation, 'scala_caratteri_zona', lambda _: 4)
    monkeypatch.setattr(preparation, 'passaggi_diagnosi_zona', lambda _: [])
    monkeypatch.setattr(preparation, 'separa_sfondo_zona_testo', lambda *_args, **_kwargs: None)
    calls = []

    def read(image, **options):
        calls.append((image.size, options['preserva_risoluzione']))
        if image.size == accepted_size and options['preserva_risoluzione'] is preserve:
            return SimpleNamespace(confidenza=.98, testo='EMISSIONE ASSUING\n20.02.2020')
        return None

    monkeypatch.setattr(reader, 'leggi_con_secondo_lettore', read)
    known = ('COMUNE ROMA\nCOGNOME / SURNAME ROSSI NOME / NAME MARIO\n'
             'LUOGO NASCITA 01.01.1980\nSEX M\nNATIONALITY ITA\nSCADENZA / EXPIRY 01.01.2030')
    with Image.new('RGB', (300, 200), 'white') as source:
        original = source.tobytes()
        text, _ = reader._leggi_zone_cie(source, 0, 0, 300, 200, 0, Image, known_text=known)
        assert source.tobytes() == original
    assert text.count('20.02.2020') == 1
    assert calls == expected_calls
