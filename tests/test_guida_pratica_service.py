from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pct.guida_pratica import GuidaPraticaService  # noqa: E402
from pct.pratiche_collegate_catalog import (  # noqa: E402
    codice_oggetto_pst_entry,
    list_codici_oggetto_pst,
    looks_like_codice_oggetto_pst,
)

FIXTURE_KB = ROOT / "pct" / "data" / "legal_knowledge_base.json"
FULL_KB = ROOT / "pct" / "data" / "legal_knowledge_base.full.json"


def test_curated_code_resolves_inheritance_and_removes_termine_grazia_for_uso_diverso():
    service = GuidaPraticaService(
        kb_path=FIXTURE_KB,
        catalog_records=[{"codice": "030012", "descrizione": "Sfratto morosita uso diverso"}],
    )

    guida = service.get_guidance("030012")
    warnings = "\n".join(guida["atto_principale"].get("avvertimenti_obbligatori", []))

    assert guida["codice"] == "030012"
    assert guida["coverage"]["level"] == "curata"
    assert guida["codice_deposito"]["depositabile"] is True
    assert "art. 55" not in warnings
    assert "termine di grazia" not in warnings.lower()


def test_generated_unknown_catalog_code_has_required_baseline_and_reviewer_flag():
    service = GuidaPraticaService(
        kb_path=FIXTURE_KB,
        catalog_records=[
            {
                "codice": "010003",
                "descrizione": "Procedimento di ingiunzione ante causam - vendita",
                "area": "procedimenti_speciali_sommari",
            }
        ],
    )

    guida = service.get_guidance("010003")

    assert guida["coverage"]["needs_reviewer"] is True
    assert guida["coverage"]["level"] == "profilo_generato"
    assert guida["codice_deposito"]["depositabile"] is True
    assert guida["atto_principale"]["campi_obbligatori"]
    assert any(field["id"] == "credito_importo" for field in guida["atto_principale"]["campi_obbligatori"])


def test_checklist_reports_missing_required_items():
    service = GuidaPraticaService(
        kb_path=FIXTURE_KB,
        catalog_records=[{"codice": "030011", "descrizione": "Sfratto morosita"}],
    )

    checklist = service.get_checklist("030011", {"fields": {"tribunale": "Tribunale di Roma"}})

    assert checklist["campi_mancanti"]
    assert checklist["allegati_mancanti"]
    assert checklist["percentuale_completamento"] < 100


def test_full_kb_loads_uploaded_macro_areas_and_logical_aliases():
    service = GuidaPraticaService(kb_path=FULL_KB)

    assert len(service.list_guidance(limit=20000)) >= 1018
    for codice in [
        "010001",
        "100011",
        "110001",
        "140011",
        "150001",
        "310001",
        "400220",
        "420300",
        "451310",
        "471401",
        "ESEC_MOB_001",
        "LAV_LIC_001",
    ]:
        guida = service.get_guidance(codice)
        assert guida["codice"] == codice
        assert guida["denominazione"]
        assert guida["coverage"]["level"] == "curata"
        assert guida["atto_principale"]["campi_obbligatori"]
        assert guida["quick_help"]["atto_da_redigere"]


def test_full_kb_inheritance_keeps_parent_fields_and_child_fields():
    service = GuidaPraticaService(kb_path=FULL_KB)

    guida = service.get_guidance("100011")
    field_ids = {field.get("id") for field in guida["atto_principale"]["campi_obbligatori"]}

    assert "precetto_estremi" in field_ids
    assert "procedura_esecutiva_in_corso" in field_ids
    assert guida["coverage"]["level"] == "curata"


def test_sparse_curated_items_are_now_operational_and_not_partial():
    service = GuidaPraticaService(kb_path=FULL_KB)

    guida = service.get_guidance("150001")

    assert guida["coverage"]["level"] == "curata"
    assert guida["coverage"]["needs_reviewer"] is False
    assert guida["codice_deposito"]["depositabile"] is True
    assert guida["atto_principale"]["campi_obbligatori"]
    assert guida["allegati_obbligatori"]
    assert guida["adempimenti_propedeutici"]


def test_v4_addendum_and_impresa_codes_are_loaded_from_sections():
    service = GuidaPraticaService(kb_path=FULL_KB)

    for codice in ["181003", "110000"]:
        guida = service.get_guidance(codice)
        assert guida["codice"] == codice
        assert guida["denominazione"]
        assert guida["coverage"]["level"] == "curata"
        assert guida["atto_principale"]["campi_obbligatori"]


