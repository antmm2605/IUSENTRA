from pathlib import Path

from lxml import etree

from pct.busta import BustaTelematica
from pct.deposito_telematico_catalogo import (
    _datiatto_root_hint,
    build_deposit_catalog_payload,
    list_deposit_catalog_entries,
    resolve_deposit_type_payload,
)
from web.services.deposito_catalogo_runtime import deposito_catalogo_datiatto_extra
from scripts.audit_deposito_catalogo_end_to_end import (
    _dati_busta_for,
    _sample_pdf,
    audit_deposit_catalog,
)


def test_catalogo_studio_telematico_contiene_270_tipi_e_fonti_ministeriali():
    payload = build_deposit_catalog_payload()

    assert payload["counts"]["totalDepositTypes"] == 270
    assert len(payload["counts"]["macroareas"]) == 6
    assert len(payload["entries"]) == 270
    fonte_ids = {source["id"] for source in payload["officialSources"]}
    assert "pst_specifiche_tecniche_dm44_2024" in fonte_ids
    assert "normattiva_dm44_2011" in fonte_ids
    assert "pst_xsd_pct" in fonte_ids
    assert "pst_xsd_sici_preview_20260611" in fonte_ids
    assert "pst_xsd_cassazione_preview_20260615" in fonte_ids
    assert payload["jsonAuthoritative"] is False
    assert payload["tenantScope"] == "catalogo_tecnico_condiviso_non_tenant"
    assert payload["ministerialSchemaEvidence"]["siciPreview20260611"]["xsdCount"] == 156
    assert payload["ministerialSchemaEvidence"]["siciPreview20260611"]["newObjectCode"] == "110046"
    assert payload["ministerialSchemaEvidence"]["siciPreview20260611"]["productionReady"] is False
    assert payload["ministerialSchemaEvidence"]["cassazionePreview20260615"]["xsdCount"] == 116
    assert payload["ministerialSchemaEvidence"]["cassazionePreview20260615"]["productionReady"] is False
    assert payload["schemaVersion"] == 3
    assert len(payload["referenceData"]["titoliEsecutivi"]) == 22
    assert len(payload["referenceData"]["ruoliProvvedimentoCassazione"]) == 9
    assert len(payload["referenceData"]["materieCassazione"]) >= 170
    assert len(payload["referenceData"]["classiImmobiliari"]) >= 50


def test_catalogo_normalizza_chiave_mancante_e_canali_pct():
    entries = list_deposit_catalog_entries()
    curatore = next(entry for entry in entries if entry["key"] == "Curatore_CONCORSUALI_SIECIC::DepositoRelazioneIniziale")
    cassazione = resolve_deposit_type_payload("Parte_CASSAZIONE::Ricorso")
    citazione = resolve_deposit_type_payload("Introduttivi_SICID::Citazione")

    assert curatore["quickOrganizer"]["aliases"] == [
        "studio-telematico::procedimenti-concorsuali-atti-del-curatore::186"
    ]
    assert curatore["rules"]["policy_code"] == "pct_civile_dm44"
    assert cassazione is not None
    assert cassazione["registry"]["code"] == "CASSCI"
    assert cassazione["rules"]["requires_atto_enc"] is True
    assert citazione is not None
    assert citazione["payload"]["tipo_atto"] == "ATTO_DI_CITAZIONE"
    assert citazione["rules"]["requires_pst_cer"] is True
    assert citazione["rules"]["server_smtp_allowed"] is False
    assert citazione["rules"]["can_prepare_in_pct_panel"] is True
    assert citazione["rules"]["real_send_allowed_from_pct_panel"] is True
    assert citazione["rules"]["real_send_blocker"] == ""
    assert citazione["schema"]["status"] == "supportato_root_catalogo"
    assert citazione["schema"]["supported"] is True
    assert citazione["schema"]["requiresSpecificGenerator"] is False
    assert citazione["schema"]["supportedMinisterialRoot"] == "Citazione"
    assert citazione["schema"]["generatorClass"] == "IntroduttiviSicid"
    assert citazione["schema"]["generatorMode"] == "introduttivo_citazione"
    assert citazione["schema"]["requiredData"] == [
        "AnagraficaProcedimento",
        "Datacitazione",
        "codice oggetto",
        "valore causa quando presente",
        "ContributoUnificato",
    ]
    assert citazione["schema"]["contributionRequired"] is True
    assert citazione["schema"]["contributionXmlMode"] == "atto_introduttivo"
    assert "Create_DatiAtto_Introduttivi_SICID_Cartabia_Citazione" in citazione["schema"]["evidenceMethods"]
    assert citazione["payload"]["datiatto_root_name"] == "Citazione"
    assert [field["id"] for field in citazione["schema"]["inputFields"]] == ["data_notifica_citazione"]


