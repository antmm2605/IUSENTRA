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
    assert "esecuzione_in_corso" in field_ids
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
