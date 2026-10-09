from __future__ import annotations

from io import BytesIO
from pathlib import Path

from web.services.client_document_reader import parse_client_document_text
from tests.test_react_shell import _app


def test_comune_letto_non_esistente_o_provincia_discordante_non_applicato(monkeypatch):
    import web.services.client_document_reader as reader
    monkeypatch.setattr(reader, '_extract_visible_fields', lambda text: [
        ('comune', text, .94), ('provincia', 'RM', .94)])
    for value in ('Comune Inventato', 'Vicenza'):
        result = reader.parse_client_document_text(value)
        assert 'comune' not in result['patch']
        assert next(row for row in result['fields'] if row['name'] == 'comune')['status'] == 'da verificare'
        assert result['warnings']
    result = reader.parse_client_document_text('Roma')
    assert result['patch']['comune'] == 'Roma'
    assert result['geographic_checks']['comune']['stato'] == 'concordante'


def test_paper_labels_do_not_leak_into_name_or_nationality():
    result = parse_client_document_text(
        "CARTA D'IDENTITÀ\nCognome.ROSSI Nome...MARIO rato il..01/01/1980\n"
        "Cittadinanza. ITALIANA ResidenraROMA(RM)\n"
    )
    assert result['patch']['nome'] == 'Mario'
    assert result['patch']['nazionalita'] == 'Italiana'
    assert 'comune' not in result['patch']


def test_cie_degraded_birth_label_requires_same_card_mrz_and_exact_catalog_province():
    source = ('CARTA DI IDENTITA/IDENTITY CARD\nCA12345AA\n'
        'LUOGO EDATADINASIIA PLACEANO DATEOFBIRTR\nROMA(RM)01.01.1980\n'
        'C<ITACA12345AA7<<<<<<<<<<<<<<< 8001014M3001019ITA<<<<<<<<<<<8 ROSS I<<MARIO<<<<<<<<<<<<<<<<<<')
    source = source.replace('ROSS I', 'ROSSI')
    result = parse_client_document_text(source)
    assert result['patch']['luogo_nascita'] == 'Roma'
    assert result['patch']['provincia_nascita'] == 'RM'
    for changed in (source.replace('ROMA(RM)', 'ROMA(VI)'), source.replace('01.01.1980', '02.01.1980'),
                    source.replace('CA12345AA\n', 'CA54321AA\n')):
        assert 'luogo_nascita' not in parse_client_document_text(changed)['patch']


def test_cie_joined_birth_label_recovers_only_printed_values_with_same_card_checks():
    front = ('CARTA DI IDENTITA/IDENTITY CARD\nCA12345AA\n'
             'LUOGOEDATADINASUIA PLACEANODATEOFBIRTR\nROMA(RM)01.01.1980\n')
    rear = 'C<ITACA12345AA7<<<<<<<<<<<<<<< 8001014M3001019ITA<<<<<<<<<<<8 ROSSI<<MARIO<<<<<<<<<<<<<<<<<<'
    for label in ('PLACEANODATEOFBIRTR', 'PLACEANDDATEOFBIRTH'):
        current = front.replace('PLACEANODATEOFBIRTR', label)
        sources = [{'page_number': 1, 'mode': 'recovery', 'text': current},
                   {'page_number': 2, 'mode': 'recovery', 'text': rear}]
        result = parse_client_document_text(current + rear, identity_sources=sources)
        assert result['patch']['luogo_nascita'] == 'Roma'
        assert result['patch']['provincia_nascita'] == 'RM'
        assert result['geographic_checks']['luogo_nascita']['stato'] == 'concordante'
    for changed in (front.replace('ROMA(RM)', 'ROMA(VI)'), front.replace('01.01.1980', '02.01.1980'),
                    front.replace('CA12345AA\n', 'CA54321AA\n'), front.replace('ROMA(RM)', 'CITTA INVENTATA(RM)'),
                    front.replace('LUOGO', 'INDIRIZZO'), front.replace('PLACEANODATE', 'UPDATE')):
        sources = [{'page_number': 1, 'mode': 'recovery', 'text': changed},
                   {'page_number': 2, 'mode': 'recovery', 'text': rear}]
        result = parse_client_document_text(changed + rear, identity_sources=sources)
        assert 'luogo_nascita' not in result['patch']
        assert 'provincia_nascita' not in result['patch']


