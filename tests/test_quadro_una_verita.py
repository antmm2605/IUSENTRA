"""Quadro del fascicolo: un solo controllore per riga (collaudo a vista del 19/11/2026).

Le righe Economia e Notifiche leggono le conclusioni del modello della causa, le stesse dei prossimi passi; la riga
Economia dà il percorso economico completo (contributo, compenso, spese liquidate) con le fonti del Conto economico.
Dati fittizi equivalenti ai fascicoli D960FA3E, 82A8E2BD, A8B49265, 9A681FDF. Norme: art. 156 c.p.c.; art. 647 c.p.c.;
artt. 10, 13 D.P.R. 115/2002; art. 6, terzo comma, e art. 21 D.P.R. 633/1972; art. 4, comma 2, D.Lgs. 231/2002;
art. 93 c.p.c.
"""

from __future__ import annotations

from datetime import date

from pct.fascicolo_quadro import allinea_al_modello, riga_notifiche
from pct.quadro_economia import compenso, contributo, percorso_economico, spese_liquidate

OGGI = date(2026, 11, 19)
DI_FATTO = {"codice": "notifica_decreto_ingiuntivo", "stato": "fatto", "onerato_codice": "noi",
            "prova_o_motivo": "Notificato il 23/12/2024: lo attesta il giudice nel provvedimento di esecutorietà (art. 647 c.p.c.)",
            "norme": [{"norma": "art. 643 c.p.c."}]}


# --- Notifiche: il modello decide per gli atti che tratta ---------------------------------------------------------

def test_decreto_ingiuntivo_notificato_secondo_il_modello_non_da_verificare():
    sintesi = [{"atto": "Decreto ingiuntivo", "stato": "da_verificare", "scadenza": ""}]
    riga = riga_notifiche(allinea_al_modello(sintesi, [DI_FATTO]), oggi=OGGI)
    assert riga["testo"] == "Decreto ingiuntivo: notificato" and riga["livello"] == "ok"


def test_costituzione_della_controparte_nel_quadro():
    conclusione = {"codice": "notifica_ricorso_decreto_415", "stato": "fatto", "onerato_codice": "noi",
                   "prova_o_motivo": "La controparte si è costituita con «CT 1762 2026 COMPARSA M.I.M..pdf.p7m»",
                   "norme": [{"norma": "art. 415, commi 4–6, c.p.c."}, {"norma": "art. 156, terzo comma, c.p.c."}]}
    riga = riga_notifiche(allinea_al_modello([], [conclusione]), oggi=OGGI)
    assert "la controparte si è costituita: notifica a buon fine (art. 156, terzo comma, c.p.c.)" in riga["testo"]
    assert riga["livello"] == "ok"
    pannello = allinea_al_modello([{"etichetta": "Decreto di fissazione udienza (art. 415 c.p.c.)", "regola": "lavoro_415",
                                    "stato": "da_verificare", "prove": ["X"]}], [conclusione], pannello=True)
    assert pannello[0]["stato"] == "notificato" and pannello[0]["prove"] == ["X"] and "costituita" in pannello[0]["motivo_modello"]


def test_atti_che_il_modello_non_tratta_restano_e_non_dovuto_toglie_la_voce():
    sintesi = [{"atto": "Sentenza", "stato": "da_verificare", "regola": "sentenza_notifica_breve"},
               {"atto": "Decreto di fissazione udienza (art. 415 c.p.c.)", "stato": "da_notificare", "scadenza": "2026-02-12"}]
    storico = {"codice": "notifica_ricorso_decreto_415", "stato": "non_dovuto", "onerato_codice": "noi"}
    allineati = allinea_al_modello(sintesi, [storico])
    assert [o["atto"] for o in allineati] == ["Sentenza"]
    assert allinea_al_modello(sintesi, None) == sintesi
    # gli ordini della controparte non sono obblighi dello studio
    assert allinea_al_modello([], [{**DI_FATTO, "onerato_codice": "controparte"}]) == []


