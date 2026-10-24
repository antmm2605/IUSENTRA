"""Procedura atti: scheda verificata, calcolatore, validazione legata alle impronte, revisione indipendente, stati.

Casi inventati e anonimi (nessun caso del banco di misura).
"""
from __future__ import annotations

import pytest

from lex.procedura_atti import SchedaNonUtilizzabile, impronte, prepara, valuta
from lex.procedura_atti.calcolatore import calcola_importi, euro
from lex.procedura_atti.verifica_scheda import contraria, in_lettere

FATTI = ("Il 10/03/2027 la sentenza n. 120/2027 del Tribunale di Lecce e' stata notificata a Rosa Fiorentino. "
         "Il credito riconosciuto e' di 12.400 euro; il 20/03/2027 la controparte ha versato un acconto di 2.400 euro.")
FONTI = {1: "Art. 325 c.p.c. Il termine per proporre l'appello e' di trenta giorni dalla notificazione della sentenza.",
         2: "Art. 1194 c.c. Il debitore non puo' imputare il pagamento al capitale anziche' agli interessi e alle spese."}


def _caso(**extra):
    caso = {"fatti": FATTI, "richiesta": "Valuta l'appello.", "oggi": "15/03/2027",
            "parte_assistita": {"nome": "Rosa Fiorentino", "ruolo": "appellante"},
            "controparte": {"nome": "Edil Sud srl", "ruolo": "appellata"},
            "fonti": dict(FONTI), "fonti_ref": [{"n": 1, "atto": "codice_procedura_civile", "articolo": "325", "sigla": "c.p.c."},
                          {"n": 2, "atto": "codice_civile", "articolo": "1194", "sigla": "c.c."}]}
    caso.update(extra)
    return caso


def _scheda():
    return {
        "forma_risposta": "consulenza", "parte_assistita": {"nome": "Rosa Fiorentino", "ruolo": "appellante"},
        "controparte": {"nome": "Edil Sud srl", "ruolo": "appellata"}, "obiettivo_cliente": "riforma della sentenza",
        "rimedio": {"strumento": "appello"}, "domande": ["in via principale riformare la sentenza n. 120/2027"],
        "punti_da_trattare": ["termine breve"], "norme_mancanti": [], "dati_mancanti": [],
        "termini": [{"id": "T1", "descrizione": "Termine breve per l'appello",
                     "evento": {"data": "10/03/2027", "citazione_fatti": "Il 10/03/2027 la sentenza n. 120/2027"},
                     "durata": {"valore": 30, "unita": "giorni"}, "direzione": "avanti", "natura": "processuale",
                     "sospensione_feriale": False, "per_agire": True,
                     "regola": {"fonte": 1, "citazione": "e' di trenta giorni dalla notificazione della sentenza"},
                     "motivazione": "sentenza notificata: termine breve"}],
        "importi": [{"id": "I1", "descrizione": "Residuo dopo l'acconto", "operazione": "differenza",
                     "operandi": [{"centesimi": 1240000, "provenienza": "fatti", "citazione": "e' di 12.400 euro"},
                                  {"centesimi": 240000, "provenienza": "fatti", "citazione": "acconto di 2.400 euro"}]}]}


def _approvata(scheda, caso):
    return {"esito": "approvata", **impronte(scheda, caso)}


def test_calcolatore_termine_processuale_e_importi_in_centesimi():
    p = prepara(_scheda(), _caso(), _approvata(_scheda(), _caso()))
    assert p.calcoli["termini"][0]["scadenza"] == "09/04/2027"
    assert p.calcoli["importi"][0]["euro"] == "10.000,00"
    assert "09/04/2027" in p.messaggio and "10.000,00" in p.messaggio


def test_importi_prodotto_e_formato():
    out = calcola_importi([{"id": "A", "descrizione": "x", "operazione": "prodotto",
                            "operandi": [{"centesimi": 2500000, "provenienza": "fatti"}, {"valore": 2, "provenienza": "moltiplicatore"}]}])
    assert out[0]["centesimi"] == 5000000 and euro(-150) == "-1,50"


