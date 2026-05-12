from __future__ import annotations

from pathlib import Path

from pct.notifiche_legali import (
    LEGAL_NOTIFICATION_SUBJECT,
    build_client_communication,
    validate_deposit_notification_proof,
    validate_legal_notification,
)
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app


def _app(tmp_path: Path):
    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    app.config["API_KEY"] = "react-test-key"
    return app


def _legal_payload() -> dict[str, object]:
    return {
        "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT,
        "avvocato_nome": "Mario Rossi",
        "avvocato_cf": "RSSMRA80A01H501U",
        "avvocato_foro": "Roma",
        "studio_indirizzo": "Via Roma 1",
        "studio_citta": "Roma",
        "mittente_pec": "studio@example.pec.it",
        "fonte_pec_mittente": "ReGIndE",
        "mittente_pec_pubblico_elenco": True,
        "assistito_nome": "Cliente S.r.l.",
        "assistito_cf": "01234567890",
        "ruolo_destinatario": "controparte",
        "destinatario_nome": "Controparte S.p.A.",
        "destinatario_pec": "controparte@example.pec.it",
        "fonte_pec_destinatario": "registro_imprese",
        "data_verifica_pec": "2026-05-12T10:30",
        "procedimento_pendente": True,
        "ufficio_giudiziario": "Tribunale di Roma",
        "sezione": "III",
        "numero_rg": "1234",
        "anno_rg": "2026",
        "ricevuta_completa": True,
        "relata_firmata": True,
        "approvazione_avvocato": True,
        "documenti": [
            {
                "nome_file": "ricorso.pdf",
                "descrizione": "Ricorso notificato",
                "origine": "copia_fascicolo",
            }
        ],
        "attestazione_conformita": "che il file ricorso.pdf e' copia informatica conforme al fascicolo informatico.",
    }


def test_notifica_l53_genera_relata_solo_con_controlli_completi():
    result = validate_legal_notification(_legal_payload())

    assert result.ok is True
    assert result.subject == LEGAL_NOTIFICATION_SUBJECT
    assert "RELAZIONE DI NOTIFICAZIONE" in result.relata_text
    assert "ricorso.pdf - Ricorso notificato" in result.relata_text
    assert "Registro Imprese" in result.relata_text
    assert "R.G. n. 1234/2026" in result.relata_text


def test_notifica_l53_blocca_cliente_e_attestazione_mancante():
    payload = _legal_payload()
    payload["ruolo_destinatario"] = "cliente"
    payload["documenti"] = [{"nome_file": "scansione.pdf", "descrizione": "Provvedimento", "origine": "scansione"}]
    payload["attestazione_conformita"] = ""

    result = validate_legal_notification(payload)

    assert result.ok is False
    assert any("Comunicazione al cliente" in item for item in result.blockers)
    assert any("serve attestazione" in item for item in result.blockers)
    assert result.relata_text == ""


def test_comunicazione_cliente_non_usa_relata_o_oggetto_l53():
    blocked = build_client_communication({
        "cliente_nome": "Cliente",
        "oggetto": LEGAL_NOTIFICATION_SUBJECT,
        "genera_relata": True,
    })
    ok = build_client_communication({
        "cliente_nome": "Cliente",
        "ufficio_giudiziario": "Tribunale di Roma",
        "numero_rg": "1234",
        "anno_rg": "2026",
        "provvedimento_descrizione": "Sentenza depositata",
    })

    assert blocked.ok is False
    assert any("non deve usare l'oggetto" in item for item in blocked.blockers)
    assert any("non genera una relata" in item for item in blocked.blockers)
    assert ok.ok is True
    assert ok.relata_text == ""
    assert ok.subject == "Comunicazione provvedimento - Tribunale di Roma - R.G. 1234/2026"


def test_prova_deposito_richiede_rac_rdac_originali():
    blocked = validate_deposit_notification_proof({
        "atto_notificato": "ricorso.pdf",
        "relata_firmata": "relata.pdf.p7m",
        "destinatario_nome": "Controparte",
        "rac_file": "accettazione.pdf",
        "rdac_file": "consegna.eml",
    })
    ok = validate_deposit_notification_proof({
        "atto_notificato": "ricorso.pdf",
        "relata_firmata": "relata.pdf.p7m",
        "destinatario_nome": "Controparte",
        "rac_file": "accettazione.eml",
        "rdac_file": "consegna.eml",
        "dati_atto_ricevute": "RAC e RdAC indicizzate",
    })

    assert blocked.ok is False
    assert any("originale digitale .eml o .msg" in item for item in blocked.blockers)
    assert ok.ok is True


def test_api_react_notifiche_legali_espone_workflow_separati(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    headers = {"X-API-Key": "react-test-key"}

    payload_response = client.get("/api/v1/ui/notifiche-legali", headers=headers)
    invalid_response = client.post(
        "/api/v1/ui/notifiche-legali/notifica",
        json={"ruolo_destinatario": "cliente", "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT},
        headers=headers,
    )
    valid_response = client.post(
        "/api/v1/ui/notifiche-legali/notifica",
        json=_legal_payload(),
        headers=headers,
    )
    client_response = client.post(
        "/api/v1/ui/notifiche-legali/comunicazione-cliente",
        json={"cliente_nome": "Cliente", "provvedimento_descrizione": "Provvedimento depositato"},
        headers=headers,
    )

    payload = payload_response.get_json()
    invalid_payload = invalid_response.get_json()
    valid_payload = valid_response.get_json()
    client_payload = client_response.get_json()

    assert payload_response.status_code == 200
    assert payload["mandatorySubject"] == LEGAL_NOTIFICATION_SUBJECT
    assert payload["contracts"]["clientCommunicationWithoutRelata"] is True
    assert invalid_response.status_code == 400
    assert invalid_payload["ok"] is False
    assert valid_response.status_code == 200
    assert valid_payload["ok"] is True
    assert "RELAZIONE DI NOTIFICAZIONE" in valid_payload["relataText"]
    assert client_response.status_code == 200
    assert client_payload["ok"] is True
    assert client_payload["relataText"] == ""
