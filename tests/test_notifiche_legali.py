from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pct.notifiche_legali import (
    LEGAL_NOTIFICATION_SUBJECT,
    build_client_communication,
    client_communication_templates_version,
    list_client_communication_templates,
    list_notification_templates,
    preview_legal_relata,
    template_catalog_version,
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
        "operazione": "notifica_pec_l53",
        "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT,
        "avvocato_nome": "Mario Rossi",
        "avvocato_cf": "RSSMRA80A01H501U",
        "avvocato_foro": "Roma",
        "studio_indirizzo": "Via Roma 1",
        "studio_citta": "Roma",
        "mittente_pec": "studio@example.pec.it",
        "fonte_pec_mittente": "ReGIndE",
        "mittente_pec_pubblico_elenco": True,
        "mittente_avvocato_abilitato": True,
        "mittente_pec_validata": True,
        "assistito_nome": "Cliente S.r.l.",
        "assistito_cf": "01234567890",
        "ruolo_destinatario": "controparte",
        "destinatario_nome": "Controparte S.p.A.",
        "destinatario_pec": "controparte@example.pec.it",
        "fonte_pec_destinatario": "registro_imprese",
        "destinatario_pec_pubblico_elenco": True,
        "data_verifica_pec": "2026-05-12T10:30",
        "procedimento_pendente": True,
        "ufficio_giudiziario": "Tribunale di Roma",
        "sezione": "III",
        "numero_rg": "1234",
        "anno_rg": "2026",
        "ricevuta_completa": True,
        "relata_firmata": True,
        "relata_documento_separato": True,
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


def test_notifica_l53_blocca_attestazione_mancante_da_origine_documento():
    payload = _legal_payload()
    payload["documenti"] = [{"nome_file": "scansione.pdf", "descrizione": "Provvedimento", "origine": "scansione"}]
    payload["attestazione_conformita"] = ""

    result = validate_legal_notification(payload)

    assert result.ok is False
    assert any("ATTESTAZIONE_REQUIRED" in item for item in result.blockers)
    assert result.relata_text == ""


def test_notifica_l53_documento_nativo_digitale_non_richiede_attestazione():
    payload = _legal_payload()
    payload["documenti"] = [{"nome_file": "atto.pdf", "descrizione": "Atto nativo", "origine": "nativo_digitale"}]
    payload["attestazione_conformita"] = ""

    result = validate_legal_notification(payload)

    assert result.ok is True
    assert "ATTESTAZIONE DI CONFORMITA" not in result.relata_text


def test_notifica_l53_riporta_piu_documenti_nell_elenco_allegati():
    payload = _legal_payload()
    payload["documenti"] = [
        {"nome_file": "ricorso.pdf", "descrizione": "Ricorso", "origine": "nativo_digitale"},
        {"nome_file": "procura.pdf", "descrizione": "Procura alle liti", "origine": "firmato_digitalmente"},
        {"nome_file": "provvedimento.pdf", "descrizione": "Provvedimento", "origine": "copia_fascicolo_informatico"},
    ]
    payload["attestazione_conformita"] = "Attesto la conformita' del provvedimento estratto dal fascicolo informatico."

    result = validate_legal_notification(payload)

    assert result.ok is True
    assert "1. ricorso.pdf - Ricorso" in result.relata_text
    assert "2. procura.pdf - Procura alle liti" in result.relata_text
    assert "3. provvedimento.pdf - Provvedimento" in result.relata_text


def test_notifica_l53_modello_personalizzato_usa_campi_iusentra_e_note_avvocato():
    payload = _legal_payload()
    payload["template_id"] = "relata_personalizzata_prova"
    payload["template_personalizzato"] = {
        "id": "relata_personalizzata_prova",
        "label": "Relata su misura",
        "custom_body": "\n".join([
            "RELAZIONE PERSONALIZZATA",
            "Avv. {{ avvocato.full_name }} per {{ cliente.nome_denominazione }}",
            "Destinatario: {{ destinatario.nome_denominazione }} - {{ destinatario.pec }}",
            "{{ documenti_righe }}",
            "{{ blocco_procedimento }}",
            "{{ attestazioni_testo }}",
            "{{ notifica.luogo }}, {{ notifica.data }}",
        ]),
        "requires_proceeding": True,
    }
    payload["note_integrative_relata"] = "Precisazione finale aggiunta dall'avvocato."

    result = validate_legal_notification(payload)

    assert result.ok is True
    assert "RELAZIONE PERSONALIZZATA" in result.relata_text
    assert "Avv. Mario Rossi per Cliente S.r.l." in result.relata_text
    assert "1. ricorso.pdf - Ricorso notificato" in result.relata_text
    assert "R.G. n. 1234/2026" in result.relata_text
    assert "INTEGRAZIONE DELL'AVVOCATO" in result.relata_text
    assert "Precisazione finale aggiunta dall'avvocato." in result.relata_text


def test_modello_personalizzato_blocca_token_sconosciuto():
    payload = _legal_payload()
    payload["template_id"] = "relata_personalizzata_non_valida"
    payload["template_personalizzato"] = {
        "id": "relata_personalizzata_non_valida",
        "label": "Relata non valida",
        "custom_body": "Avv. {{ avvocato.full_name }} - {{ segreto.interno }}",
    }

    result = validate_legal_notification(payload)

    assert result.ok is False
    assert any("Campo automatico non consentito" in item for item in result.blockers)
    assert result.relata_text == ""


def test_modello_personalizzato_blocca_blocchi_jinja():
    payload = _legal_payload()
    payload["template_id"] = "relata_personalizzata_if"
    payload["template_personalizzato"] = {
        "id": "relata_personalizzata_if",
        "label": "Relata con istruzioni",
        "custom_body": "{% if avvocato %}Avv. {{ avvocato.full_name }}{% endif %}",
    }

    result = validate_legal_notification(payload)

    assert result.ok is False
    assert any("istruzioni Jinja" in item for item in result.blockers)


def test_modello_personalizzato_blocca_accesso_pericoloso():
    payload = _legal_payload()
    payload["template_id"] = "relata_personalizzata_globals"
    payload["template_personalizzato"] = {
        "id": "relata_personalizzata_globals",
        "label": "Relata pericolosa",
        "custom_body": "Accesso {{ cycler.__init__.__globals__ }}",
    }

    result = validate_legal_notification(payload)

    assert result.ok is False
    assert any("accesso riservato" in item or "non consentito" in item for item in result.blockers)


def test_modelli_standard_restano_renderizzabili():
    payload = _legal_payload()
    payload["template_id"] = "relata_pec_base_l53"

    result = validate_legal_notification(payload)

    assert result.ok is True
    assert "RELAZIONE DI NOTIFICAZIONE" in result.relata_text


def test_anteprima_relata_compilata_con_placeholder():
    full = preview_legal_relata(_legal_payload())
    missing_payload = _legal_payload()
    missing_payload["destinatario_pec"] = ""
    missing = preview_legal_relata(missing_payload)

    assert full["ok"] is True
    assert "Cliente S.r.l." in full["previewText"]
    assert missing["ok"] is True
    assert "[dato mancante: PEC destinatario]" in missing["previewText"]
    assert "PEC destinatario" in missing["missingFields"]


def test_anteprima_modelli_standard_catalogo_non_bloccata():
    for template in list_notification_templates(kind="relata"):
        payload = _legal_payload()
        payload["template_id"] = template["id"]
        preview = preview_legal_relata(payload)
        assert preview["ok"] is True, template["id"]


def test_comunicazione_cliente_non_usa_relata_o_oggetto_l53():
    blocked = build_client_communication({
        "operazione": "comunicazione_cliente_non_notifica",
        "cliente_nome": "Cliente",
        "oggetto": LEGAL_NOTIFICATION_SUBJECT,
        "genera_relata": True,
    })
    ok = build_client_communication({
        "operazione": "comunicazione_cliente_non_notifica",
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
    assert ok.subject == "Aggiornamento pratica"
    assert ok.template_version == client_communication_templates_version()


def test_comunicazione_cliente_usa_modelli_separati():
    templates = list_client_communication_templates()
    result = build_client_communication({
        "operazione": "comunicazione_cliente_non_notifica",
        "template_id": "richiesta_documenti",
        "cliente_nome": "Cliente",
        "pratica_codice": "2026/001",
        "provvedimento_descrizione": "Documenti reddituali",
    })

    assert {item["id"] for item in templates} >= {"aggiornamento_pratica", "esito_notifica", "richiesta_documenti"}
    assert result.ok is True
    assert result.relata_text == ""
    assert result.template_id == "richiesta_documenti"
    assert "Richiesta documenti" in result.subject
    assert result.template_version != template_catalog_version()


def test_comunicazione_cliente_blocca_catalogo_relata_l53():
    result = build_client_communication({
        "operazione": "comunicazione_cliente_non_notifica",
        "template_id": "relata_pec_base_l53",
        "cliente_nome": "Cliente",
        "provvedimento_descrizione": "Provvedimento",
    })

    assert result.ok is False
    assert any("modello comunicazione cliente" in item for item in result.blockers)


def test_prova_deposito_richiede_rac_rdac_originali():
    blocked = validate_deposit_notification_proof({
        "atto_notificato": "ricorso.pdf",
        "atto_sha256": "a" * 64,
        "relata_firmata": "relata.pdf.p7m",
        "relata_sha256": "b" * 64,
        "pec_inviata": "pec_inviata.eml",
        "pec_inviata_sha256": "c" * 64,
        "destinatario_nome": "Controparte",
        "rac_file": "accettazione.pdf",
        "rac_sha256": "d" * 64,
        "rdac_file": "consegna.eml",
        "rdac_sha256": "e" * 64,
        "ricevuta_completa": True,
    })
    ok = validate_deposit_notification_proof({
        "atto_notificato": "ricorso.pdf",
        "atto_sha256": "a" * 64,
        "relata_firmata": "relata.pdf.p7m",
        "relata_sha256": "b" * 64,
        "pec_inviata": "pec_inviata.eml",
        "pec_inviata_sha256": "c" * 64,
        "destinatario_nome": "Controparte",
        "rac_file": "accettazione.eml",
        "rac_sha256": "d" * 64,
        "rdac_file": "consegna.eml",
        "rdac_sha256": "e" * 64,
        "ricevuta_completa": True,
        "dati_atto_ricevute": "RAC e RdAC indicizzate",
    })

    assert blocked.ok is False
    assert any("originale digitale .eml o .msg" in item for item in blocked.blockers)
    assert ok.ok is True


def test_prova_deposito_accetta_piu_atti_notificati_con_hash():
    result = validate_deposit_notification_proof({
        "atti_notificati": [
            {"nome_file": "pst:JPW_SIGP:2182464 - ricorso.pdf", "hash_sha256": "a" * 64},
            {"nome_file": "procura.pdf", "hash_sha256": "f" * 64},
        ],
        "relata_firmata": "relata_notifica.pdf.p7m",
        "relata_sha256": "b" * 64,
        "pec_inviata": "pec_inviata.eml",
        "pec_inviata_sha256": "c" * 64,
        "destinatario_nome": "Controparte",
        "rac_file": "accettazione.eml",
        "rac_sha256": "d" * 64,
        "rdac_file": "consegna.eml",
        "rdac_sha256": "e" * 64,
        "ricevuta_completa": True,
        "dati_atto_ricevute": "RAC e RdAC indicizzate",
    })

    assert result.ok is True
    items = result.output_plan["evidencePack"]["items"]
    assert any(item["kind"] == "atto" and "pst:JPW_SIGP:2182464" in item["filename"] for item in items)
    assert any(item["kind"] == "allegato_2" and item["filename"] == "procura.pdf" for item in items)


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
        json={"operazione": "comunicazione_cliente_non_notifica", "cliente_nome": "Cliente", "provvedimento_descrizione": "Provvedimento depositato"},
        headers=headers,
    )

    payload = payload_response.get_json()
    invalid_payload = invalid_response.get_json()
    valid_payload = valid_response.get_json()
    client_payload = client_response.get_json()

    assert payload_response.status_code == 200
    assert payload["mandatorySubject"] == LEGAL_NOTIFICATION_SUBJECT
    assert payload["contracts"]["clientCommunicationWithoutRelata"] is True
    assert payload["modelliRelata"][0]["previewText"]
    assert any(field["token"] == "{{ documenti_righe }}" for field in payload["campiDisponibili"])
    assert invalid_response.status_code == 400
    assert invalid_payload["ok"] is False
    assert valid_response.status_code == 200
    assert valid_payload["ok"] is True
    assert "RELAZIONE DI NOTIFICAZIONE" in valid_payload["relataText"]
    assert client_response.status_code == 200
    assert client_payload["ok"] is True
    assert client_payload["relataText"] == ""


def test_api_react_notifiche_legali_salva_e_usa_modello_relata_personalizzato(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    headers = {"X-API-Key": "react-test-key"}
    body = "\n".join([
        "RELAZIONE DI NOTIFICAZIONE PERSONALIZZATA",
        "Avv. {{ avvocato.full_name }} notifica per {{ cliente.nome_denominazione }}.",
        "Destinatario {{ destinatario.nome_denominazione }} presso {{ destinatario.pec }}.",
        "{{ documenti_righe }}",
        "{{ blocco_procedimento }}",
        "{{ notifica.luogo }}, {{ notifica.data }}",
    ])

    save_response = client.post(
        "/api/v1/ui/notifiche-legali/modelli-relata",
        json={"label": "Relata prova studio", "description": "Uso interno studio", "body": body, "requiresProceeding": True},
        headers=headers,
    )
    saved = save_response.get_json()
    catalog = client.get("/api/v1/ui/notifiche-legali", headers=headers).get_json()
    payload = _legal_payload()
    payload["template_id"] = saved["template"]["value"]
    preview_response = client.post("/api/v1/ui/notifiche-legali/notifica", json=payload, headers=headers)
    preview = preview_response.get_json()

    assert save_response.status_code == 200
    assert saved["ok"] is True
    assert saved["template"]["custom"] is True
    assert any(item["value"] == saved["template"]["value"] and item["custom"] for item in catalog["modelliRelata"])
    assert preview_response.status_code == 200
    assert preview["ok"] is True
    assert "RELAZIONE DI NOTIFICAZIONE PERSONALIZZATA" in preview["relataText"]
    assert "Cliente S.r.l." in preview["relataText"]


def test_api_react_notifiche_legali_anteprima_relata_e_token_sicuri(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    headers = {"X-API-Key": "react-test-key"}
    payload = _legal_payload()
    payload["destinatario_pec"] = ""
    preview_response = client.post("/api/v1/ui/notifiche-legali/anteprima-relata", json=payload, headers=headers)
    preview = preview_response.get_json()
    dangerous = _legal_payload()
    dangerous["template_id"] = "relata_personalizzata_pericolosa"
    dangerous["template_personalizzato"] = {
        "id": "relata_personalizzata_pericolosa",
        "label": "Pericolosa",
        "custom_body": "Accesso {{ cycler.__init__.__globals__ }}",
    }
    dangerous_response = client.post("/api/v1/ui/notifiche-legali/anteprima-relata", json=dangerous, headers=headers)
    dangerous_payload = dangerous_response.get_json()

    assert preview_response.status_code == 200
    assert preview["ok"] is True
    assert "[dato mancante: PEC destinatario]" in preview["previewText"]
    assert dangerous_response.status_code == 400
    assert dangerous_payload["ok"] is False
    assert dangerous_payload["blockers"]


def test_api_react_notifiche_legali_salva_bozza_relata_e_non_modello(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    headers = {"X-API-Key": "react-test-key"}
    draft_response = client.post(
        "/api/v1/ui/notifiche-legali/bozze-relata",
        json={"practiceId": "fascicolo-1", "templateId": "relata_pec_base_l53", "relataText": "Bozza relata modificata per questa notifica."},
        headers=headers,
    )
    empty_response = client.post(
        "/api/v1/ui/notifiche-legali/bozze-relata",
        json={"templateId": "relata_pec_base_l53", "relataText": ""},
        headers=headers,
    )
    catalog = client.get("/api/v1/ui/notifiche-legali", headers=headers).get_json()
    draft_payload = draft_response.get_json()

    assert draft_response.status_code == 200
    assert draft_payload["ok"] is True
    assert draft_payload["draftId"]
    assert empty_response.status_code == 400
    assert not any("Bozza relata modificata" in item["previewText"] for item in catalog["modelliRelata"])
    assert (tmp_path / "notifiche" / "bozze_relata.json").exists()


def test_bozza_relata_override_usata_ma_controlli_restano_attivi():
    payload = _legal_payload()
    payload["relata_override_text"] = "TESTO MANUALE DELLA RELATA"
    ok = validate_legal_notification(payload)
    blocked = _legal_payload()
    blocked["relata_override_text"] = "TESTO MANUALE DELLA RELATA"
    blocked["destinatario_pec"] = ""

    blocked_result = validate_legal_notification(blocked)

    assert ok.ok is True
    assert ok.relata_text == "TESTO MANUALE DELLA RELATA\n"
    assert blocked_result.ok is False
    assert any("PEC del destinatario" in item for item in blocked_result.blockers)


def test_api_react_notifiche_legali_robustezza_json_e_limiti(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    headers = {"X-API-Key": "react-test-key"}
    no_json = client.post("/api/v1/ui/notifiche-legali/notifica", data="non json", headers=headers)
    malformed = client.post(
        "/api/v1/ui/notifiche-legali/notifica",
        data="{",
        content_type="application/json",
        headers=headers,
    )
    label_empty = client.post(
        "/api/v1/ui/notifiche-legali/modelli-relata",
        json={"label": "", "body": "RELAZIONE\n{{ avvocato.full_name }}\n" * 10},
        headers=headers,
    )
    too_long = client.post(
        "/api/v1/ui/notifiche-legali/modelli-relata",
        json={"label": "Relata", "body": "x" * 25000},
        headers=headers,
    )
    forbidden = client.post(
        "/api/v1/ui/notifiche-legali/modelli-relata",
        json={"label": "Relata", "body": ("RELAZIONE\n{{ token_non_permesso }}\n" * 10)},
        headers=headers,
    )

    assert no_json.status_code == 400
    assert no_json.get_json()["ok"] is False
    assert malformed.status_code == 400
    assert malformed.get_json()["ok"] is False
    assert label_empty.status_code == 400
    assert too_long.status_code == 400
    assert forbidden.status_code == 400
    assert forbidden.get_json()["blockers"]


def test_api_react_notifiche_legali_modelli_cliente_separati(tmp_path: Path):
    app = _app(tmp_path)
    client = app.test_client()
    headers = {"X-API-Key": "react-test-key"}
    payload = client.get("/api/v1/ui/notifiche-legali", headers=headers).get_json()
    communication_response = client.post(
        "/api/v1/ui/notifiche-legali/comunicazione-cliente",
        json={
            "operazione": "comunicazione_cliente_non_notifica",
            "template_id": "invio_provvedimento",
            "cliente_nome": "Cliente",
            "ufficio_giudiziario": "Tribunale di Roma",
            "numero_rg": "1234",
            "anno_rg": "2026",
            "provvedimento_descrizione": "Ordinanza depositata",
        },
        headers=headers,
    )
    blocked_response = client.post(
        "/api/v1/ui/notifiche-legali/comunicazione-cliente",
        json={"template_id": "relata_pec_base_l53", "cliente_nome": "Cliente", "provvedimento_descrizione": "Atto"},
        headers=headers,
    )
    communication = communication_response.get_json()

    assert payload["clientCommunicationTemplateVersion"] != payload["templateCatalogVersion"]
    assert "2026.05.12" not in payload["clientCommunicationTemplateVersion"]
    assert payload["modelliComunicazioneCliente"]
    assert {item["value"] for item in payload["modelliComunicazioneCliente"]}.isdisjoint({item["value"] for item in payload["modelliRelata"]})
    assert communication_response.status_code == 200
    assert communication["ok"] is True
    assert communication["relataText"] == ""
    assert communication["templateId"] == "invio_provvedimento"
    assert blocked_response.status_code == 400
    assert blocked_response.get_json()["ok"] is False


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
    assert documento_payload["riferimentoPortale"] == "pst-doc-1"
    assert documento_payload["necessitaAttestazione"] is True
