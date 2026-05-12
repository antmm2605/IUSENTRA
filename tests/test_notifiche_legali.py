from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pct.notifiche_legali import (
    LEGAL_NOTIFICATION_SUBJECT,
    build_client_communication,
    validate_deposit_notification_proof,
    validate_legal_notification,
)
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services.react_notifiche_legali_bridge import build_react_notifiche_legali_payload


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
    assert result.relata_text == ""


def test_notifica_l53_compila_attestazione_da_origine_documento():
    payload = _legal_payload()
    payload["documenti"] = [{"nome_file": "scansione.pdf", "descrizione": "Provvedimento", "origine": "scansione"}]
    payload["attestazione_conformita"] = ""

    result = validate_legal_notification(payload)

    assert result.ok is True
    assert "copia informatica per immagine conforme all'originale analogico" in result.relata_text


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


def test_payload_react_notifiche_legali_precompila_da_dati_iusentra():
    cliente = SimpleNamespace(
        id="cliente-1",
        nome_completo="Cliente S.r.l.",
        identificativo_fiscale="01234567890",
        recapiti=SimpleNamespace(pec="cliente@example.pec.it"),
    )
    documento = SimpleNamespace(
        id="doc-1",
        nome_originale="ordinanza_rg_1234_2026.pdf",
        nome_portale="",
        nome="ordinanza.pdf",
        percorso="ordinanza.pdf",
        tipo_atto_portale="ordinanza emessa dal Tribunale di Roma",
        classificazione_portale="",
        note="",
        fonte_documento="PORTALE_TELEMATICO",
        hash_sha256="abc123",
        data_documento="2026-05-10",
        data_deposito_portale="",
        id_documento_portale="pst-doc-1",
        tags=[],
    )
    fascicolo = SimpleNamespace(
        id="fascicolo-1",
        numero="2026/001",
        titolo="Cliente S.r.l. / Alfa S.p.A.",
        id_cliente="cliente-1",
        nome_cliente="Cliente S.r.l.",
        controparte="Alfa S.p.A.",
        cf_controparte="09876543210",
        tribunale="Tribunale di Roma",
        sezione="III Civile",
        numero_rg="1234",
        anno_rg=2026,
        giudice="Dott. Verdi",
        tipo_procedimento="civile ordinario",
        documenti=[documento],
    )
    soggetto = SimpleNamespace(
        id="soggetto-1",
        tipo=SimpleNamespace(value="PERSONA_GIURIDICA"),
        nome_completo="Alfa S.p.A.",
        ragione_sociale="Alfa S.p.A.",
        identificativo="09876543210",
        recapiti=SimpleNamespace(pec="alfa@example.pec.it"),
        qualifica="",
    )
    parte = SimpleNamespace(ruolo=SimpleNamespace(value="CONTROPARTE"), note="")

    payload = build_react_notifiche_legali_payload(
        get_clienti=lambda: SimpleNamespace(tutti=lambda: [cliente]),
        get_fascicoli=lambda: SimpleNamespace(tutti=lambda archiviati=False: [fascicolo]),
        get_soggetti=lambda: SimpleNamespace(
            tutti=lambda: [soggetto],
            parti_fascicolo=lambda id_fascicolo: [(parte, soggetto)],
        ),
    )

    pratica = payload["precompilazione"]["pratiche"][0]
    destinatario = pratica["destinatari"][0]
    documento_payload = pratica["documenti"][0]

    assert pratica["assistitoNome"] == "Cliente S.r.l."
    assert pratica["procedimento"]["ufficio"] == "Tribunale di Roma"
    assert destinatario["pec"] == "alfa@example.pec.it"
    assert destinatario["fontePecSuggerita"] == "ini_pec"
    assert documento_payload["origine"] == "copia_fascicolo_informatico"
    assert documento_payload["necessitaAttestazione"] is True
