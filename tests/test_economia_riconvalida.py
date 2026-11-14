"""Collaudo 10/11/2026 (G-4, G-13, G-14, G-16, lezione B): dati fittizi.

Norme: artt. 1188 e 2697 c.c.; art. 6, terzo comma, D.P.R. 633/1972; art. 641 c.p.c.; artt. 9, comma 1-bis, 10, 13 e
30 D.P.R. 115/2002; D.M. 22/04/2025 (G.U. n. 159 dell'11/07/2025); art. 14 D.L. 669/1996.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from pct.contributo_dovuto import LAVORO, MONITORIO, VOLONTARIA, categoria, confronta, contributo_dovuto
from pct.contributo_unificato_stato import stato_contributo
from pct.esenzione_reddito_cu import leggi_autocertificazione, verifica
from pct.incasso_provato import (STATO_DA_INCASSARE, motivo_credito_aperto, pagato_deciso_dall_avvocato, pagato_senza_prova,
                                 riconvalida_voce)
from pct.proforma_unica import decidi, superata
from pct.spese_liquidate_provvedimento import natura_provvedimento, spese_liquidate

LIQUIDAZIONE_AUTOMATICA = {
    "status": "pagato", "pagato": True, "importo": 515.0, "data_pagamento": "2026-04-17", "metodo": "Bonifico bancario",
    "updated_by": "Lex AI backfill", "origine": "lex_ai_sentenza_tribunale",
    "history": [{"by": "Mario Rossi", "toStatus": "da_registrare", "toImporto": 296.7},
                {"by": "Lex AI backfill", "fromStatus": "da_registrare", "toStatus": "pagato", "origine": "lex_ai_sentenza_tribunale"}],
}


# --- G-4: «pagato» solo con prova d'incasso o decisione dell'avvocato --------------------------------------------

def test_pagato_scritto_da_un_automatismo_torna_da_incassare():
    assert pagato_senza_prova(LIQUIDAZIONE_AUTOMATICA)
    nuova = riconvalida_voce(LIQUIDAZIONE_AUTOMATICA, adesso="2026-11-10T10:00:00Z")
    assert nuova["status"] == STATO_DA_INCASSARE and nuova["pagato"] is False and nuova["data_pagamento"] == ""
    assert nuova["history"][-1]["fromStatus"] == "pagato" and "2026-04-17" in nuova["history"][-1]["note"]
    assert riconvalida_voce(nuova) is None  # una sola volta


def test_decisione_dell_avvocato_e_incasso_registrato_non_si_toccano():
    dell_avvocato = dict(LIQUIDAZIONE_AUTOMATICA, history=[{"by": "Mario Rossi", "toStatus": "pagato"}])
    assert pagato_deciso_dall_avvocato(dell_avvocato) and riconvalida_voce(dell_avvocato) is None
    assert riconvalida_voce(LIQUIDAZIONE_AUTOMATICA, incasso_registrato=True) is None
    provato = dict(LIQUIDAZIONE_AUTOMATICA, evidenza_dispositivo={"payment_proven": True})
    assert riconvalida_voce(provato) is None


def test_credito_aperto_impedisce_pronto_per_l_archivio():
    from pct.fascicolo_lettura.prossimi_passi import stato_passi

    economico = {"liquidazione_incasso": "non_incassata", "liquidato_it": "€ 515,00"}
    assert "120 giorni" in motivo_credito_aperto(economico)
    stato = stato_passi({"da_archiviare": True, "stato_codice": "DEFINITO"}, {}, date(2026, 11, 10), economico)
    assert "pronto per l'archivio" not in stato["motivo"] and "€ 515,00" in stato["motivo"]
    assert "pronto per l'archivio" in stato_passi({"da_archiviare": True, "stato_codice": "DEFINITO"}, {}, date(2026, 11, 10),
                                                   {"liquidazione_incasso": "incassata"})["motivo"]


# --- G-13: una sola proforma automatica per lo stesso compenso ----------------------------------------------------

def _parcella(numero, origine, creato_il, stato="BOZZA", **dati):
    return SimpleNamespace(id=numero, numero=numero, origine=origine, stato=SimpleNamespace(value=stato), creato_il=creato_il,
                           dati_personalizzati=dati)


def test_la_bozza_dalla_sentenza_supera_quella_del_fascicolo_definito():
    presidio = _parcella("2026/036", "presidio_economico_fascicolo_definito", "2026-07-27")
    sentenza = _parcella("2026/062", "lex_ai_sentenza_tribunale", "2026-09-20")
    manuale = _parcella("2026/070", "", "2026-10-01")
    valida, superate = decidi([presidio, sentenza, manuale])
    assert valida is sentenza and superate == [presidio]
    assert decidi([presidio, _parcella("2026/062", "lex_ai_sentenza_tribunale", "2026-09-20", stato="EMESSA")]) == (presidio, [])
    assert superata(_parcella("x", "presidio_economico_fascicolo_definito", "", superata={"da_numero": "2026/062"}))


# --- G-14: spese liquidate dal decreto ingiuntivo -----------------------------------------------------------------

def test_decreto_ingiuntivo_liquida_compensi_ed_esborsi():
    testo = ("INGIUNGE di pagare 1) € 2.400,00. 2) Le spese di questa procedura di ingiunzione, liquidate in € 76,00 per spese "
             "non imponibili ed € 300,00 per compensi professionali, oltre rimborso spese generali nella misura del 15%, Cpa e Iva.")
    letto = spese_liquidate(testo)
    assert (letto["compensi"], letto["esborsi"], letto["accessori"], letto["distrazione"]) == (300.0, 76.0, True, False)
    assert natura_provvedimento("Decreto ingiuntivo")[0] == "decreto ingiuntivo"
    assert natura_provvedimento("Ricorso per decreto ingiuntivo") is None and natura_provvedimento("Sentenza") is None


# --- G-16: il versato si confronta con lo scaglione dovuto --------------------------------------------------------

def test_scaglione_e_dimezzamento_per_rito():
    assert categoria(area="Volontaria giurisdizione") == VOLONTARIA
    assert categoria(area="Lavoro e previdenza", padre="Pubblico impiego") == LAVORO
    assert categoria(area="Procedimenti speciali sommari", padre="Decreto Ingiuntivo") == MONITORIO
    assert confronta([27, 49, 12], contributo_dovuto(MONITORIO, 2400))["esito"] == "coincide"  # 98 / 2
    assert confronta([21.5], None, cat=LAVORO)["esito"] == "coincide"  # 43 / 2, valore non dichiarato
    vg = confronta([27], contributo_dovuto(VOLONTARIA, None))
    assert vg["esito"] == "insufficiente" and "forse non versato" in vg["dettaglio"] and "art. 30" in vg["dettaglio"]


def test_stato_contributo_certo_se_coincide_e_istanza_non_e_ricevuta():
    documenti = [{"etichetta": "Contributo unificato / pagamento", "id": "R", "nome": "rt.xml", "confermato": False},
                 {"etichetta": "Contributo unificato / pagamento", "id": "I", "nome": "Istanza_autorizzazione.PDF", "confermato": True}]
    voce = {"status": "pagato", "importo": 49.0, "importiLetti": ["27.00", "49.00"], "richiedeConferma": True,
            "confronto": confronta([27, 49], contributo_dovuto(MONITORIO, 2400))}
    stato = stato_contributo(voce, documenti)
    assert stato["codice"] == "pagato" and stato["importo"] == 49.0 and [f["id"] for f in stato["fonti"]] == ["R"]
    voce_vg = {"status": "pagato", "importo": 27.0, "importiLetti": ["27.00"], "confronto": confronta([27], contributo_dovuto(VOLONTARIA, None))}
    assert stato_contributo(voce_vg, documenti)["codice"] == "da_verificare"


def test_ricevuta_del_contributo_conferma_il_versamento_anche_se_il_ricorso_richiama_esenzione():
    voce = {"status": "pagato", "importo": 21.5, "richiamoEsenzione": True, "confronto": confronta([21.5], None, cat=LAVORO)}
    stato = stato_contributo(voce, [{"etichetta": "Contributo unificato / pagamento", "id": "R", "nome": "rt.xml"}])
    assert stato["codice"] == "pagato" and stato["confermato"]
    assert stato["importo"] == 21.5 and stato["documento"]["id"] == "R"
    assert "art. 13" in stato["norma"]


# --- Lezione B: soglia di reddito datata ---------------------------------------------------------------------------

def test_autocertificazione_depositata_con_soglia_vigente_e_certa():
    testo = ("ESENZIONE DAL CONTRIBUTO UNIFICATO ... DICHIARA che il proprio reddito non è superiore a € 40.978,92 "
             "relativamente all'ANNO 2024.")
    letta = leggi_autocertificazione(testo)
    assert letta["anno"] == 2024 and letta["soglia"] == Decimal("40978.92")
    assert verifica(anno=2024, soglia=letta["soglia"], data_deposito=date(2026, 1, 15))["certa"]
    # Con il D.M. 10/05/2023 (prima dell'11/07/2025) il triplo era € 38.514,03: 40.978,92 è oltre → nessuna esenzione.
    assert not verifica(anno=2023, soglia=letta["soglia"], data_deposito=date(2025, 3, 1))["certa"]


def test_soglia_precedente_vale_a_maggior_ragione_ma_l_anno_deve_essere_leggibile():
    assert verifica(anno=2024, soglia=Decimal("38514.03"), data_deposito=date(2026, 1, 15))["certa"]
    dubbio = verifica(anno=None, soglia=Decimal("38514.03"), data_deposito=date(2026, 5, 26))
    assert not dubbio["certa"] and "illeggibile" in dubbio["motivo"]
    assert not verifica(anno=2021, soglia=Decimal("40978.92"), data_deposito=date(2026, 1, 15))["certa"]


def test_esenzione_certa_vince_sulla_ricevuta_proposta():
    voce = {"status": "non_previsto", "documento_fonte": "AUTOCERTIFICAZIONE_ESENZIONE.PDF",
            "esenzioneVerificata": {"certa": True, "motivo": "Esenzione certa: ..."}}
    assert stato_contributo(voce, [])["codice"] == "esente"


def test_processi_esecutivi_art_13_comma_2():
    from pct.contributo_dovuto import ESECUZIONE_ALTRA, ESECUZIONE_IMMOBILIARE

    assert categoria(area="Esecuzioni mobiliari / obblighi") == ESECUZIONE_ALTRA
    assert confronta([139, 27], contributo_dovuto(ESECUZIONE_ALTRA, 3846))["esito"] == "coincide"
    assert confronta([43], contributo_dovuto(ESECUZIONE_ALTRA, 1800))["esito"] == "coincide"
    assert confronta([278], None, cat=ESECUZIONE_IMMOBILIARE)["esito"] == "coincide"
    assert contributo_dovuto(ESECUZIONE_ALTRA, None) is None  # sopra o sotto € 2.500: senza valore non si sceglie


def test_distrazione_subito_dopo_la_liquidazione():
    testo = ("P.Q.M. condanna il Ministero al pagamento delle spese legali, che liquida in € 515,00 per compenso di avvocato, "
             "oltre rimborso forfettario spese generali 15%, CPA e IVA come per legge, il tutto da distrarsi a favore "
             "dell'avv. Rossi dichiaratosi antistatario.")
    assert spese_liquidate(testo)["distrazione"] is True


def test_liquidazione_al_plurale_distinta_dal_beneficio_principale():
    testo = (
        "P.Q.M. condanna a consentire la generazione dei buoni spesa di importo pari a Euro 500. "
        "Condanna il Ministero a rimborsare le spese di lite, che si liquidano complessivamente "
        "in € 258 oltre spese generali al 15%, IVA e CPA con distrazione a favore del difensore antistatario."
    )

    letto = spese_liquidate(testo)

    assert letto["compensi"] == 258
    assert letto["accessori"] and letto["distrazione"]
    assert "si liquidano complessivamente in € 258" in letto["brano"]
