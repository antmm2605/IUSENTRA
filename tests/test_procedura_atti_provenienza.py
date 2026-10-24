"""Controesempi sintetici: provenienza, identità e valori monetari."""
import copy
import hashlib

import pytest

from lex.procedura_atti import SchedaNonUtilizzabile, impronte, prepara, valuta
from lex.procedura_atti.contabilita import verifica_credito
from lex.procedura_atti.denaro import importi
from tests.test_procedura_atti import _approvata, _caso, _scheda


@pytest.mark.parametrize("campo", ["tipo", "url", "versione", "acquisita_il", "sha256"])
def test_ogni_elemento_della_provenienza_e_obbligatorio(campo):
    s, c = _scheda(), _caso()
    del c["fonti_ref"][0]["provenienza"][campo]
    with pytest.raises(SchedaNonUtilizzabile):
        prepara(s, c, _approvata(s, c))


@pytest.mark.parametrize("campo,valore", [
    ("url", "https://www.normattiva.it/"),
    ("archivio", "altro archivio autorizzato"),
    ("versione", "altra versione"),
    ("data_pubblicazione", "2026-10-23"),
    ("acquisita_il", "25/10/2026"),
    ("fornitore", "altro fornitore"),
])
def test_testo_identico_ma_provenienza_diversa_invalida_approvazione(campo, valore):
    s, c = _scheda(), _caso()
    approvazione = _approvata(s, c)
    c["fonti_ref"][0]["provenienza"][campo] = valore
    with pytest.raises(SchedaNonUtilizzabile, match="fonti_sha256"):
        prepara(s, c, approvazione)


def test_sha_non_corrispondente_e_testo_vuoto_bloccano():
    s, c = _scheda(), _caso()
    c["fonti"][1] += " aggiunta"
    with pytest.raises(SchedaNonUtilizzabile, match="SHA-256"):
        prepara(s, c, _approvata(s, c))
    c["fonti"][1] = ""
    with pytest.raises(SchedaNonUtilizzabile, match="testo assente"):
        prepara(s, c, _approvata(s, c))


def test_decisione_necessita_integrale_e_provenienza_e_non_accetta_metadata_only():
    s, c = _scheda(), _caso()
    s["termini"] = []
    c["fonti"][1] = "Testo integrale sintetico della decisione numero 120/2027."
    ref = c["fonti_ref"][0]
    ref["provenienza"].update(tipo="decisione",
        sha256=hashlib.sha256(c["fonti"][1].encode()).hexdigest())
    with pytest.raises(SchedaNonUtilizzabile, match="testo integrale"):
        prepara(s, c, _approvata(s, c))
    ref["provenienza"]["testo_integrale"] = True
    assert prepara(s, c, _approvata(s, c)).impronte == impronte(s, c)
    ref["evidence_scope"] = "metadata_only"
    with pytest.raises(SchedaNonUtilizzabile, match="spunto"):
        prepara(s, c, _approvata(s, c))
    del ref["evidence_scope"]
    del ref["provenienza"]
    with pytest.raises(SchedaNonUtilizzabile, match="provenienza"):
        prepara(s, c, _approvata(s, c))


def test_spunti_r6_separati_non_diventano_fonti_o_messaggio_di_stesura():
    s, c = _scheda(), _caso()
    prima = impronte(s, c)
    c["spunti_giurisprudenza"] = [{"evidence_scope": "metadata_only", "oggetto": "SPUNTO_NON_FONTE"}]
    prepared = prepara(s, c, _approvata(s, c))
    assert "SPUNTO_NON_FONTE" not in prepared.messaggio
    assert impronte(s, c) == prima


@pytest.mark.parametrize("parte", ["scheda", "fascicolo", "provenienza", "calcoli"])
def test_valutazione_rifiuta_modifiche_dopo_preparazione(parte):
    s, c = _scheda(), _caso()
    prepared = prepara(s, c, _approvata(s, c))
    if parte == "scheda":
        s["domande"].append("domanda aggiunta")
    elif parte == "fascicolo":
        c["richiesta"] += " nuova richiesta"
    elif parte == "provenienza":
        c["fonti_ref"][0]["provenienza"]["archivio"] = "altro archivio"
    else:
        prepared.calcoli["importi"][0]["centesimi"] += 1
    with pytest.raises(SchedaNonUtilizzabile):
        valuta("testo " * 100, s, c, prepared)


