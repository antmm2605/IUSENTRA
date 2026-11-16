"""Conto economico del fascicolo: fonti, norme e percorso sentenza → proforma → pagamento → fattura → conferma."""

from __future__ import annotations

from datetime import date

from pct.fascicolo_conto_economico import conto_economico, percorso, riga_contributo, riga_sentenza

_SENTENZA = {"label": "sentenza.pdf", "href": "/fascicoli/F1/documenti/D1/visualizza", "norma": "sentenza della causa"}
_COPIA_PEC = {"label": "sentenza via PEC", "href": "/api/v1/ui/email/source/m1", "norma": "sentenza della causa"}


def test_sentenza_stesso_importo_in_due_documenti_contato_una_volta():
    riga = riga_sentenza([{"importo": 350, "distrazione": False, "fonti": [_SENTENZA]},
                          {"importo": 350, "distrazione": False, "fonti": [_COPIA_PEC]}])
    assert riga["importo"] == 350 and riga["importoLabel"] == "€ 350,00"
    assert "contato una volta" in riga["dettaglio"] and len(riga["fonti"]) == 2


def test_distrazione_indica_l_avvocato_antistatario_e_la_norma():
    riga = riga_sentenza([{"importo": 250, "distrazione": True, "fonti": [_SENTENZA]}])
    assert riga["stato"] == "Distratte in favore dell'avvocato" and riga["norma"] == "art. 93 c.p.c."


def test_contributo_esente_da_autocertificazione_confermata():
    riga = riga_contributo({}, [{"etichetta": "Contributo unificato / esenzione", "nome": "Autocertificazione.PDF",
                                 "href": "/x", "confermato": True}])
    assert riga["stato"] == "Esente" and "9, comma 1-bis" in riga["norma"] and riga["fonti"][0]["href"] == "/x"


def test_pec_di_deposito_proposta_come_versamento_non_vince_sull_autocertificazione():
    riga = riga_contributo({}, [
        {"etichetta": "Contributo unificato / pagamento", "nome": "DEPOSITO TELEMATICO: Ricorso", "href": "/a", "confermato": False},
        {"etichetta": "Contributo unificato / esenzione", "nome": "Autocertificazione", "href": "/b", "confermato": False}])
    assert riga["stato"] == "Esente, da confermare" and riga["tono"] == "warning"


def test_contributo_senza_documenti_da_verificare():
    assert riga_contributo({}, [])["stato"] == "Da verificare"


def _proforma(**altro):
    base = {"id": "P1", "numero": "2026/049", "stato": "BOZZA", "operativo": "PROFORMA", "totale": 350.0,
            "onorari": 300.0, "spese": 0.0, "anticipazioni": 0.0, "incassato": 0.0, "data_pagamento": "", "sdi_stato": ""}
    base.update(altro)
    return base


def test_proforma_senza_incasso_si_attende_il_pagamento():
    esito = percorso([_proforma()], [{"importo": 350}])
    assert [p["fatto"] for p in esito["passi"]] == [True, True, False, False, False]
    assert "attendere il pagamento" in esito["prossimoPasso"]


def test_pagamento_ricevuto_senza_fattura_indica_il_termine_di_dodici_giorni():
    esito = percorso([_proforma(incassato=350.0, data_pagamento="2026-11-02")], [], oggi=date(2026, 11, 6))
    assert "entro il 14/11/2026" in esito["prossimoPasso"] and "art. 21, comma 4" in esito["prossimoPasso"]


def test_termine_scaduto_detto():
    esito = percorso([_proforma(incassato=350.0, data_pagamento="2026-10-01")], [], oggi=date(2026, 11, 6))
    assert esito["prossimoPasso"].startswith("Termine scaduto")


def test_fattura_diversa_dall_incasso_non_si_conferma():
    esito = percorso([_proforma(operativo="FATTURA", stato="PAGATA", totale=400.0, incassato=350.0, data_pagamento="2026-11-02")], [])
    assert "non coincide" in esito["prossimoPasso"] and not esito["passi"][-1]["fatto"]


def test_fattura_pari_all_incasso_e_pagata_conclude_il_percorso():
    esito = percorso([_proforma(operativo="FATTURA", stato="PAGATA", incassato=350.0, data_pagamento="2026-11-02")], [{"importo": 350}])
    assert all(p["fatto"] for p in esito["passi"]) and "concluso" in esito["prossimoPasso"]


def test_pagato_segnato_dalla_lettura_automatica_non_e_un_incasso():
    conto = conto_economico(
        voci={"liquidazione_giudice": {"status": "pagato", "data_pagamento": "2026-07-01", "origine": "lex_ai_sentenza_tribunale"}},
        crediti=[{"importo": 350, "fonti": [_SENTENZA]}], documenti_contributo=[], parcelle=[_proforma()])
    pagamento = conto["percorso"]["passi"][2]
    assert not pagamento["fatto"] and "lettura automatica" in pagamento["dettaglio"]
    # Direttiva 10/11/2026 (G-4): senza prova d'incasso il «pagato» automatico non vale, il credito è da incassare.
    assert "da incassare" in pagamento["dettaglio"]
    assert "attendere il pagamento" in conto["percorso"]["prossimoPasso"]


