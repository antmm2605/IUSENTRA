from __future__ import annotations

from pathlib import Path
import sys

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
