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
    assert conteggio["testo"] == "0 PEC collegate al fascicolo · 1 da confermare il collegamento"


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
    assert documenti["testo"] == "43 documenti · 40 da classificare · 1 PEC da confermare · 0 PEC collegate"


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
    assert "riscontro storico" not in riga_notifiche_da_lettura(sintesi, precedente, OGGI)["testo"]


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