def test_cie_issuer_degraded_translation_requires_exact_existing_municipality():
    source = ('CARTA DI IDENTITA/IDENTITY CARD CA12345AA\n'
        'COMUNE DE/MINICIPAULY ROMA COGNOME / SURNAME ROSSI NOME / NAME MARIO')
    assert parse_client_document_text(source)['patch']['doc_rilasciato_da'] == 'Comune di Roma'
    assert 'doc_rilasciato_da' not in parse_client_document_text(source.replace('ROMA', 'CITTA INVENTATA'))['patch']
    assert 'doc_rilasciato_da' not in parse_client_document_text(source.replace('COMUNE', 'RESIDENZA'))['patch']


def test_cie_emission_zone_does_not_use_expiry_from_mixed_row():
    source = 'CARTA DI IDENTITA/IDENTITY CARD CA12345AA\nEMISSIONEASSUING\n\n20.02.2020'
    assert parse_client_document_text(source)['patch']['doc_data_rilascio'] == '2020-02-20'
    mixed = source.replace('EMISSIONEASSUING\n\n20.02.2020',
                           'SCADENZA EXPIRY EMISSIONE ASSUING 27.08.2030\n20.02.2020')
    assert 'doc_data_rilascio' not in parse_client_document_text(mixed)['patch']


def test_multiple_valid_cf_never_selects_first_holder():
    from web.services.client_document_reader import _find_cf
    from pct.codice_fiscale import _checksum
    first = 'RSSMRA80A01H501'
    second = 'VRDLGI80A01H501'
    first += _checksum(first)
    second += _checksum(second)
    assert _find_cf(first + '\n' + first) == first
    assert _find_cf(first + '\n' + second) == ''


def test_new_client_never_combines_fields_of_multiple_identity_holders():
    from pct.codice_fiscale import _checksum
    first = 'RSSMRA80A01H501'
    second = 'VRDLGI80A01H501'
    first += _checksum(first)
    second += _checksum(second)
    source = ("CARTA D'IDENTITÀ\nCognome ROSSI\nNome MARIO\nCodice fiscale "
              + first + "\nCARTA D'IDENTITÀ\nCognome VERDI\nNome LUIGI\nCodice fiscale " + second)
    result = parse_client_document_text(source)
    assert not result['ok'] and result['patch'] == {} and result['fields'] == []
    assert 'più titolari' in result['message']
    # Due copie o fronte/retro del medesimo titolare non sono due persone.
    duplicate = parse_client_document_text(source.replace(second, first))
    assert duplicate['patch']['codice_fiscale'] == first


def test_uploaded_identity_cannot_fill_another_existing_client(monkeypatch):
    from types import SimpleNamespace
    import pytest
    from web.services.client_document_reader import ClientDocumentReaderError, read_client_document_bytes
    text = "CARTA D'IDENTITÀ / IDENTITY CARD\nCOGNOME / SURNAME BIANCHI\nNOME / NAME ANNA\nCodice fiscale BNCNNA90C41H501X"
    monkeypatch.setattr('web.services.client_document_reader._extract_text', lambda *_: (text, ''))
    client = SimpleNamespace(nome='Mario', cognome='Rossi', nome_completo='Mario Rossi', codice_fiscale='RSSMRA80A01H501U')
    with pytest.raises(ClientDocumentReaderError):
        read_client_document_bytes(b'controlled', 'identita.pdf', client=client)
    assert client.nome == 'Mario' and client.codice_fiscale == 'RSSMRA80A01H501U'


def test_multiple_checked_mrz_cards_without_cf_never_select_first():
    first = 'I<UTOD231458907<<<<<<<<<<<<<<<'
    second = '7408122F1204159UTO<<<<<<<<<<<6'
    names = 'ERIKSSON<<ANNA<MARIA<<<<<<<<<<'
    source = '\n'.join((first, second, names))
    another = source.replace(names, 'ROSSI<<MARIO<<<<<<<<<<<<<<<<<<')
    result = parse_client_document_text(source + '\n' + another)
    assert not result['ok'] and result['patch'] == {} and result['fields'] == []
    assert 'MRZ verificate distinte' in result['message']
    assert parse_client_document_text(source + '\n' + source)['ok']