# --- Economia: contributo dal modello, compenso, spese ---------------------------------------------------------

def test_contributo_come_lo_conclude_il_modello():
    esente_con_dubbio = {"codice": "contributo_unificato", "stato": "dubbio",
                         "cosa": "Contributo unificato non dovuto (art. 10, comma 2, D.P.R. 115/2002): nell'atto introduttivo manca "
                                 "la dichiarazione della ragione dell'esenzione (art. 10, comma 6)"}
    testo, dubbio = contributo(esente_con_dubbio, presidio={"etichetta": "Esente, da confermare", "tono": "warning"})
    assert testo.startswith("non dovuto (art. 10, comma 2") and "art. 10, comma 6" in testo and dubbio
    assert "Esente, da confermare" not in testo
    versato = {"codice": "contributo_unificato", "stato": "fatto", "cosa": "Contributo unificato: versato (€ 21,50)"}
    assert contributo(versato, {"status": "pagato", "data_pagamento": "21/09/2026"}) == ("versato € 21,50 (ricevuta del 21/09/2026)", False)
    assert contributo(versato, {"status": "da_registrare"}) == ("versato € 21,50", False)
    esente = {"codice": "contributo_unificato", "stato": "non_dovuto", "cosa": "esente", "norme": [{"norma": "art. 9, comma 1-bis, D.P.R. 115/2002"}]}
    assert contributo(esente) == ("non dovuto (art. 9, comma 1-bis, D.P.R. 115/2002)", False)


def test_compenso_proforma_fattura_incasso():
    assert compenso([], oggi=OGGI) == ("compenso: proforma da preparare", "info")
    proforma = {"id": "P1", "numero": "2026/062", "data": "2026-09-20", "stato": "BOZZA", "operativo": "PROFORMA",
                "totale": 617.94, "netto_a_pagare": 617.94, "incassato": 0, "data_pagamento": ""}
    # cliente impresa, professionista o P.A.: transazione commerciale, termine legale di 30 giorni (artt. 2 e 4 D.Lgs. 231/2002)
    testo, livello = compenso([proforma], oggi=OGGI, cliente="impresa")
    assert testo == ("compenso: proforma n. 2026/062 del 20/09/2026, € 617,94: non ancora incassato, da 60 giorni dalla proforma "
                     "(oltre i 30 giorni dalla richiesta di pagamento, art. 4, comma 2, lett. a), D.Lgs. 231/2002)") and livello == "attenzione"
    assert "D.Lgs. 231/2002" in compenso([proforma], oggi=OGGI, cliente="pa")[0]
    # cliente consumatore o non noto: nessuna norma, promemoria di sollecito dello studio
    for natura in ("consumatore", ""):
        testo, livello = compenso([proforma], oggi=OGGI, cliente=natura)
        assert testo.endswith("da 60 giorni dalla proforma (oltre i 30 giorni: promemoria dello studio per il sollecito)")
        assert "231/2002" not in testo and livello == "attenzione"
    recente = {**proforma, "data": "2026-11-10"}
    assert compenso([recente], oggi=OGGI)[1] == "info"
    incassata = {**proforma, "incassato": 617.94, "data_pagamento": "2026-10-15"}
    testo, livello = compenso([incassata], oggi=OGGI)
    assert "incassati € 617,94 il 15/10/2026, fattura da emettere" in testo and livello == "attenzione"
    fattura = {**incassata, "operativo": "FATTURA", "stato": "PAGATA", "numero": "2026/070", "data": "2026-10-16"}
    testo, livello = compenso([fattura], oggi=OGGI)
    assert testo == "compenso: fattura n. 2026/070 del 16/10/2026, € 617,94: incassati € 617,94 il 15/10/2026" and livello == "ok"
    superata = {**proforma, "id": "P0", "numero": "2026/036", "superata": {"da_numero": "2026/062"}}
    assert "2026/036" not in compenso([superata, proforma], oggi=OGGI)[0]


