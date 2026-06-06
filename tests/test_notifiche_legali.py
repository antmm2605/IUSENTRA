from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pct.notifiche_legali import (
    LEGAL_NOTIFICATION_SUBJECT,
    available_template_fields,
    build_attestazione_conformita_payload,
    build_client_communication,
    generate_attestazione_conformita_docx,
    build_notification_attachment_manifest,
    build_notification_normative_checks,
    build_notification_send_plan,
    build_notification_signature_plan,
    build_notification_timing_plan,
    client_communication_templates_version,
    legal_notification_automation_payload,
    list_client_communication_templates,
    list_notification_templates,
    get_notification_template,
    notification_directive_matrix,
    office_notification_evidence_from_pec,
    preview_legal_relata,
    prepare_pst_failed_notification_workflow,
    released_office_documents_from_pec,
    template_catalog_version,
    validate_deposit_notification_proof,
    validate_legal_notification,
)
from tests.test_web_bootstrap import _cfg_web, _write_studio_config
from web.app import create_app
from web.services import react_notifiche_legali_bridge
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
        "attestazione_conformita": "che il file ricorso.pdf è copia informatica conforme al fascicolo informatico.",
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
    payload["attestazione_conformita"] = "Attesto la conformità del provvedimento estratto dal fascicolo informatico."

    result = validate_legal_notification(payload)

    assert result.ok is True
    assert "1. ricorso.pdf - Ricorso" in result.relata_text
    assert "2. procura.pdf - Procura alle liti" in result.relata_text
    assert "3. provvedimento.pdf - Provvedimento" in result.relata_text


def test_attestazione_conformita_autocompila_fascicolo_cliente_e_documenti():
    payload = _legal_payload()
    payload["documenti"] = [
        {
            "nome_file": "ricorso.pdf",
            "descrizione": "Ricorso per il recupero delle annualità Carta del docente",
            "origine": "copia_fascicolo_informatico",
            "hash_sha256": "a" * 64,
        },
        {
            "nome_file": "procura.pdf",
            "descrizione": "Procura alle liti",
            "origine": "firmato_digitalmente",
            "hash_sha256": "b" * 64,
        },
        {
            "nome_file": "decreto_fissazione_udienza.pdf",
            "descrizione": "Decreto fissazione udienza",
            "origine": "comunicazione_cancelleria",
            "data_comunicazione_cancelleria": "2026-05-18",
            "hash_sha256": "c" * 64,
        },
    ]

    model = build_attestazione_conformita_payload(payload)

    assert model["ok"] is True
    assert model["missing_fields"] == []
    assert "ATTESTAZIONE DI CONFORMITÀ" in model["text"]
    assert "Avv. Mario Rossi" in model["text"]
    assert "R.G. n. 1234/2026" in model["text"]
    assert "Ricorso per il recupero delle annualità Carta del docente" in model["text"]
    assert "Procura alle liti" in model["text"]
    assert len(model["documenti"]) == 3
    assert "comunicazione_cancelleria" in {item["origine"] for item in model["documenti"]}
    assert "art. 196-undecies" in " ".join(model["normativa"])


def test_attestazione_conformita_docx_generato_contiene_placeholder_compilati(tmp_path):
    output = tmp_path / "attestazione.docx"

    result = generate_attestazione_conformita_docx(_legal_payload(), output)

    assert result["ok"] is True
    assert output.exists()

    from docx import Document

    text = "\n".join(paragraph.text for paragraph in Document(output).paragraphs)
    assert "ATTESTAZIONE DI CONFORMITÀ" in text
    assert "Avv. Mario Rossi" in text
    assert "ricorso.pdf" in text


def test_attestazione_sentenza_autocompila_modello_word_e_firma():
    payload = _legal_payload()
    payload.update({
        "caso_notifica": "sentenza_termine_breve",
        "avvocato_nome": "Giuseppe",
        "avvocato_cognome": "Montagnese",
        "avvocato_cf": "MNTGPP94L01G791A",
        "avvocato_foro": "Palmi",
        "ufficio_giudiziario": "Tribunale di Palmi",
        "sezione": "Lavoro",
        "numero_rg": "704",
        "anno_rg": "2026",
        "provvedimento_tipo": "Sentenza",
        "provvedimento_data_deposito": "2026-06-05",
        "documenti": [
            {
                "nome_file": "sentenza.pdf",
                "descrizione": "Sentenza",
                "origine": "copia_fascicolo_informatico",
                "data_documento": "2026-06-05",
            }
        ],
        "attestazione_multipla": True,
    })

    model = build_attestazione_conformita_payload(payload)
    result = validate_legal_notification(payload)

    assert model["ok"] is True
    assert "Il sottoscritto Avv. Giuseppe Montagnese C. F. MNTGPP94L01G791A, del Foro di Palmi," in model["text"]
    assert "Sentenza, emessa dal Tribunale di Palmi Sez. Lavoro in data 05/06/2026" in model["text"]
    assert "R.G. n. 704/2026 dal quale è estratta." in model["text"]
    assert "Avv. Giuseppe Montagnese" in model["text"]
    assert "Firmato digitalmente" in model["text"]
    assert model["campi_database"]["avvocato"]["firma_in_calce"] == "Avv. Giuseppe Montagnese"
    assert model["campi_database"]["avvocato"]["firma_digitale_dicitura"] == "Firmato digitalmente"
    assert result.ok is True
    assert result.template_id == "relata_sentenza_attestazione_conformita"
    assert "ATTESTAZIONE DI CONFORMITÀ" in result.relata_text
    assert "Sentenza, emessa dal Tribunale di Palmi Sez. Lavoro in data 05/06/2026" in result.relata_text


