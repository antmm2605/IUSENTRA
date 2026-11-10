"""Quadro del fascicolo: stato della pratica, righe e coerenza del contributo unificato fra i pannelli."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from pct.fascicolo_pec_conteggio import conteggio_pec
from pct.fascicolo_quadro import riga_documenti, riga_economia, riga_notifiche, riga_prossimo_passo, riga_termini
from pct.fascicolo_stato_pratica import codice_stato, stato_pratica

OGGI = date(2026, 11, 10)
HEADERS = {"X-API-Key": "react-test-key"}


def test_stato_pratica_definita_con_sentenza_e_data():
    stato = stato_pratica({"stato": "DEFINITO", "archivio_pronto": True, "data_chiusura": "2026-04-17",
                           "avanzamento": [{"stato_nuovo": "DEFINITO", "note": "Sentenza n. 679/2026; RG 161/2026"}]})
    assert stato == {"codice": "da_archiviare", "etichetta": "Definita, da archiviare",
                     "dettaglio": "Sentenza n. 679/2026 del 17/04/2026"}


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


def test_riga_economia_dal_conto_economico():
    contributo = {"etichetta": "Esente, da confermare", "categoria": "esente", "tono": "warning",
                  "norma": "art. 9, comma 1-bis, D.P.R. 115/2002", "importoLabel": ""}
    righe = [{"voce": "sentenza", "importo": 515.0, "importoLabel": "€ 515,00", "stato": "Distratte in favore dell'avvocato"},
             {"voce": "parcella", "stato": "Da preparare"}]
    riga = riga_economia(contributo, righe, "Preparare la proforma.")
    assert riga["testo"].startswith("Contributo unificato: Esente, da confermare (art. 9, comma 1-bis, D.P.R. 115/2002)")
    assert "liquidate in sentenza € 515,00, distratte in favore dell'avvocato" in riga["testo"]
    assert riga["livello"] == "attenzione" and riga["sezione"] == "sezione-economia"


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
    assert dati["ok"] is True and set(dati) == {"ok", "stato", "righe", "generato_il"}
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
