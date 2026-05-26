from __future__ import annotations

from io import BytesIO
from pathlib import Path

from web.services.client_document_reader import parse_client_document_text
from tests.test_react_shell import _app


def test_client_document_reader_parse_mrz_passaporto() -> None:
    mrz = "\n".join(
        [
            "P<ITAROSSI<<MARIO<<<<<<<<<<<<<<<<<<<<<<<<<<<<",
            "YA12345678ITA8001017M3001019<<<<<<<<<<<<<<06",
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
    Codice fiscale VRDLRA82B41H501Z
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
    assert payload["patch"]["codice_fiscale"] == "VRDLRA82B41H501Z"
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
        return "Cognome: Bianchi\nNome: Anna\nCodice fiscale BNCNNA90C41H501Q\nNata a Roma (RM) il 01/03/1990\nScadenza 01/03/2030"

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
    assert payload["patch"]["codice_fiscale"] == "BNCNNA90C41H501Q"
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
