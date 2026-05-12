from types import SimpleNamespace

from pct.studio_timbro import StudioTimbro
from pct.template_atti_prefill import merge_prefill_values, resolve_template_prefill


def test_prefill_priorita_cliente_pratica_ufficio_autore_e_conflitto():
    cliente = SimpleNamespace(id="cli_1", nome_completo="Cliente da anagrafica")
    fascicolo = SimpleNamespace(
        id="fas_1",
        tribunale="Tribunale di Milano",
        numero_rg="1234/2026",
        rg_completo="1234/2026 RG",
        titolo="Impugnazione delibera",
        oggetto="Oggetto da fascicolo",
        controparte="Controparte da fascicolo",
        documenti=[SimpleNamespace(nome="Procura alle liti.pdf")],
    )
    parti = SimpleNamespace(
        assistito_principale=SimpleNamespace(nome_completo="Assistito da parti fascicolo"),
        controparte_principale=SimpleNamespace(nome_completo="Controparte da parti"),
    )
    utente = SimpleNamespace(id="usr_1", username="avv.test", nome_completo="Avv. Assegnato")
    timbro = StudioTimbro.from_payload({"studio_nome": "Studio Alfa", "pec": "studio@example.test"})

    resolved = resolve_template_prefill(
        model_code="CIV_CIT_001",
        required_fields=[
            "destinatario_ufficio_giudiziario",
            "cliente_mittente",
            "pratica_collegata",
            "autore",
            "client_or_sender",
            "counterparty_or_recipient",
            "recipient_or_court",
            "case_id",
            "author_user_id",
            "attachments_list",
            "pec_studio",
            "dato_non_presente",
        ],
        fascicolo=fascicolo,
        cliente=cliente,
        utente=utente,
        config={"studio": {"avvocato": "Avv. Titolare Studio"}},
        studio_timbro=timbro,
        parti=parti,
    )

    assert resolved["fields"]["client_or_sender"]["value"] == "Assistito da parti fascicolo"
    assert resolved["fields"]["cliente_mittente"]["value"] == "Assistito da parti fascicolo"
    assert resolved["fields"]["client_or_sender"]["source"] == "parti"
    assert resolved["fields"]["client_or_sender"]["conflict"] is True
    assert resolved["fields"]["counterparty_or_recipient"]["value"] == "Controparte da parti"
    assert resolved["fields"]["recipient_or_court"]["value"] == "Tribunale di Milano"
    assert resolved["fields"]["destinatario_ufficio_giudiziario"]["value"] == "Tribunale di Milano"
    assert resolved["fields"]["case_id"]["value"] == "fas_1"
    assert resolved["fields"]["pratica_collegata"]["value"] == "fas_1"
    assert resolved["fields"]["author_user_id"]["value"] == "Avv. Titolare Studio"
    assert resolved["fields"]["author_user_id"]["source"] == "studio"
    assert resolved["fields"]["autore"]["value"] == "Avv. Titolare Studio"
    assert resolved["fields"]["autore"]["source"] == "studio"
    assert resolved["fields"]["attachments_list"]["value"] == ["Procura alle liti.pdf"]
    assert resolved["fields"]["pec_studio"]["value"] == "studio@example.test"
    assert resolved["fields"]["dato_non_presente"]["missing_reason"]
    assert "dato_non_presente" in resolved["required_missing"]


def test_prefill_senza_pratica_non_blocca_template_ma_chiede_selezione_contesto():
    resolved = resolve_template_prefill(model_code="CIV_CIT_001")

    for field_name in ("destinatario_ufficio_giudiziario", "cliente_mittente", "pratica_collegata", "autore"):
        assert field_name in resolved["fields"]
        assert field_name in resolved["required_missing"]
        assert resolved["fields"][field_name]["missing_reason"]


def test_merge_prefill_non_sovrascrive_input_utente_e_conserva_missing_reason():
    merged = merge_prefill_values(
        {"client_or_sender": "Cliente digitato", "subject": ""},
        {"client_or_sender": "Cliente da IUSENTRA", "subject": "Oggetto da fascicolo"},
        {
            "client_or_sender": {"missing_reason": ""},
            "dato_assente": {"missing_reason": "Dato non presente negli archivi."},
        },
    )

    assert merged["values"]["client_or_sender"] == "Cliente digitato"
    assert merged["values"]["subject"] == "Oggetto da fascicolo"
    assert "client_or_sender" in merged["preserved_user_inputs"]
    assert "subject" in merged["applied_prefill"]
    assert merged["missing_reasons"]["dato_assente"] == "Dato non presente negli archivi."