def test_v4_top9_high_priority_enriches_decreto_ingiuntivo():
    service = GuidaPraticaService(kb_path=FULL_KB)

    guida = service.get_guidance("010001")
    fields = {field.get("id") for field in guida["atto_principale"].get("campi_obbligatori", [])}

    assert "importo_capitale" in fields
    assert len(guida.get("allegati_obbligatori") or []) >= 5
    assert "top9" in " ".join(guida.get("_source_files") or []).lower() or guida["coverage"]["level"] == "curata"


def test_all_official_pst_xsd_codes_have_curated_operational_guidance():
    service = GuidaPraticaService(kb_path=FULL_KB)
    official_codes = [row["codice"] for row in list_codici_oggetto_pst()]
    failures: list[tuple[str, str]] = []

    assert len(official_codes) == 1018
    for codice in official_codes:
        guida = service.get_guidance(codice)
        atto = guida.get("atto_principale") or {}
        if (
            guida["coverage"]["level"] != "curata"
            or guida["coverage"]["needs_reviewer"]
            or not guida.get("allegati_obbligatori")
            or not guida.get("adempimenti_propedeutici")
            or not atto.get("campi_obbligatori")
            or not (guida.get("codice_deposito") or {}).get("depositabile")
        ):
            failures.append((codice, guida.get("denominazione", "")))

    assert failures == []


def test_logical_aliases_remain_internal_and_block_deposit_generation():
    service = GuidaPraticaService(kb_path=FULL_KB)

    for codice in ["ESEC_MOB_001", "LAV_LIC_001"]:
        assert not looks_like_codice_oggetto_pst(codice)
        assert codice_oggetto_pst_entry(codice) is None

        guida = service.get_guidance(codice)
        checklist = service.get_checklist(codice, {})

        assert guida["coverage"]["level"] == "curata"
        assert guida["codice_deposito"]["depositabile"] is False
        assert checklist["pronto_per_generazione"] is False
        assert any(blocker.get("type") == "codice_deposito_non_ufficiale" for blocker in checklist["blockers"])


def test_official_alphanumeric_codes_are_valid_and_depositable():
    service = GuidaPraticaService(kb_path=FULL_KB)

    guida = service.get_guidance("B02001")

    assert looks_like_codice_oggetto_pst("B02001") is True
    assert codice_oggetto_pst_entry("B02001") is not None
    assert guida["coverage"]["level"] == "curata"
    assert guida["codice_deposito"]["depositabile"] is True
    assert guida["atto_principale"]["campi_obbligatori"]


def test_top9_set2_part1_integrates_official_and_internal_guides():
    service = GuidaPraticaService(kb_path=FULL_KB)

    expected = {
        "111021": True,
        "620001": True,
        "100002": False,
        "413071": False,
        "143002": False,
    }
    for codice, depositabile in expected.items():
        guida = service.get_guidance(codice)

        assert guida["coverage"]["level"] == "curata"
        assert "kb_98_top9_set2_parte1.json" in (guida.get("_source_files") or [])
        assert guida["codice_deposito"]["depositabile"] is depositabile
        if depositabile:
            assert codice_oggetto_pst_entry(codice) is not None
        else:
            assert codice_oggetto_pst_entry(codice) is None


def test_top9_priority_preserves_user_hyper_detailed_fields_over_generated_profiles():
    service = GuidaPraticaService(kb_path=FULL_KB)

    expected_labels = {
        "111021": "Divorzio congiunto (su domanda di entrambi i coniugi)",
        "620001": "Esecuzione esattoriale immobiliare / Espropriazione immobiliare ordinaria",
        "220070": "Risarcimento danni da infortunio sul lavoro / malattia professionale",
    }
    for codice, expected_label in expected_labels.items():
        guida = service.get_guidance(codice)

        assert guida["denominazione"] == expected_label
        assert any("top9" in source for source in (guida.get("_source_files") or []))