def test_mrz_check_digits_match_icao_published_examples() -> None:
    from web.services.client_document_reader import _mrz_check_digit, _parse_mrz_from_text
    assert _mrz_check_digit('520727', '3')
    assert _mrz_check_digit('AB2134<<<', '5')
    # ICAO 9303-3 Appendix A, published composite TD1 example.
    first = 'I<YTOD231458907<<<<<<<<<<<<<<<'
    second = '3407127M9507122YTO<<<<<<<<<<<2'
    names = 'ERIKSSON<<ANNA<MARIA<<<<<<<<<<<'
    assert _parse_mrz_from_text('\n'.join((first, second, names)))['detected']
    for row_index, position in ((0, 14), (1, 6), (1, 14), (1, 29)):
        rows = [first, second, names]
        row = rows[row_index]
        rows[row_index] = row[:position] + str((int(row[position]) + 1) % 10) + row[position + 1:]
        payload = parse_client_document_text('\n'.join(rows))
        assert not payload['mrz']['detected']
        assert 'doc_numero' not in payload['patch']
        assert any('MRZ non validata' in warning for warning in payload['warnings'])
    # Nationality and sex are outside the numeric check digits. A correct
    # checksum must not make OCR noise in those positions an accepted value.
    for position, noise, missing in ((7, '0', 'sesso'), (15, '1', 'nazionalita')):
        invalid = second[:position] + noise + second[position + 1:]
        payload = parse_client_document_text('\n'.join((first, invalid, names)))
        assert payload['mrz']['detected']
        assert missing not in payload['patch']
        assert payload['patch']['doc_numero'] == 'D23145890'
        assert any('non leggibile nella zona MRZ' in warning for warning in payload['warnings'])
    passport = 'YA12345676ITA8001014M3001019<<<<<<<<<<<<<<00'
    heading = 'P<ITAROSSI<<MARIO'.ljust(44, '<')
    for position, noise, missing in ((20, '0', 'sesso'), (10, '1', 'nazionalita')):
        invalid = passport[:position] + noise + passport[position + 1:]
        payload = parse_client_document_text(heading + '\n' + invalid)
        assert payload['mrz']['detected']
        assert payload['patch']['doc_numero'] == 'YA1234567'
        assert missing not in payload['patch']


def test_paper_identity_keeps_name_before_truncated_birth_label() -> None:
    text = "CARTA D'IDENTITA\nCognome.. ROSSI\nNome.. MARIO nat 01-01-198\nScade Il 01/01/2030"
    patch = parse_client_document_text(text)['patch']
    assert patch['nome'] == 'Mario'
    assert patch['cognome'] == 'Rossi'
    assert 'data_nascita' not in patch


def test_paper_identity_issuer_header_before_stamp_and_title() -> None:
    patch = parse_client_document_text(
        "COMVNE DI ROMA\nDiritti Euro 6,20\nCARTA D'IDENTITA\n"
        "Cognome: Rossi\nNome: Mario\nResidenza: MILANO\n"
    )['patch']
    assert patch['doc_rilasciato_da'] == 'Comune di Roma'
    assert 'doc_data_rilascio' not in patch


def test_mrz_zero_in_name_requires_independent_visible_word() -> None:
    from web.services.client_document_reader import _parse_mrz_from_text
    mrz = 'C<ITACA12345AA7<<<<<<<<<<<<<<< 8001014M3001019ITA<<<<<<<<<<<8 ROSS0<<MARIO<<<<<<<<<<<<<<<<<<'
    # Il nome proviene dalle due zone della fonte, mai dal cliente atteso.
    assert _parse_mrz_from_text('COGNOME ROSSO\n' + mrz)['patch']['cognome'].strip() == 'ROSSO'
    assert not _parse_mrz_from_text(mrz)['detected']
    assert not _parse_mrz_from_text('COGNOME ROSSI\n' + mrz)['detected']


