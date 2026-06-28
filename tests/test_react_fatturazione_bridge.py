from __future__ import annotations

import base64
from datetime import date
from types import SimpleNamespace

from pct.clienti import Cliente, Indirizzo, Recapiti, TipoCliente
from pct.fatturazione import GestioneFatturazione, VoceParcella
from web.services.react_fatturazione_bridge import (
    build_react_fatturazione_payload,
    create_react_fattura,
    update_react_fatturazione_numbering,
)
from web.services.react_fatturazione_archive_actions import (
    build_react_fatturazione_detail_payload,
    confirm_react_fatturazione_sdi_sent,
    confirm_react_fatturazione_xml_signed,
    prepare_react_fatturazione_commercialista,
    prepare_react_fatturazione_sdi_pec,
    update_react_fatturazione_detail,
)


class _Loader:
    def __init__(self, *items):
        self._items = {getattr(item, "id", ""): item for item in items}

    def tutti(self):
        return list(self._items.values())

    def get(self, item_id: str):
        return self._items.get(item_id)


class _User:
    id = "user-1"
    username = "operatore"

    def ha_permesso(self, permission: str) -> bool:
        return permission in {"fatturazione.leggi", "fatturazione.scrivi"}


class _AuditUsers:
    def __init__(self):
        self.events: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def registra_evento(self, *args, **kwargs):
        self.events.append((args, kwargs))


def _cliente() -> Cliente:
    return Cliente(
        id="CLI-001",
        tipo=TipoCliente.PERSONA_GIURIDICA,
        ragione_sociale="Beta Srl",
        partita_iva="12345678901",
        codice_fiscale="12345678901",
        indirizzo_sede_legale=Indirizzo(
            via="Via Garibaldi",
            civico="12",
            cap="20100",
            comune="Milano",
            provincia="MI",
            nazione="Italia",
        ),
        recapiti=Recapiti(
            telefono="021234567",
            email="amministrazione@beta.example",
            pec="beta@pec.example",
        ),
    )


def _fascicolo(cliente_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="FAS-001",
        id_cliente=cliente_id,
        titolo="Opposizione a decreto ingiuntivo",
        numero_rg="120/2026",
        tribunale="Tribunale di Milano",
        giudice="Dott.ssa Bianchi",
        oggetto="Opposizione e sospensione provvisoria esecuzione",
    )


def _fascicolo_rg_separato(cliente_id: str) -> SimpleNamespace:
    return SimpleNamespace(
        id="FC81009F",
        id_cliente=cliente_id,
        titolo="Montagnese R. C. MIM",
        numero_rg="697",
        anno_rg=2025,
        tribunale="Tribunale di Vicenza",
        giudice="",
        oggetto="222050 - Retribuzione",
    )


def _studio_config() -> dict[str, str]:
    return {
        "STUDIO_NOME": "Studio Legale Rossi",
        "STUDIO_AVVOCATO": "Avv. Mario Rossi",
        "STUDIO_INDIRIZZO": "Via Verdi 8",
        "STUDIO_CAP": "00100",
        "STUDIO_CITY": "Roma",
        "STUDIO_PROVINCE": "RM",
        "STUDIO_PIVA": "09876543210",
        "STUDIO_CF": "RSSMRA80A01H501Z",
        "STUDIO_TELEFONO": "061234567",
        "STUDIO_EMAIL": "segreteria@studio-rossi.example",
        "STUDIO_IBAN": "IT60X0542811101000000123456",
        "STUDIO_BANCA": "Banca Forense",
    }


