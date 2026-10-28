import hashlib
from copy import deepcopy
import pytest
from lex.normativa.applicabilita import impronta, valuta_applicabilita

SHA = "a" * 64

def event(value="2026-12-31"):
    return {"notifica": {"data": value, "confermato": True, "fonte_sha256": SHA}}

def source():
    return {"atto_id": "urn:test:atto:1", "ambito": "processuale", "evento_riferimento": "notifica"}

def rule(start=None, end=None, outcome="applicabile"):
    text = "Disposizione simulata per test: applicazione dal primo gennaio."
    return {"atto_id": "urn:test:atto:1", "ambito": "processuale", "evento": "notifica",
            "dal": start, "al_escluso": end, "esito": outcome,
            "fonte": {"url": "https://example.org/test", "versione": "fixture",
                      "acquisita_il": "25/10/2026", "testo": text, "estratto": "applicazione dal primo gennaio",
                      "sha256": hashlib.sha256(text.encode()).hexdigest()}}

def evaluate(rules, events=None):
    f=source()
    f["copertura_versione"]={"dal":"2026-01-01","al_escluso":"2030-01-01","confermata":True}
    return valuta_applicabilita(f, event() if events is None else events,
                                rules, frozenset(impronta(r) for r in rules))

def test_exclusive_boundary_and_no_today_fallback():
    rules = [rule(end="2027-01-01", outcome="non_applicabile"), rule(start="2027-01-01")]
    assert evaluate(rules).stato == "non_applicabile"
    assert evaluate(rules, event("2027-01-01")).stato == "applicabile"
    assert evaluate(rules, {}).stato == "da_verificare"

def test_changed_rule_invalidates_approval_and_ai_flag_does_not_approve():
    r = rule(); approved = frozenset({impronta(r)})
    r["esito"] = "non_applicabile"; r["approved"] = True
    assert valuta_applicabilita(source(), event(), [r], approved).stato == "da_verificare"

def test_conflicting_rules_fail_closed():
    assert evaluate([rule(), rule(outcome="non_applicabile")]).stato == "da_verificare"

def test_event_must_be_confirmed_and_provenanced():
    e = event();e["notifica"]["confermato"] = False
    assert evaluate([rule()], e).stato == "da_verificare"
    e = event();e["notifica"]["fonte_sha256"] = "not-a-hash"
    assert evaluate([rule()], e).stato == "da_verificare"

def test_rule_source_must_match_acquired_text():
    r = rule();r["fonte"]["testo"] += " alterato"
    assert evaluate([r]).stato == "da_verificare"

def test_no_latest_snapshot_as_historical_version():
    f = source();f["vigenza"] = "VIGENTE";f["raccolto_il"] = "2026-10-25"
    assert valuta_applicabilita(f, event(), [], frozenset()).stato == "da_verificare"
    f["copertura_versione"] = {"dal": "2026-01-01", "al_escluso": "2027-01-01", "confermata": True}
    assert valuta_applicabilita(f, event(), [], frozenset()).stato == "applicabile"
    assert valuta_applicabilita(f, event("2021-01-01"), [], frozenset()).stato == "da_verificare"

def test_substantive_and_procedural_dates_are_distinct():
    f = source();f["ambito"] = "sostanziale"
    result = valuta_applicabilita(f, event(), [rule()], frozenset({impronta(rule())}))
    assert result.stato == "da_verificare"


def test_transitoria_positiva_non_approva_versione_assente_o_fuori_data():
    r=rule();approved=frozenset({impronta(r)});f=source()
    assert valuta_applicabilita(f,event(),[r],approved).stato=="da_verificare"
    f["copertura_versione"]={"dal":"2020-01-01","al_escluso":"2021-01-01","confermata":True}
    assert valuta_applicabilita(f,event(),[r],approved).stato=="da_verificare"
    f["copertura_versione"]={"dal":"2026-01-01","al_escluso":"2027-01-01","confermata":True}
    assert valuta_applicabilita(f,event(),[r],approved).stato=="applicabile"


@pytest.mark.parametrize("events,name",[(None,"notifica"),([],"notifica"),({},[]),({},True),({},"")])
def test_evento_non_strutturato_non_diventa_data_confermata(events,name):
    from lex.normativa.applicabilita import data_evento_confermato
    assert data_evento_confermato(events,name) is None