def test_notifica_l53_audit_automatico_include_normativa_e_piu_allegati():
    payload = _legal_payload()
    payload["documenti"] = [
        {"nome_file": "ricorso.pdf", "descrizione": "Ricorso", "origine": "nativo_digitale", "hash_sha256": "a" * 64},
        {"nome_file": "procura.pdf", "descrizione": "Procura alle liti", "origine": "firmato_digitalmente", "hash_sha256": "b" * 64},
        {"nome_file": "provvedimento.pdf", "descrizione": "Provvedimento", "origine": "copia_fascicolo_informatico", "hash_sha256": "c" * 64},
    ]
    payload["attestazione_multipla"] = True

    result = validate_legal_notification(payload)

    assert result.ok is True
    assert {item["id"] for item in legal_notification_automation_payload()["notifica"]} >= {"precompilazione", "pubblici_elenchi", "allegati"}
    assert result.output_plan["auditTrail"]["documentsCount"] == 3
    assert result.output_plan["workflowSteps"][0]["source"].startswith("L. 53/1994")
    assert any(item["id"] == "allegati" and item["status"] == "superato" for item in result.output_plan["normativeChecks"])
    assert any(item["id"] == "attestazioni" and item["status"] == "superato" for item in result.output_plan["normativeChecks"])


def test_notifica_l53_blocca_documento_ufficio_rilasciato_non_acquisito():
    payload = _legal_payload()
    payload["documento_ufficio_rilasciato"] = True
    payload["acquisizione_portale_richiesta"] = True
    payload["documenti"] = []

    result = validate_legal_notification(payload)
    checks = build_notification_normative_checks(payload)

    assert result.ok is False
    assert any("DOCUMENTO_UFFICIO_ACQUISIZIONE_REQUIRED" in item for item in result.blockers)
    assert any(item["id"] == "documento_ufficio_acquisito" and item["status"] == "bloccante" for item in checks)


def test_notifica_l53_documento_ufficio_acquisito_dal_portale_supera_controllo():
    payload = _legal_payload()
    payload["documento_ufficio_rilasciato"] = True
    payload["acquisizione_portale_richiesta"] = True
    payload["pec_ufficio_eml_file"] = "pec-cancelleria.eml"
    payload["pec_ufficio_eml_sha256"] = "d" * 64
    payload["documenti"] = [
        {
            "nome_file": "ordinanza_da_notificare.pdf",
            "descrizione": "Ordinanza rilasciata dall'ufficio",
            "origine": "copia_fascicolo_informatico",
            "fonte_documento": "PORTALE_TELEMATICO",
            "servizio_portale": "PST",
            "riferimento_portale": "PST-REL-2026-0001",
            "documento_ufficio": True,
            "acquisito_da_portale": True,
            "notifica_richiesta": True,
            "data_rilascio_portale": "2026-05-23",
        }
    ]
    payload["attestazione_multipla"] = True

    result = validate_legal_notification(payload)

    assert result.ok is True
    assert result.output_plan["auditTrail"]["officeDocumentAcquisition"]["acquired"] is True
    assert any(item["id"] == "documento_ufficio_acquisito" and item["status"] == "superato" for item in result.output_plan["normativeChecks"])


