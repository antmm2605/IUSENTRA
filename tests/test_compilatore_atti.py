from types import SimpleNamespace

from pct.compilatore_atti import (
    campi_extra_modello,
    get_modello,
    prefill_payload,
    render_compiled_act,
    validate_payload,
)


def _fake_document(name: str):
    return SimpleNamespace(nome=name)


def _fake_fascicolo():
    return SimpleNamespace(
        id="FASC123",
        id_cliente="CLI123",
        titolo="RG 1025/2024 - Vendita di cose immobili",
        oggetto="Vendita di cose immobili",
        note="Controversia sulla vendita immobiliare e sugli adempimenti delle parti.",
        nome_cliente="Montagnese Elisabetta",
        controparte="Stillitano Francesco",
        tribunale="Tribunale di Palmi",
        sezione="Civile",
        giudice="Giovannella Maria Elena",
        numero="2026/002",
        rg_completo="RG 1025/2024",
        tipo=SimpleNamespace(value="CIVILE"),
        valore_causa=12000,
        data_prima_udienza="2024-12-12",
        data_prossima_udienza="2025-05-20",
        documenti=[_fake_document("comparsa.pdf"), _fake_document("procura.pdf")],
    )


def _fake_cliente():
    return SimpleNamespace(
        id="CLI123",
        nome_completo="Montagnese Elisabetta",
    )


def _fake_utente():
    return SimpleNamespace(
        id="USR123",
        username="admin",
        nome_completo="Avv. Mario Rossi",
    )


def test_modello_ha_campi_extra_coerenti():
    model = get_modello("CIV_CIT_001")
    assert model is not None
    assert model["name"] == "Atto di Citazione"
    field_names = [field["name"] for field in campi_extra_modello("CIV_CIT_001")]
    assert "court_name" in field_names
    assert "documents_offered" in field_names


def test_prefill_payload_recupera_dati_dalla_pratica():
    payload = prefill_payload(
        "CIV_CIT_001",
        fascicolo=_fake_fascicolo(),
        cliente=_fake_cliente(),
        utente=_fake_utente(),
        config={
            "STUDIO_AVVOCATO": "Avv. Mario Rossi",
            "STUDIO_INDIRIZZO": "Via Roma 1, Palmi",
            "STUDIO_CF": "RSSMRA80A01H501Z",
            "SMTP_FROM": "studio@examplepec.it",
        },
    )
    assert payload["case_id"] == "FASC123"
    assert payload["client_or_sender"] == "Montagnese Elisabetta"
    assert payload["counterparty_or_recipient"] == "Stillitano Francesco"
    assert payload["court_name"] == "Tribunale di Palmi - Civile - Giovannella Maria Elena"
    assert payload["lawyer_pec"] == "studio@examplepec.it"
    assert payload["documents_offered"] == ["comparsa.pdf", "procura.pdf"]


def test_validate_and_render_compiled_act():
    fascicolo = _fake_fascicolo()
    payload = prefill_payload(
        "STR_DIFF_001",
        fascicolo=fascicolo,
        cliente=_fake_cliente(),
        utente=_fake_utente(),
        config={"STUDIO_INDIRIZZO": "Palmi", "STUDIO_AVVOCATO": "Avv. Mario Rossi"},
    )
    payload.update(
        {
            "recipient_or_court": "Stillitano Francesco",
            "subject": "Diffida ad adempiere",
            "requests_or_conclusions": "Si invita all'immediato adempimento.",
            "sender": "Montagnese Elisabetta",
            "recipient": "Stillitano Francesco",
            "breach_description": "Mancata esecuzione dell'obbligazione contrattuale.",
            "specific_request": "Adempiere entro il termine assegnato.",
            "deadline_assigned": "2026-04-15",
            "final_warning": "In difetto si procedera in giudizio.",
        }
    )
    errors = validate_payload("STR_DIFF_001", payload)
    assert errors == {}
    testo = render_compiled_act("STR_DIFF_001", payload)
    assert "DIFFIDA" in testo.upper()
    assert "OGGETTO" in testo
    assert "DATI SPECIFICI DEL MODELLO" in testo
    assert "Montagnese Elisabetta" in testo
