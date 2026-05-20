from __future__ import annotations

from pct.studio_timbro import StudioTimbro
from pct.template_normative_compliance import (
    CartabiaContextualComplianceEngine,
    analyze_template_compliance,
    enforce_generation_gate,
)


def _timbro() -> dict:
    return StudioTimbro.from_payload(
        {
            "studio_nome": "Studio Test",
            "professionista_nome": "Avv. Test",
            "pec": "studio@test.pec",
        }
    ).to_payload()


def _base_payload(**overrides):
    payload = {
        "case_id": "fas-1",
        "id_cliente": "cli-1",
        "client_or_sender": "Mario Rossi",
        "counterparty_or_recipient": "Bianchi",
        "facts": "Fatti rilevanti.",
        "requests_or_conclusions": "Conclusioni.",
        "place": "Roma",
        "document_date": "2026-05-20",
        "signature": "Avv. Test",
        "attachments_list": "Contratto e documenti di prova",
        "_studio_timbro": _timbro(),
    }
    payload.update(overrides)
    return payload


def test_citazione_ok_applica_fonti_ragioni_layout_e_timbro():
    result = analyze_template_compliance(
        "CIV_CIT_001",
        _base_payload(
            court_name="Tribunale di Roma",
            plaintiff="Mario Rossi",
            defendant="Bianchi",
            lawyer_tax_code="TSTTST70A01H501A",
            lawyer_pec="avv@test.pec",
            claim_subject="Domanda di adempimento",
            legal_arguments="Articolazione in diritto.",
            evidence_means="Prova documentale e testi.",
            documents_offered="Contratto",
            hearing_date="2026-10-20",
            appearance_notice="Invito a comparire con avvertimenti.",
            ritual_warnings="Avvertimenti di rito.",
            case_value="10000",
        ),
    )

    assert result.overall_state == "ok"
    assert result.can_generate_final_draft is True
    assert result.can_open_editor is True
    assert result.layout_compliance and result.layout_compliance.layout_profile_id == "civil_pct_act_layout"
    assert result.page_stamp_compliance and result.page_stamp_compliance.repeat_on_each_page is True
    assert result.page_stamp_compliance.position == "top_left"
    assert result.normative_references
    assert all(ref.reason_for_application for ref in result.normative_references)
    assert all(source.verification_status for source in result.source_pack)


def test_comparsa_warning_richiede_conferma_per_bozza_lavoro():
    result = analyze_template_compliance(
        "CIV_COM_001",
        _base_payload(
            court_name="Tribunale di Roma",
            proceeding_number="123/2026",
            defendant="Bianchi",
            plaintiff="Mario Rossi",
            lawyer_tax_code="TSTTST70A01H501A",
            lawyer_pec="avv@test.pec",
            position_on_facts="Si contesta la ricostruzione avversaria.",
            procedural_exceptions="Nessuna eccezione preliminare.",
            merit_exceptions="Eccezioni di merito.",
            evidence_means="Documenti",
            documents_offered="Comparsa e allegati",
        ),
    )

    assert result.overall_state == "warning"
    assert result.can_generate_final_draft is False
    assert result.can_generate_working_draft is True
    allowed, state, _ = enforce_generation_gate(result, requested_draft="final_draft", confirmed_warning=False)
    assert allowed is False
    assert state == "warning_requires_confirmation"
    allowed, state, _ = enforce_generation_gate(result, requested_draft="working_draft", confirmed_warning=True)
    assert allowed is True
    assert state == "working_draft"


def test_decreto_ingiuntivo_block_senza_prova_scritta():
    result = analyze_template_compliance(
        "CIV_RDI_001",
        _base_payload(
            competent_court="Tribunale di Milano",
            claimant="Mario Rossi",
            debtor="Bianchi",
            credit_source="Fatture",
            requested_amount="5000",
            credit_due_date="2026-04-01",
        ),
    )

    assert result.overall_state == "block"
    assert result.can_generate_final_draft is False
    assert result.reliability_score.value <= 0.49


def test_diffida_ok_non_applica_regole_pct_generiche():
    result = analyze_template_compliance(
        "STR_DIFF_001",
        _base_payload(
            sender="Mario Rossi",
            recipient="Bianchi",
            breach_description="Inadempimento contrattuale.",
            specific_request="Pagamento.",
            deadline_assigned="2026-06-20",
            final_warning="In difetto si agirà.",
        ),
    )

    assert result.overall_state == "ok"
    assert result.layout_compliance and result.layout_compliance.layout_profile_id == "civil_extrajudicial_pec_layout"
    assert all("PCT" not in ref.title for ref in result.normative_references)


def test_penale_block_senza_riferimento_procedimento():
    result = analyze_template_compliance(
        "PEN_NOM_001",
        _base_payload(
            proceeding_authority="Procura di Roma",
            assisted_person="Mario Rossi",
            appointed_defender="Avv. Test",
            defender_bar_association="Roma",
            defender_pec="avv@test.pec",
            elected_domicile="Studio Test",
            assisted_person_signature="Mario Rossi",
        ),
    )

    assert result.overall_state == "block"
    assert any(field.name == "criminal_proceeding_reference" for field in result.missing_fields)


def test_layout_stamp_e_fonti_influenzano_affidabilita():
    engine = CartabiaContextualComplianceEngine()
    result = engine.analyze_template_context(
        model_code="AMM_RIC_001",
        payload=_base_payload(
            competent_tar="TAR Lazio",
            claimant="Mario Rossi",
            respondent_administration="Comune",
            interested_third_parties="",
            challenged_administrative_act="Provvedimento",
            knowledge_or_service_date="2026-05-01",
            legal_arguments="Motivi",
            request_for_annulment_or_other_relief="Annullamento",
            interim_relief_request="Sospensione",
            documents_offered="Provvedimento",
            case_value="10000",
        ),
    )

    assert result.source_pack
    assert any(source.verification_status for source in result.source_pack)
    assert result.reliability_score.value <= 0.79