def test_rilascio_documento_ufficio_parte_da_pec_cancelleria_e_non_da_metadati_portale():
    fascicolo = SimpleNamespace(
        id="fasc-portal",
        numero="FASC-1",
        titolo="Rossi c/ Bianchi",
        tribunale="Tribunale di Roma",
        numero_rg="1234",
        anno_rg=2026,
        documenti=[],
        depositi_pct=[
            SimpleNamespace(
                id="dep-1",
                id_deposito_esterno="PST-REL-2026-0001",
                fonte="PST",
                servizio_portale="ConsultazioneFascicolo",
                tipo_atto="Ordinanza da notificare",
                data_deposito="2026-05-23",
                mittente="Tribunale di Roma",
                documenti_portale=[
                    {
                        "id_documento": "doc-rel-1",
                        "nome": "ordinanza_da_notificare.pdf",
                        "tipo": "Ordinanza da notificare",
                        "data_deposito": "2026-05-23",
                        "disponibile": True,
                    }
                ],
            )
        ],
    )

    assert released_office_documents_from_pec(fascicolo, []) == []

    pec = SimpleNamespace(
        id="pec-cancelleria-1",
        mittente="cancelleria.tribunale.roma@giustiziacert.it",
        oggetto="Tribunale di Roma R.G. 1234/2026 - provvedimento da notificare",
        data="2026-05-23T10:15:00",
        corpo_testo="Si comunica il provvedimento ordinanza_da_notificare.pdf da notificare nel procedimento R.G. 1234/2026.",
        allegati=[{"nome": "ordinanza_da_notificare.pdf", "sha256": "a" * 64}],
        message_id="<pec-cancelleria-1@giustizia>",
    )
    releases = released_office_documents_from_pec(fascicolo, [pec])

    assert len(releases) == 1
    assert releases[0]["nome"] == "ordinanza_da_notificare.pdf"
    assert releases[0]["fonteControllo"] == "pec_cancelleria"
    assert releases[0]["notificaRichiesta"] is True
    assert "single_document=1" in releases[0]["acquisitionHref"]
    assert "documento=ordinanza_da_notificare.pdf" in releases[0]["acquisitionHref"]
    assert "non_duplicare_documenti=1" in releases[0]["acquisitionHref"]

    fascicolo.documenti = [SimpleNamespace(id="doc-local", id_documento_portale="doc-rel-1", nome="ordinanza_da_notificare.pdf", hash_sha256="a" * 64)]
    assert released_office_documents_from_pec(fascicolo, [pec]) == []
    evidence = office_notification_evidence_from_pec(fascicolo, [pec])
    assert evidence[0]["acquisito"] is True

    altro_fascicolo_stesso_anno = SimpleNamespace(
        id="fasc-altro",
        numero="FASC-ALTRO",
        titolo="Altro fascicolo",
        tribunale="Tribunale di Roma",
        numero_rg="2026",
        anno_rg=2026,
        documenti=[],
    )
    assert released_office_documents_from_pec(altro_fascicolo_stesso_anno, [pec]) == []


def test_matrice_notifica_blocca_registro_incoerente_per_destinatario():
    payload = _legal_payload()
    payload.update({
        "ruolo_destinatario": "difensore",
        "destinatario_parte_rappresentata": "Controparte S.p.A.",
        "fonte_pec_destinatario": "registro_imprese",
        "caso_notifica": "appello_impugnazione",
        "provvedimento_tipo": "sentenza",
        "provvedimento_data": "2026-05-20",
    })

    result = validate_legal_notification(payload)

    assert result.ok is False
    assert any("PEC_DESTINATARIO_REGISTRO_INCOERENTE" in item for item in result.blockers)


def test_matrice_notifica_caso_e_destinatario_generano_output_governato():
    payload = _legal_payload()
    payload.update({
        "ruolo_destinatario": "difensore",
        "destinatario_parte_rappresentata": "Controparte S.p.A.",
        "fonte_pec_destinatario": "reginde",
        "caso_notifica": "appello_impugnazione",
        "provvedimento_tipo": "sentenza",
        "provvedimento_numero": "101",
        "provvedimento_anno": "2026",
        "provvedimento_ufficio_origine": "Tribunale di Roma",
        "provvedimento_data": "2026-05-20",
        "provvedimento_data_deposito": "2026-05-20",
    })

    result = validate_legal_notification(payload)

    assert result.ok is True
    assert result.template_id == "relata_appello_impugnazione"
    directive = result.output_plan["notificationDirective"]
    assert directive["role"] == "difensore"
    assert directive["caseId"] == "appello_impugnazione"
    assert "reginde" in directive["allowedRegisters"]
    assert "difensore" in directive["allowedRecipientRoles"]
    assert directive["recipientRule"]
    assert directive["caseLegalBasis"]
    delivery = result.output_plan["deliveryPlan"]
    signature = result.output_plan["signaturePlan"]
    assert delivery["ready"] is True
    assert delivery["subject"] == LEGAL_NOTIFICATION_SUBJECT
    assert delivery["recipients"][0]["role"] == "difensore"
    assert any(item["id"] == "relata_firmata" for item in delivery["attachments"])
    assert signature["requiredBeforeSend"][0]["id"] == "relata_notifica"
    assert signature["requiredBeforeSend"][0]["sourceFile"] == "relata_notifica.pdf"
    assert signature["requiredBeforeSend"][0]["signedFile"] == "relata_notifica.pdf.p7m"
    assert delivery["signaturePlan"]["requiredBeforeSend"][0]["id"] == "relata_notifica"
    assert any(item["id"] == "allegati_pec" and item["status"] == "superato" for item in delivery["sendChecks"])


def test_piano_invio_prepara_pec_distinte_e_allegati_per_destinatario():
    payload = _legal_payload()
    payload.update({
        "destinatari": [
            {
                "nome": "Controparte S.p.A.",
                "pec": "controparte@example.pec.it",
                "ruolo": "controparte",
                "fonte_pec": "registro_imprese",
            },
            {
                "nome": "Avv. Laura Bianchi",
                "pec": "laura.bianchi@example.pec.it",
                "ruolo": "difensore",
                "fonte_pec": "reginde",
                "parte_rappresentata": "Controparte S.p.A.",
            },
        ],
        "documenti": [
            {"nome_file": "ordinanza.pdf", "descrizione": "Ordinanza da notificare", "origine": "nativo_digitale", "hash_sha256": "a" * 64}
        ],
    })

    plan = build_notification_send_plan(payload)

    assert plan["ready"] is True
    assert plan["separatePecRequired"] is True
    assert plan["messagesCount"] == 2
    assert {item["pec"] for item in plan["recipients"]} == {"controparte@example.pec.it", "laura.bianchi@example.pec.it"}
    assert any(item["filename"] == "relata_notifica.pdf.p7m" for item in plan["attachments"])
    assert any(item["filename"] == "ordinanza.pdf" for item in plan["attachments"])
    assert "RAC per ogni destinatario" in plan["postSendEvidenceRequired"]


