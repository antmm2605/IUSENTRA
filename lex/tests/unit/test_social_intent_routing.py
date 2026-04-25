from __future__ import annotations

from lex.memory.social_intent import (
    build_daily_overview_lead,
    build_relational_reply,
    build_social_only_reply,
    build_social_prefix,
    is_daily_overview_request,
    is_operational_internal_topic,
    is_referential_followup,
    is_small_talk_message,
    latest_user_message,
    prepend_social_prefix,
    resolve_social_and_operational_intent,
    split_social_and_request,
)


def test_social_intent_copre_saluti_ringraziamenti_conferme_chiusure_e_scuse():
    cases = {
        "buongiorno": "Buongiorno. Dimmi pure.",
        "grazie mille": "Di nulla.",
        "perfetto": "Perfetto.",
        "a domani": "A domani.",
        "scusami": "Nessun problema.",
        "bravo": "Grazie.",
    }

    for message, expected_reply in cases.items():
        routing = resolve_social_and_operational_intent(message)
        assert routing.is_social_only is True
        assert routing.effective_query == ""
        assert build_social_only_reply(routing.social_kind, routing.raw_text) == expected_reply


def test_social_intent_distingue_smalltalk_da_richiesta_operativa_mista():
    smalltalk = resolve_social_and_operational_intent("come stai oggi")
    mixed = resolve_social_and_operational_intent("ciao controlla le udienze di oggi")

    assert smalltalk.social_kind == "smalltalk"
    assert smalltalk.is_followup is False
    assert build_relational_reply("come stai oggi") == "Bene, grazie. Dimmi pure."
    assert is_small_talk_message("tutto bene") is True

    assert mixed.social_kind == "greeting_with_request"
    assert mixed.is_social_with_request is True
    assert mixed.request_text == "controlla le udienze di oggi"
    assert mixed.effective_query == "controlla le udienze di oggi"
    assert mixed.social_prefix == "Ciao."


def test_social_intent_followup_riusa_tema_precedente_solo_quando_serve():
    daily_followup = resolve_social_and_operational_intent(
        "cosa dobbiamo fare",
        previous_user_text="udienze e scadenze del fascicolo 1025/2024",
    )
    referential = resolve_social_and_operational_intent(
        "e adesso",
        previous_user_text="sincronizza fascicolo GDP 466/2023",
    )
    standalone_daily = resolve_social_and_operational_intent("quadro di oggi")

    assert daily_followup.is_followup is True
    assert daily_followup.reused_previous_topic is True
    assert "udienze e scadenze" in daily_followup.effective_query
    assert referential.reason == "referential_followup_reused_previous"
    assert standalone_daily.is_daily_overview is True
    assert standalone_daily.is_followup is False


def test_social_intent_helper_operativi_e_prefix_restano_stabili():
    assert split_social_and_request("salve Lex") == ("greeting", "salve", "")
    assert split_social_and_request("ok verifica i documenti") == ("ack", "ok", "verifica i documenti")
    assert is_daily_overview_request("oggi cosa dobbiamo fare") is True
    assert is_operational_internal_topic("controlla fascicoli e documenti") is True
    assert is_referential_followup("quello prima") is True
    assert is_referential_followup("questa frase e troppo lunga per essere un follow up puntuale", max_words=4) is False
    assert build_social_prefix("farewell", "buon lavoro") == "Grazie, buon lavoro anche a te."
    assert prepend_social_prefix("Buongiorno.", "Buongiorno. Ti aggiorno subito.") == "Buongiorno. Ti aggiorno subito."
    assert build_daily_overview_lead("Buongiorno.") == "Buongiorno. Ti faccio subito il quadro operativo di oggi."


def test_latest_user_message_salta_assistente_e_supporta_skip_last():
    messages = [
        {"role": "system", "content": "setup"},
        {"role": "user", "content": "prima richiesta"},
        {"role": "assistant", "content": "risposta"},
        {"role": "user", "content": "ultima richiesta"},
    ]

    assert latest_user_message(messages) == "ultima richiesta"
    assert latest_user_message(messages, skip_last=True) == "prima richiesta"
    assert latest_user_message([{"role": "assistant", "content": "solo risposta"}]) == ""

