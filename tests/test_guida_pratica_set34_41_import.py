from __future__ import annotations

import json
import re
from pathlib import Path

from pct.guida_pratica import GuidaPraticaService
from scripts.import_guida_pratica_termini_processuali import collect_terms


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATTERN = re.compile(r"kb_98_set(?:34|35|37|38|39|40|41)_p\d+\.json$")
SET34_41_MODULES = sorted(
    path
    for path in (ROOT / "pct" / "data" / "legal_knowledge_base_modules").glob("kb_98_set*_p*.json")
    if MODULE_PATTERN.match(path.name)
)
IMPORT_REPORT = ROOT / "artifacts" / "guida-pratica" / "kb-set34-41-import-summary.json"
TERMS_REPORT = ROOT / "artifacts" / "guida-pratica" / "termini-processuali-import-2026-06-11-set34-41.json"
AUDIT_REPORT = (
    ROOT
    / "artifacts"
    / "guida-pratica"
    / "guida-pratica-user-material-field-audit-2026-06-11-set34-41.json"
)
VALIDATION_REPORT = ROOT / "artifacts" / "guida-pratica" / "guida-pratica-audit-2026-06-11-set34-41.json"
MISSING_CSV = (
    ROOT
    / "artifacts"
    / "guida-pratica"
    / "codici-ufficiali-senza-guida-curata-2026-06-11-set34-41.csv"
)


def _records() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in SET34_41_MODULES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(item for item in payload.get("codici_materia", []) if isinstance(item, dict))
    return rows


def test_set34_41_files_zip_integrati_in_sessantotto_moduli_e_trecentoquaranta_guide():
    rows = _records()
    report = json.loads(IMPORT_REPORT.read_text(encoding="utf-8"))

    assert len(SET34_41_MODULES) == 68
    assert len(rows) == 340
    assert sum(len(item.get("termini_processuali") or []) for item in rows) == 343
    assert report["records_received"] == 340
    assert report["records_integrated"] == 340
    assert report["official_depositable_kept"] == []
    assert len(report["internal_non_depositable_aliases"]) == 340
    assert all(item.get("guida_interna_non_depositabile") is True for item in rows)
    assert all(item.get("depositabile") is False for item in rows)
    assert all(item.get("codice_deposito_automatico") is False for item in rows)


def test_set34_41_codici_numerici_incoerenti_restano_guide_interne_non_depositabili():
    service = GuidaPraticaService()

    guida = service.get_guidance("GUIDA_ARBITRATO_IRRITUALE_VALIDITA_IMPUGNAZIONE_211010")

    assert guida["codice_originale_ricevuto"] == "211010"
    assert "808-ter" in guida["denominazione"]
    assert guida["codice_deposito"]["depositabile"] is False
    assert guida["codice_deposito"]["ufficiale"] is False
    assert "catalogo PST/XSD ufficiale" in guida["codice_deposito"]["messaggio"]
    assert guida["coverage"]["level"] == "curata"
    assert guida["termini_processuali"]
    assert guida["fonti_verifica_web"]


def test_set34_41_scadenziario_importa_termini_dai_moduli_versionati():
    rows = collect_terms(SET34_41_MODULES)
    report = json.loads(TERMS_REPORT.read_text(encoding="utf-8"))

    assert len(rows) == 343
    assert report["records"] == 3908
    assert report["calculable_templates"] == 1184
    assert report["by_phase"]["notifica"] >= 2180


def test_set34_41_audit_voce_per_voce_e_copertura_ufficiale_non_lasciano_mancanti():
    audit = json.loads(AUDIT_REPORT.read_text(encoding="utf-8"))["summary"]
    validation = json.loads(VALIDATION_REPORT.read_text(encoding="utf-8"))

    assert audit["records_checked"] == 746
    assert audit["source_fields_present"] == 11138
    assert audit["lost_from_software"] == 0
    assert audit["missing_full_kb_when_source_present"] == 0
    assert audit["missing_service_when_source_present"] == 0
    assert audit["missing_ui_support_when_source_present"] == 0
    assert audit["missing_lex_support_when_source_present"] == 0
    assert audit["scalar_values_changed_in_service"] == 0
    assert validation["official_coverage"]["total_official_codes"] == 1018
    assert validation["official_coverage"]["official_codes_curated"] == 1018
    assert validation["official_coverage"]["official_codes_without_curated_guidance"] == 0
    assert len(MISSING_CSV.read_text(encoding="utf-8").splitlines()) == 1