def test_scheda_senza_validazione_si_ferma():
    with pytest.raises(SchedaNonUtilizzabile, match="non approvata"):
        prepara(_scheda(), _caso(), None)


def test_validazione_non_vale_se_cambiano_le_fonti():
    s, c = _scheda(), _caso()
    v = _approvata(s, c)
    c2 = _caso(fonti={**FONTI, 2: FONTI[2] + " Modificata."})
    with pytest.raises(SchedaNonUtilizzabile, match="fonti_sha256"):
        prepara(s, c2, v)


def test_scheda_con_citazione_inventata_non_passa():
    s = _scheda()
    s["termini"][0]["regola"]["citazione"] = "e' di sessanta giorni dalla notificazione"
    with pytest.raises(SchedaNonUtilizzabile, match="citazione della regola"):
        prepara(s, _caso(), None, consenti_non_validata=True)


def test_revisione_indipendente_segnala_norma_fuori_fonti_e_pagamento_ignorato():
    s, c = _scheda(), _caso()
    p = prepara(s, c, _approvata(s, c))
    bozza = ("Gentile Rosa Fiorentino, l'appello va proposto entro il 09/04/2027 ai sensi dell'art. 325 c.p.c. [1]. "
             "Si richiama anche l'art. 2043 c.c. Il credito resta di 12.400 euro. ") * 3
    esito = valuta(bozza, s, c, p)
    tipi = {g[0] for g in esito["revisione_indipendente"]["gravi"]}
    assert "norma_fuori_fonti" in tipi and "pagamento_ignorato" in tipi
    assert esito["stato_consegna"]["stato"] == "bozza_con_verifiche_pendenti"


def test_bozza_coerente_e_pronta_solo_per_la_revisione_dell_avvocato():
    s, c = _scheda(), _caso()
    p = prepara(s, c, _approvata(s, c))
    bozza = ("Gentile Rosa Fiorentino, la sentenza notificata il 10/03/2027 si impugna con appello entro il 09/04/2027 "
             "(art. 325 c.p.c. [1]). Sul credito di 12.400 euro il residuo, dedotto l'acconto di 2.400 euro, e' di 10.000,00 euro; "
             "l'imputazione segue l'art. 1194 c.c. [2]. ") * 2
    esito = valuta(bozza, s, c, p)
    assert esito["revisione_indipendente"]["gravi"] == []
    assert esito["stato_consegna"]["stato"] == "pronta_per_revisione_avvocato"


def test_non_validata_non_e_mai_pronta():
    s, c = _scheda(), _caso()
    p = prepara(s, c, None, consenti_non_validata=True)
    bozza = ("Gentile Rosa Fiorentino, appello entro il 09/04/2027 (art. 325 c.p.c. [1]); residuo 10.000,00 euro dopo "
             "l'acconto di 2.400 euro, art. 1194 c.c. [2]. ") * 3
    esito = valuta(bozza, s, c, p)
    assert esito["stato_consegna"]["stato"] != "pronta_per_revisione_avvocato"
    assert any("non validata" in m for m in esito["stato_consegna"]["motivi"])


def test_atto_senza_requisiti_e_incompleto():
    s, c = _scheda(), _caso()
    s["forma_risposta"] = "atto"
    s["rimedio"] = {"strumento": "atto di citazione in appello"}
    p = prepara(s, c, _approvata(s, c))
    esito = valuta("Breve nota per Rosa Fiorentino. " * 20, s, c, p)
    assert esito["stato_consegna"]["stato"] == "bozza_incompleta"
    assert esito["requisiti_mancanti"]


def test_lettere_e_conclusioni_contrarie():
    assert in_lettere(180) == "centottanta" and in_lettere(21) == "ventuno"
    assert contraria("chiede di rigettare il ricorso")
    assert not contraria("chiede di rigettare il ricorso proposto da controparte")