def test_cie_bilingual_columns_are_values_not_labels() -> None:
    text = """REPUBBLICA ITALIANA CA12345AB
MINISTERO DELL'INTERNO
CARTA DI IDENTITA / IDENTITY CARD
COGNOME / SURNAME ROSSI
NOME / NAME MARIO LUOGO E DATA DI NASCITA PLACE AND DATE OF BIRTH
ROMA (RM) 01.01.1980
SESSO STATURA CITTADINANZA HEIGHT NATIONALITY SEX
M 175 ITA
EMISSIONE / ISSUING SCADENZA / EXPIRY
27.11.2024 01.01.2034 FIRMA DEL TITOLARE
"""
    patch = parse_client_document_text(text)["patch"]
    assert patch["cognome"] == "Rossi"
    assert patch["nome"] == "Mario"
    assert patch["data_nascita"] == "1980-01-01"
    assert patch["luogo_nascita"] == "Roma"
    assert patch["provincia_nascita"] == "RM"
    assert patch["doc_data_rilascio"] == "2024-11-27"
    assert patch["doc_data_scadenza"] == "2034-01-01"
    assert patch["doc_numero"] == "CA12345AB"
    assert patch["sesso"] == "M"
    assert patch["nazionalita"] == "Italiana"


def test_carta_cartacea_non_usa_scadenza_tessera_sanitaria():
    text = """scade il 22/11/2026
    COMUNE DI ROMA
    CARTA D'IDENTITA
    N° AX1234567
    Cognome...ROSSI
    MARIO Nome... 01/01/1980 nato il.
    REPUBBLICA ITALIANA TESSERA SANITARIA
    Data di scadenza 14/04/2022"""
    patch = parse_client_document_text(text)['patch']
    assert patch['cognome'] == 'Rossi'
    assert patch['nome'] == 'Mario'
    assert patch['doc_numero'] == 'AX1234567'
    assert patch['data_nascita'] == '1980-01-01'
    assert patch['doc_data_scadenza'] == '2026-11-22'


def test_paper_issuer_date_with_printed_separator_remains_in_its_model():
    source = "COMUNE DI ROMA\nCARTA D'IDENTITA\nN° AB1234567\nROMA-08/08/2014\n"
    assert parse_client_document_text(source)['patch']['doc_data_rilascio'] == '2014-08-08'
    columns = source.replace('ROMA-08/08/2014', 'CONNOTATI E CONTRASSEGNI SALIENTTROMA-08/08/2014')
    assert parse_client_document_text(columns)['patch']['doc_data_rilascio'] == '2014-08-08'
    other_city = source.replace('ROMA-08/08/2014', 'MILANO-08/08/2014')
    assert 'doc_data_rilascio' not in parse_client_document_text(other_city)['patch']
    health = source.replace('ROMA-08/08/2014', '') + 'TESSERA SANITARIA\nROMA-08/08/2014'
    assert 'doc_data_rilascio' not in parse_client_document_text(health)['patch']
    discordant = source + 'ROMA-09/08/2014\n'
    assert 'doc_data_rilascio' not in parse_client_document_text(discordant)['patch']


def test_degraded_paper_labels_require_independent_fiscal_concordance():
    source = ("COMUNE DI ROMA\nCARTA D'IDENTITA\nN° AB1234567\n"
              "COGNOME ROSSI\nNOME MARIO\nrato il..01/01/1980\n"
              "ROMA((RM) Cittadinanza ITALIANA\nResidenraROMA(RM)\n"
              "TESSERA SANITARIA\nCODICE FISCALE RSSMRA80A01H501U")
    patch = parse_client_document_text(source)['patch']
    assert patch['data_nascita'] == '1980-01-01'
    assert patch['luogo_nascita'] == 'Roma' and patch['provincia_nascita'] == 'RM'
    assert patch['comune'] == 'Roma' and patch['provincia'] == 'RM'
    discordant = parse_client_document_text(source.replace('01/01/1980', '02/01/1980'))['patch']
    assert 'data_nascita' not in discordant
    no_cf = parse_client_document_text(source.split('TESSERA SANITARIA')[0])['patch']
    assert 'data_nascita' not in no_cf and 'luogo_nascita' not in no_cf
    assert 'via' not in patch  # nessuna denominazione della via ricostruita dal CF


