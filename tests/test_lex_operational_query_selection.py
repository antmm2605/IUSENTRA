from datetime import date

import pytest

from lex.operational_knowledge.query_selection import resolve_query_selection


def select(question):
    return resolve_query_selection(question, today=date(2026, 10, 16))


def test_udienze_non_significa_tutti_gli_appuntamenti_del_giorno():
    assert select('udienze oggi').kinds == ('UDIENZA',)
    assert select('agenda oggi').kinds == ()


@pytest.mark.parametrize('question', ['agenda oggi', 'scadenze ieri', 'PEC ricevute oggi', 'notifiche da fare domani'])
def test_contesto_cliente_o_fascicolo_non_diventa_ricerca_globale(question):
    from lex.operational_knowledge.query_router import OperationalQueryRouter

    route = OperationalQueryRouter().route(question, metadata={'active_context': {'case_id': 'controlled-case'}})
    assert route is None or route.intent not in {'pec_query_page', 'notification_query_page', 'calendar_query_page'}


def test_percorso_pagina_specifica_non_perde_il_contesto_prima_del_router():
    from lex.operational_knowledge.query_selection import has_scoped_query_context

    assert has_scoped_query_context({'page_path': '/fascicoli/controlled#documenti'})
    assert has_scoped_query_context({'active_context': {'page_path': '/clienti/controlled'}})
    assert not has_scoped_query_context({'page_path': '/fascicoli'})


@pytest.mark.parametrize("day", ["14 10 2026", "14/10/26", "14/10/2026", "14.10.2026", "14-10-2026", "14-10-26"])
@pytest.mark.parametrize("domain,expected", [("PEC ricevute", "pec"), ("Agenda", "agenda"), ("Scadenze", "deadlines"), ("Depositi accettati", "deposits"), ("Notifiche accettate", "legal_notifications")])
def test_stesso_periodo_per_ogni_dominio(day, domain, expected):
    value = select(f"{domain} il {day}")
    assert value.domain == expected
    assert not value.error
    assert value.dates.ranges == ((date(2026, 10, 14), date(2026, 10, 14)),)


def test_accettazione_cancelleria_distinta_da_gestore_e_rac():
    registry = select("depositi accettati ieri")
    transport = select("depositi accettati dal gestore ieri")
    notification = select("notifiche accettate ieri")
    assert (registry.states, registry.date_axis) == (("ACCETTATO_CANCELLERIA",), "registry_acceptance_at")
    assert (transport.states, transport.date_axis) == (("ACCETTATO_PEC",), "pec_acceptance_at")
    assert (notification.states, notification.date_axis) == (("rac_received",), "rac_at")
    assert select("depositi accettati PEC ieri").states == ("ACCETTATO_PEC",)


def test_metadata_opzionali_preservano_il_contratto_precedente():
    from lex.operational_knowledge.models import OperationalToolResult

    result = OperationalToolResult(True, "email_pec", data=[])
    assert "query_metadata" not in result.to_dict()
    result.query_metadata = {"has_more": True, "cursor": ["data", "id"]}
    assert result.to_dict()["query_metadata"] == result.query_metadata


@pytest.mark.parametrize("question", ["depositi da fare domani", "notifiche da fare domani"])
def test_attivita_da_fare_usano_scadenza_non_creazione(question):
    value = select(question)
    assert value.states == ("pending",)
    assert value.date_axis == "due_on"


def test_cestino_non_implica_ricevuta_e_date_non_cambiano_dominio():
    value = select("PEC inviate nel cestino oggi")
    assert (value.domain, value.folder, value.direction) == ("pec", "trash", "sent")
    assert select("agenda oggi").domain == "agenda"
    assert select("scadenziario oggi").domain == "deadlines"


def test_dati_ambigui_non_diventano_una_selezione_silenziosa():
    assert select("PEC ricevute e inviate oggi").error
    assert select("agenda e scadenze oggi").error
    assert select("PEC ricevute il 31/02/2026").error
    assert select("notifiche operative oggi") is None
    assert select("art. 327 procedura civile") is None


def test_stati_agenda_e_scadenze_non_confusi():
    assert select("appuntamenti rinviati ieri").states == ("RINVIATO",)
    assert select("scadenze completate ieri").states == ("COMPLETATO",)
    assert select("scadenze aperte oggi").states == ("APERTO",)


@pytest.mark.parametrize("question", ["PEC ricevute il 14/10/26", "quali PEC ho ricevuto ieri", "PEC inviate nel cestino oggi"])
def test_route_posta_semplice_non_carica_altri_domini(question):
    from lex.operational_knowledge.query_router import OperationalQueryRouter

    route = OperationalQueryRouter().route(question)
    assert route.intent == 'pec_query_page'
    assert route.source_ids == ('email_pec',)
    assert route.entity_query == ''


@pytest.mark.parametrize("question", ["PEC del cliente Rossi", "PEC con allegati", "ultima PEC ricevuta", "invia PEC oggi"])
def test_non_si_perdono_filtri_complessi_o_blocco_azioni(question):
    from lex.operational_knowledge.query_router import OperationalQueryRouter

    assert OperationalQueryRouter().route(question).intent != 'pec_query_page'


def test_risposta_pagina_vuota_non_e_un_errore_di_lettura():
    from lex.operational_knowledge.models import OperationalRoute, OperationalToolResult
    from lex.operational_knowledge.response_composer import OperationalResponseComposer

    route = OperationalRoute('pec_query_page', 'pec_query_page', ('email_pec',))
    result = OperationalToolResult(True, 'email_pec', data=[], query_metadata={
        'ranges': [['2026-10-14', '2026-10-14']], 'direction': 'received', 'has_more': False,
    })
    composer = OperationalResponseComposer()
    answer = composer.compose(question='PEC ieri', route=route, results=[result])
    assert 'Nessuna PEC corrisponde' in answer.answer
    assert '14 ottobre 2026' in answer.answer
    assert not answer.blocked_reason
    failed = composer.compose(question='PEC ieri', route=route, results=[
        OperationalToolResult(False, 'email_pec', coverage_gaps=['Indice della casella da riallineare.'])])
    assert 'Non ho eseguito' in failed.answer
    assert 'Nessuna PEC corrisponde' not in failed.answer
    assert failed.blocked_reason


def test_data_non_valida_non_diventa_errore_permessi():
    from lex.operational_knowledge.integration import _confidence_reason
    from lex.operational_knowledge.models import OperationalRoute, OperationalToolResult
    from lex.operational_knowledge.response_composer import OperationalResponseComposer
    from lex.operational_knowledge.unified_chat import LexSourceVerifier

    route = OperationalRoute('pec_query_page', 'pec_query_page', ('email_pec',))
    result = OperationalToolResult(False, 'email_pec', blocked_reason='invalid_query_selection',
                                   coverage_gaps=['Data non valida: 31/02/2026'])
    answer = OperationalResponseComposer().compose(question='PEC 31/02/2026', route=route, results=[result])
    assert answer.blocked_reason == 'invalid_query_selection'
    assert 'parametri' in _confidence_reason(answer)
    report = LexSourceVerifier().verify(answer=answer, detected_intent=route.intent,
                                       structured_context={}, sources=[])
    assert not report['allowed']
    assert 'Accesso non autorizzato' not in str(report)
    answer.blocked_reason = 'missing_permission'
    report = LexSourceVerifier().verify(answer=answer, detected_intent=route.intent,
                                       structured_context={}, sources=[])
    assert not report['allowed']
    assert 'Accesso non autorizzato' in str(report)
