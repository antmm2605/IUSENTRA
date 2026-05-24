from __future__ import annotations

from datetime import date

from legal_regex import LEGAL_REGEX_PACK_VERSION, validate_codice_fiscale_persona_fisica, validate_regex_pack


def test_regex_pack_valida_campi_obbligatori_legali():
    text = """
    Tribunale di Milano
    Atto di citazione N. RG 1234/2026
    Avv. Mario Rossi CF RSSMRA80A01H501U
    PEC studio.rossi@pec.it
    data atto 10/05/2026
    importo Euro 1.234,56
    """

    summary = validate_regex_pack(text, attempts=2, now=date(2026, 5, 24))

    assert summary["pack_version"] == LEGAL_REGEX_PACK_VERSION
    statuses = {field["id"]: field["status"] for field in summary["mandatory_fields"]}
    assert statuses["cf_avvocato"] == "ok"
    assert statuses["n_rg"] == "ok"
    assert statuses["pec"] == "ok"
    assert statuses["date"] == "ok"
    assert statuses["importi"] == "ok"
    assert summary["matches"]["n_rg"] == ["1234/2026"]


def test_regex_pack_blocca_cf_errato_e_data_atto_futura():
    assert validate_codice_fiscale_persona_fisica("RSSMRA80A01H501U")
    assert not validate_codice_fiscale_persona_fisica("RSSMRA80A01H501A")

    summary = validate_regex_pack(
        "CF RSSMRA80A01H501A PEC studio.rossi@pec.it N. RG 1234/2026 data atto 31/12/2099 importo 100,00",
        attempts=2,
        now=date(2026, 5, 24),
    )

    fields = {field["id"]: field for field in summary["mandatory_fields"]}
    assert fields["cf_avvocato"]["status"] == "fail"
    assert fields["date_plausibility"]["status"] == "fail"
    assert fields["date_plausibility"]["tries"] == 2