def test_pagato_segnato_dall_avvocato_resta_e_chiede_l_incasso_reale():
    voce = {"status": "pagato", "data_pagamento": "2026-07-01", "origine": "lex_ai_sentenza_tribunale",
            "history": [{"by": "Mario Rossi", "toStatus": "pagato"}]}
    conto = conto_economico(voci={"liquidazione_giudice": voce}, crediti=[{"importo": 350, "fonti": [_SENTENZA]}],
                            documenti_contributo=[], parcelle=[_proforma()])
    assert "registrare l'incasso reale" in conto["percorso"]["prossimoPasso"]


def test_credito_verso_la_pa_dopo_i_120_giorni_richiesta_o_precetto():
    from datetime import date

    conto = conto_economico(voci={}, crediti=[{"importo": 515, "distrazione": True, "fonti": [_SENTENZA]}], documenti_contributo=[],
                            parcelle=[_proforma()], oggi=date(2026, 11, 10),
                            esecuzione={"codice": "esecuzione_pa_120_giorni", "deadline": "2026-08-18"})
    assert "18/08/2026" in conto["percorso"]["prossimoPasso"] and "precetto" in conto["percorso"]["prossimoPasso"]


def test_bozza_superata_non_si_somma():
    superata = _proforma(numero="2026/036", onorari=296.70) | {"id": "A", "superata": {"da_numero": "2026/062"}}
    valida = _proforma(numero="2026/062", onorari=515.0) | {"id": "B"}
    riga = next(r for r in conto_economico(voci={}, crediti=[], documenti_contributo=[], parcelle=[superata, valida])["righe"]
                if r["voce"] == "parcella")
    assert riga["importo"] == 515.0 and "2026/036" in riga["dettaglio"] and "annullarla" in riga["dettaglio"]


def test_anticipazioni_con_fonte_e_norma():
    conto = conto_economico(voci={"fondo_spese": {"importo": 100, "documento_fonte": "bonifico.pdf", "href": "/f"}},
                            crediti=[], documenti_contributo=[], parcelle=[_proforma(anticipazioni=43.0)])
    riga = next(r for r in conto["righe"] if r["voce"] == "anticipazioni")
    assert riga["importo"] == 43.0 and "art. 15" in riga["norma"] and len(riga["fonti"]) == 2


def test_ogni_passo_da_fare_porta_dove_l_avvocato_lo_compie():
    senza = percorso([], [{"importo": 350}])
    assert senza["passi"][1]["azione"] == {"label": "Prepara la proforma", "comando": "genera_proforma"}
    con = percorso([_proforma()], [{"importo": 350}])
    assert con["passi"][2]["azione"]["label"] == "Registra l'incasso"
    assert con["passi"][2]["azione"]["href"] == "/fatturazione?id_documento=P1"
    assert "azione" not in con["passi"][1]  # passo già fatto: nessun pulsante
    pagata = percorso([_proforma(incassato=350.0, data_pagamento="2026-11-02")], [])
    assert pagata["passi"][3]["azione"]["label"] == "Emetti la fattura elettronica"


def test_liquidazione_registrata_dalla_sentenza_alimenta_la_riga_sentenza():
    """Caso reale 2F637234: proforma da sentenza ma nessun evento del controllo economico."""
    from types import SimpleNamespace

    from web.services.fascicolo_conto_economico_runtime import credito_da_liquidazione_registrata

    fascicolo = SimpleNamespace(id="F1", documenti=[SimpleNamespace(id="D1", nome="sentenza.pdf")], pagamenti={
        "liquidazione_giudice": {"importo": 500.0, "status": "da_registrare", "origine": "lex_ai_sentenza_tribunale",
                                 "documento_fonte": "document_id:D1", "beneficiario_credito": "avvocato",
                                 "evidenza_dispositivo": {"distraction_granted": True}}})
    crediti = credito_da_liquidazione_registrata(fascicolo)
    riga = riga_sentenza(crediti)
    assert riga["importo"] == 500 and riga["stato"] == "Distratte in favore dell'avvocato"
    assert riga["fonti"][0]["href"] == "/fascicoli/F1/documenti/D1/visualizza"
    manuale = SimpleNamespace(id="F1", documenti=[], pagamenti={"liquidazione_giudice": {"importo": 500.0, "origine": "manuale"}})
    assert credito_da_liquidazione_registrata(manuale) == []


def test_fonte_senza_importo_non_produce_una_seconda_liquidazione():
    riga = riga_sentenza([
        {"importo": 258.0, "distrazione": True, "fonti": [_SENTENZA]},
        {"importo": None, "distrazione": True, "fonti": []},
    ])
    assert riga["importo"] == 258.0
    assert "Importi diversi" not in riga["dettaglio"]
    assert "senza riportare un importo" in riga["dettaglio"]


def test_conto_economico_mostra_lo_stesso_totale_della_proforma_collegata():
    conto = conto_economico(voci={}, crediti=[{"importo": 500, "distrazione": True, "fonti": [_SENTENZA]}],
                            documenti_contributo=[], parcelle=[_proforma(onorari=500, totale=600, netto_a_pagare=600)])
    assert conto["righe"][0]["importo"] == 500
    parcella = next(r for r in conto["righe"] if r["voce"] == "parcella")
    assert parcella["importo"] == 600
    assert "€ 500,00 di compensi" in parcella["dettaglio"]
    assert parcella["fonti"][0]["href"] == "/fatturazione?id_documento=P1"
