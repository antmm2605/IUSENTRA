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
    validate_rulepack_source_references,
    validate_source_registry,
)
from pct.pec_pipeline import PecAuditRepository


def test_rulepack_e_regex_sono_caricati_una_sola_volta():
    assert load_notification_rulepack() is load_notification_rulepack()
    assert compiled_notification_rules() is compiled_notification_rules()
    assert load_notification_rulepack()["version"] == "legal_notification_detection_rules_v1.0.4"


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


def test_sentenza_a_verbale_429_allegata_crea_revisione_notifica_ma_comunicazione_xml_non_prova():
    findings = detect_notification_candidates(
        {
            "headers": {"subject": "Tribunale Ordinario di Padova Notificazione ai sensi del D.L. 179/2012"},
            "attachments": [
                {
                    "filename": "Comunicazione.xml",
                    "extracted_text": "Notificato alla PEC del difensore e in cancelleria. Oggetto: SENTENZA A VERBALE (art. 127 ter cpc).",
                },
                {
                    "filename": "19040620s.pdf",
                    "extracted_text": (
                        "TRIBUNALE ORDINARIO DI PADOVA. Il Giudice decide la causa con sentenza a norma "
                        "dell'art. 429 c.p.c. Il Giudice, definitivamente decidendo, accerta il diritto e "
                        "condanna il Ministero alle spese, con distrazione in favore del procuratore antistatario."
                    ),
                },
            ],
        }
    )

    office = next(item for item in findings if item["rule_id"] == "notif.detect.comunicazione_xml_office_negative.v1")
    judgment = next(item for item in findings if item["rule_id"] == "notif.detect.sentenza_verbale_429_review.v1")
    assert office["creates_notification_candidate"] is False
    assert judgment["creates_notification_candidate"] is True
    assert judgment["notification_case"] == "judgment_to_notify_review"


def test_pqm_429_e_127ter_senza_segnali_decisori_non_creano_notifica_sentenza():
    findings = detect_notification_candidates(
        {
            "attachments": [
                {
                    "filename": "ordinanza-127-ter.pdf",
                    "extracted_text": (
                        "TRIBUNALE ORDINARIO. P.Q.M. dispone la trattazione scritta ai sensi "
                        "dell'art. 127-ter c.p.c. e assegna termine per note. L'art. 429 c.p.c. "
                        "è richiamato esclusivamente per la successiva fase decisoria."
                    ),
                }
            ]
        }
    )

    assert not any(
        item.get("notification_case") in {"judgment_to_notify", "judgment_to_notify_review"}
        for item in findings
    )


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


def test_ogni_regola_eseguibile_cita_solo_fonti_censite():
    result = validate_rulepack_source_references()

    assert result["rulepack_version"] == "legal_notification_detection_rules_v1.0.4"
    assert {
        "src.it.cpc.art133",
        "src.it.cpc.art285",
        "src.it.cpc.art325",
        "src.it.cpc.art326",
        "src.it.cpc.art429",
    }.issubset(result["referenced_source_ids"])


def test_get_dettaglio_non_riesegue_il_motore_di_scansione():
    source = inspect.getsource(PecAuditRepository.get_message_detail)
    assert "build_legal_event_understanding" not in source
    assert "latest_legal_event_understanding" in source