def test_bridge_fatturazione_prefila_nuova_parcella_personalizzata(tmp_path):
    cliente = _cliente()
    fascicolo = _fascicolo(cliente.id)
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    manager.crea(
        id_cliente=cliente.id,
        voci=[VoceParcella(descrizione="Acconto", quantita=1, prezzo_unitario=100.0)],
        data_emissione=date.today().isoformat(),
    )

    payload = build_react_fatturazione_payload(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(fascicolo),
        current_user=_User(),
        query={"id_cliente": cliente.id, "id_fascicolo": fascicolo.id},
        route="/fatturazione/nuova",
        config=_studio_config(),
    )

    defaults = payload["form"]["defaults"]
    personalized = defaults["dati_personalizzati"]

    assert payload["form"]["title"] == "Nuova parcella personalizzata"
    assert payload["nextNumber"].endswith("/002")
    assert payload["studioProfile"]["nome"] == "Mario"
    assert payload["studioProfile"]["cognome"] == "Rossi"
    assert personalized["transmission"]["identificativo_fiscale"] == "RSSMRA80A01H501Z"
    assert personalized["recipient"]["nome_denominazione"] == "Beta Srl"
    assert personalized["recipient"]["pec"] == "beta@pec.example"
    assert personalized["document"]["numero_documento"] == payload["nextNumber"]
    assert personalized["document"]["fascicolo_label"].startswith("Opposizione a decreto ingiuntivo")
    assert personalized["payment"]["iban"] == "IT60X0542811101000000123456"
    assert personalized["payment"]["modalita_pagamento_label"] == "Bonifico"


def test_bridge_fatturazione_presidia_sdi_senza_falso_canale_accreditato(tmp_path):
    cliente = _cliente()
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    parcella = manager.crea(
        id_cliente=cliente.id,
        voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=150.0)],
        data_emissione="2026-06-02",
        sdi_stato="SCARTATA",
        sdi_identificativo="1234567890",
        sdi_ricevuta="Ricevuta di scarto",
        sdi_note="Correggere e ritrasmettere dal canale abilitato",
    )

    payload = build_react_fatturazione_payload(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(),
        current_user=_User(),
        route="/fatturazione",
        config=_studio_config(),
    )

    record = next(item for item in payload["records"] if item["id"] == parcella.id)
    source_ids = {source["id"] for source in payload["officialSources"]}
    warning_codes = {warning["code"] for warning in payload["warnings"]}
    workflow_ids = {step["id"] for step in payload["sdiWorkflow"]}

    assert payload["sdiChannel"]["configured"] is False
    assert "sdi_canale_non_configurato" in warning_codes
    assert "fatturapa_specifiche_formato" in source_ids
    assert "fatturapa_sdi_trasmissione" in source_ids
    assert "agenzia_entrate_guida_fe" in source_ids
    assert {"xml_fatturapa", "canale_accreditato", "monitoraggio_ricevute", "esito_fiscale"}.issubset(workflow_ids)
    assert record["sdiState"] == "SCARTATA"
    assert record["sdiStateLabel"] == "Scartata"
    assert record["sdiStateTone"] == "danger"
    assert "non emessa" in record["sdiStatusMessage"]


def test_bridge_fatturazione_payload_espone_riferimento_fascicolo_per_filtri(tmp_path):
    cliente = _cliente()
    fascicolo = _fascicolo(cliente.id)
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    parcella = manager.crea(
        id_cliente=cliente.id,
        id_fascicolo=fascicolo.id,
        voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=150.0)],
        data_emissione="2026-06-02",
    )

    payload = build_react_fatturazione_payload(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(fascicolo),
        current_user=_User(),
        route="/fatturazione",
        config=_studio_config(),
    )

    record = next(item for item in payload["records"] if item["id"] == parcella.id)

    assert record["caseId"] == "FAS-001"
    assert record["caseRg"] == "120/2026"
    assert "FAS-001" in record["caseReference"]
    assert "RG 120/2026" in record["caseReference"]


def test_bridge_fatturazione_ricostruisce_rg_completo_da_numero_e_anno(tmp_path):
    cliente = _cliente()
    fascicolo = _fascicolo_rg_separato(cliente.id)
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    parcella = manager.crea(
        id_cliente=cliente.id,
        id_fascicolo=fascicolo.id,
        voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=321.50)],
        data_emissione="2025-09-23",
    )

    payload = build_react_fatturazione_payload(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(fascicolo),
        current_user=_User(),
        route="/fatturazione",
        config=_studio_config(),
    )

    record = next(item for item in payload["records"] if item["id"] == parcella.id)

    assert record["caseId"] == "FC81009F"
    assert record["caseRg"] == "697/2025"
    assert "RG 697/2025" in record["caseReference"]
    assert "RG 697/2025" in record["caseTitle"]