def test_profili_separano_tessera_prima_della_cie():
    from pct.document_intelligence.catalog_identita_personale import segmenti_identita_italiana
    text = "TESSERA SANITARIA\nScadenza 14/04/2022\nCARTA D'IDENTITA / IDENTITY CARD\nCognome ROSSI\nNome MARIO\nScadenza 01/01/2034"
    segments = segmenti_identita_italiana(text)
    assert [item['model'] for item in segments] == ['tessera_sanitaria', 'cie']
    assert parse_client_document_text(text)['patch']['doc_data_scadenza'] == '2034-01-01'


def test_fascicolo_altrui_non_attiva_lettura():
    import pytest
    from types import SimpleNamespace
    from web.services.client_document_reader import read_client_case_document, ClientDocumentReaderError
    manager = SimpleNamespace(get=lambda _: SimpleNamespace(id_cliente='altro-cliente'))
    with pytest.raises(ClientDocumentReaderError) as raised:
        read_client_case_document(manager, None, 'tenant', 'case', 'cliente')
    assert raised.value.status_code == 403


def test_client_document_reader_parse_mrz_passaporto() -> None:
    mrz = "\n".join(
        [
            "P<ITAROSSI<<MARIO<<<<<<<<<<<<<<<<<<<<<<<<<<<<",
            "YA12345676ITA8001014M3001019<<<<<<<<<<<<<<00",
        ]
    )

    payload = parse_client_document_text(mrz, filename="passaporto.pdf", mime_type="application/pdf")

    assert payload["ok"] is True
    assert payload["mrz"]["detected"] is True
    assert payload["patch"]["doc_tipo"] == "PASSAPORTO"
    assert payload["patch"]["doc_numero"] == "YA1234567"
    assert payload["patch"]["cognome"] == "Rossi"
    assert payload["patch"]["nome"] == "Mario"
    assert payload["patch"]["data_nascita"] == "1980-01-01"
    assert payload["patch"]["doc_data_scadenza"] == "2030-01-01"
    assert payload["patch"]["sesso"] == "M"
    assert any(item["name"] == "doc_numero" and item["status"] == "affidabile" for item in payload["fields"])


def test_client_document_reader_parse_testo_visibile() -> None:
    testo = """
    CARTA D'IDENTITA
    Cognome: Verdi
    Nome: Laura
    Sesso: F
    Codice fiscale VRDLRA82B41H501U
    Nata a Roma (RM) il 01/02/1982
    Numero documento CA12345AA
    Rilasciato da Comune di Roma
    Data rilascio 02/03/2020
    Scadenza 01/02/2030
    Residenza: Via Nazionale 10, 00184 Roma RM
    Telefono: 06 123456
    Cellulare: 333 1234567
    Email laura.verdi@example.test
    """

    payload = parse_client_document_text(testo, filename="carta.png", mime_type="image/png")

    assert payload["ok"] is True
    assert payload["patch"]["doc_tipo"] == "CARTA_IDENTITA"
    assert payload["patch"]["codice_fiscale"] == "VRDLRA82B41H501U"
    assert payload["patch"]["cognome"] == "Verdi"
    assert payload["patch"]["nome"] == "Laura"
    assert payload["patch"]["data_nascita"] == "1982-02-01"
    assert payload["patch"]["luogo_nascita"] == "Roma"
    assert payload["patch"]["provincia_nascita"] == "RM"
    assert payload["patch"]["doc_data_scadenza"] == "2030-02-01"
    assert payload["patch"]["via"] == "Via Nazionale"
    assert payload["patch"]["civico"] == "10"
    assert payload["patch"]["cap"] == "00184"
    assert payload["patch"]["comune"] == "Roma"
    assert payload["patch"]["provincia"] == "RM"
    assert payload["patch"]["nazione"] == "Italia"
    assert payload["patch"]["telefono"] == "06 123456"
    assert payload["patch"]["cellulare"] == "333 1234567"
    assert payload["patch"]["email"] == "laura.verdi@example.test"


