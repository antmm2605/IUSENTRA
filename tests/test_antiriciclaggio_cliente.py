"""Adeguata verifica dalla scheda del cliente: griglia CNF, documento, SOS, screening UE e fascicolo PDF (D.Lgs. 231/2007)."""

from __future__ import annotations

import pytest

INTESTAZIONI = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
    from pct.clienti import TipoCliente
    from tests.test_revisione_2410_sicurezza import _app
    from web.helpers import get_clienti

    esiti = []

    def finto_screening(soggetto, *, cache_dir):
        esiti.append(soggetto)
        return {"provider_key": "eu-consolidated-financial-sanctions", "source_url": "https://webgate.ec.europa.eu/fsd/fsf",
                "source_version": "2026-09-28", "snapshot_hash": "a" * 64, "subject_label": soggetto,
                "outcome": "NESSUN_RISCONTRO", "matches": [], "note": ""}

    monkeypatch.setattr("pct.aml_screening.screen_eu_financial_sanctions", finto_screening)
    app = _app(tmp_path)
    with app.test_request_context("/"):
        cliente = get_clienti().nuovo(TipoCliente.PERSONA_FISICA, nome="Mario", cognome="Rossi")
    return app, cliente.id, esiti


def _client(app):
    from tests.test_topbar_operational_api import _login

    client = app.test_client()
    _login(client)
    return client


def test_scheda_dal_cliente_con_griglia_documento_e_pdf(ambiente):
    app, cid, esiti = ambiente
    base = f"/clienti/{cid}/antiriciclaggio"
    with _client(app) as client:
        vuoto = client.get(f"/api/v1/ui{base}", headers=INTESTAZIONI).get_json()
        assert vuoto["ok"] and vuoto["schede"] == [] and "Rossi" in vuoto["cliente"] and vuoto["puoModificare"]
        errore = client.post(f"{base}/avvia", json={"prestazione": "trasferimento_immobili"}, headers=INTESTAZIONI).get_json()
        assert errore["ok"] is False and "scopo" in errore["message"].lower()
        creata = client.post(f"{base}/avvia", headers=INTESTAZIONI, json={
            "prestazione": "trasferimento_immobili", "scopoNatura": "Acquisto di immobile", "documentoTipo": "carta_identita",
            "documentoNumero": "CA00000AA", "documentoScadenza": "2020-01-01"}).get_json()
        assert creata["ok"], creata
        vid = creata["verificaId"]
        stato = client.get(f"/api/v1/ui{base}", headers=INTESTAZIONI).get_json()
        scheda = stato["schede"][0]
        assert scheda["documento_scaduto"] and any("scaduto" in p for p in scheda["promemoria"])
        assert len(scheda["indici"]) >= 6 and scheda["livello_suggerito"] != "RAFFORZATA"
        indici = [dict(i, punteggio=5) for i in scheda["indici"]]
        assert client.post(f"{base}/{vid}/aggiorna", headers=INTESTAZIONI, json={
            "indici": indici, "sosValutazione": "in_valutazione", "documentoScadenza": "2031-01-01"}).get_json()["ok"]
        cattivo = client.post(f"{base}/{vid}/aggiorna", headers=INTESTAZIONI, json={"indici": [dict(indici[0], punteggio=9)]}).get_json()
        assert cattivo["ok"] is False and "1 a 5" in cattivo["message"]
        scheda = client.get(f"/api/v1/ui{base}", headers=INTESTAZIONI).get_json()["schede"][0]
        assert scheda["livello_suggerito"] == "RAFFORZATA" and scheda["sos_valutazione"] == "in_valutazione"
        assert not scheda["documento_scaduto"]
        assert any("Infostat" in p for p in scheda["promemoria"])
        # Meno rigoroso del suggerito senza motivazione: rifiutato; con motivazione: confermato.
        assert client.post(f"{base}/{vid}/conferma", json={"livello": "ORDINARIA"}, headers=INTESTAZIONI).status_code == 400
        assert client.post(f"{base}/{vid}/conferma", json={"livello": "RAFFORZATA"}, headers=INTESTAZIONI).get_json()["ok"]
        screening = client.post(f"{base}/{vid}/screening-ue", headers=INTESTAZIONI).get_json()
        assert screening["ok"] and esiti and "Nessun riscontro" in screening["message"]
        pdf = client.get(f"{base}/{vid}/fascicolo.pdf")
        assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF") and pdf.mimetype == "application/pdf"
        assert client.get(f"/clienti/ALTRO/antiriciclaggio/{vid}/fascicolo.pdf").status_code == 404


def test_difesa_in_giudizio_fuori_ambito(ambiente):
    app, cid, _ = ambiente
    base = f"/clienti/{cid}/antiriciclaggio"
    with _client(app) as client:
        vid = client.post(f"{base}/avvia", headers=INTESTAZIONI,
                          json={"prestazione": "difesa_giudiziale", "scopoNatura": "Difesa in appello"}).get_json()["verificaId"]
        scheda = client.get(f"/api/v1/ui{base}", headers=INTESTAZIONI).get_json()["schede"][0]
        assert scheda["in_ambito"] is False and "art. 17 c. 7" in scheda["promemoria"][0]
        assert client.post(f"{base}/{vid}/conferma", json={"livello": "ORDINARIA"}, headers=INTESTAZIONI).status_code == 400