def test_catalogo_espone_i_campi_specifici_solo_sui_rami_pertinenti():
    reclamo = resolve_deposit_type_payload("Introduttivi_SICID::RicorsoReclamoSospensiva")
    pignoramento = resolve_deposit_type_payload(
        "Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoTerzi"
    )
    cassazione = resolve_deposit_type_payload("Parte_CASSAZIONE::Ricorso")
    memoria = resolve_deposit_type_payload("Parte_SICID::Memoria183")

    assert reclamo is not None
    reclamo_ids = {field["id"] for field in reclamo["schema"]["inputFields"]}
    assert {"cui", "precedente_provvedimento_numero", "precedente_provvedimento_anno"} <= reclamo_ids

    assert pignoramento is not None
    pignoramento_ids = {field["id"] for field in pignoramento["schema"]["inputFields"]}
    assert {"beni_pignorati", "titolo", "terzi", "data_citazione", "stima_diritto"} <= pignoramento_ids

    assert cassazione is not None
    cassazione_ids = {field["id"] for field in cassazione["schema"]["inputFields"]}
    assert {"tipo_ricorso_cassazione", "provvedimento_impugnato", "materia_ricorso_cassazione", "motivi_cassazione"} <= cassazione_ids

    assert memoria is not None
    assert memoria["schema"]["inputFields"] == []


def test_catalogo_unep_non_attiva_busta_pct_civile():
    unep = resolve_deposit_type_payload("Atti_UNEP::AttoCivileDebito")

    assert unep is not None
    assert unep["rules"]["policy_code"] == "unep_notifiche"
    assert unep["rules"]["can_prepare_in_pct_panel"] is False
    assert unep["rules"]["requires_atto_enc"] is False
    assert unep["rules"]["requires_pst_cer"] is False
    assert unep["rules"]["server_smtp_allowed"] is False
    assert "UNEP" in unep["rules"]["real_send_blocker"]


def test_catalogo_documenti_attesi_segue_flag_studio_telematico():
    citazione = resolve_deposit_type_payload("Introduttivi_SICID::Citazione")
    memoria = resolve_deposit_type_payload("Parte_SICID::Memoria183")
    cassazione = resolve_deposit_type_payload("Parte_CASSAZIONE::Ricorso")
    unep = resolve_deposit_type_payload("Atti_UNEP::AttoCivileDebito")

    assert citazione is not None
    citazione_docs = citazione["ui"]["documents"]
    assert "atto principale" in citazione_docs
    assert "procura alle liti" in citazione_docs
    assert "contributo unificato o esenzione" in citazione_docs
    assert "nota iscrizione a ruolo" not in citazione_docs
    assert "anagrafica procedimento" in citazione_docs
    assert "data citazione" in citazione_docs
    assert "valore causa o esenzione" in citazione_docs

    assert memoria is not None
    memoria_docs = memoria["ui"]["documents"]
    assert "atto principale" in memoria_docs
    assert "procura alle liti" not in memoria_docs
    assert "contributo unificato o esenzione" not in memoria_docs
    assert "riferimento procedimento" in memoria_docs
    assert "istanze o richieste" in memoria_docs

    assert cassazione is not None
    cassazione_docs = cassazione["ui"]["documents"]
    assert "procura alle liti" in cassazione_docs
    assert "contributo unificato o esenzione" in cassazione_docs
    assert "nota iscrizione a ruolo" in cassazione_docs
    assert "provvedimento impugnato" in cassazione_docs
    assert "prova notifica" in cassazione_docs

    visibilita = resolve_deposit_type_payload("Parte_SICID::AttoRichiestaVisibilità")
    assert visibilita is not None
    assert visibilita["schema"]["contributionRequired"] is False
    assert visibilita["schema"]["contributionXmlMode"] == "none"
    assert "ContributoUnificato" not in visibilita["schema"]["requiredData"]
    assert "contributo unificato o esenzione" not in visibilita["ui"]["documents"]

    assert unep is not None
    unep_docs = unep["ui"]["documents"]
    assert unep_docs[:3] == ["atto da notificare", "relata o richiesta", "destinatari"]
    assert "contributo o anticipazione spese UNEP" in unep_docs


