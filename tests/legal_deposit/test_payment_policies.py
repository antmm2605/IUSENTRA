from __future__ import annotations

from legal_deposit.payment_policies import (
    list_payment_policies,
    payment_policy_for_channel,
    payment_policy_for_procedure,
)
from legal_deposit.policies import channel_profile_for


def test_pst_pagopa_policy_uses_rt_xml_and_official_statuses() -> None:
    policy = payment_policy_for_channel("pct_sicid")

    assert policy is not None
    assert policy.id == "pst_pagopa_cu_diritti_spese"
    assert "RT.xml" in policy.proof_documents
    assert {"DISPONIBILE", "USATO", "OK_PSP", "RIMBORSATO"}.issubset(policy.accepted_statuses)
    assert {"CONTRIB", "DIRCANC", "DIRCOPIA", "CONTRBENI", "UNPIG", "UNNOT"}.issubset(policy.collection_codes)
    assert policy.forbids_continuous_polling is True
    assert any("servizipst.giustizia.it/PST/it/pagopa.wp" in source for source in policy.official_sources)


def test_pat_policy_records_f24_elide_fields_and_profile_metadata() -> None:
    policy = payment_policy_for_channel("pat_siga")
    profile = channel_profile_for("pat_siga")

    assert policy is not None
    assert policy.id == "pat_f24_elide_contributo_unificato"
    assert profile.metadata["payment_policy"] == policy.id
    assert {"data_versamento", "codice_tributo", "numero_riga", "elementi_identificativi"}.issubset(
        policy.required_inputs
    )
    assert {"GA01", "GA02", "GA03", "GA04", "GA05"}.issubset(policy.collection_codes)
    assert "quietanza_f24_elide" in policy.proof_documents


def test_ptt_cut_policy_is_attached_to_payment_procedures() -> None:
    policy = payment_policy_for_procedure("PTT_RICORSO")

    assert policy is not None
    assert policy.id == "ptt_cut_pagopa"
    assert policy.metadata["auto_association_to_rgr_rga"] is True
    assert policy.metadata["receipt_deposit_required_when_auto_associated"] is False
    assert "RGR_RGA" in policy.required_inputs
    assert any("mef.gov.it" in source for source in policy.official_sources)


def test_non_payment_procedure_does_not_force_payment_policy() -> None:
    assert payment_policy_for_procedure("PTT_CONSULTAZIONE_FASCICOLO") is None


def test_payment_policy_registry_covers_telematic_payment_channels() -> None:
    policies = {policy.id for policy in list_payment_policies()}
    assert {
        "pst_pagopa_cu_diritti_spese",
        "pat_f24_elide_contributo_unificato",
        "ptt_cut_pagopa",
    }.issubset(policies)