def test_clienti_nuovo_documento_leggi_api_upload_in_memoria(tmp_path, monkeypatch) -> None:
    app = _app(tmp_path)

    def fake_ocr(_content: bytes, _filename: str, file_type: str, *, identity_scan: bool = False):
        from pct.document_intelligence.extraction import ExtractionResult
        assert file_type == "pdf"
        assert identity_scan is True
        return ExtractionResult(ok=True, text="Cognome: Bianchi\nNome: Anna\nCodice fiscale BNCNNA90C41H501X\nNata a Roma (RM) il 01/03/1990\nScadenza 01/03/2030", pages=[], extraction_engine="controlled-test")

    monkeypatch.setattr("pct.document_intelligence.extraction.extract_text_from_document", fake_ocr)

    with app.test_client() as client:
        response = client.post(
            "/api/v1/ui/clienti/nuovo/documento/leggi",
            data={"file": (BytesIO(b"%PDF-1.7 documento"), "documento.pdf")},
            content_type="multipart/form-data",
            headers={"X-API-Key": "react-test-key"},
        )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["source"] == "lettore_documento_cliente"
    assert payload["filename"] == "documento.pdf"
    assert payload["patch"]["cognome"] == "Bianchi"
    assert payload["patch"]["nome"] == "Anna"
    assert payload["patch"]["codice_fiscale"] == "BNCNNA90C41H501X"
    assert payload["patch"]["data_nascita"] == "1990-03-01"
    assert payload["patch"]["doc_data_scadenza"] == "2030-03-01"


def test_uploaded_document_with_unknown_client_is_rejected_before_ocr(tmp_path, monkeypatch):
    app = _app(tmp_path)
    def unexpected_reader(*args, **kwargs):
        raise AssertionError('OCR non ammesso prima del riscontro cliente')
    monkeypatch.setattr('web.blueprints.api_v1_react.read_client_document_upload', unexpected_reader)
    monkeypatch.setattr('web.blueprints.api_v1_react._session_user_can', lambda permission: permission == 'clienti.scrivi')
    with app.test_client() as client:
        response = client.post('/api/v1/ui/clienti/nuovo/documento/leggi',
            data={'file': (BytesIO(b'%PDF-1.7 controlled'), 'identita.pdf'), 'id_cliente': 'CLIENTE_ASSENTE'},
            content_type='multipart/form-data', headers={'X-API-Key': 'react-test-key'})
    assert response.status_code == 404
    assert response.get_json()['patch'] == {}


def test_react_soggetti_nuovo_usa_ocr_mrz_e_popola_campi_anagrafici() -> None:
    source = Path("frontend/src/components/NuovoClientePage.tsx").read_text(encoding="utf-8")

    assert "IUSENTRA_SOGGETTO_NUOVO" in source
    assert "iusentra:soggetto-documento-rilevato" in source
    assert "normalizeSubjectDocumentScan" in source
    assert "canAutofillSubjectField" in source
    assert "setValues(nextValues)" in source
    for field in [
        "codice_fiscale",
        "cognome",
        "nome",
        "sesso",
        "data_nascita",
        "luogo_nascita",
        "provincia_nascita",
        "doc_numero",
        "doc_data_scadenza",
    ]:
        assert f"{field}:" in source or f"'{field}'" in source
    assert "Dati documento applicati al nuovo soggetto." in source
    assert "data.actions.documentReader" in source
    assert "DocumentAutofillPanel" in source


def test_codice_fiscale_con_controllo_errato_non_compilato():
    payload = parse_client_document_text("Cognome: Verdi\nNome: Laura\nCodice fiscale VRDLRA82B41H501Z")
    assert "codice_fiscale" not in payload["patch"]
    assert "codice fiscale" in payload["missing"]