def test_piano_firma_seleziona_relata_e_non_rifirma_provvedimento_portale():
    payload = _legal_payload()
    payload.update({
        "documento_ufficio_rilasciato": True,
        "acquisizione_portale_richiesta": True,
        "pec_ufficio_eml_file": "pec-cancelleria.eml",
        "pec_ufficio_eml_sha256": "d" * 64,
        "documenti": [
            {
                "nome_file": "ordinanza_da_notificare.pdf",
                "descrizione": "Ordinanza rilasciata dall'ufficio",
                "origine": "copia_fascicolo_informatico",
                "fonte_documento": "PORTALE_TELEMATICO",
                "servizio_portale": "PST",
                "riferimento_portale": "PST-REL-2026-0001",
                "documento_ufficio": True,
                "acquisito_da_portale": True,
                "notifica_richiesta": True,
                "hash_sha256": "a" * 64,
            }
        ],
        "attestazione_multipla": True,
    })

    plan = build_notification_signature_plan(payload)

    assert plan["localSignerRequired"] is True
    assert plan["requiredBeforeSend"] == [
        {
            "id": "relata_notifica",
            "label": "Relata di notificazione",
            "sourceFile": "relata_notifica.pdf",
            "signedFile": "relata_notifica.pdf.p7m",
            "required": True,
            "phase": "prima_invio_pec",
            "format": "CADES",
            "signer": "Mario Rossi",
            "source": "L. 53/1994, art. 3-bis, comma 5; art. 56-bis disp. att. c.p.p. per il flusso penale",
            "reason": "La normativa richiede la relazione di notificazione su documento informatico separato, sottoscritta dall'avvocato prima dell'invio PEC.",
            "automaticSelection": True,
        }
    ]
    assert plan["notToSign"][0]["filename"] == "ordinanza_da_notificare.pdf"
    assert "relata firmata" in plan["notToSign"][0]["reason"]
    assert any(item["id"] == "relata_firmata" and item["status"] == "superato" for item in plan["checks"])


def test_piano_firma_include_solo_documento_marcato_come_atto_da_sottoscrivere():
    payload = _legal_payload()
    payload["documenti"] = [
        {
            "nome_file": "atto_principale.pdf",
            "descrizione": "Atto principale da notificare",
            "origine": "nativo_digitale",
            "firma_digitale_richiesta": True,
            "hash_sha256": "a" * 64,
        },
        {
            "nome_file": "provvedimento.pdf.p7m",
            "descrizione": "Provvedimento già firmato",
            "origine": "firmato_digitalmente",
            "hash_sha256": "b" * 64,
        },
    ]

    plan = build_notification_signature_plan(payload)

    assert [item["id"] for item in plan["requiredBeforeSend"]] == ["relata_notifica", "documento_1"]
    assert plan["requiredBeforeSend"][1]["signedFile"] == "atto_principale.pdf.p7m"
    assert plan["alreadySigned"] == [{"filename": "provvedimento.pdf.p7m", "reason": "Documento già firmato digitalmente o già in formato firmato."}]


def test_piano_orario_applica_scissione_e_blocco_notturno():
    ordinario = build_notification_timing_plan({"data_ora_invio_pec": "2026-05-24T10:40:57"})
    assert ordinario["ready"] is True
    assert ordinario["status"] == "fascia_ordinaria"
    assert ordinario["plannedAt"] == "24/05/2026 10:40:57"

    serale = build_notification_timing_plan({"data_ora_invio_pec": "2026-05-24T21:30"})

    assert serale["ready"] is True
    assert serale["status"] == "fascia_serale_con_scissione"
    assert "RAC" in serale["senderEffect"]
    assert "07:00" in serale["recipientEffect"]
    assert any(item["id"] == "corte_cost_75_2019" for item in serale["legalBasis"])

    notturno = build_notification_timing_plan({"data_ora_invio_pec": "2026-05-24T06:30"})

    assert notturno["ready"] is False
    assert notturno["status"] == "fuori_fascia_destinatario"


def test_area_web_pst_mancata_notifica_salva_art_3ter_e_avviso_eml():
    payload = {
        "pec_non_consegnata": True,
        "causa_imputabile_destinatario": True,
        "valutazione_avvocato": "Casella PEC satura risultante da avviso di mancata consegna.",
        "avviso_mancata_consegna": "mancata-consegna.eml",
        "atto_notificato": "atto.pdf",
        "atto_notificato_sha256": "a" * 64,
        "relata_firmata": "relata_notifica.pdf.p7m",
        "relata_sha256": "b" * 64,
        "pec_inviata": "notifica-inviata.eml",
        "pec_inviata_sha256": "c" * 64,
        "rac_file": "rac.eml",
        "rac_sha256": "d" * 64,
        "rdac_file": "rdac-completa.eml",
        "rdac_sha256": "e" * 64,
    }

    result = prepare_pst_failed_notification_workflow(payload)

    assert result.ok is True
    assert result.output_plan["legalBasis"][0]["id"] == "l53_art3ter"
    assert "Carica avviso di mancata consegna in formato EML" in result.output_plan["portalSteps"]