# Formule reali dei decreti di fissazione udienza (testi anonimizzati, PEC dal 26/10 al 09/11/2026):
# L. 53/1994 art. 3-bis; artt. 415, commi 4-5, 435 e 281-undecies c.p.c.
_ORDINI_DI_NOTIFICA_REALI = {
    "onera": (
        "FISSA ai sensi dell’art. 127 ter c.p.c. in sostituzione dell’udienza il termine del 10.12.2026 per note; "
        "ONERA parte ricorrente della notificazione a parte resistente del ricorso e del presente decreto entro e "
        "non oltre 30 giorni prima dell’udienza fissata; Manda alla Cancelleria per le comunicazioni."
    ),
    "manda_al_ricorrente": (
        "Manda al ricorrente di notificare ricorso e pedissequo decreto alla controparte entro e non oltre il "
        "termine di legge. Manda alla Cancelleria per quanto di competenza."
    ),
    "dispone_sia_notificata": (
        "FISSA per la discussione l’udienza del 23.12.2026, ore 9.30. Dispone che copia del ricorso e del presente "
        "decreto sia notificata a parte resistente a cura di parte ricorrente nel termine di trenta giorni."
    ),
    "siano_notificati_a_cura": "Ricorso e decreto siano notificati al convenuto a cura dell'attore entro dieci giorni.",
    "deve_essere_notificato_281_undecies": (
        "Il ricorso, unitamente al presente decreto, deve essere notificato al convenuto a cura dell’attore."
    ),
    "notificarsi": "Fissa l'udienza del 12.01.2027; ricorso e decreto da notificarsi entro il 10.12.2026.",
    "a_cura_di_parte": "La notificazione del ricorso e del decreto avverrà a cura di parte ricorrente nei termini.",
    "assegna_termine_rinnovazione": (
        "Assegna alla parte ricorrente termine di giorni trenta per la rinnovazione della notificazione del ricorso."
    ),
}

_SENZA_ORDINE_AL_DIFENSORE = {
    "manda_alla_cancelleria": "Manda alla Cancelleria per le comunicazioni e notificazioni di rito.",
    "a_cura_della_cancelleria": "Dispone che il presente decreto sia notificato a cura della cancelleria alle parti.",
    "notificarsi_dalla_cancelleria": "Ricorso e decreto da notificarsi a cura della cancelleria.",
    "fatto_storico": "Il ricorso, ritualmente notificato, veniva depositato e la convenuta si costituiva.",
    "termine_di_costituzione": "ASSEGNA al resistente termine sino a 10 giorni prima dell’udienza per la costituzione.",
}


@pytest.mark.parametrize("caso", sorted(_ORDINI_DI_NOTIFICA_REALI))
def test_ordine_di_notifica_al_difensore_crea_proposta_in_revisione(caso: str):
    findings = detect_notification_candidates(
        {"headers": {"subject": "POSTA CERTIFICATA: COMUNICAZIONE 1234/2026/LAV"}},
        {},
        attachments=[{"filename": "decreto.pdf", "text": _ORDINI_DI_NOTIFICA_REALI[caso]}],
    )
    ordini = [item for item in findings if item["rule_id"] == "notif.detect.explicit_order.v1"]
    assert ordini, caso
    assert ordini[0]["creates_notification_candidate"] is True
    assert ordini[0]["human_review_required"] is True
    assert ordini[0]["rulepack_version"] == "legal_notification_detection_rules_v1.0.4"
    assert {"src.it.l53_1994.art3bis", "src.it.cpc.art415"}.issubset(ordini[0]["legal_sources"])


@pytest.mark.parametrize("caso", sorted(_SENZA_ORDINE_AL_DIFENSORE))
def test_comunicazioni_di_cancelleria_senza_ordine_al_difensore_restano_escluse(caso: str):
    findings = detect_notification_candidates(
        {"headers": {"subject": "Comunicazione di cancelleria"}},
        {},
        attachments=[{"filename": "decreto.pdf", "text": _SENZA_ORDINE_AL_DIFENSORE[caso]}],
    )
    assert not any(item["creates_notification_candidate"] for item in findings), caso


def test_comunicazione_xml_con_formula_di_cancelleria_non_crea_proposta():
    findings = detect_notification_candidates(
        {},
        {},
        attachments=[
            {
                "filename": "Comunicazione.xml",
                "text": (
                    "Oggetto: FISSAZIONE UDIENZA DI DISCUSSIONE Descrizione: FISSATA UDIENZA DI DISCUSSIONE "
                    "IL 23/12/2026 09:30 Note: Notificato alla PEC / in cancelleria il 09/11/2026 14:54"
                ),
            }
        ],
    )
    assert not any(item["creates_notification_candidate"] for item in findings)
