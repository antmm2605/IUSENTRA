from pct.practice_engine import get_profile, list_profiles
from pct.practice_engine.deposit_orchestrator import send_deposit
from tests.regia_test_utils import make_simple_fascicolo


def test_canali_telematici_hanno_regole_distinte():
    channels = {profile.channel: profile for profile in list_profiles()}
    assert channels["PCT_CIVILE"].depositable is True
    assert channels["PDP_PENALE"].depositable is True
    assert channels["SIGP_GDP"].depositable is True
    assert channels["PAT_AMMINISTRATIVO"].depositable is True
    assert channels["PTT_TRIBUTARIO"].depositable is True
    assert channels["PEC_ONLY"].depositable is False
    assert channels["INTERNO_STUDIO"].depositable is False


def test_pdp_non_usa_pec_generica_e_sigp_richiede_xsd():
    pdp = get_profile("PROC_PEN_001")
    sigp = get_profile("PROC_SIGP_GDP_001")
    assert pdp.channel == "PDP_PENALE"
    assert "PDP" in pdp.channel
    assert "schema_xsd_presente" in sigp.blocking_validators


def test_canale_senza_adapter_non_dichiara_invio_reale(tmp_path):
    gf, repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    session = repo.create_deposit_session(fascicolo.id, profile.code, profile.channel, status="PRONTO")
    result = send_deposit(repo, session_id=session.id, fascicolo=fascicolo, profile=profile, fascicoli_manager=gf, adapter=None, accept_warnings=True)
    assert result["sent"] is False
    assert result["session"].real_transport is False
    assert result["session"].simulated is False
    assert result["session"].transport_mode in {"non_configurato", "predeposito"}