def test_spese_liquidate_col_provvedimento_reale_e_il_pagamento_provato():
    riga_di = {"voce": "sentenza", "etichetta": "Spese liquidate nel decreto ingiuntivo", "importo": 300.0, "importoLabel": "€ 300,00",
               "stato": "Spese liquidate al cliente"}
    testo, livello = spese_liquidate(riga_di)
    assert testo == "spese liquidate nel decreto ingiuntivo € 300,00: non ancora pagate dalla controparte" and livello == "info"
    distratte = {**riga_di, "etichetta": "Importo liquidato in sentenza", "stato": "Distratte in favore dell'avvocato"}
    pagate = {"status": "pagato", "data_pagamento": "2026-10-01", "proforma_id": "P1", "updated_by": "avv.rossi"}
    testo, livello = spese_liquidate(distratte, liquidazione=pagate)
    assert testo == ("spese liquidate in sentenza € 300,00, distratte in favore dell'avvocato (art. 93 c.p.c.): "
                     "pagate dalla controparte il 01/10/2026") and livello == "ok"
    # «pagato» scritto da una lettura automatica senza prova d'incasso non è un pagamento
    automatico = {"status": "pagato", "data_pagamento": "2026-04-17", "updated_by": "Lex AI backfill", "origine": "lex_ai_sentenza"}
    assert spese_liquidate(distratte, liquidazione=automatico)[0].endswith("non ancora pagate dalla controparte")
    # senza Conto economico: il modello, con il provvedimento letto
    modello = {"codice": "spese_liquidate", "cosa": "Riscuotere le spese liquidate dal giudice: € 300,00 di compensi",
               "letto": {"documento_id": "DI", "documento": "accoglimento.pdf", "data": "20/12/2024"}}
    testo, _ = spese_liquidate(None, conclusione=modello, atti={"DI": {"etichetta": "Decreto ingiuntivo"}})
    assert testo.startswith("spese liquidate nel decreto ingiuntivo del 20/12/2024 € 300,00")
    assert spese_liquidate({"voce": "sentenza", "stato": "Spese compensate"})[0] == "spese di lite compensate (art. 92 c.p.c.)"
    assert spese_liquidate({"voce": "sentenza", "stato": "Nessuna sentenza con spese liquidate"}) == ("", "ok")


def test_percorso_economico_in_ordine_solo_se_tutto_incassato():
    conclusioni = [{"codice": "contributo_unificato", "stato": "fatto", "cosa": "Contributo unificato: versato (€ 49,00)"}]
    fattura = {"id": "F", "numero": "2026/070", "data": "2026-10-16", "operativo": "FATTURA", "stato": "PAGATA",
               "totale": 100.0, "netto_a_pagare": 100.0, "incassato": 100.0, "data_pagamento": "2026-10-15"}
    testo, livello = percorso_economico(conclusioni=conclusioni, atti=[], righe_conto=[], parcelle=[fattura],
                                        voci={"contributo_unificato": {"status": "pagato", "data_pagamento": "2025-01-13"}},
                                        presidio_contributo=None, oggi=OGGI)
    assert testo == ("Contributo unificato: versato € 49,00 (ricevuta del 13/01/2025) · compenso: fattura n. 2026/070 del "
                     "16/10/2026, € 100,00: incassati € 100,00 il 15/10/2026") and livello == "ok"
    riga_di = {"voce": "sentenza", "etichetta": "Spese liquidate nel decreto ingiuntivo", "importo": 300.0, "importoLabel": "€ 300,00"}
    _, livello = percorso_economico(conclusioni=conclusioni, atti=[], righe_conto=[riga_di], parcelle=[fattura], voci={},
                                    presidio_contributo=None, oggi=OGGI)
    assert livello == "info"
    _, livello = percorso_economico(conclusioni=[], atti=[], righe_conto=[], parcelle=[], voci={},
                                    presidio_contributo={"etichetta": "Da verificare", "tono": "warning"}, oggi=OGGI)
    assert livello == "attenzione"


