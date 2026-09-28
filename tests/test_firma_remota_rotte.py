"""Firma remota dal fascicolo: impostazioni del prestatore, invio del codice e firma salvata.

Il servizio del prestatore è simulato con una vera chiave RSA (tests/firma_remota_simulata.py);
password e OTP non devono finire né nella configurazione né nel registro delle azioni.
"""

from __future__ import annotations

import io
import json

import pytest

from tests.firma_remota_simulata import ServizioSimulato


def _pdf() -> bytes:
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    tela = canvas.Canvas(buffer)
    tela.drawString(72, 720, "Ricorso")
    tela.save()
    return buffer.getvalue()


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
    import requests

    from pct.fascicoli import TipoDocumento, TipoFascicolo
    from tests.test_revisione_2410_sicurezza import _app
    from web.helpers import get_fascicoli

    servizio = ServizioSimulato()
    monkeypatch.setattr(requests, "post", servizio.post)
    app = _app(tmp_path)
    with app.test_request_context("/"):
        fascicolo = get_fascicoli().nuovo("Rossi c. Bianchi", TipoFascicolo.CIVILE)
        pdf = get_fascicoli().aggiungi_documento(fascicolo.id, "Ricorso.pdf", TipoDocumento.RICORSO, _pdf())
        testo = get_fascicoli().aggiungi_documento(fascicolo.id, "Nota.txt", TipoDocumento.COMUNICAZIONE, b"nota di deposito")
    return app, servizio, fascicolo.id, pdf.id, testo.id, tmp_path


def _client(app):
    from tests.test_topbar_operational_api import _login

    client = app.test_client()
    _login(client)
    return client


def _salva_impostazioni(client, **campi):
    corpo = {"backend_preferito": "remota", "prestatore": "aruba", "remota_utente": "avv.rossi",
             "remota_dominio": "firma", "remota_tipo_otp": "sms", **campi}
    return client.post("/api/v1/ui/impostazioni/firma", json=corpo, headers={"Accept": "application/json"})


def test_impostazioni_firma_remota_e_dispositivo(ambiente):
    app, _servizio, *_ = ambiente
    with _client(app) as client:
        risposta = _salva_impostazioni(client, dispositivo_produttore="athena").get_json()
        assert risposta["ok"], risposta
        firma = risposta["firma"]
        assert firma["backend_preferito"] == "remota" and firma["prestatore"] == "aruba"
        assert firma["prestatore_info"]["protocolli"] == ["arss"]
        assert firma["prestatore_info"]["endpoint_predefinito"].startswith("https://arss.arubapec.it/")
        assert any(p.endswith("asepkcs.dll") for p in firma["librerie_dispositivo"]["windows"])
        errore = _salva_impostazioni(client, prestatore="acme").get_json()
        assert errore["ok"] is False and "prestatore" in errore["errors"]
        errore = _salva_impostazioni(client, prestatore="infocert", remota_endpoint="http://x/csc/v1").get_json()
        assert errore["errors"]["remota_endpoint"].startswith("L'indirizzo")
        errore = _salva_impostazioni(client, remota_protocollo="sws").get_json()
        assert "remota_protocollo" in errore["errors"]


def test_stato_invio_codice_e_firma_pades_e_cades(ambiente):
    app, servizio, id_fasc, id_pdf, id_txt, tmp_path = ambiente
    intestazioni = {"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"}
    with _client(app) as client:
        assert _salva_impostazioni(client).get_json()["ok"]
        stato = client.get("/api/firma/remota/stato", headers=intestazioni).get_json()
        assert stato["attiva"] and stato["protocollo"] == "arss" and stato["invia_codice"]
        otp = client.post("/api/firma/remota/otp", json={"password": "Firma!2026"}, headers=intestazioni).get_json()
        assert otp == {"ok": True, "messaggio": "Codice inviato per SMS."}
        errato = client.post("/api/firma/remota/firma-documento", headers=intestazioni, json={
            "fascicolo_id": id_fasc, "documento_id": id_pdf, "password": "Firma!2026", "otp": "000000"})
        assert errato.status_code == 400 and "Credenziali non valide" in errato.get_json()["messaggio"]
        pades = client.post("/api/firma/remota/firma-documento", headers=intestazioni, json={
            "fascicolo_id": id_fasc, "documento_id": id_pdf, "password": "Firma!2026", "otp": "123456",
            "visible_signature_mode": "basso_destra", "visible_signature_place": "Taurianova"}).get_json()
        assert pades["ok"] and pades["formato"] == "pades" and pades["nome_firmato"] == "Ricorso.pdf"
        assert pades["intestatario"] == "ROSSI MARIO"
        cades = client.post("/api/firma/remota/firma-documento", headers=intestazioni, json={
            "fascicolo_id": id_fasc, "documento_id": id_txt, "password": "Firma!2026", "otp": "123456"}).get_json()
        assert cades["ok"] and cades["nome_firmato"] == "Nota.txt.p7m"
        ancora = client.post("/api/firma/remota/firma-documento", headers=intestazioni, json={
            "fascicolo_id": id_fasc, "documento_id": id_pdf, "password": "Firma!2026", "otp": "123456"})
        assert ancora.status_code == 409 and ancora.get_json()["requires_confirm_resign"]

    from pct.firma import analizza_firma_documento
    from web.helpers import get_fascicoli

    with app.test_request_context("/"):
        documenti = {d.id: d for d in get_fascicoli().get(id_fasc).documenti}
        firmato = get_fascicoli().percorso_documento_lettura(id_fasc, id_pdf).read_bytes()
    assert documenti[id_pdf].firmato_digitalmente and documenti[id_txt].firmato_digitalmente
    assert documenti[id_pdf].signature_metadata["remote_provider"] == "aruba"
    assert all(f["cryptographic_signature_verified"] for f in analizza_firma_documento(firmato, "Ricorso.pdf"))
    # Password e OTP non restano da nessuna parte nei dati dello studio.
    for file in tmp_path.rglob("*"):
        if file.is_file() and file.suffix in {".json", ".db", ".sqlite", ".log"}:
            contenuto = file.read_bytes()
            assert b"Firma!2026" not in contenuto and b"123456" not in contenuto, file


def test_firma_remota_non_scelta_o_prestatore_senza_api(ambiente):
    app, _servizio, id_fasc, id_pdf, *_ = ambiente
    intestazioni = {"Accept": "application/json"}
    with _client(app) as client:
        stato = client.get("/api/firma/remota/stato", headers=intestazioni).get_json()
        assert stato["attiva"] is False
        assert _salva_impostazioni(client, prestatore="poste").get_json()["ok"]
        stato = client.get("/api/firma/remota/stato", headers=intestazioni).get_json()
        assert stato["attiva"] is False and "Firma esterna" in stato["messaggio"]
        risposta = client.post("/api/firma/remota/firma-documento", headers=intestazioni, json={
            "fascicolo_id": id_fasc, "documento_id": id_pdf, "password": "x", "otp": "1"})
        assert risposta.status_code == 400 and "Firma esterna" in json.dumps(risposta.get_json())