def test_matrice_notifica_blocca_destinatario_incoerente_con_caso():
    payload = _legal_payload()
    payload.update({
        "ruolo_destinatario": "controparte",
        "fonte_pec_destinatario": "registro_imprese",
        "caso_notifica": "chiamata_terzo",
        "provvedimento_data": "2026-05-20",
    })

    result = validate_legal_notification(payload)

    assert result.ok is False
    assert any("DESTINATARIO_CASO_INCOERENTE" in item for item in result.blockers)

    payload.update({
        "ruolo_destinatario": "terzo",
        "destinatario_nome": "Terzo Chiamato S.r.l.",
        "destinatario_qualifica": "terzo destinatario",
    })

    valid = validate_legal_notification(payload)

    assert valid.ok is True
    assert valid.output_plan["notificationDirective"]["caseId"] == "chiamata_terzo"


def test_matrice_notifica_esposta_per_ui_e_script():
    matrix = notification_directive_matrix()

    assert any(item["value"] == "difensore" and "reginde" in item["allowedRegisters"] for item in matrix["roles"])
    assert any(item["value"] == "sentenza_termine_breve" and item["templateId"] == "relata_sentenza_attestazione_conformita" for item in matrix["cases"])
    assert all(item["legalBasis"] for item in matrix["roles"])
    assert all(item["legalBasis"] and item["recipientRule"] and item["allowedRecipientRoles"] for item in matrix["cases"])
    assert any(item["id"] == "l53_art3ter" for item in matrix["roles"][0]["legalBasis"])
    provvedimento = next(item for item in matrix["cases"] if item["value"] == "provvedimento_giudice")
    assert any(item["id"] == "dgsia_2024_art22" for item in provvedimento["legalBasis"])
    sentenza = next(item for item in matrix["cases"] if item["value"] == "sentenza_termine_breve")
    assert any(item["id"] == "cpc_326" for item in sentenza["legalBasis"])
    assert any(item["id"] == "dl179_art16decies" for item in sentenza["legalBasis"])


def test_modello_sentenza_attestazione_esposto_con_campi_autocompilanti():
    template = get_notification_template("relata_sentenza_attestazione_conformita")
    tokens = {item["token"] for item in available_template_fields()}

    assert template is not None
    assert template["label"] == "Sentenza con attestazione di conformità"
    assert "avvocato.full_name" in template["required_fields"]
    assert "provvedimento.data_deposito" in template["required_fields"]
    assert "{{ avvocato.firma_in_calce }}" in tokens
    assert "{{ avvocato.firma_digitale_dicitura }}" in tokens
    assert "{{ provvedimento.data_deposito }}" in tokens


def test_allegati_notifica_ed_eml_pec_ufficio_sono_controllati():
    payload = _legal_payload()
    payload.update({
        "caso_notifica": "provvedimento_giudice",
        "provvedimento_data": "2026-05-23",
        "documento_ufficio_rilasciato": True,
        "pec_ufficio_rilascio": True,
        "pec_ufficio_eml_file": "pec-cancelleria.eml",
        "pec_ufficio_eml_sha256": "a" * 64,
        "documenti": [
            {
                "nome_file": "ordinanza.pdf",
                "descrizione": "Ordinanza comunicata dalla cancelleria",
                "origine": "comunicazione_cancelleria",
                "data_comunicazione_cancelleria": "2026-05-23",
                "hash_sha256": "b" * 64,
                "documento_ufficio": True,
                "notifica_richiesta": True,
                "acquisito_da_portale": True,
                "riferimento_portale": "pst-doc-1",
            }
        ],
        "attestazione_multipla": True,
    })

    manifest = build_notification_attachment_manifest(payload)
    result = validate_legal_notification(payload)

    assert result.ok is True
    assert all(item["present"] for item in manifest if item["required"])
    assert any(item["id"] == "eml_ufficio" and item["present"] for item in manifest)
    assert any(item["id"] == "eml_pec_ufficio" and item["status"] == "superato" for item in build_notification_normative_checks(payload))

    payload.pop("pec_ufficio_eml_file")
    payload.pop("pec_ufficio_eml_sha256")
    blocked = validate_legal_notification(payload)

    assert blocked.ok is False
    assert any("PEC_UFFICIO_EML_REQUIRED" in item for item in blocked.blockers)


def test_notifica_l53_controllo_attestazioni_non_basta_per_un_solo_allegato():
    payload = _legal_payload()
    payload["documenti"] = [
        {
            "nome_file": "provvedimento.pdf",
            "descrizione": "Provvedimento",
            "origine": "copia_fascicolo_informatico",
            "attestazione_conformita_presente": True,
        },
        {"nome_file": "scansione.pdf", "descrizione": "Scansione", "origine": "scansione_analogico"},
    ]
    payload["attestazione_conformita"] = ""

    checks = build_notification_normative_checks(payload)

    assert any(item["id"] == "attestazioni" and item["status"] == "bloccante" for item in checks)


