from types import SimpleNamespace

from pct.compilatore_atti import (
    catalogo_compilatore,
    campi_extra_modello,
    get_modello,
    prefill_payload,
    professional_guidance_for_model,
    render_compiled_act,
    validate_payload,
    wizard_schema_modello,
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
    assert model["renderer"] == "civil_citation_v1"
    assert "vocatio_in_ius" in model["sections"]
    field_names = [field["name"] for field in campi_extra_modello("CIV_CIT_001")]
    assert "court_name" in field_names
    assert "documents_offered" in field_names


def test_catalogo_compilatore_espone_schema_pronto_per_software():
    schema = catalogo_compilatore()
    assert "field_catalog" in schema
    assert "base_required_fields" in schema
    assert "models" in schema
    assert schema["field_catalog"]["court_name"]["label"] == "Ufficio Giudiziario"
    assert schema["field_catalog"]["court_name"]["placeholder"].startswith("Inserisci ")
    model = next(item for item in schema["models"] if item["code"] == "CIV_CIT_001")
    assert model["renderer"] == "civil_citation_v1"
    assert "summary" in model
    assert "validation_rules" in model
    assert "prefill_map" in model


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
    assert payload["court_name"] == "Tribunale di Palmi"
    assert payload["lawyer_pec"] == "studio@examplepec.it"
    assert payload["documents_offered"] == ["comparsa.pdf", "procura.pdf"]
    assert payload["_client_tax_id"] == ""
    assert payload["_court_heading"] == "Tribunale di Palmi"


def test_professional_guidance_for_citation_has_cartabia_notes():
    guidance = professional_guidance_for_model("CIV_CIT_001")
    assert "giudizio ordinario di cognizione" in guidance["summary"]
    assert any("120 giorni" in item for item in guidance["technical_notes"])
    assert any("Art. 163-bis c.p.c." in item for item in guidance["references"])


def test_wizard_schema_modello_riusa_catalogo_centrale():
    schema = wizard_schema_modello("STR_DIFF_001")
    assert schema["model"]["code"] == "STR_DIFF_001"
    assert schema["renderer"] == "extrajudicial_notice_v1"
    assert any(field["name"] == "sender" for field in schema["extra_fields"])
    assert "diffida" in " ".join(schema["sections"])
    assert "sender" in schema["prefill_map"]


def test_modelli_ereditano_renderer_professionale_per_area():
    pen_schema = wizard_schema_modello("PEN_MEM_001")
    amm_schema = wizard_schema_modello("AMM_RIC_001")
    trib_schema = wizard_schema_modello("TRIB_RIC_001")
    civ_schema = wizard_schema_modello("CIV_COM_001")
    assert pen_schema["renderer"] == "criminal_defense_v1"
    assert amm_schema["renderer"] == "administrative_litigation_v1"
    assert trib_schema["renderer"] == "tax_litigation_v1"
    assert civ_schema["renderer"] == "civil_judicial_v1"


def test_render_citation_compiled_act_uses_professional_structure():
    fascicolo = _fake_fascicolo()
    payload = prefill_payload(
        "CIV_CIT_001",
        fascicolo=fascicolo,
        cliente=_fake_cliente(),
        utente=_fake_utente(),
        config={
            "STUDIO_AVVOCATO": "Mario Rossi",
            "STUDIO_INDIRIZZO": "Via Roma 1, Palmi",
            "STUDIO_CF": "RSSMRA80A01H501Z",
            "SMTP_FROM": "studio@examplepec.it",
        },
    )
    payload.update(
        {
            "plaintiff": "Montagnese Elisabetta",
            "defendant": "Stillitano Francesco",
            "claim_subject": "Domanda di accertamento dell'inadempimento e condanna al pagamento.",
            "facts": "L'attrice ha eseguito le proprie obbligazioni, mentre il convenuto non ha corrisposto quanto dovuto nonostante i ripetuti solleciti.",
            "legal_arguments": "L'inadempimento integra violazione dell'art. 1218 c.c.; risultano dovuti capitale, interessi e spese secondo i titoli allegati.",
            "evidence_means": "Si chiede ammissione della prova documentale e, ove necessario, prova testimoniale sui capitoli da articolare.",
            "requests_or_conclusions": "Voglia l'Ill.mo Tribunale accertare l'inadempimento del convenuto e condannarlo al pagamento del dovuto, oltre interessi e spese di lite.",
            "hearing_date": "2026-10-15",
            "case_value": 12000,
        }
    )
    errors = validate_payload("CIV_CIT_001", payload)
    assert errors == {}
    testo = render_compiled_act("CIV_CIT_001", payload)
    assert "TRIBUNALE DI PALMI" in testo
    assert "Atto di Citazione" in testo
    assert "FATTO" in testo
    assert "DIRITTO" in testo
    assert "CITA" in testo
    assert "CONCLUSIONI" in testo
    assert "15/10/2026" in testo
    assert "Dichiarazione di valore" in testo


def test_render_penal_memory_uses_professional_sections():
    payload = prefill_payload(
        "PEN_MEM_001",
        fascicolo=_fake_fascicolo(),
        cliente=_fake_cliente(),
        utente=_fake_utente(),
        config={"STUDIO_AVVOCATO": "Avv. Mario Rossi"},
    )
    payload.update(
        {
            "proceeding_authority": "Procura della Repubblica presso il Tribunale di Palmi",
            "assisted_person": "Montagnese Elisabetta",
            "criminal_proceeding_reference": "RGNR 102/2026",
            "defensive_arguments": "L'assistita chiede che siano valorizzati gli elementi gia versati in atti.",
            "specific_requests": "Si chiede l'acquisizione della documentazione difensiva allegata.",
            "requests_or_conclusions": "Ogni piu ampia riserva in rito e nel merito.",
            "documents_offered": ["memoria_precedente.pdf", "allegato_difensivo.pdf"],
            "place": "Palmi",
        }
    )
    errors = validate_payload("PEN_MEM_001", payload)
    assert errors == {}
    testo = render_compiled_act("PEN_MEM_001", payload)
    assert "PROCURA DELLA REPUBBLICA PRESSO IL TRIBUNALE DI PALMI" in testo
    assert "ARGOMENTAZIONI DIFENSIVE" in testo
    assert "RICHIESTE" in testo
    assert "DOCUMENTI E ALLEGATI" in testo


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
    assert "DIFFIDA E INVITO AD ADEMPIERE" in testo
    assert "Montagnese Elisabetta" in testo
