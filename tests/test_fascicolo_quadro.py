"""Quadro del fascicolo: stato della pratica, righe e coerenza del contributo unificato fra i pannelli."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pct.fascicolo_pec_conteggio import conteggio_pec
from pct.fascicolo_quadro import riga_documenti, riga_economia, riga_notifiche, riga_prossimo_passo, riga_termini
from pct.fascicolo_stato_pratica import codice_stato, stato_pratica

OGGI = date(2026, 11, 10)
HEADERS = {"X-API-Key": "react-test-key"}


def test_stato_pratica_definita_non_attribuisce_la_chiusura_alla_sentenza():
    stato = stato_pratica({"stato": "DEFINITO", "archivio_pronto": True, "data_chiusura": "2026-04-17",
                           "avanzamento": [{"stato_nuovo": "DEFINITO", "note": "Sentenza n. 679/2026; RG 161/2026"}]})
    assert stato == {"codice": "da_archiviare", "etichetta": "Definita, da archiviare",
                     "dettaglio": "Sentenza n. 679/2026 · Chiusura registrata il 17/04/2026"}


def test_codici_stato_pratica():
    assert codice_stato("APERTO") == codice_stato("IN_CORSO") == "in_corso"
    assert codice_stato("SOSPESO") == "sospesa"
    assert codice_stato("DEFINITO") == "definita"
    assert codice_stato("ARCHIVIATO") == "archiviata"


def test_regia_fuori_deposito_non_dice_in_lavorazione_una_pratica_definita():
    from pct.practice_engine.completamento import stato_operativo

    assert stato_operativo(in_deposito=False, stato_fascicolo="DEFINITO") == "DEFINITO"
    assert stato_operativo(in_deposito=False, stato_fascicolo="IN_CORSO") == "FASCICOLO_APERTO"


def test_conteggio_pec_unico():
    conteggio = conteggio_pec({"totale": 0, "da_controllare": []},
                              {"esiti": {"pec": {"esaminate": 1, "da_confermare": [{"id": "M1"}]}}})
    assert conteggio["collegate"] == 0 and conteggio["da_confermare"] == 1
    assert conteggio["testo"] == "0 PEC collegate dalla casella · 1 da confermare il collegamento"
    assert conteggio_pec({"totale": 4, "collegate": 2})["collegate"] == 2


def test_righe_del_quadro():
    assert riga_prossimo_passo([{"azione": "Preparare la proforma", "urgenza": 1, "entro": "20/11/2026"}])["livello"] == "attenzione"
    assert "non è ancora pronta" in riga_prossimo_passo(None)["testo"]
    termini = riga_termini([{"data": "2026-01-10", "titolo": "passato", "tipo": "scadenza"},
                            {"data": "2026-11-14", "titolo": "Note scritte", "tipo": "udienza"}], oggi=OGGI)
    assert termini["testo"] == "Udienza del 14/11/2026: Note scritte" and termini["livello"] == "urgente"
    assert riga_termini([], oggi=OGGI)["livello"] == "ok"
    notifiche = riga_notifiche([{"atto": "Ricorso in materia di lavoro", "stato": "notificato"},
                                {"atto": "Sentenza", "stato": "facoltativo"}], oggi=OGGI)
    assert notifiche["testo"] == "Ricorso in materia di lavoro: notificato · Sentenza: notifica facoltativa"
    assert notifiche["sezione"] == "sezione-comunicazioni"
    assert "da calcolare" in riga_notifiche(None, oggi=OGGI)["testo"]
    documenti = riga_documenti(43, 40, {"collegate": 0, "da_confermare": 1})
    assert documenti["testo"] == "43 documenti · 40 da classificare · 1 PEC da confermare"


def test_presidio_storico_riusa_atto_e_non_convoca_da_ricevuta(monkeypatch):
    import json

    from flask import Flask
    from web.services import riscontri_processuali_runtime
    from web.services.pannelli_pronti_catalogo import Pannello
    from web.services.pannelli_pronti_ricomposizione import allinea_presidio_udienze
    from web.services.pannelli_pronti_runtime import _ricomponi

    azione = {"historical": True, "type": "udienza_127_bis", "documentId": "BUSTA",
              "date": "01/04/2026", "dateIso": "2026-04-01", "time": "09:45"}
    ricevuta = dict(azione, documentId="RICEVUTA", date="15/12/2025",
                   source="CONSEGNA: Notificazione ai sensi della legge n. 53/1994")
    manuale = dict(ricevuta, registeredHref="/agenda/1")
    collegata = dict(azione, registeredHref="/agenda/2")
    altra_ora = dict(azione, time="10:30")
    termine = dict(azione, type="termine_documento", dateIso="2026-06-01")
    dati = {"documentPresidio": {"actions": [azione, collegata, ricevuta, manuale, altra_ora, termine]}}
    lettura = {
        "documenti": {"tutti": [{"id": "BUSTA", "etichetta": "Copia non crittografata del deposito telematico"}]},
        "ragionamento": {"udienze": [{"data": "01/04/2026", "ora": "09:45", "modalita": "da remoto",
                                     "documento_id": "DECRETO", "documento": "Decreto"}],
                         "conclusioni": [{"codice": "notifica_ordinata", "stato": "fatto", "prova_o_motivo": "Eseguita",
                                          "letto": {"documento_id": "ORD", "documento": "Ordinanza"},
                                          "prova_notifica": {"deposito_inviato": {"copia_in_chiaro_id": "BUSTA"}},
                                          "termine": {"scadenza_iso": "2026-06-01"}}]},
    }
    originale = json.dumps(dati).encode()
    allinea_presidio_udienze(dati, lettura, "F1")
    udienza, appuntamento, rinnovazione = dati["documentPresidio"]["actions"]
    assert udienza["documentId"] == "DECRETO" and udienza["sourceHref"].endswith("/DECRETO/visualizza")
    assert udienza["registeredHref"] == "/agenda/2"
    assert appuntamento is manuale
    assert rinnovazione["documentId"] == "ORD" and rinnovazione["description"] == "Eseguita"
    monkeypatch.setattr(riscontri_processuali_runtime, "lettura_consultiva", lambda _fid: lettura)
    pannello = Pannello("dettaglio", "test", ricomponi="lettura_del_dettaglio")
    app = Flask(__name__)
    with app.test_request_context("/fascicoli/F1?include=documenti,scadenze&confirm_revision=1"):
        confermato = json.loads(_ricomponi(pannello, originale, "F1"))
    assert confermato["documentPresidio"] == dati["documentPresidio"]


def test_costituzione_storica_riusa_il_computo_solo_per_il_decreto_o_la_pec_provata():
    from web.services.pannelli_pronti_ricomposizione import allinea_presidio_udienze

    grezza = {"id": "A1", "historical": True, "date": "06/12/2025", "dateIso": "2025-12-06",
              "type": "costituzione_resistente", "documentId": "NOTIFICA"}
    altra = {**grezza, "id": "A2", "documentId": "ALTRA"}
    manuale = {**grezza, "id": "A3", "registeredHref": "/scadenziario?focus=S1"}
    dati = {"documentPresidio": {"actions": [grezza, altra, manuale], "nextAction": grezza}}
    lettura = {"ragionamento": {"conclusioni": [{
        "codice": "costituzione_convenuto", "onerato_codice": "controparte",
        "letto": {"documento_id": "DECRETO", "documento": "Decreto di fissazione udienza"},
        "termine": {"data_grezza": "2025-12-06", "scadenza_iso": "2025-12-05", "scadenza": "05/12/2025",
                    "fonti_trasmissione": ["NOTIFICA"], "computo": "Anticipo al venerdì (art. 155 c.p.c.)."},
    }]}}
    allinea_presidio_udienze(dati, lettura, "F1")
    corretta, invariata, registrata = dati["documentPresidio"]["actions"]
    assert corretta["dateIso"] == "2025-12-05" and corretta["sourceHref"].endswith("/DECRETO/visualizza")
    assert corretta["description"].endswith("Termine della controparte.")
    assert (invariata, registrata) == (altra, manuale)
    assert dati["documentPresidio"]["nextAction"] == corretta


def test_quadro_notifica_con_data_trascorsa_chiede_la_prova():
    notifiche = riga_notifiche([
        {"atto": "Ricorso e decreto", "stato": "da_notificare", "scadenza": "2026-10-19"},
        {"atto": "Altro atto", "stato": "da_notificare", "scadenza": "2026-12-15"},
    ], oggi=OGGI)
    assert "Data indicata 19/10/2026 già trascorsa. Verificare invio e ricevute PEC." in notifiche["testo"]
    assert "da notificare entro il 15/12/2026" in notifiche["testo"]
    assert notifiche["livello"] == "urgente"


def test_riga_economia_dal_conto_economico():
    contributo = {"etichetta": "Esente, da confermare", "categoria": "esente", "tono": "warning",
                  "norma": "art. 9, comma 1-bis, D.P.R. 115/2002", "importoLabel": ""}
    righe = [{"voce": "sentenza", "importo": 515.0, "importoLabel": "€ 515,00", "stato": "Distratte in favore dell'avvocato"},
             {"voce": "parcella", "stato": "Da preparare"}]
    riga = riga_economia(contributo, righe, "Preparare la proforma.")
    assert riga["testo"].startswith("Contributo unificato: Esente, da confermare (art. 9, comma 1-bis, D.P.R. 115/2002)")
    assert "liquidate in sentenza € 515,00, distratte in favore dell'avvocato" in riga["testo"]
    assert "Preparare la proforma." in riga["testo"]
    assert riga["testo"].lower().count("proforma") == 1
    assert riga["livello"] == "attenzione" and riga["sezione"] == "sezione-economia"


def test_economia_richiede_verifica_dispositivo_prima_della_proforma():
    righe = [
        {"voce": "sentenza", "tono": "warning", "stato": "Sentenza presente: spese da verificare"},
        {"voce": "parcella", "stato": "Da preparare"},
    ]
    contributo = {"etichetta": "Esente", "categoria": "esente", "tono": "success"}

    riga = riga_economia(contributo, righe, "Verificare il dispositivo sulle spese della sentenza.")

    assert riga["livello"] == "attenzione"
    assert "Verificare il dispositivo" in riga["testo"]
    assert "proforma da preparare" not in riga["testo"]


def test_quadro_mostra_le_spese_compensate_anche_prima_del_conto(monkeypatch):
    from web.services import riscontri_processuali_runtime
    from web.services.fascicolo_quadro_runtime import riga_economia_materializzata

    monkeypatch.setattr(riscontri_processuali_runtime, "risultato_materializzato", lambda *_: None)
    lettura = {
        "percorso": {"documento_id": "S1", "spese": {"regolazione": "compensazione"}},
        "ragionamento": {"economia": {"contributo_unificato": {"codice": "esente", "etichetta": "Esente"}}},
    }
    assert riga_economia_materializzata("F1", lettura)["testo"] == "Contributo unificato: Esente · spese compensate"


def _fascicolo_esente(tmp_path: Path):
    from pct.fascicoli import TipoFascicolo
    from tests.test_react_shell import _app

    app = _app(tmp_path)
    with app.app_context():
        gestione = app.extensions["core_runtime"]["get_fascicoli"]()
        fascicolo = gestione.nuovo("Carbone / MIM", TipoFascicolo.LAVORO, nome_cliente="Carbone Claudia")
        fascicolo.pagamenti = {"contributo_unificato": {
            "kind": "contributo_unificato", "status": "non_previsto", "previsto": False,
            "documento_fonte": "AUTOCERTIFICAZIONE_DELLA_SITUAZIONE_REDDITUALE_-_ESENZIONE_CONTRIBUTO_UNIFICATO.PDF",
            "origine": "Controllo economico", "updated_by": "Avv. Giuseppe Montagnese"}}
        gestione._salva()
    return app, fascicolo.id


def test_endpoint_quadro_contratto(tmp_path: Path):
    app, fid = _fascicolo_esente(tmp_path)
    with app.test_client() as client:
        risposta = client.get(f"/api/v1/ui/fascicoli/{fid}/quadro", headers=HEADERS)
        assente = client.get("/api/v1/ui/fascicoli/NONESISTE/quadro", headers=HEADERS)
    assert risposta.status_code == 200
    dati = risposta.get_json()
    assert dati["ok"] is True and set(dati) == {"ok", "stato", "righe", "generato_il", "esito_dispositivo", "lettura_precedente"}
    assert dati["stato"]["codice"] in {"in_corso", "definita", "da_archiviare", "archiviata", "sospesa"}
    assert [r["tema"] for r in dati["righe"]] == ["prossimo_passo", "termini", "economia", "notifiche", "documenti"]
    for voce in dati["righe"]:
        assert set(voce) == {"tema", "titolo", "testo", "livello", "sezione"} and voce["testo"]
        assert voce["livello"] in {"ok", "info", "attenzione", "urgente"}
    assert assente.status_code == 404


def test_stessa_etichetta_del_contributo_in_card_finestra_conto_e_quadro(tmp_path: Path):
    app, fid = _fascicolo_esente(tmp_path)
    with app.test_client() as client:
        conto = client.get(f"/api/v1/ui/fascicoli/{fid}/conto-economico", headers=HEADERS).get_json()
        quadro = client.get(f"/api/v1/ui/fascicoli/{fid}/quadro", headers=HEADERS).get_json()
    with app.test_request_context(headers=HEADERS):
        from web.services.react_fascicoli_bridge import payment_summary_for_fascicolo, payment_summary_for_fascicolo_fast

        fascicolo = app.extensions["core_runtime"]["get_fascicoli"]().get(fid)
        card = payment_summary_for_fascicolo_fast(fascicolo)["items"]["contributo_unificato"]
        finestra = payment_summary_for_fascicolo(fascicolo)["items"]["contributo_unificato"]
    etichetta = next(r["stato"] for r in conto["righe"] if r["voce"] == "contributo_unificato")
    assert etichetta == "Esente"  # esenzione registrata dall'avvocato con l'autocertificazione come fonte
    assert card["statusLabel"] == finestra["statusLabel"] == etichetta
    assert card["statoContributo"]["codice"] == finestra["statoContributo"]["codice"] == "esente"
    economia = next(r for r in quadro["righe"] if r["tema"] == "economia")
    assert economia["testo"].startswith(f"Contributo unificato: {etichetta}")


def test_sintesi_obblighi_compatta_solo_atto_stato_scadenza():
    from web.services.obblighi_notifica_sintesi import compatta

    assert compatta([{"etichetta": "Sentenza", "stato": "facoltativo", "scadenza": "", "motivo": "lungo"},
                     {"etichetta": "", "stato": "notificato"}]) == [{"atto": "Sentenza", "stato": "facoltativo", "scadenza": ""}]


def test_fatturazione_filtrata_solo_per_un_fascicolo_dello_studio():
    from types import SimpleNamespace

    from web.services.react_fatturazione_bridge import _filtro_fascicolo

    fascicoli = {"F1": SimpleNamespace(id="F1", numero="2026/1", titolo="Rossi c. Bianchi", numero_rg="", anno_rg="")}
    filtro = _filtro_fascicolo({"id_fascicolo": "F1"}, fascicoli)
    assert filtro["id"] == "F1" and filtro["rimuoviHref"] == "/fatturazione"
    assert _filtro_fascicolo({"id_fascicolo": "ALTRO"}, fascicoli) is None
    assert _filtro_fascicolo({}, fascicoli) is None


def test_lettura_porta_alla_fatturazione_del_solo_fascicolo():
    from pct.fascicolo_lettura.prossimi_passi import _passi_economico

    passi = _passi_economico({"presente": True, "ha_incarico": True, "liquidato": 515, "liquidato_it": "€ 515,00",
                              "liquidazione": {}, "liquidazione_incasso": "non_incassata"}, "9A681FDF")
    assert any(p.href == "/fatturazione?id_fascicolo=9A681FDF" for p in passi)


def test_riscontri_leggono_lo_stesso_quadro_per_sezione(monkeypatch):
    import json

    from web.services import riscontri_processuali_runtime as runtime

    quadro = {"impronta": "fonti-f1", "versione": "v3", "conclusioni": [
        {"codice": "notifica_sentenza", "stato": "dubbio"},
        {"codice": "termine_impugnazione", "stato": "dubbio"},
        {"codice": "spese_liquidate", "stato": "da_fare"},
    ]}
    corpo = json.dumps({"lettura": {"ragionamento": quadro}}).encode()
    monkeypatch.setattr(runtime, "pannello_del_profilo", lambda fid, nome: corpo if (fid, nome) == ("F1", "lettura") else None)
    for sezione, codice in (("notifiche", "notifica_sentenza"), ("termini", "termine_impugnazione"), ("economia", "spese_liquidate")):
        vista = runtime.riscontri_processuali("F1", sezione)
        assert vista["impronta"] == "fonti-f1"
        assert [c["codice"] for c in vista["conclusioni"]] == [codice]
    assert runtime.riscontri_processuali("F2", "regia") == {"stato": "da_preparare"}


def test_quadro_distingue_scadenza_in_bozza_dal_termine_confermato():
    from web.services.fascicolo_quadro_runtime import riga_termini_da_lettura

    oggi = date(2026, 11, 14)
    bozza = {"data": "2027-01-04", "titolo": "Impugnazione sentenza", "tipo": "scadenza", "stato": "BOZZA"}
    riga = riga_termini_da_lettura([bozza], {"ragionamento": {"impronta": "i", "versione": "v"}}, oggi)
    assert "confermata in agenda" in riga["testo"]
    assert "1 scadenza da verificare in agenda" in riga["testo"]
    assert riga["livello"] == "attenzione"


def test_riscontro_spese_da_sentenza_richiede_una_fonte_del_fascicolo():
    from web.services.riscontri_processuali_runtime import chiarisci_spese_da_sentenza

    riga = {"voce": "sentenza", "stato": "Nessuna sentenza con spese liquidate", "tono": "neutral"}
    proforma = {"azione": {"comando": "genera_proforma"}}
    conto = {"ok": True, "fascicoloId": "F1", "righe": [riga], "percorso": {"passi": [proforma]}}
    chiarisci_spese_da_sentenza(conto, {"ragionamento": {"conclusioni": []}})
    assert riga["tono"] == "neutral"
    assert proforma["azione"]["comando"] == "genera_proforma"
    assert "prossimoPasso" not in conto["percorso"]

    conclusione = {"codice": "termine_impugnazione", "letto": {"documento_id": "S1", "documento": "Sentenza.pdf"}}
    chiarisci_spese_da_sentenza(conto, {"ragionamento": {"conclusioni": [conclusione]}})
    assert riga["tono"] == "warning"
    assert riga["fonti"][0]["href"] == "/fascicoli/F1/documenti/S1/visualizza"
    assert "azione" not in proforma


def test_quadro_riusa_riscontro_storico_solo_per_lo_stesso_atto_e_la_stessa_finalita():
    from web.services.fascicolo_quadro_runtime import riga_notifiche_da_lettura
    from web.services.obblighi_notifica_sintesi import compatta

    lettura = {"ragionamento": {"conclusioni": [{
        "codice": "notifica_sentenza", "stato": "non_dovuto",
        "letto": {"documento_id": "originale"},
    }]}}
    obblighi = compatta([
        {"etichetta": "Sentenza", "regola": "sentenza_notifica_breve", "documentoId": "copia",
         "fonti_documentali": [{"documentoId": "originale"}], "stato": "da_verificare"},
        {"etichetta": "Altra sentenza", "regola": "sentenza_notifica_breve",
         "documentoId": "altra", "stato": "da_verificare"},
        {"etichetta": "Titolo esecutivo", "documentoId": "originale", "stato": "da_verificare"},
    ])
    sintesi = {"obblighi": obblighi}
    testo = riga_notifiche_da_lettura(sintesi, lettura, OGGI)["testo"]
    assert "Sentenza: riscontro storico" in testo
    assert "Altra sentenza: notifica da verificare" in testo
    assert "Titolo esecutivo: notifica da verificare" in testo
    assert obblighi[0]["stato"] == "da_verificare"
    precedente = {**lettura, "aggiornamento_pendente": True}
    testo_precedente = riga_notifiche_da_lettura(sintesi, precedente, OGGI)["testo"]
    assert "Sentenza: ultimo riscontro storico del termine breve, aggiornamento automatico in corso" in testo_precedente
    assert "Altra sentenza: notifica da verificare" in testo_precedente
    assert "Titolo esecutivo: notifica da verificare" in testo_precedente
    assert riga_notifiche_da_lettura({"obblighi": obblighi[:1]}, precedente, OGGI)["livello"] == "info"


def test_quadro_senza_sintesi_mostra_i_soli_riscontri_documentati():
    from web.services.fascicolo_quadro_runtime import riga_notifiche_da_lettura

    lettura = {"ragionamento": {"versione": "1", "impronta": "fonti", "conclusioni": [
        {"codice": "notifica_ricorso_decreto_415", "stato": "non_dovuto", "letto": {"documento_id": "D1"}},
        {"codice": "notifica_sentenza", "stato": "non_dovuto", "letto": {"documento_id": "S1"}},
        {"codice": "notifica_sentenza", "stato": "da_fare", "letto": {"documento_id": "S2"}},
    ]}}
    riga = riga_notifiche_da_lettura(None, lettura, OGGI)
    assert "adempimento storico" in riga["testo"]
    assert "riscontro storico del termine breve" in riga["testo"]
    assert riga["livello"] == "info"
    assert "Ultima lettura salvata" in riga_notifiche_da_lettura(
        None, {**lettura, "aggiornamento_pendente": True}, OGGI
    )["testo"]
    assert "da calcolare" in riga_notifiche_da_lettura(None, None, OGGI)["testo"]


def test_pannello_obblighi_proietta_lettura_senza_riproporre_la_notifica_storica(monkeypatch):
    import json

    from flask import Flask
    from web.blueprints import api_v1_react
    from web.services import riscontri_processuali_runtime
    from web.services.pannelli_pronti_ricomposizione import obblighi_da_lettura

    storica = {"regola": "sentenza_notifica_breve", "stato": "da_verificare",
               "documentoId": "copia", "fonti_documentali": [{"documentoId": "S1"}]}
    corrente = {**storica, "documentoId": "S2", "fonti_documentali": []}
    titolo = {**storica, "regola": "titolo_esecutivo"}
    payload = {"ok": True, "obblighi": [storica, corrente, titolo],
               "riscontriProcessuali": {"stato": "da_preparare"}}
    riscontri = {"stato": "pronto", "conclusioni": [
        {"codice": "notifica_sentenza", "stato": "non_dovuto", "letto": {"documento_id": "S1"}}
    ]}
    monkeypatch.setattr(api_v1_react, "_api_key_valida", lambda: False)
    monkeypatch.setattr(api_v1_react, "_session_user_can", lambda permission: permission == "fascicoli.leggi")

    def salvati(fid, sezione):
        assert (fid, sezione) == ("F1", "notifiche")
        return riscontri

    monkeypatch.setattr(riscontri_processuali_runtime, "riscontri_processuali", salvati)
    with Flask(__name__).test_request_context():
        risposta = json.loads(obblighi_da_lettura(json.dumps(payload).encode(), "F1"))
        assert risposta["obblighi"] == [corrente, titolo]
        assert risposta["riscontriProcessuali"] == riscontri
        riscontri["conclusioni"].clear()
        risposta = json.loads(obblighi_da_lettura(json.dumps(payload).encode(), "F1"))
        assert risposta["obblighi"] == payload["obblighi"]



def test_pannello_obblighi_riusa_riscontro_storico_con_lettura_in_aggiornamento(monkeypatch):
    from web.services import riscontri_processuali_runtime as runtime

    precedente = {"aggiornamento_pendente": True, "ragionamento": {
        "versione": "v1", "impronta": "precedente", "conclusioni": [
            {"codice": "notifica_sentenza", "stato": "non_dovuto",
             "letto": {"documento_id": "S1"}}
        ],
    }}
    monkeypatch.setattr(runtime, "lettura_materializzata", lambda _: None)
    monkeypatch.setattr(runtime, "lettura_precedente", lambda _: precedente)
    storica = {"regola": "sentenza_notifica_breve", "stato": "da_verificare", "documentoId": "S1"}
    altra = {**storica, "documentoId": "S2"}
    titolo = {**storica, "regola": "titolo_esecutivo"}
    payload = {"ok": True, "obblighi": [storica, altra, titolo]}

    riscontri = runtime.riscontri_processuali("F1", "notifiche")
    risposta = runtime.proietta_obblighi_notifica(payload, riscontri)
    assert risposta["obblighi"] == [altra, titolo]
    assert risposta["riscontriProcessuali"]["aggiornamento_pendente"] is True
    assert risposta["riscontriProcessuali"]["conclusioni"] == precedente["ragionamento"]["conclusioni"]
    assert payload["obblighi"] == [storica, altra, titolo]
    assert runtime.riscontri_processuali("F1", "economia") == {"stato": "da_preparare"}


def test_sintesi_storica_riusa_l_identita_solo_dallo_stesso_risultato(monkeypatch):
    import json
    from types import SimpleNamespace

    from web.services import pannelli_pronti_runtime
    from web.services.obblighi_notifica_sintesi import _integra_identita

    integrale = {"ok": True, "obblighi": [{
        "etichetta": "Sentenza", "stato": "da_verificare", "documentoId": "S1", "regola": "sentenza_notifica_breve",
    }]}
    istante_archivio = "2026-11-15T02:46:17.865+00:00"

    def pannello(fascicolo_id, nome, *, precedente):
        assert (fascicolo_id, nome, precedente) == ("F1", "obblighi-notifica", True)
        return SimpleNamespace(corpo=json.dumps(integrale).encode(), calcolato_il=istante_archivio)

    monkeypatch.setattr(pannelli_pronti_runtime, "voce_del_profilo", pannello)
    sintesi = {"obblighi": [{"atto": "Sentenza", "stato": "da_verificare", "scadenza": ""}],
               "calcolata_il": "2026-11-15T02:46:17Z"}
    aggiornata = _integra_identita(sintesi, "F1")
    assert aggiornata["obblighi"][0]["documenti"] == ["S1"]
    assert "documenti" not in sintesi["obblighi"][0]
    integrale["obblighi"][0]["stato"] = "notificato"
    assert _integra_identita(sintesi, "F1") is sintesi
    integrale["obblighi"][0]["stato"] = "da_verificare"
    istante_archivio = "2026-11-14T02:46:17.865+00:00"
    assert _integra_identita(sintesi, "F1") is sintesi


def test_risultato_obblighi_condiviso_vuoto_e_revisione_fonti(monkeypatch):
    from types import SimpleNamespace

    from flask import Flask
    from web.services import obblighi_notifica_fonti, obblighi_notifica_runtime, obblighi_notifica_sintesi
    from web.services import registro_letture_runtime

    righe = {}
    registro = SimpleNamespace(
        payload_cache_get=lambda tenant, fid, key: righe.get((tenant, fid, key)),
        payload_cache_set=lambda tenant, fid, key, payload, **_: righe.update({(tenant, fid, key): payload}),
    )
    fonte = {"F1": "iniziale", "F2": "iniziale"}
    chiamate = []
    monkeypatch.setattr(registro_letture_runtime, "registro_corrente", lambda: registro)
    monkeypatch.setattr(registro_letture_runtime, "tenant_corrente", lambda: "studio")
    monkeypatch.setattr(obblighi_notifica_fonti, "impronta", lambda fid: fonte[fid])
    monkeypatch.setattr(obblighi_notifica_fonti, "riferimento_corrente", lambda fid: fonte[fid])

    def calcola(fascicolo, *, rigoroso=False):
        chiamate.append((fascicolo.id, rigoroso))
        return []

    monkeypatch.setattr(obblighi_notifica_runtime, "obblighi_fascicolo", calcola)
    app = Flask(__name__)
    f1 = SimpleNamespace(id="F1")
    with app.test_request_context():
        obblighi_notifica_sintesi.salva("F1", obblighi_notifica_sintesi.valuta(f1))
    with app.test_request_context():
        fonte["F2"] = "aggiornata"
        assert obblighi_notifica_sintesi.valuta(f1) == []
        assert obblighi_notifica_sintesi.leggi("F1")["obblighi"] == []
        assert obblighi_notifica_sintesi.leggi_completi("F1") == []
    assert chiamate == [("F1", True)]
    with app.test_request_context():
        fonte["F1"] = "corrente"
        risultato = obblighi_notifica_sintesi.valuta(f1)
        fonte["F1"] = "modificata durante la valutazione"
        obblighi_notifica_sintesi.salva("F1", risultato)
        assert obblighi_notifica_sintesi.leggi_completi("F1") is None
        assert obblighi_notifica_sintesi.leggi("F1") is None
    assert chiamate == [("F1", True), ("F1", True)]