def test_quadro_runtime_usa_il_modello_e_la_fatturazione(monkeypatch):
    from web.services import fascicolo_conto_economico_runtime, riscontri_processuali_runtime
    from web.services.fascicolo_quadro_runtime import riga_economia_materializzata, testata_da_lettura

    monkeypatch.setattr(riscontri_processuali_runtime, "risultato_materializzato", lambda *_: None)
    monkeypatch.setattr(fascicolo_conto_economico_runtime, "parcelle_del_fascicolo", lambda _fid: [])
    lettura = {"ragionamento": {"conclusioni": [{"codice": "contributo_unificato", "stato": "fatto",
                                                 "cosa": "Contributo unificato: versato (€ 21,50)"}],
                                "parti": {"controparte": "Ministero dell'Istruzione e del Merito",
                                          "difensore_controparte": "Avvocatura Distrettuale dello Stato di Venezia",
                                          "valore": {"tipo": "non_dichiarato", "fonte": "atto introduttivo «Ricorso.pdf»"}}}}
    fascicolo = type("F", (), {"pagamenti": {"contributo_unificato": {"status": "pagato", "data_pagamento": "21/09/2026"}}})()
    riga = riga_economia_materializzata("F1", lettura, fascicolo=fascicolo, oggi=OGGI)
    assert riga["testo"] == "Contributo unificato: versato € 21,50 (ricevuta del 21/09/2026) · compenso: proforma da preparare"
    assert riga["livello"] == "info"
    testata = testata_da_lettura(lettura)
    assert testata["controparte"] == "Ministero dell'Istruzione e del Merito"
    assert testata["difensore_controparte"].startswith("Avvocatura") and testata["valore"].startswith("Valore non dichiarato")


def test_conto_economico_mostra_il_contributo_come_il_modello():
    from web.services.fascicolo_conto_economico_runtime import allinea_contributo_al_modello

    righe = [{"voce": "contributo_unificato", "stato": "Esente, da confermare", "tono": "warning", "dettaglio": "presidio"}]
    lettura = {"ragionamento": {"conclusioni": [{"codice": "contributo_unificato", "stato": "non_dovuto", "cosa": "esente",
                                                 "prova_o_motivo": "Esenzione certa: autocertificazione depositata.",
                                                 "norme": [{"norma": "art. 9, comma 1-bis, D.P.R. 115/2002"}]}]}}
    allinea_contributo_al_modello(righe, lettura, {})
    assert righe[0]["stato"] == "Non dovuto (art. 9, comma 1-bis, D.P.R. 115/2002)" and righe[0]["tono"] == "success"
    assert righe[0]["dettaglio"] == "Esenzione certa: autocertificazione depositata."
    invariata = [{"voce": "contributo_unificato", "stato": "Versato"}]
    allinea_contributo_al_modello(invariata, None, {})
    assert invariata[0]["stato"] == "Versato"


def test_natura_del_cliente_dall_anagrafica():
    from types import SimpleNamespace

    from pct.quadro_economia import natura_cliente

    assert natura_cliente(SimpleNamespace(tipo="PERSONA_GIURIDICA", partita_iva="", nome="Alfa srl")) == "impresa"
    assert natura_cliente(SimpleNamespace(tipo="PERSONA_FISICA", partita_iva="01234567890", nome="Avv. Bianchi")) == "impresa"
    assert natura_cliente(SimpleNamespace(tipo="PERSONA_FISICA", partita_iva="", nome="Rossi Maria")) == "consumatore"
    assert natura_cliente(None, "Comune di Palmi") == "pa"
    assert natura_cliente(None, "Rossi Maria") == ""