def test_bridge_fatturazione_configura_numerazione_fatture(tmp_path):
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))

    result, status = update_react_fatturazione_numbering(
        get_fatturazione=lambda: manager,
        current_user=_User(),
        payload={"anno": 2024, "ultimoNumeroUsato": 40},
    )
    page = build_react_fatturazione_payload(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(),
        get_fascicoli=lambda: _Loader(),
        current_user=_User(),
        query={"anno": "2024"},
        route="/fatturazione",
        config=_studio_config(),
    )

    assert status == 200
    assert result["ok"] is True
    assert result["numbering"]["prossimoNumero"] == "2024/041"
    assert page["numbering"]["ultimoNumeroConfigurato"] == 40
    assert page["nextNumber"] == "2024/041"


def test_create_react_fattura_salva_snapshot_personalizzato_e_registra_audit(tmp_path):
    cliente = _cliente()
    fascicolo = _fascicolo(cliente.id)
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    audit_users = _AuditUsers()

    payload = {
        "id_cliente": cliente.id,
        "id_fascicolo": fascicolo.id,
        "data_emissione": "2026-05-10",
        "data_scadenza": "2026-06-09",
        "note": "Parcella personalizzata per attivita giudiziale",
        "voci": [
            {"descrizione": "Compenso professionale", "quantita": "1", "prezzo_unitario": "240.00", "tipo": "ONORARIO"},
            {"descrizione": "Spese imponibili", "quantita": "1", "prezzo_unitario": "20.00", "tipo": "SPESE"},
        ],
        "opzioni_fiscali": {
            "applica_iva": True,
            "applica_cassa": True,
            "applica_ritenuta": False,
            "applica_bollo": False,
        },
        "percentuale_spese_generali": "15",
        "metodo_pagamento": "Bonifico",
        "dati_personalizzati": {
            "transmission": {
                "identificativo_fiscale": "RSSMRA80A01H501Z",
                "codice_invio": "A1202",
                "telefono": "061234567",
                "email": "segreteria@studio-rossi.example",
            },
            "studio": {
                "nome_denominazione": "Studio Legale Rossi",
                "partita_iva": "09876543210",
                "codice_fiscale": "RSSMRA80A01H501Z",
            },
            "recipient": {
                "denominazione": "Beta Srl",
                "nome_denominazione": "Beta Srl",
                "partita_iva": "12345678901",
                "codice_fiscale": "12345678901",
                "indirizzo": "Via Garibaldi 12",
                "cap": "20100",
                "citta": "Milano",
                "provincia": "MI",
                "nazione": "IT",
                "codice_destinatario": "0000000",
                "pec": "beta@pec.example",
            },
            "document": {
                "tipo_documento": "TD01",
                "numero_documento": "2026/010",
                "data_documento": "2026-05-10",
                "causale_oggetto": "Parcella fascicolo RG 120/2026",
                "regime_fiscale": "RF01",
                "esigibilita_iva": "I",
            },
            "payment": {
                "modalita_pagamento_label": "Bonifico",
                "modalita_pagamento_codice": "MP05",
                "beneficiario": "Studio Legale Rossi",
                "istituto_finanziario": "Banca Forense",
                "iban": "IT60X0542811101000000123456",
                "giorni_termini": "30",
            },
        },
    }

    result, status = create_react_fattura(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(fascicolo),
        get_utenti=lambda: audit_users,
        get_preventivi=None,
        current_user=_User(),
        payload=payload,
        config=_studio_config(),
        ip_address="127.0.0.1",
    )

    assert status == 200
    assert result["ok"] is True
    assert manager.tutte()
    parcella = manager.tutte()[0]
    assert parcella.percentuale_spese_generali == 15.0
    assert parcella.metodo_pagamento == "Bonifico"
    assert parcella.voci[1].tipo == "SPESE"
    assert parcella.dati_personalizzati["recipient"]["denominazione"] == "Beta Srl"
    assert parcella.dati_personalizzati["payment"]["iban"] == "IT60X0542811101000000123456"
    assert audit_users.events
    assert audit_users.events[0][0][0] == "fatturazione.crea"