def test_cie_issuer_bilingual_inline_and_separate_lines():
    for label in ('COMUNE DI / MUNICIPALITY\nROMBIOLO', 'COMUNE DI/ MUNICIPAUTY ROMBIOLO'):
        payload = parse_client_document_text(
            'CARTA DI IDENTITÀ /IDENTITY CARD ' + label +
            '\nCOGNOME / SURNAME ROSSI\nNOME / NAME MARIO\n'
            'INDIRIZZO DI RESIDENZA / ADDRESS\nVIA ROMA 10 MILANO'
        )
        assert payload['patch']['doc_rilasciato_da'] == 'Comune di Rombiolo'


def test_cie_issuer_missing_value_does_not_take_next_label():
    payload = parse_client_document_text('CARTA DI IDENTITÀ / IDENTITY CARD\nCOMUNE DI / MUNICIPALITY\nCOGNOME / SURNAME ROSSI')
    assert 'doc_rilasciato_da' not in payload['patch']


def test_cie_inline_issuer_and_residence_do_not_consume_other_labels():
    result = parse_client_document_text(
        "CARTA DI IDENTITÀ / IDENTITY CARD COMUNE DI/ MUNICIPALITY VICENZA COGNOME/SURNAME ROSSI\n"
        "NOME / NAME\nMARIO\nINDIRIZZO DIRESIDENZA/ RESIDENCE VIALE ROMA, N. 341 VICENZA (VI)\n"
    )
    assert result['patch']['doc_rilasciato_da'] == 'Comune di Vicenza'
    assert result['patch']['via'] == 'VIALE ROMA'
    assert result['patch']['civico'] == '341'
    assert result['patch']['comune'] == 'Vicenza'
    assert result['patch']['provincia'] == 'VI'


def test_disordered_identity_labels_never_become_personal_values():
    result = parse_client_document_text(
        "CARTA DI IDENTITÀ / IDENTITY CARD\nCOMUNE DI / MUNICIPALITY\nSEX\n"
        "COGNOME E NOME DEL PADRE E DELLA MADRE O DI CHI NE FA LE VECI\n"
        "17.04.2033 CITTADINANZA SCADENZA/EXPIRY\n"
    )
    for field in ('nome', 'cognome', 'doc_rilasciato_da', 'nazionalita'):
        assert field not in result['patch']


def test_old_paper_identity_remains_separate_from_health_card():
    result = parse_client_document_text(
        "COMUNE DI ROMA CARTA D'IDENTITÀ\nN. AB1234567\nCognome: Rossi\nNome: Mario\n"
        "SCADE IL 17.04.2033\nTESSERA SANITARIA\nSCADENZA 01.01.2027\n"
    )
    assert result['document_profiles'][0]['model'] == 'carta_cartacea'
    assert result['document_profiles'][1]['model'] == 'tessera_sanitaria'
    assert result['patch']['doc_numero'] == 'AB1234567'
    assert result['patch']['doc_data_scadenza'] == '2033-04-17'


def test_cie_number_before_title_and_issuer_without_slash():
    result = parse_client_document_text(
        'CA62436OK\nREPUBBLICA ITALIANA\nCARTA DI IDENTITÀ / IDENTITY CARD\n'
        'COMUNE DIMUNICIPALITY ROSARNO COGNOME / SURNAME BORGESE NOME/NAME CX8 MARIA\n'
        'EMISSIONE/ISSUING SCADENZA/EXPIRY\n10.03.2023 01.03.2033\n'
        'TESSERA SANITARIA\nSCADENZA 13.05.2030\n'
    )
    assert result['patch']['doc_numero'] == 'CA62436OK'
    assert result['patch']['doc_rilasciato_da'] == 'Comune di Rosarno'
    assert result['patch']['cognome'] == 'Borgese'
    assert result['patch']['doc_data_scadenza'] == '2033-03-01'


def test_cie_heading_number_does_not_repair_zero_or_take_health_card_code():
    result = parse_client_document_text(
        'CA624360K\nCARTA DI IDENTITÀ / IDENTITY CARD\nCOGNOME / SURNAME ROSSI\n'
        'TESSERA SANITARIA\nCA62436OK\n'
    )
    assert 'doc_numero' not in result['patch']


