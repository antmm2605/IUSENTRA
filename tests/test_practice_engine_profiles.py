from pct.legal_platform_catalog import PROCEDURE_REGISTRY
from pct.practice_engine.profiles import build_profile_from_procedure, get_profile, list_profiles
from pct.practice_engine.resolver import resolve_practice_profile


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
    assert {"PCT_CIVILE", "PDP_PENALE", "PAT_AMMINISTRATIVO", "PTT_TRIBUTARIO", "SIGP_GDP"} <= channels
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
