from web.services.assistente_execution_policy import build_execution_policy


def test_execution_policy_tratta_il_llm_come_voce_e_non_come_fonte_di_verita():
    policy = build_execution_policy(
        question="ricerca web sentenze civili recenti",
        focus_topic="sentenze_civili",
        verified_legal_references=[],
        web_execution_requested=True,
    )

    assert policy.mode == "strict_verified_sources"
    assert policy.llm_role == "voce_e_ragionamento_locale"
    assert policy.truth_strategy == "fonti_ufficiali_verificate"
    assert policy.requires_verified_legal_reference is True
    assert policy.allow_web_fallback is True
    assert "il modello serve per tono umano, scrittura, sintesi" in policy.prompt_block.lower()
    assert "non puo' stabilire da solo cosa e' vero" in policy.prompt_block


def test_execution_policy_blocca_stati_interni_non_verificati():
    policy = build_execution_policy(
        question="qual e' lo stato reale del fascicolo attivo",
        focus_topic="fascicoli",
        verified_legal_references=[],
        web_execution_requested=False,
    )

    assert policy.mode == "strict_internal_state"
    assert policy.requires_internal_state_source is True
    assert policy.requires_verified_legal_reference is False
    assert policy.truth_strategy == "contesto_applicativo_interno"