def test_riferimenti_non_contigui_non_usano_indici_di_lista():
    s, c = _scheda(), _caso()
    c["fonti"][5] = c["fonti"].pop(1)
    c["fonti_ref"][0]["n"] = 5
    s["termini"][0]["regola"]["fonte"] = 5
    prepared = prepara(s, c, _approvata(s, c))
    bozza = ("Rosa Fiorentino può proporre appello entro il 09/04/2027 (art. 325 c.p.c. [5]). "
             "Il residuo è di 10.000,00 euro dopo l'acconto di 2.400 euro, art. 1194 c.c. [2]. ") * 3
    assert valuta(bozza, s, c, prepared)["revisione_indipendente"]["gravi"] == []


@pytest.mark.parametrize("centesimi", [1240001, 200, -1240000])
def test_operando_non_puo_cambiare_centesimi_o_usare_sottostringhe(centesimi):
    s, c = _scheda(), _caso()
    s["importi"][0]["operandi"][0]["centesimi"] = centesimi
    with pytest.raises(SchedaNonUtilizzabile, match="operando"):
        prepara(s, c, _approvata(s, c))


def test_date_e_articoli_non_sono_importi_e_niente_float():
    assert importi("art. 325, 15/03/2027, fattura n. 500") == set()
    assert importi("euro 12.400,01 e 2.400,50 euro") == {1240001, 240050}


def test_credito_non_accetta_cifre_inventate_o_id_duplicati():
    credito = {"voci": [{"id": "F1", "centesimi": 1240001, "citazione": "12.400 euro"}]}
    assert verifica_credito(credito, "Credito di 12.400 euro.")
    credito["voci"][0]["centesimi"] = 1240000
    assert verifica_credito(credito, "Credito di 12.400 euro.") == []
    credito["voci"].append(copy.deepcopy(credito["voci"][0]))
    assert any("duplicati" in e for e in verifica_credito(credito, "Credito di 12.400 euro."))

@pytest.mark.parametrize("data", ["31/02/2026", "2026-10-24", "1/3/2027", "00/01/2027"])
def test_data_acquisizione_deve_essere_una_data_reale_nel_formato_richiesto(data):
    s, c = _scheda(), _caso()
    c["fonti_ref"][0]["provenienza"]["acquisita_il"] = data
    with pytest.raises(SchedaNonUtilizzabile, match="data di acquisizione"):
        prepara(s, c, _approvata(s, c))


def test_svuotare_avvisi_non_promuove_preparazione_non_approvata():
    s, c = _scheda(), _caso()
    prepared = prepara(s, c, None, consenti_non_validata=True)
    prepared.avvisi.clear()
    assert valuta("Rosa Fiorentino " * 50, s, c, prepared)["stato_consegna"]["stato"] != "pronta_per_revisione_avvocato"


def test_pagamenti_con_centesimi_e_capitale_non_confusi():
    from lex.procedura_atti.revisione_indipendente import _pagamenti
    assert list(_pagamenti("Credito di 12.400 euro la controparte ha versato un acconto di 2.400,50 euro."))[0][0] == "2.400,50"
    assert len(list(_pagamenti("Credito di 12.400 euro la controparte ha versato un acconto di 2.400,50 euro."))) == 1

@pytest.mark.parametrize("valore", [30.9, True, 0, -1])
def test_durate_non_intere_o_non_positive_non_sono_troncate(valore):
    s, c = _scheda(), _caso()
    s["termini"][0]["durata"]["valore"] = valore
    with pytest.raises(SchedaNonUtilizzabile, match="durata"):
        prepara(s, c, _approvata(s, c))


def test_identificativi_calcolati_non_possono_essere_duplicati():
    s, c = _scheda(), _caso()
    s["importi"].append(copy.deepcopy(s["importi"][0]))
    with pytest.raises(SchedaNonUtilizzabile, match="duplicato"):
        prepara(s, c, _approvata(s, c))