def test_create_react_fattura_forfettaria_disattiva_iva_anche_se_selezionata(tmp_path):
    cliente = _cliente()
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    audit_users = _AuditUsers()

    payload = {
        "id_cliente": cliente.id,
        "data_emissione": "2026-05-10",
        "data_scadenza": "2026-06-09",
        "note": "Parcella forfettaria",
        "voci": [
            {"descrizione": "Compenso professionale", "quantita": "1", "prezzo_unitario": "258.00", "tipo": "ONORARIO"},
        ],
        "opzioni_fiscali": {
            "applica_iva": True,
            "applica_cassa": True,
            "applica_ritenuta": False,
            "applica_bollo": False,
        },
        "percentuale_spese_generali": "15",
        "metodo_pagamento": "Bonifico",
        "dati_personalizzati": {
            "document": {
                "regime_fiscale": "RF19",
            },
        },
    }

    result, status = create_react_fattura(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(),
        get_utenti=lambda: audit_users,
        get_preventivi=None,
        current_user=_User(),
        payload=payload,
        config=_studio_config(),
        ip_address="127.0.0.1",
    )

    assert status == 200
    assert result["ok"] is True
    parcella = manager.tutte()[0]
    assert parcella.applica_iva is False
    assert parcella.iva == 0.0


def test_fatturazione_detail_modal_payload_e_modifica_voci_preservano_calcoli(tmp_path):
    cliente = _cliente()
    fascicolo = _fascicolo(cliente.id)
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    audit_users = _AuditUsers()
    parcella = manager.crea(
        id_cliente=cliente.id,
        id_fascicolo=fascicolo.id,
        voci=[VoceParcella(descrizione="Compenso iniziale", quantita=1, prezzo_unitario=120.0)],
        note="Nota iniziale",
    )

    payload, status = build_react_fatturazione_detail_payload(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(fascicolo),
        id_documento=parcella.id,
        sdi_cfg=SimpleNamespace(pec_notifiche="sdi@pec.example", email_commercialista="contabile@example"),
    )

    assert status == 200
    assert payload["item"]["note"] == "Nota iniziale"
    assert payload["item"]["workflow"]["sdiPecAddress"] == "sdi@pec.example"
    assert payload["item"]["voci"][0]["prezzoUnitario"] == "120.0"

    result, status = update_react_fatturazione_detail(
        get_fatturazione=lambda: manager,
        get_utenti=lambda: audit_users,
        current_user=_User(),
        id_documento=parcella.id,
        payload={
            "note": "Nota aggiornata",
            "voci": [
                {"descrizione": "Compenso aggiornato", "quantita": "2", "prezzo_unitario": "100,50", "tipo": "ONORARIO"},
                {"descrizione": "Spese documentate", "quantita": "1", "prezzo_unitario": "25", "tipo": "SPESE"},
            ],
        },
        ip_address="127.0.0.1",
    )

    updated = manager.get(parcella.id)
    assert status == 200
    assert result["ok"] is True
    assert updated is not None
    assert updated.note == "Nota aggiornata"
    assert updated.voci[0].importo == 201.0
    assert updated.voci[1].tipo == "SPESE"
    assert audit_users.events[-1][0][0] == "fatturazione.dettaglio"

    blocked, status = update_react_fatturazione_detail(
        get_fatturazione=lambda: manager,
        get_utenti=lambda: audit_users,
        current_user=_User(),
        id_documento=parcella.id,
        payload={"note": "No", "totale": "1", "voci": [{"descrizione": "Voce", "quantita": "1", "prezzo_unitario": "1"}]},
    )

    assert status == 400
    assert blocked["ok"] is False
    assert "totale" in blocked["errors"]


