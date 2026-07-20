from __future__ import annotations

import inspect

import pytest

from pct.legal_notification_rulepack import (
    build_notification_timing_plan,
    calculate_notification_effects,
    calculate_recipients_effects,
    compiled_notification_rules,
    detect_notification_candidates,
    load_notification_rulepack,
    portal_original_requirement,
    resolve_legacy_policy,
    resolve_procedural_regime,
    validate_source_registry,
)
from pct.pec_pipeline import PecAuditRepository


def test_rulepack_e_regex_sono_caricati_una_sola_volta():
    assert load_notification_rulepack() is load_notification_rulepack()
    assert compiled_notification_rules() is compiled_notification_rules()
    assert load_notification_rulepack()["version"] == "legal_notification_detection_rules_v1.0.0"


@pytest.mark.parametrize(
    ("commenced_on", "expected"),
    [
        ("2023-02-28", "pre_cartabia_historical"),
        ("2023-03-01", "cartabia_current"),
    ],
)
def test_confine_cartabia_28_febbraio_1_marzo(commenced_on: str, expected: str):
    regime = resolve_procedural_regime(commenced_on, context_kind="proceeding")
    assert regime["regime_id"] == expected
    assert regime["policy_used_for_selection"] is False


def test_regime_non_inferito_senza_data_procedimento():
    regime = resolve_procedural_regime("", context_kind="proceeding", notification_event_at="2026-07-19T12:00:00+02:00")
    assert regime["regime_id"] == "needs_review"
    assert regime["human_review_required"] is True


@pytest.mark.parametrize(
    ("rdac_time", "expected", "deferred"),
    [
        ("2026-07-19T20:59:00+02:00", "2026-07-19T20:59:00+02:00", False),
        ("2026-07-19T21:00:00+02:00", "2026-07-20T07:00:00+02:00", True),
        ("2026-07-19T23:59:00+02:00", "2026-07-20T07:00:00+02:00", True),
        ("2026-07-19T00:00:00+02:00", "2026-07-19T07:00:00+02:00", True),
        ("2026-07-19T06:59:00+02:00", "2026-07-19T07:00:00+02:00", True),
        ("2026-07-19T07:00:00+02:00", "2026-07-19T07:00:00+02:00", False),
    ],
)
def test_effetto_rdac_confini_orari_correnti(rdac_time: str, expected: str, deferred: bool):
    result = calculate_notification_effects(
        rac_at="2026-07-19T20:58:00+02:00",
        rdac_at=rdac_time,
        proceeding_commenced_on="2026-01-10",
    )
    assert result["recipient_effect_at"] == expected
    assert result["recipient_effect_deferred"] is deferred


def test_differimento_rdac_rispetta_dst_europe_rome():
    result = calculate_notification_effects(
        rac_at="2026-03-28T23:55:00+01:00",
        rdac_at="2026-03-29T00:30:00+01:00",
        proceeding_commenced_on="2026-01-10",
    )
    assert result["recipient_effect_at"] == "2026-03-29T07:00:00+02:00"
    assert result["recipient_effect_label"] == "29/03/2026 07:00:00"


def test_rac_non_prova_consegna_e_rdac_completa_gli_effetti():
    only_rac = calculate_notification_effects(
        rac_at="2026-07-19T21:15:00+02:00",
        proceeding_commenced_on="2026-01-10",
    )
    assert only_rac["sender_effect_at"] == "2026-07-19T21:15:00+02:00"
    assert only_rac["recipient_effect_at"] is None
    assert only_rac["delivery_proven"] is False
    assert only_rac["complete"] is False


def test_matrice_destinatari_mista_resta_parziale_e_failure_incerta_richiede_review():
    result = calculate_recipients_effects(
        [
            {
                "recipient_id": "destinatario-1",
                "sent_at": "2026-07-20T10:30:00+02:00",
                "rac_at": "2026-07-20T10:31:00+02:00",
                "rdac_at": "2026-07-20T10:32:00+02:00",
            },
            {
                "recipient_id": "destinatario-2",
                "sent_at": "2026-07-20T10:30:00+02:00",
                "failure_at": "2026-07-20T10:40:00+02:00",
                "failure_attribution": "uncertain",
            },
        ],
        proceeding_commenced_on="2026-01-10",
    )

    assert result["status"] == "PARTIAL_DELIVERY"
    assert result["priority"] == "P0"
    assert result["delivered_recipients"] == 1
    assert result["failed_recipients"] == 1
    assert result["human_review_required"] is True
    assert result["recipients"][1]["failure_attribution"] == "uncertain"


def test_comunicazione_xml_non_diventa_notifica_avvocato():
    findings = detect_notification_candidates(
        {
            "attachments": [
                {
                    "filename": "Comunicazione.xml",
                    "extracted_text": "Notificato alla PEC del difensore e in cancelleria.",
                }
            ]
        }
    )
    assert findings
    assert all(item["creates_notification_candidate"] is False for item in findings)
    assert findings[0]["rule_id"] == "notif.detect.comunicazione_xml_office_negative.v1"


def test_originale_portale_e_richiesto_solo_se_documento_non_allegato():
    parsed = {"body_text": "Avviso di disponibilità: documento presente nell'area download PST."}
    missing = portal_original_requirement(parsed)
    present = portal_original_requirement(
        parsed,
        [{"filename": "provvedimento.pdf", "extracted_text": "Provvedimento originale"}],
    )
    assert missing["required"] is True
    assert present["required"] is False
    candidate = detect_notification_candidates(
        {"body_text": "Il provvedimento è da notificare. Avviso di disponibilità nell'area download PST."}
    )
    assert candidate[0]["portal_original_required"] is True


def test_cutoff_migrazione_non_seleziona_il_regime_legale():
    before = resolve_legacy_policy("2026-07-18T23:59:00+02:00")
    after = resolve_legacy_policy("2026-07-20T00:00:00+02:00")
    assert before["applies"] is True
    assert after["applies"] is False
    assert before["legal_regime_selector"] is False


def test_blocco_notturno_corrente_e_solo_policy_configurabile():
    base = {"data_inizio_procedimento": "2026-01-10", "data_ora_invio_pec": "2026-07-19T06:30:00+02:00"}
    default = build_notification_timing_plan(base)
    blocked = build_notification_timing_plan({**base, "policy_fascia_notturna": "block"})
    assert default["ready"] is True
    assert blocked["ready"] is False
    assert blocked["status"] == "policy_prudenziale_notturna"
    assert blocked["policy"]["night_send_prudential"]["legal_rule"] is False


def test_hash_verificati_e_fonti_mancanti_falliscono_con_istruzione():
    registry = validate_source_registry(require_snapshots=False)
    assert registry["schema_version"] == "iusentra.legal_sources_registry.v2"
    with pytest.raises(ValueError, match="Acquisire da Normattiva"):
        validate_source_registry(require_snapshots=True)


def test_get_dettaglio_non_riesegue_il_motore_di_scansione():
    source = inspect.getsource(PecAuditRepository.get_message_detail)
    assert "build_legal_event_understanding" not in source
    assert "latest_legal_event_understanding" in source
