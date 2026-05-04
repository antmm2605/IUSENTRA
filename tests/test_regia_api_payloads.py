from pathlib import Path

from pct.clienti import GestioneClienti, Indirizzo, Recapiti, TipoCliente
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from tests.regia_test_utils import pdfa_bytes
from tests.test_web_bootstrap import _cfg_web
from web.app import create_app


def _app_with_fascicolo(tmp_path: Path):
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "regia-test-key"
    clienti = GestioneClienti(db_path=app.config["CLIENTI_DB"])
    cliente = clienti.nuovo(
        TipoCliente.PERSONA_FISICA,
        nome="Cliente",
        cognome="Regia",
        codice_fiscale="RSSMRA80A01H501U",
    )
    cliente = clienti.aggiorna(
        cliente.id,
        recapiti=Recapiti(email="cliente.regia@example.test"),
        indirizzo_residenza=Indirizzo(via="Via Regia", civico="1", comune="Palmi", provincia="RC"),
    )
    gf = GestioneFascicoli(
        db_path=app.config["FASCICOLI_DB"],
        documents_dir=app.config["FASCICOLI_DOCS"],
        archive_dir=app.config["FASCICOLI_ARCH"],
    )
    fascicolo = gf.nuovo(
        titolo="Regia API",
        tipo=TipoFascicolo.LAVORO,
        id_cliente=cliente.id,
        nome_cliente="Cliente Regia",
        oggetto="Impugnazione licenziamento",
        tribunale="Tribunale di Palmi",
        avvocato="Avv. Regia",
        codice_fiscale_cliente="RSSMRA80A01H501U",
        procedura_operativa_codice="PROC_LIC_IMP_001",
    )
    return app, gf, fascicolo


def test_api_regia_payload_completo_e_mock_false(tmp_path):
    app, _gf, fascicolo = _app_with_fascicolo(tmp_path)
    client = app.test_client()
    response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/regia", headers={"X-API-Key": "regia-test-key"})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["mock_fallback"] is False
    assert payload["source"] == "repository reale"
    assert payload["header"]["title"] == "Regia API"
    assert payload["checklist"]
    assert payload["documentSlots"]
    assert payload["validation"]["blockers"]


def test_api_slot_predeposito_deposito_ricevuta_evidence_pack(tmp_path):
    app, gf, fascicolo = _app_with_fascicolo(tmp_path)
    doc = gf.aggiungi_documento(fascicolo.id, "atto.pdf", TipoDocumento.ATTO_GIUDIZIARIO, pdfa_bytes(), firmato=True)
    procura = gf.aggiungi_documento(fascicolo.id, "procura.pdf", TipoDocumento.PROCURA, pdfa_bytes(), firmato=True)
    client = app.test_client()
    headers = {"X-API-Key": "regia-test-key"}

    link = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/document-slots/ATTO_PRINCIPALE/link",
        json={"document_id": doc.id},
        headers=headers,
    )
    assert link.status_code == 200
    assert link.get_json()["mock_fallback"] is False
    client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/document-slots/PROCURA/link", json={"document_id": procura.id}, headers=headers)
    validate = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/document-slots/ATTO_PRINCIPALE/validate", headers=headers)
    assert validate.status_code == 200
    check = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/predeposito/check", headers=headers)
    assert check.status_code == 200
    prepare = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/prepara", headers=headers)
    assert prepare.status_code == 200
    deposito_id = prepare.get_json()["session"]["id"]
    send = client.post(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/invia", json={"deposito_id": deposito_id}, headers=headers)
    assert send.status_code == 409
    assert send.get_json()["mock_fallback"] is False
    receipt = client.post(
        f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/{deposito_id}/importa-ricevuta",
        json={"receipt_type": "ESITO_CANCELLERIA", "status": "accettato", "positive": True, "message": "Esito cancelleria positivo"},
        headers=headers,
    )
    assert receipt.status_code == 200
    assert receipt.get_json()["session"]["status"] == "ACQUISITO"
    timeline = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/{deposito_id}/timeline", headers=headers)
    assert timeline.status_code == 200
    assert timeline.get_json()["timeline"]
    evidence = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}/depositi/{deposito_id}/evidence-pack", headers=headers)
    assert evidence.status_code == 200
    assert evidence.mimetype == "application/zip"