def test_catalogo_recupera_rami_decompilati_non_presenti_nel_json_menu():
    ricorso_702 = resolve_deposit_type_payload("Introduttivi_SICID::Ricorso702Bis")
    memoria_cartabia = resolve_deposit_type_payload("Parte_SICID::Memoria171ter1")
    curatore = resolve_deposit_type_payload("Curatore_CONCORSUALI_SIECIC::DepositoRelazioneIniziale")
    visibilita = resolve_deposit_type_payload("Parte_SICID::AttoRichiestaVisibilità")
    progetto = resolve_deposit_type_payload("Professionista_ESECUZIONI_SIECIC::ProgettoDistribuzione")

    assert ricorso_702 is not None
    assert ricorso_702["schema"]["generatorClass"] == "IntroduttiviSicid"
    assert ricorso_702["schema"]["supportedMinisterialRoot"] == "Ricorso702Bis"
    assert ricorso_702["rules"]["real_send_allowed_from_pct_panel"] is True

    assert memoria_cartabia is not None
    assert memoria_cartabia["schema"]["generatorClass"] == "Parte"
    assert memoria_cartabia["schema"]["supportedMinisterialRoot"] == "MemorieCartabia"
    assert memoria_cartabia["rules"]["real_send_allowed_from_pct_panel"] is True
    assert "Create_DatiAtto_Parte_MemorieCartabia" in memoria_cartabia["schema"]["evidenceMethods"]

    assert curatore is not None
    assert curatore["quickOrganizer"]["aliases"] == [
        "studio-telematico::procedimenti-concorsuali-atti-del-curatore::186"
    ]
    assert curatore["schema"]["generatorClass"] == "CurSiecicConcorsuali"
    assert curatore["schema"]["supportedMinisterialRoot"] == "DepositoRelazioneIniziale"
    assert curatore["rules"]["real_send_allowed_from_pct_panel"] is True
    assert curatore["rules"]["real_send_blocker"] == ""

    assert visibilita is not None
    assert visibilita["schema"]["supportedMinisterialRoot"] == "AttoRichiestaVisibilita"
    assert visibilita["rules"]["real_send_allowed_from_pct_panel"] is True

    assert progetto is not None
    assert progetto["quickOrganizer"]["aliases"] == [
        "Professionista_ESECUZIONI_SIECIC::Progett369oDistribuzione"
    ]
    assert progetto["schema"]["supportedMinisterialRoot"] == "ProgettoDistribuzione"
    assert progetto["rules"]["real_send_allowed_from_pct_panel"] is True


def test_audit_catalogo_end_to_end_tutti_i_tipi_senza_falso_verde():
    report = audit_deposit_catalog()
    blocked_keys = {item["key"] for item in report["blocked_keys"]}

    assert report["ok"] is True
    assert report["total"] == 270
    assert report["channels"] == {"pct": 252, "unep": 18, "other": 0}
    assert report["pct_generated_datiatto"] == 252
    assert report["pct_expected_datiatto"] == 252
    assert report["pct_contribution_exemption_branches_checked"] > 0
    assert report["pct_required_input_guards_checked"] >= 120
    assert report["pct_real_send_suspended_until_dedicated_generator"] == 0
    assert report["office_catalog"]["ok"] is True
    assert report["office_catalog"]["pct_target_codes"] == 593
    assert report["office_catalog"]["pct_target_missing_in_iusentra"] == 0
    assert report["office_catalog"]["pct_target_without_pec_or_code"] == 0
    assert report["office_catalog"]["react_resolver_errors"] == 0
    assert report["office_catalog"]["external_operational_pct_rows"] == 593
    assert report["office_catalog"]["external_operational_missing_in_iusentra"] == 0
    assert report["office_catalog"]["external_operational_without_pec"] == 0
    assert report["office_catalog"]["external_operational_pec_mismatch"] == 0
    blocked_keys_regression_watchlist = {
        "Parte_SICID::AttoRichiestaVisibilità",
        "Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoImmobiliare",
        "Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoDebitore",
        "Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoTerzi",
        "Parte_ESECUZIONI_SIECIC::AttoRichiestaVisibilità",
        "Professionista_ESECUZIONI_SIECIC::ProgettoDistribuzione",
        "Parte_CONCORSUALI_SIECIC::AttoRichiestaVisibilità",
        "Curatore_CONCORSUALI_SIECIC::DepositoRelazioneIniziale",
        "CorsoCausa_SIGP::AttoRichiestaVisibilità",
    }
    assert blocked_keys_regression_watchlist
    assert blocked_keys == set()
    assert report["errors"] == []


