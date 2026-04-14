from web.services.assistente_conversation_focus import resolve_conversation_focus
from web.services.assistente_live_web import build_live_official_web_context
from web.services.assistente_web_execution import (
    is_web_execution_request,
    resolve_effective_query,
)


def test_focus_conversazionale_instrada_richiesta_tematizzata_breve():
    focus = resolve_conversation_focus("udienze")

    assert focus["topic"] == "udienze"
    assert "Agenda" in focus["section_titles"]
    assert "Fascicoli" in focus["section_titles"]
    assert focus["focus_label"] == "udienze rilevanti"
    assert focus["include_live_web"] is False


def test_focus_conversazionale_recupera_follow_up_dalla_storia():
    focus = resolve_conversation_focus(
        "quelli attivi",
        messages=[
            {"role": "user", "content": "Mostrami le udienze imminenti"},
            {"role": "assistant", "content": "Ti mostro le udienze piu' vicine."},
        ],
    )

    assert focus["topic"] == "udienze"
    assert focus["is_follow_up"] is True
    assert focus["focus_label"] == "procedimenti attivi"
    assert focus["effective_question"].startswith("udienze ")


def test_web_execution_request_riconosce_follow_up_operativo():
    assert is_web_execution_request("puoi controllare tu sul web") is True
    assert (
        resolve_effective_query(
            "puoi controllare tu sul web",
            "ultime sentenze sul civile tutti gli ambienti",
        )
        == "ultime sentenze sul civile tutti gli ambienti"
    )


def test_focus_conversazionale_eredita_tema_precedente_per_richiesta_web_breve():
    focus = resolve_conversation_focus(
        "puoi controllare tu sul web",
        messages=[
            {"role": "user", "content": "Ultime sentenze sul civile tutti gli ambienti"},
            {"role": "assistant", "content": "Posso controllare le sentenze civili piu' recenti."},
        ],
    )

    assert focus["topic"] == "sentenze_civili"
    assert focus["include_live_web"] is True
    assert focus["web_execution_requested"] is True
    assert focus["inherited_previous_theme"] is True
    assert focus["effective_question"] == "Ultime sentenze sul civile tutti gli ambienti"


def test_focus_conversazionale_dedica_un_intento_alle_sentenze_civili():
    focus = resolve_conversation_focus("ricerca web sentenze civili")

    assert focus["topic"] == "sentenze_civili"
    assert focus["focus_label"] == "sentenze civili recenti"
    assert focus["include_live_web"] is True
    assert focus["research_strategy"] == "auto_narrow_recent_civil_case_law"
    assert "Archivio sentenze" in focus["section_titles"]
    assert "Ricerca legale e fonti web" in focus["section_titles"]


def test_focus_conversazionale_eredita_il_fascicolo_per_followup_operativo_generico():
    focus = resolve_conversation_focus(
        "Qual e' la prossima attivita' operativa?",
        messages=[
            {"role": "user", "content": "Ho appena aperto il fascicolo."},
            {"role": "assistant", "content": "Perfetto, possiamo impostare le prossime azioni."},
        ],
    )

    assert focus["topic"] == "fascicoli"
    assert focus["is_follow_up"] is True
    assert focus["focus_label"] == "procedimenti attivi"
    assert focus["effective_question"].startswith("fascicoli ")


def test_live_web_context_supporta_force_fallback_senza_keyword_esplicita():
    class FakeResponse:
        status_code = 200
        url = "https://www.normattiva.it/"
        headers = {"content-type": "text/html; charset=utf-8"}
        text = "<html><head><title>Normattiva</title><meta name='description' content='Portale ufficiale normativa'></head><body><h1>Normattiva</h1></body></html>"

    payload = build_live_official_web_context(
        "contesto interno debole",
        force=True,
        request_get=lambda *args, **kwargs: FakeResponse(),
    )

    assert payload["source_ids"]
    assert payload["sources"]
    assert payload["citations"]