def test_recovered_cie_preamble_is_not_assigned_to_previous_health_card():
    from pct.document_intelligence.catalog_identita_personale import segmenti_identita_italiana
    text = (
        'TESSERA SANITARIA\nSCADENZA 13.05.2030\n'
        '#### CA62436OK\n\n## REPUBBLICA ITALIANA\n\n'
        "#### MINISTERO DELL'INTERNO\n\n"
        'CARTA DI IDENTITÀ /IDENTITY CARD COMUNE DI/ MUNICIPALITY ROSARNO '
        'COGNOME / SURNAME BORGESE NOME/NAME CX8 MARIA\n'
        'EMISSIONE/ISSUING SCADENZA/EXPIRY\n10.03.2023 01.03.2033\n'
    )
    segments = segmenti_identita_italiana(text)
    assert 'CA62436OK' not in segments[0]['text']
    assert 'CA62436OK' in segments[1]['text']
    patch = parse_client_document_text(text)['patch']
    assert patch['doc_numero'] == 'CA62436OK'
    assert patch['cognome'] == 'Borgese'
    assert patch['doc_data_scadenza'] == '2033-03-01'


def test_reader_reports_barcode_provenance_only_from_engine_audit(monkeypatch):
    from types import SimpleNamespace
    import web.services.client_document_reader as reader
    import pct.document_intelligence.extraction as extraction
    proof = 'Pagina 2: Codice a barre del retro CIE AA12345BB: CF decodificato localmente, checksum e dati MRZ concordanti; originale invariato.'
    text = 'CODICE FISCALE: RSSMRA80A01H501U'
    for warnings, expected in (([proof], True), ([], False)):
        monkeypatch.setattr(extraction, 'extract_text_from_document', lambda *a, **k: SimpleNamespace(
            ok=True, text=text + '\n' + proof, pages=[object(), object()], warnings=warnings))
        result = reader.read_client_document_bytes(b'controlled', 'documento.pdf')
        row = next(item for item in result['fields'] if item['name'] == 'codice_fiscale')
        assert ('codice a barre' in row['source']) == expected
        assert ('CF decodificato localmente dal codice a barre' in result['warnings'][0]) == expected


def test_reader_missing_document_and_residence_fields_are_explicit():
    result = parse_client_document_text('CODICE FISCALE: RSSMRA80A01H501U')
    assert {'rilasciato da', 'data rilascio', 'via', 'civico', 'comune'} <= set(result['missing'])


def test_health_card_never_supplies_identity_document_fields():
    result = parse_client_document_text(
        'TESSERA SANITARIA\nCOGNOME: ROSSI\nNOME: MARIO\n'
        'CODICE FISCALE: RSSMRA80A01H501U\nNUMERO DOCUMENTO: AB1234567\n'
        'SCADENZA: 01.01.2030\nRILASCIATO DA: Comune di Roma\n'
        'DATA RILASCIO: 01.01.2020\nINDIRIZZO: VIA ROMA 1\n')
    assert result['document_profiles'][0]['model'] == 'tessera_sanitaria'
    assert result['patch']['codice_fiscale'] == 'RSSMRA80A01H501U'
    assert not any(key.startswith('doc_') for key in result['patch'])
    assert 'via' not in result['patch']


def test_cie_rear_without_front_title_uses_cie_address_rules():
    result = parse_client_document_text(
        'CODICE FISCALE / FISCAL CODE\nRSSMRA80A01H501U\n'
        'INDIRIZZO DI RESIDENZA / RESIDENCE VIA ROMA, N. 12 ROMA (RM)\n')
    assert result['document_profiles'][0]['model'] == 'cie'
    assert result['patch']['via'] == 'VIA ROMA'
    assert result['patch']['civico'] == '12'
    assert 'doc_data_rilascio' not in result['patch']


def test_paper_and_cie_distinct_numbers_do_not_compose_one_identity():
    result = parse_client_document_text(
        "COMUNE DI ROMA CARTA D'IDENTITÀ\nN. AB1234567\nCOGNOME: ROSSI\nNOME: MARIO\n"
        "CARTA DI IDENTITÀ / IDENTITY CARD\nAA12345BB\nCOGNOME: VERDI\nNOME: LUCA\n")
    assert result['patch'] == {}
    assert 'numeri di carte distinti' in result['message']
