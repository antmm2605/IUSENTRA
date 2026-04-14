from web.services.assistente_language_guidance import build_language_guidance


def test_language_guidance_prende_in_carico_ricerca_sentenze_civili():
    guidance = build_language_guidance(
        question="ricerca web sentenze civili",
        research_strategy="auto_narrow_recent_civil_case_law",
        focus_topic="sentenze_civili",
        web_execution_requested=True,
    )

    assert guidance.mode == "civil_case_law_web"
    assert guidance.opening_line == (
        "Controllo io sul web. Parto dalle sentenze civili piu' recenti e rilevanti, "
        "dando precedenza alla Cassazione e alle fonti ufficiali disponibili."
    )
    assert "niente saluti automatici" in guidance.prompt_block
    assert "Cassazione" in guidance.prompt_block


def test_language_guidance_mantiene_prefisso_sociale_su_richiesta_web_operativa():
    guidance = build_language_guidance(
        question="buongiorno, verifica normativa pec aggiornata",
        social_prefix="Buongiorno.",
        web_execution_requested=True,
    )

    assert guidance.mode == "normative_web"
    assert guidance.opening_line.startswith("Buongiorno. ")
    assert "Controllo io sul web." in guidance.opening_line


def test_language_guidance_costruisce_overview_giornaliera_sobria():
    guidance = build_language_guidance(
        question="oggi cosa dobbiamo fare",
        social_prefix="Buongiorno.",
        is_daily_overview=True,
    )

    assert guidance.mode == "daily_overview"
    assert guidance.opening_line == "Buongiorno. Ti faccio subito il quadro operativo di oggi."
    assert "quadro operativo della giornata" in guidance.prompt_block