def test_top9_set2_part2_integrates_without_corrupting_official_codes():
    service = GuidaPraticaService(kb_path=FULL_KB)

    licenziamento = service.get_guidance("220101")
    assert licenziamento["coverage"]["level"] == "curata"
    assert licenziamento["codice_deposito"]["depositabile"] is True
    assert "kb_98_top9_set2_parte2.json" in (licenziamento.get("_source_files") or [])

    divisione = service.get_guidance("121003")
    assert divisione["coverage"]["level"] == "curata"
    assert divisione["codice_deposito"]["depositabile"] is False
    assert divisione["codice_originale_ricevuto"] == "121003"
    assert codice_oggetto_pst_entry("121003") is None

    tutela_ufficiale = service.get_guidance("413011")
    assert tutela_ufficiale["denominazione"] == "Provvedimenti urgenti prima dell'assunzione delle funzioni del tutore o del protutore (art. 361 c.c.)"
    assert tutela_ufficiale["codice_deposito"]["depositabile"] is True
    assert "kb_98_top9_set2_parte2.json" not in (tutela_ufficiale.get("_source_files") or [])

    tutela_guida = service.get_guidance("GUIDA_TUTELA_MINORI_ORDINARIA")
    assert tutela_guida["coverage"]["level"] == "curata"
    assert tutela_guida["codice_deposito"]["depositabile"] is False
    assert tutela_guida["codice_originale_ricevuto"] == "413011"
    assert "kb_98_top9_set2_parte2.json" in (tutela_guida.get("_source_files") or [])

    vendita_ufficiale = service.get_guidance("140012")
    assert vendita_ufficiale["denominazione"] == "Vendita di cose mobili"
    assert vendita_ufficiale["codice_deposito"]["depositabile"] is True
    assert "kb_98_top9_set2_parte2.json" not in (vendita_ufficiale.get("_source_files") or [])

    compravendita_guida = service.get_guidance("GUIDA_COMPRAVENDITA_IMMOBILIARE_RISOLUZIONE")
    assert compravendita_guida["coverage"]["level"] == "curata"
    assert compravendita_guida["codice_deposito"]["depositabile"] is False
    assert compravendita_guida["codice_originale_ricevuto"] == "140012"
    assert "kb_98_top9_set2_parte2.json" in (compravendita_guida.get("_source_files") or [])


def test_top9_set5_integrates_guides_without_corrupting_official_codes():
    service = GuidaPraticaService(kb_path=FULL_KB)

    for codice in ["411601", "102002", "151110", "220020"]:
        guida = service.get_guidance(codice)
        assert guida["coverage"]["level"] == "curata"
        assert guida["codice_deposito"]["depositabile"] is True
        assert any("kb_98_top9_set5" in source for source in (guida.get("_source_files") or []))
        assert guida["atto_principale"]["campi_obbligatori"]

    aliases = {
        "GUIDA_REGOLAMENTO_CONFINI_130032": "130032",
        "GUIDA_IMPUGNAZIONE_TESTAMENTO_120020": "120020",
        "GUIDA_RESPONSABILITA_NOTAIO_COMMERCIALISTA_143003": "143003",
        "GUIDA_CONSUMATORE_CLAUSOLE_VESSATORIE_180001": "180001",
        "GUIDA_AZIONE_NEGATORIA_SERVITU_POSSESSORIA_130031": "130031",
    }
    for alias, original_code in aliases.items():
        guida = service.get_guidance(alias)
        assert guida["coverage"]["level"] == "curata"
        assert guida["codice_deposito"]["depositabile"] is False
        assert guida["guida_interna_non_depositabile"] is True
        assert guida["depositabile"] is False
        assert guida["codice_originale_ricevuto"] == original_code
        assert any("kb_98_top9_set5" in source for source in (guida.get("_source_files") or []))

    assert service.get_guidance("130031")["denominazione"] == "Usufrutto"
    assert service.get_guidance("130032")["denominazione"] == "Abitazione - Uso"
    assert "ordinanza-ingiunzione" in service.get_guidance("180001")["denominazione"].lower()


