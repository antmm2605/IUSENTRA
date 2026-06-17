from pct.pst_cifratura import (
    canali_telematici_cifratura_policy,
    valida_canale_telematico_per_cifratura,
)


def test_policy_canali_telematici_copre_pct_pat_ptt_pdp():
    policy = canali_telematici_cifratura_policy()

    assert {"pct_civile_dm44", "pdp_penale", "pat_amministrativo", "ptt_tributario"} <= set(policy)
    assert policy["pct_civile_dm44"]["usa_certificati_pst_cer"] is True
    assert policy["pdp_penale"]["usa_certificati_pst_cer"] is False
    assert policy["pat_amministrativo"]["usa_certificati_pst_cer"] is False
    assert policy["ptt_tributario"]["usa_certificati_pst_cer"] is False


def test_canali_non_pct_non_possono_usare_cer_atto_enc():
    for canale in ("pdp_penale", "pat_amministrativo", "ptt_tributario"):
        audit = valida_canale_telematico_per_cifratura(canale)

        assert audit["ok"] is True
        assert audit["usa_certificati_pst_cer"] is False
        assert audit["procedura"] == "procedura_dedicata_non_pst"
        assert any("non usare .cer PST" in item for item in audit["controlli_software"])


def test_canale_pct_richiede_cer_e_atto_enc_aes256():
    audit = valida_canale_telematico_per_cifratura("pct_civile_dm44")

    assert audit["ok"] is True
    assert audit["usa_certificati_pst_cer"] is True
    assert audit["procedura"] == "cifratura_pst_atto_enc"
    assert "Atto.enc AES256" in " ".join(audit["controlli_software"])