def test_fatturazione_xml_firmato_sdi_e_commercialista_usano_storage_tenant_aware(tmp_path):
    cliente = _cliente()
    fascicolo = _fascicolo(cliente.id)
    manager = GestioneFatturazione(db_path=str(tmp_path / "parcelle.json"))
    audit_users = _AuditUsers()
    parcella = manager.crea(
        id_cliente=cliente.id,
        id_fascicolo=fascicolo.id,
        voci=[VoceParcella(descrizione="Compenso", quantita=1, prezzo_unitario=300.0)],
    )
    parcella = manager.aggiorna(parcella.id, numero="2026/077")
    storage_root = tmp_path / "fatturazione" / "documenti_fatturapa"
    pec_cfg = SimpleNamespace(
        indirizzo="studio@pec.example",
        username="studio@pec.example",
        smtp_host="smtp.pec.example",
        smtp_port=465,
        use_ssl=True,
        use_tls=False,
    )
    sdi_cfg = SimpleNamespace(
        pec_notifiche="sdi@pec.example",
        email_commercialista="contabile@example",
        pec_commercialista="contabile@pec.example",
        nome_commercialista="Studio Contabile",
    )

    signed_content = base64.b64encode(b"PKCS7-SIGNED-FATTURAPA" * 16).decode("ascii")
    signed_result, status = confirm_react_fatturazione_xml_signed(
        get_fatturazione=lambda: manager,
        get_utenti=lambda: audit_users,
        current_user=_User(),
        id_documento=parcella.id,
        payload={"signed_base64": signed_content, "fileName": "IT09876543210_00077.xml", "intestatario": "Avv. Rossi"},
        storage_root=storage_root,
        ip_address="127.0.0.1",
    )

    updated = manager.get(parcella.id)
    assert status == 200
    assert signed_result["ok"] is True
    assert updated is not None
    assert updated.sdi_stato == "PREPARATA"
    signed_meta = updated.dati_personalizzati["fatturapa_workflow"]["signed_xml"]
    assert signed_meta["fileName"].endswith(".p7m")
    assert (storage_root / parcella.id / signed_meta["storageFile"]).is_file()

    sdi_result, status = prepare_react_fatturazione_sdi_pec(
        get_fatturazione=lambda: manager,
        current_user=_User(),
        id_documento=parcella.id,
        storage_root=storage_root,
        pec_cfg=pec_cfg,
        sdi_cfg=sdi_cfg,
    )

    assert status == 200
    assert sdi_result["draft"]["to"] == "sdi@pec.example"
    assert sdi_result["localPec"]["endpoint"].endswith("/pec/send")
    assert sdi_result["localPec"]["payload"]["attachments"][0]["storageFile"] == signed_meta["storageFile"]

    sent_result, status = confirm_react_fatturazione_sdi_sent(
        get_fatturazione=lambda: manager,
        get_utenti=lambda: audit_users,
        current_user=_User(),
        id_documento=parcella.id,
        payload={"message_id": "<pec-123@example>", "destinatario": "sdi@pec.example", "oggetto": "Invio"},
    )

    assert status == 200
    assert sent_result["item"]["sdiState"] == "INVIATA"
    assert manager.get(parcella.id).dati_personalizzati["fatturapa_workflow"]["sdi_send"]["messageId"] == "<pec-123@example>"

    comm_email_result, status = prepare_react_fatturazione_commercialista(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(fascicolo),
        current_user=_User(),
        id_documento=parcella.id,
        payload={"channel": "ordinaria", "attachments": "pdf"},
        storage_root=storage_root,
        pec_cfg=pec_cfg,
        sdi_cfg=sdi_cfg,
        config=_studio_config(),
    )

    assert status == 200
    assert comm_email_result["draft"]["channel"] == "ordinaria"
    assert comm_email_result["draft"]["to"] == "contabile@example"
    assert len(comm_email_result["draft"]["attachments"]) == 1
    assert "localPec" not in comm_email_result

    comm_result, status = prepare_react_fatturazione_commercialista(
        get_fatturazione=lambda: manager,
        get_clienti=lambda: _Loader(cliente),
        get_fascicoli=lambda: _Loader(fascicolo),
        current_user=_User(),
        id_documento=parcella.id,
        payload={"channel": "pec", "attachments": "pdf_xml_firmato"},
        storage_root=storage_root,
        pec_cfg=pec_cfg,
        sdi_cfg=sdi_cfg,
        config=_studio_config(),
    )

    assert status == 200
    assert comm_result["draft"]["channel"] == "pec"
    assert comm_result["draft"]["to"] == "contabile@pec.example"
    assert len(comm_result["draft"]["attachments"]) == 2
    assert {item["storageFile"] for item in comm_result["draft"]["attachments"]} >= {signed_meta["storageFile"]}
    assert comm_result["localPec"]["payload"]["to"] == "contabile@pec.example"
