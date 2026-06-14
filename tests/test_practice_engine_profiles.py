from types import SimpleNamespace

from legal_deposit.policies import channel_profile_for, list_channel_profiles
from pct.legal_platform_catalog import PROCEDURE_REGISTRY
from pct.practice_engine.evaluator import _deposit_delivery_policy
from pct.practice_engine.profiles import build_profile_from_procedure, get_profile, list_profiles
from pct.practice_engine.resolver import resolve_practice_profile
from pct.practice_engine.validators import ValidationContext, codice_oggetto_pst_valido
from pct.pratiche_collegate_catalog import normalize_codice_oggetto_pst


def test_ogni_procedura_operativa_genera_profilo_valido():
    for procedure in PROCEDURE_REGISTRY.values():
        profile = build_profile_from_procedure(procedure)
        assert profile.code
        assert profile.name
        assert profile.channel
        assert profile.registry
        assert profile.workflow_code
        assert profile.required_documents
        assert profile.required_slots


def test_famiglie_pratica_principali_presenti():
    profiles = list_profiles()
    channels = {profile.channel for profile in profiles}
    areas = " ".join(profile.area.lower() for profile in profiles)
    assert {"PCT_CIVILE", "PCT_LAVORO", "PDP_PENALE", "PAT_AMMINISTRATIVO", "PTT_TRIBUTARIO", "SIGP_GDP"} <= channels
    for expected in (
        "privacy",
        "231",
        "succession",
        "bancario",
        "assicurativo",
        "societario",
        "crisi",
        "appalt",
        "immigrazione",
        "sanitario",
        "consumatori",
    ):
        assert expected in areas or any(expected in profile.name.lower() for profile in profiles)


def test_documenti_checklist_deadlines_diventano_slot_e_payload():
    profile = get_profile("PROC_LIC_IMP_001")
    assert profile is not None
    assert any(slot["slot_key"] == "ATTO_PRINCIPALE" for slot in profile.required_slots)
    assert any(slot["slot_key"] == "PROCURA" for slot in profile.required_slots)
    assert profile.checklist_items
    assert profile.deadlines
    assert profile.template_labels
    assert profile.depositable is True
    assert profile.channel == "PCT_LAVORO"


def test_resolver_da_preventivo_conferimento_fascicolo_e_fallback_manuale():
    class Obj:
        pass

    preventivo = Obj()
    preventivo.procedura_operativa_codice = "PROC_LIC_IMP_001"
    result = resolve_practice_profile(preventivo=preventivo)
    assert result.profile.code == "PROC_LIC_IMP_001"
    assert result.confidence >= 0.9

    conferimento = Obj()
    conferimento.id_pratica = "licenziamento"
    result = resolve_practice_profile(conferimento=conferimento)
    assert result.profile.code == "PROC_LIC_IMP_001"

    fascicolo = Obj()
    fascicolo.workflow_operativo_codice = "WF_LAVORO_IMPUGNAZIONE_LICENZIAMENTO"
    result = resolve_practice_profile(fascicolo=fascicolo)
    assert result.profile

    manual = resolve_practice_profile(manual_code="PROC_SIGP_GDP_001")
    assert manual.profile.code == "PROC_SIGP_GDP_001"
    assert manual.needs_manual_confirmation is False

    unknown = resolve_practice_profile(payload={"oggetto": ""})
    assert unknown.needs_manual_confirmation is True
    assert unknown.alternatives


def test_codice_oggetto_pst_lavoro_risolve_canale_deposito_senza_manualita():
    fascicolo = SimpleNamespace(
        tipo="LAVORO",
        oggetto="222050 - Retribuzione",
        codice_oggetto_pst="222050 - Retribuzione",
    )

    assert normalize_codice_oggetto_pst(fascicolo.codice_oggetto_pst) == "222050"
    result = resolve_practice_profile(fascicolo=fascicolo)

    assert result.profile is not None
    assert result.profile.code == "PROC_LAV_RETRIB_001"
    assert result.profile.channel == "PCT_LAVORO"
    assert result.profile.registry == "SICID"
    assert result.confidence >= 0.9
    assert result.needs_manual_confirmation is False

    validation = codice_oggetto_pst_valido(ValidationContext(fascicolo=fascicolo, profile=result.profile))
    assert validation.status == "OK"
    assert validation.evidence["codice_oggetto_pst"] == "222050"


def test_matrice_canali_deposito_non_viene_ridotta_al_solo_pct():
    channels = {profile.id for profile in list_channel_profiles()}
    assert {
        "pct_sicid",
        "pct_siecic",
        "sigp_gdp",
        "unep",
        "pdp_penale",
        "pat_siga",
        "ptt_sigit",
        "pec_stragiudiziale",
        "notifiche_pec",
    } <= channels


def test_tutti_i_profili_depositabili_hanno_canale_ministeriale_o_portale_risolto():
    profiles = [profile for profile in list_profiles() if profile.depositable]

    assert profiles
    for profile in profiles:
        policy = _deposit_delivery_policy(profile)

        assert policy["mode"] in {"direct_pec", "portal_upload"}
        assert policy["packageKind"]
        assert policy["officialChannel"]
        assert policy["sendButtonLabel"] not in {"Conferma canale", "Invia deposito"}
        assert policy["documentIndexGeneratedBySoftware"] is True


def test_alias_canali_deposito_non_ambigui_coprono_la_matrice_operativa():
    expected_aliases = {
        "pct_sicid": "pct_sicid",
        "pct_siecic": "pct_siecic",
        "sigp": "sigp_gdp",
        "unep": "unep",
        "pdp": "pdp_penale",
        "pat": "pat_siga",
        "ptt": "ptt_sigit",
        "pec": "pec_stragiudiziale",
        "notifica_pec": "notifiche_pec",
    }

    for alias, expected_id in expected_aliases.items():
        assert channel_profile_for(alias).id == expected_id
