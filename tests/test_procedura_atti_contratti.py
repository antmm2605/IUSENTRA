"""Comportamenti professionali sintetici, non casi del banco di misura."""
import copy

import pytest

from lex.procedura_atti.contabilita import prospetto, verifica_credito
from lex.procedura_atti.controlla_atto import controlla
from lex.procedura_atti.verifica_scheda import verifica
from tests.test_procedura_atti import FONTI, _caso, _scheda


def test_accounting_keeps_capital_interest_costs_and_unassigned_separate():
    credit = {"voci": [{"id": "F", "centesimi": 100000, "citazione": "1.000 euro"}],
              "pagamenti": [
                  {"id": "P", "centesimi": 20000, "citazione": "200 euro", "imputazione": "voce:F"},
                  {"id": "I", "centesimi": 1000, "citazione": "10 euro", "imputazione": "interessi"},
                  {"id": "S", "centesimi": 500, "citazione": "5 euro", "imputazione": "spese"},
                  {"id": "U", "centesimi": 300, "citazione": "3 euro", "imputazione": "da_imputare"}],
              "spese": [{"centesimi": 2000, "citazione": "20 euro"}]}
    assert verifica_credito(credit, "1.000 euro, 200 euro, 10 euro, 5 euro, 3 euro, 20 euro") == []
    result = prospetto(credit)
    assert result["residuo_capitale"] == "800,00"
    assert result["pagato_a_interessi"] == "10,00"
    assert result["pagato_a_spese"] == "5,00"
    assert result["pagamenti_da_imputare"] == ["U"]
    credit["pagamenti"][0]["centesimi"] = 120000
    assert prospetto(credit)["voci_negative"] == ["F"]


@pytest.mark.parametrize("allocation", ["voce:ASSENTE", "scelta_automatica"])
def test_unknown_payment_allocation_rejected(allocation):
    credit = {"voci": [], "pagamenti": [{"id": "P", "centesimi": 100,
              "citazione": "1 euro", "imputazione": allocation}]}
    assert verifica_credito(credit, "1 euro")


def draft_case():
    return {"fonti_ref": [{"n": 1, "articolo": "325", "sigla": "c.p.c."}],
            "fonti": "[1] Art. 325 c.p.c. rinvia all'art. 617.",
            "scheda_risolta": "", "scadenze": [], "oggi": "24/10/2026",
            "assistito": {"nome": "Rosa Fiorentino", "ruolo": "appellante"},
            "controparte": {"nome": "Edil Sud"}, "dati_mancanti": []}


@pytest.mark.parametrize("text, expected", [
    ("art. 325 c.p.c. [1]", None),
    ("art. 325 c.c. [1]", "numero_sbagliato"),
    ("art. 325 c.p.c. [9]", "richiamo_inesistente"),
    ("art. 100 c.p.c.", "norma_fuori_fonti"),
    ("art. 617 [1]", None),
    ("art. 325 c.p.c.", None),
    ("art. 42", None),
    ("Il 01/01/2099 si terrà l'udienza", "data_inventata"),
    ("Si chiede di rigettare il presente ricorso", "contro_il_cliente"),
    ("Si chiede di condannare Rosa Fiorentino", "contro_il_cliente"),
    ("<think>ragionamento</think>", "lingua"),
])
def test_draft_references_client_direction_and_dates(text, expected):
    case = draft_case()
    result = controlla(text + " Rosa Fiorentino. " + "Argomentazione italiana. " * 20, case)
    if expected:
        assert expected in result["tipi"]
    else:
        assert result["ok"], result


def test_missing_data_and_defendant_interests_are_not_silently_changed():
    case = draft_case()
    case["dati_mancanti"] = ["data"]
    assert "dati_inventati" in controlla("Rosa Fiorentino. " * 30, case)["tipi"]
    case["assistito"]["ruolo"] = "convenuto"
    assert "contro_il_cliente" in controlla("accogliere la domanda avversaria " * 15, case)["tipi"]


@pytest.mark.parametrize("field,value,fragment", [
    ("forma_risposta", "altro", "forma_risposta"),
    ("domande", [], "nessuna domanda"),
    ("domande", ["rigettare il presente ricorso"], "contraria"),
    ("parte_assistita", {"nome": "Altra persona"}, "diversa"),
])
def test_sheet_cannot_change_client_or_delivery(field, value, fragment):
    sheet = _scheda()
    sheet[field] = value
    assert any(fragment in error for error in verifica(sheet, _caso(), FONTI))


@pytest.mark.parametrize("change,fragment", [
    ({"evento": {"da_termine": "ASSENTE"}}, "non dichiarato"),
    ({"evento": {"data": "10/03/2027", "citazione_fatti": "evento inventato"}}, "evento non trovata"),
    ({"evento": {"data": "11/03/2027", "citazione_fatti": "Il 10/03/2027 la sentenza n. 120/2027"}}, "data dell"),
    ({"regola": {"fonte": 9, "citazione": "inesistente"}}, "regola non trovata"),
    ({"regola": {"fonte": 1, "citazione": "notificazione della sentenza"}}, "durata non compare"),
    ({"natura": "scelta"}, "natura"),
    ({"sospensione_feriale": True, "motivo_sospensione": ""}, "senza motivo"),
    ({"motivazione": ""}, "motivazione"),
])
def test_deadline_provenance_is_required(change, fragment):
    sheet = _scheda()
    sheet["termini"][0].update(copy.deepcopy(change))
    assert any(fragment in error for error in verifica(sheet, _caso(), FONTI))


@pytest.mark.parametrize("operand", [
    {"provenienza": "importo:ASSENTE"}, {"provenienza": "sconosciuta"},
    {"provenienza": "moltiplicatore", "valore": 2.5},
    {"provenienza": "moltiplicatore", "valore": 20},
])
def test_credit_operations_cannot_invent_origin(operand):
    sheet = _scheda()
    sheet["importi"][0]["operandi"] = [operand]
    assert verifica(sheet, _caso(), FONTI)
