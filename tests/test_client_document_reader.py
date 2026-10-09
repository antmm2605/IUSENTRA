from __future__ import annotations

from io import BytesIO
from pathlib import Path

from web.services.client_document_reader import parse_client_document_text
from tests.test_react_shell import _app


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

    def fake_ocr(_content: bytes, _filename: str, lang: str = "ita") -> str:
        assert lang == "ita"
        return "Cognome: Bianchi\nNome: Anna\nCodice fiscale BNCNNA90C41H501X\nNata a Roma (RM) il 01/03/1990\nScadenza 01/03/2030"

    monkeypatch.setattr("pct.ocr.estrai_testo", fake_ocr)

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
