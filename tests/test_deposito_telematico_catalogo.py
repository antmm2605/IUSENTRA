from pathlib import Path

from pct.deposito_telematico_catalogo import (
    _datiatto_root_hint,
    build_deposit_catalog_payload,
    list_deposit_catalog_entries,
    resolve_deposit_type_payload,
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


def test_catalogo_normalizza_chiave_mancante_e_canali_pct():
    entries = list_deposit_catalog_entries()
    curatore = next(entry for entry in entries if entry["label"] == "Atti del Curatore")
    cassazione = resolve_deposit_type_payload("Parte_CASSAZIONE::Ricorso")
    citazione = resolve_deposit_type_payload("Introduttivi_SICID::Citazione")

    assert curatore["key"].startswith("studio-telematico::")
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
    ]
    assert "Create_DatiAtto_Introduttivi_SICID_Cartabia_Citazione" in citazione["schema"]["evidenceMethods"]
    assert citazione["payload"]["datiatto_root_name"] == "Citazione"


def test_catalogo_unep_non_attiva_busta_pct_civile():
    unep = resolve_deposit_type_payload("Atti_UNEP::AttoCivileDebito")

    assert unep is not None
    assert unep["rules"]["policy_code"] == "unep_notifiche"
    assert unep["rules"]["can_prepare_in_pct_panel"] is False
    assert unep["rules"]["requires_atto_enc"] is False
    assert unep["rules"]["requires_pst_cer"] is False
    assert unep["rules"]["server_smtp_allowed"] is False
    assert "UNEP" in unep["rules"]["real_send_blocker"]


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
    assert "tipo_deposito_telematico_key" in catalogo_runtime_source
    assert "generatore DatiAtto ministeriale specifico" not in catalogo_runtime_source