def test_top9_set6_integrates_guides_without_corrupting_official_codes():
    service = GuidaPraticaService(kb_path=FULL_KB)

    separazione = service.get_guidance("111003")
    assert separazione["coverage"]["level"] == "curata"
    assert separazione["codice_deposito"]["depositabile"] is True
    assert "Separazione consensuale" in separazione["denominazione"]
    assert "kb_98_top9_set6_parte2.json" in (separazione.get("_source_files") or [])

    aliases = {
        "GUIDA_PRELIMINARE_COMPRAVENDITA_2932_140002": "140002",
        "GUIDA_IMPUGNAZIONE_DELIBERE_ASSEMBLEARI_155001": "155001",
        "GUIDA_LICENZIAMENTO_DISCIPLINARE_220003": "220003",
        "GUIDA_OPPOSIZIONE_CARTELLA_ESATTORIALE_191001": "191001",
        "GUIDA_IMMISSIONI_INTOLLERABILI_130012": "130012",
        "GUIDA_EREDITA_GIACENTE_413021": "413021",
        "GUIDA_OPPOSIZIONE_SANZIONE_AMMINISTRATIVA_240001": "240001",
        "GUIDA_DEMANSIONAMENTO_DEQUALIFICAZIONE_220030": "220030",
    }
    for alias, original_code in aliases.items():
        guida = service.get_guidance(alias)

        assert not looks_like_codice_oggetto_pst(alias)
        assert codice_oggetto_pst_entry(alias) is None
        assert guida["coverage"]["level"] == "curata"
        assert guida["codice_deposito"]["depositabile"] is False
        assert guida["guida_interna_non_depositabile"] is True
        assert guida["depositabile"] is False
        assert guida["codice_originale_ricevuto"] == original_code
        assert any("kb_98_top9_set6" in source for source in (guida.get("_source_files") or []))

    assert service.get_guidance("140002")["denominazione"] == "Arbitraggio - Perizia contrattuale"
    assert service.get_guidance("220003")["denominazione"] == "lavoro interinale"
    assert service.get_guidance("220030")["denominazione"] == "trasferimento del lavoratore"
    assert service.get_guidance("130121")["codice_deposito"]["depositabile"] is True


def test_top9_set7_integrates_guides_without_corrupting_official_codes():
    service = GuidaPraticaService(kb_path=FULL_KB)

    official_codes = {
        "011001": "Sequestro conservativo",
        "170001": "Azione di nullità o decadenza di marchio",
    }
    for codice, expected_label in official_codes.items():
        guida = service.get_guidance(codice)

        assert guida["coverage"]["level"] == "curata"
        assert guida["codice_deposito"]["depositabile"] is True
        assert expected_label in guida["denominazione"]
        assert any("kb_98_top9_set7" in source for source in (guida.get("_source_files") or []))
        assert guida["atto_principale"]["campi_obbligatori"]

    aliases = {
        "GUIDA_GARANZIA_VIZI_COSA_VENDUTA_140011": "140011",
        "GUIDA_RESPONSABILITA_COSE_CUSTODIA_160021": "160021",
        "GUIDA_DISTANZE_LEGALI_COSTRUZIONI_130011": "130011",
        "GUIDA_SCIOGLIMENTO_SOCIETA_PERSONE_211001": "211001",
        "GUIDA_TUTELA_MAGGIORE_GRAVE_HANDICAP_413051": "413051",
        "GUIDA_RISOLUZIONE_MUTUO_DECADENZA_TERMINE_142001": "142001",
        "GUIDA_OPPOSIZIONE_PRECETTO_199001": "199001",
    }
    for alias, original_code in aliases.items():
        guida = service.get_guidance(alias)
        checklist = service.get_checklist(alias, {})

        assert not looks_like_codice_oggetto_pst(alias)
        assert codice_oggetto_pst_entry(alias) is None
        assert guida["coverage"]["level"] == "curata"
        assert guida["codice_deposito"]["depositabile"] is False
        assert checklist["pronto_per_generazione"] is False
        assert guida["guida_interna_non_depositabile"] is True
        assert guida["depositabile"] is False
        assert guida["codice_originale_ricevuto"] == original_code
        assert any("kb_98_top9_set7" in source for source in (guida.get("_source_files") or []))

    assert service.get_guidance("140011")["denominazione"] == "Vendita di cose immobili"
    assert service.get_guidance("130011")["denominazione"] == "Superficie"
    assert service.get_guidance("211001")["denominazione"].casefold() == "sequestro conservativo"
    assert service.get_guidance("142001")["denominazione"] == "Prestazione d'opera intellettuale"
    assert service.get_guidance("100001")["codice_deposito"]["depositabile"] is True
    assert service.get_guidance("145013")["codice_deposito"]["depositabile"] is True


def test_fascicolo_without_code_gets_practical_suggestion_from_object():
    service = GuidaPraticaService(kb_path=FULL_KB)

    match = service.suggest_guidance_from_fascicolo(
        {
            "titolo": "RG 466/2023 - Azioni di competenza del Giudice di Pace in materia di risarcimento danno",
            "oggetto": "Azioni di competenza del Giudice di Pace in materia di risarcimento danno",
            "codice_oggetto_pst": "",
        }
    )

    assert match is not None
    assert match["codice"] == "145009"
    assert match["confirmation_required"] is True
    assert "deposito" not in match["message"].casefold()

    guida = service.get_guidance(match["codice"])
    assert guida["coverage"]["level"] == "curata"
    assert guida["codice_deposito"]["depositabile"] is True