def test_notifica_l53_modello_personalizzato_usa_campi_iusentra_e_note_avvocato():
    payload = _legal_payload()
    payload["luogo"] = "TAURIANOVA RC"
    payload["data_relata"] = "2026-05-14"
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
    assert "TAURIANOVA RC, 14/05/2026" in result.relata_text
    assert "TAURIANOVA RC, 2026-05-14" not in result.relata_text


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
    assert ok.output_plan["workflowSteps"][0]["id"] == "atti"
    assert any(item["id"] == "rac_rdac" and item["status"] == "superato" for item in ok.output_plan["normativeChecks"])


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
    assert result.output_plan["auditTrail"]["documentsCount"] == 2


def test_prova_deposito_blocca_hash_non_sha256_e_dati_atto_mancanti():
    result = validate_deposit_notification_proof({
        "atto_notificato": "ricorso.pdf",
        "atto_sha256": "abc",
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
    })

    assert result.ok is False
    assert any("HASH_SHA256_INVALID" in item and "Atto notificato" in item for item in result.blockers)
    assert any("DATI_ATTO_RICEVUTE_REQUIRED" in item for item in result.blockers)


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
    send_payload = _legal_payload()
    send_payload["operazione"] = "invio_pec_l53"
    send_payload["data_verifica_pec"] = ""
    send_response = client.post(
        "/api/v1/ui/notifiche-legali/notifica",
        json=send_payload,
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
    send_result = send_response.get_json()
    client_payload = client_response.get_json()

    assert payload_response.status_code == 200
    assert payload["mandatorySubject"] == LEGAL_NOTIFICATION_SUBJECT
    assert payload["contracts"]["clientCommunicationWithoutRelata"] is True
    assert payload["modelliRelata"][0]["previewText"]
    assert payload["automazioneGuidata"]["notifica"][0]["source"].startswith("L. 53/1994")
    assert payload["automazioneGuidata"]["deposito"][0]["id"] == "atti"
    assert any(item["id"] == "eml_ufficio" for item in payload["automazioneGuidata"]["allegati"])
    assert any(field["token"] == "{{ documenti_righe }}" for field in payload["campiDisponibili"])
    assert invalid_response.status_code == 400
    assert invalid_payload["ok"] is False
    assert valid_response.status_code == 200
    assert valid_payload["ok"] is True
    assert "RELAZIONE DI NOTIFICAZIONE" in valid_payload["relataText"]
    assert valid_payload["outputPlan"]["workflowSteps"]
    assert valid_payload["outputPlan"]["auditTrail"]["documentsCount"] == 1
    assert send_response.status_code == 200
    assert send_result["ok"] is True
    assert send_result["message"] == "Piano di invio PEC pronto per la conferma dell'avvocato."
    assert len(send_result["outputPlan"]["timingPlan"]["plannedAt"].split(":")) == 3
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
        nome_originale="20260510185021337.PDF",
        nome_portale="",
        nome="Ordinanza udienza 10 maggio 2026.pdf",
        percorso="20260510185021337.PDF",
        tipo_atto_portale="ordinanza emessa dal Tribunale di Roma",
        classificazione_portale="",
        note="",
        fonte_documento="PORTALE_TELEMATICO",
        servizio_portale="PST",
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
        depositi_pct=[],
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
    assert pratica["procedimento"]["numeroRg"] == "1234"
    assert pratica["procedimento"]["annoRg"] == "2026"
    assert destinatario["pec"] == "alfa@example.pec.it"
    assert destinatario["fontePecSuggerita"] == "ini_pec"
    assert destinatario["parteRappresentata"] == "Alfa S.p.A."
    assert documento_payload["nomeFile"] == "Ordinanza udienza 10 maggio 2026.pdf"
    assert documento_payload["label"].startswith("Ordinanza udienza 10 maggio 2026.pdf")
    assert "20260510185021337.PDF" not in documento_payload["label"]
    assert documento_payload["origine"] == "copia_fascicolo_informatico"
    assert documento_payload["riferimentoPortale"] == "pst-doc-1"
    assert documento_payload["servizioPortale"] == "PST"
    assert documento_payload["documentoUfficio"] is False
    assert documento_payload["acquisitoDaPortale"] is True
    assert documento_payload["notificaRichiesta"] is False
    assert documento_payload["necessitaAttestazione"] is True
    assert pratica["portaleAcquisizioneHref"].startswith("/portali/pst/acquisizione?")
    assert pratica["documentoUfficioMonitor"]["stato"] == "da_verificare"
    assert payload["azioni"]["firmaDigitale"] == "/guida/firma-digitale"


def test_payload_react_notifiche_legali_deriva_parti_rg_destinatari_e_nomi_quickorganizer():
    documento = SimpleNamespace(
        id="doc-quick-1",
        nome_originale="20260510185021337.PDF",
        nome_portale="",
        nome="20260510185021337.PDF",
        percorso="20260510185021337.PDF",
        tipo_atto_portale="",
        classificazione_portale="QuickOrganizer",
        note=(
            "Import QuickOrganizer. Ricorso Lisciotto.pdf - Depositante: Studio. "
            "PEC: ads.rc@mailcert.avvocaturastato.it; dgosv@postcert.istruzione.it"
        ),
        fonte_documento="PORTALE_TELEMATICO",
        servizio_portale="PST",
        hash_sha256="f" * 64,
        data_documento="2026-05-10",
        data_deposito_portale="",
        id_documento_portale="",
        tags=[],
    )
    fascicolo = SimpleNamespace(
        id="fascicolo-quick",
        numero="2026/332",
        titolo="RG 2048/2025 - Lorenzetto II c. MIM",
        id_cliente="",
        nome_cliente="",
        controparte="",
        cf_controparte="",
        tribunale="Tribunale di Milano",
        sezione="",
        numero_rg="",
        anno_rg=0,
        giudice="",
        tipo_procedimento="",
        documenti=[documento],
        depositi_pct=[],
        note="",
        oggetto="",
    )

    payload = build_react_notifiche_legali_payload(
        get_clienti=lambda: SimpleNamespace(tutti=lambda: []),
        get_fascicoli=lambda: SimpleNamespace(tutti=lambda archiviati=False: [fascicolo]),
        get_soggetti=lambda: SimpleNamespace(tutti=lambda: [], parti_fascicolo=lambda id_fascicolo: []),
    )

    pratica = payload["precompilazione"]["pratiche"][0]
    recipient_names = {item["nome"] for item in pratica["destinatari"]}
    recipient_pecs = {item["pec"] for item in pratica["destinatari"] if item["pec"]}
    documento_payload = pratica["documenti"][0]

    assert pratica["assistitoNome"] == "Lorenzetto II"
    assert pratica["controparte"] == "MIM"
    assert pratica["procedimento"]["numeroRg"] == "2048"
    assert pratica["procedimento"]["annoRg"] == "2025"
    assert "MIM" in recipient_names
    assert "ads.rc@mailcert.avvocaturastato.it" in recipient_pecs
    assert "dgosv@postcert.istruzione.it" in recipient_pecs
    assert documento_payload["nomeFile"] == "Ricorso Lisciotto.pdf"
    assert documento_payload["label"] == "Ricorso Lisciotto.pdf"
    assert "QuickOrganizer" not in documento_payload["label"]


def test_payload_documenti_pratica_idrata_nome_timestamp_da_contenuto(monkeypatch):
    documento = SimpleNamespace(
        id="doc-ocr",
        nome="20260510185021337.PDF",
        nome_originale="20260510185021337.PDF",
        nome_portale="",
        percorso="fascicolo-1\\20260510185021337.PDF",
        tipo_atto_portale="",
        classificazione_portale="QuickOrganizer",
        note="Import QuickOrganizer. ",
        fonte_documento="IMPORT_ESTERNO",
        servizio_portale="",
        hash_sha256="",
        data_documento="",
        data_deposito_portale="",
        id_documento_portale="",
        tags=["quickorganizer"],
    )
    fascicolo = SimpleNamespace(id="fascicolo-1", documenti=[documento])

    monkeypatch.setattr(
        react_notifiche_legali_bridge,
        "_quickorganizer_content_label",
        lambda _documento: "Contratto individuale di lavoro a tempo determinato",
    )

    payload = react_notifiche_legali_bridge.build_react_notifiche_legali_practice_documents_payload(
        "fascicolo-1",
        get_fascicoli=lambda: SimpleNamespace(get=lambda id_fascicolo: fascicolo if id_fascicolo == "fascicolo-1" else None),
    )

    documento_payload = payload["documenti"][0]

    assert payload["ok"] is True
    assert documento_payload["label"] == "Contratto individuale di lavoro a tempo determinato"
    assert documento_payload["nomeFile"] == "20260510185021337.PDF"
    assert documento_payload["nomeOriginale"] == "20260510185021337.PDF"


def test_deriva_titolo_documento_da_testo_ocr():
    text = """
    ISTITUTO COMPRENSIVO IC 2 E 4 DI VICENZA
    Oggetto: contratto individuale di lavoro a tempo determinato stipulato tra il
    Dirigente scolastico e il sig. Rossi Mario
    """

    assert (
        react_notifiche_legali_bridge._derive_document_title_from_text(text)
        == "Contratto individuale di lavoro a tempo determinato"
    )


def test_deriva_titoli_documenti_carta_docente_da_testo_ocr():
    richiesta = """
    Oggetto: Richiesta pagamento annualità “CARTA DEL DOCENTE” Grosso Angelo Eugenio, C.F.
    """
    ricorso = """
    STUDIO LEGALE
    Ricorso per il recupero della cd. carta del docente
    Tribunale di Milano
    """

    assert react_notifiche_legali_bridge._derive_document_title_from_text(richiesta) == "Richiesta pagamento Carta del docente"
    assert react_notifiche_legali_bridge._derive_document_title_from_text(ricorso) == "Ricorso per il recupero della Carta del docente"


def test_deriva_titoli_provvedimenti_carta_docente_da_ocr_reale():
    ricorso_lavoro = """
    STUDIO LEGALE MONTAGNESE Tribunale Civile di Vicenza SEZIONE LAVORO
    Ricorso ex Art. 414 C.p.c. contro MINISTERO DELL'ISTRUZIONE E DEL MERITO.
    OGGETTO: Diritto insegnanti precari e personale educativo ad usufruire del beneficio previsto dall'art. 1 della Legge n. 107/2015.
    """
    cassazione = """
    REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO LA CORTE SUPREMA DI CASSAZIONE SEZIONE LAVORO.
    Oggetto: Composta dagli Ill.mi Sigg.ri Magistrati. CARTA DOCENTE. Ha pronunciato la seguente SENTENZA.
    """
    sentenza_lavoro = """
    REPUBBLICA ITALIANA TRIBUNALE ORDINARIO di VICENZA SETTORE LAVORO.
    Ha pronunciato la seguente SENTENZA. Oggetto: Altre ipotesi. docente a tempo determinato.
    """

    assert react_notifiche_legali_bridge._derive_document_title_from_text(ricorso_lavoro) == "Ricorso lavoro Carta del docente"
    assert react_notifiche_legali_bridge._derive_document_title_from_text(cassazione) == "Sentenza Cassazione Carta del docente"
    assert (
        react_notifiche_legali_bridge._derive_document_title_from_text(sentenza_lavoro)
        == "Sentenza lavoro personale docente a tempo determinato"
    )


def test_ui_notifiche_legali_carica_relata_firmata_nel_flusso_operativo():
    page = Path("frontend/src/components/NotificheLegaliPage.tsx").read_text(encoding="utf-8")

    assert "handleSignedRelataFile" in page
    assert "Carica relata firmata" in page
    assert "relata_sha256" in page
    assert "setNotifica((current) => ({ ...current, relata_firmata: true }))" in page


def test_payload_react_notifiche_legali_segnala_pec_ufficio_da_collegare(monkeypatch):
    fascicolo = SimpleNamespace(
        id="fascicolo-portale",
        numero="2026/002",
        titolo="Cliente / Beta",
        id_cliente="",
        nome_cliente="Cliente",
        controparte="Beta S.p.A.",
        cf_controparte="",
        tribunale="Tribunale di Roma",
        sezione="",
        numero_rg="5678",
        anno_rg=2026,
        giudice="",
        tipo_procedimento="civile ordinario",
        documenti=[],
        depositi_pct=[
            SimpleNamespace(
                id="dep-relata",
                id_deposito_esterno="PST-REL-2026-0002",
                fonte="PST",
                servizio_portale="ConsultazioneFascicolo",
                tipo_atto="Ordinanza da notificare",
                data_deposito="2026-05-23",
                mittente="Tribunale di Roma",
                documenti_portale=[
                    {
                        "id_documento": "pst-doc-relata",
                        "nome": "ordinanza_da_notificare.pdf",
                        "tipo": "Ordinanza da notificare",
                        "data_deposito": "2026-05-23",
                        "disponibile": True,
                    }
                ],
            )
        ],
    )
    pec = SimpleNamespace(
        id="pec-cancelleria-5678",
        mittente="cancelleria.tribunale.roma@giustiziacert.it",
        oggetto="Tribunale di Roma R.G. 5678/2026 - ordinanza da notificare",
        data="2026-05-23T10:15:00",
        corpo_testo="Si comunica il provvedimento ordinanza_da_notificare.pdf da notificare nel procedimento R.G. 5678/2026.",
        allegati=[{"nome": "ordinanza_da_notificare.pdf", "sha256": "b" * 64}],
        message_id="<pec-cancelleria-5678@giustizia>",
    )
    monkeypatch.setattr("web.services.react_notifiche_legali_bridge._office_pec_messages", lambda: [pec])

    payload = build_react_notifiche_legali_payload(
        get_clienti=lambda: SimpleNamespace(tutti=lambda: []),
        get_fascicoli=lambda: SimpleNamespace(tutti=lambda archiviati=False: [fascicolo]),
        get_soggetti=lambda: SimpleNamespace(tutti=lambda: [], parti_fascicolo=lambda id_fascicolo: []),
    )

    pratica = payload["precompilazione"]["pratiche"][0]

    assert payload["contracts"]["officeDocumentPecEvidence"] is True
    assert pratica["documentoUfficioMonitor"]["stato"] == "da_acquisire"
    assert pratica["documentoUfficioMonitor"]["documentiDaAcquisire"] == 1
    assert pratica["documentoUfficioMonitor"]["documentiRilasciati"][0]["nome"] == "ordinanza_da_notificare.pdf"
    assert pratica["documentoUfficioMonitor"]["documentiRilasciati"][0]["pecHref"] == "/email/messaggio/pec-cancelleria-5678"
    assert "single_document=1" in pratica["documentoUfficioMonitor"]["documentiRilasciati"][0]["acquisitionHref"]
    assert "documento=ordinanza_da_notificare.pdf" in pratica["documentoUfficioMonitor"]["documentiRilasciati"][0]["acquisitionHref"]
    assert "non_duplicare_documenti=1" in pratica["documentoUfficioMonitor"]["documentiRilasciati"][0]["acquisitionHref"]
    assert "id_fasc=fascicolo-portale" in pratica["portaleAcquisizioneHref"]
    assert "numero=5678" in pratica["portaleAcquisizioneHref"]