def test_datiatto_extra_runtime_porta_campi_specifici_ai_generatori():
    class Form:
        def __init__(self):
            self.values = {
                "datiatto_extra": '{"parte_codice_fiscale":"RSSMRA80A01H501Z"}',
                "tipo_pignoramento": "mobiliare_presso_terzi",
                "data_consegna_pignoramento": "01/07/2026",
                "importo_precetto": "1.234,56",
                "beni_pignorati_json": '[{"tipo":"mobile","descrizione":"Credito","valore":"1200,00"}]',
                "terzo_json": '{"codice_fiscale":"TRZPLA80A01H501B","data_notifica_pignoramento":"04/07/2026"}',
                "terzi_json": '[{"codice_fiscale":"TRZPLA80A01H501B"},{"codice_fiscale":"TRZLNZ80A01H501C"}]',
                "titolo_json": '{"descrizione":"Titolo esecutivo","tipologia":"Sentenza"}',
            }

        def get(self, key, default=""):
            return self.values.get(key, default)

    extra = deposito_catalogo_datiatto_extra(Form())

    assert extra["parte_codice_fiscale"] == "RSSMRA80A01H501Z"
    assert extra["tipo_pignoramento"] == "mobiliare_presso_terzi"
    assert extra["importo_precetto"] == "1.234,56"
    assert extra["beni_pignorati"][0]["descrizione"] == "Credito"
    assert extra["terzo"]["codice_fiscale"] == "TRZPLA80A01H501B"
    assert len(extra["terzi"]) == 2
    assert extra["titolo"]["descrizione"] == "Titolo esecutivo"


def test_generatore_pignoramento_presso_terzi_gestisce_la_griglia_completa(tmp_path):
    entry = resolve_deposit_type_payload(
        "Introduttivi_ESECUZIONI_SIECIC::IscrizioneRuoloPignoramentoMobiliarePressoTerzi"
    )
    assert entry is not None
    dati = _dati_busta_for(entry, _sample_pdf(tmp_path / "atto.pdf"))

    root = etree.fromstring(BustaTelematica(dati).crea_dati_atto_xml_per_firma())

    assert len(root.xpath(".//*[local-name()='DatiTerzo']")) == 2
    assert len(root.xpath(".//*[local-name()='Altro']")) == 2


def test_catalogo_atto_sistema_e_operativo_senza_numero_rg_obbligatorio():
    roots = [
        ("AttoSistemaSicid.DepositoComplementare", "AttoSistemaSicid"),
        ("AttoSistemaSiecic.DepositoComplementare", "AttoSistemaSiecic"),
        ("AttoSistema_SIGP.DepositoComplementare", "AttoSistema_SIGP"),
    ]

    for root, generator_class in roots:
        entry = {
            "datiatto_roots": [root],
            "datiatto_methods": [f"Create_DatiAtto_{generator_class}_DepositoComplementare"],
            "datiatto_required_data": ["CodiceOggetto"],
        }
        hint = _datiatto_root_hint(entry, {"channel_kind": "pct_civile"}, "DEPOSITO_COMPLEMENTARE")

        assert hint["generatorClass"] == generator_class
        assert hint["ministerialRoot"] == "DepositoComplementare"
        assert hint["generatorMode"] == "sistema_destinazione"
        assert "numero RG" not in hint["requiredData"]
        assert "anno RG" not in hint["requiredData"]
        assert hint["requiredData"] == ["codice oggetto"]


def test_api_e_rotte_busta_usano_catalogo_backend():
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    deposito_source = Path("web/bootstrap/deposito_routes.py").read_text(encoding="utf-8")
    catalogo_runtime_source = Path("web/services/deposito_catalogo_runtime.py").read_text(encoding="utf-8")

    assert '/telematico/depositi/catalogo' in api_source
    assert "build_deposit_catalog_payload" in api_source
    assert "resolve_deposit_type_payload" in catalogo_runtime_source
    assert "deposito_catalogo_entry" in deposito_source
    assert "_deposito_catalogo_blocker" in deposito_source
    assert "deposito_catalogo_datiatto_extra" in deposito_source
    assert "deposito_catalogo_busta_metadata" in deposito_source
    assert '"datiatto_extra": extra' in catalogo_runtime_source
    assert "tipo_deposito_telematico_key" in catalogo_runtime_source
    assert "generatore DatiAtto ministeriale specifico" not in catalogo_runtime_source
