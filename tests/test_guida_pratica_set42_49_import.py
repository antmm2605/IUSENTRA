from __future__ import annotations

import json
import re
from pathlib import Path

from pct.guida_pratica import GuidaPraticaService
from scripts.import_guida_pratica_termini_processuali import collect_terms

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATTERN = re.compile(r"kb_98_set(?:42|43|44|45|46|47|48|49)_p\d+\.json$")
SET42_49_MODULES = sorted(
    path
    for path in (ROOT / "pct" / "data" / "legal_knowledge_base_modules").glob("kb_98_set*_p*.json")
    if MODULE_PATTERN.match(path.name)
)
IMPORT_REPORT = ROOT / "artifacts" / "guida-pratica" / "kb-set42-43-44-45-46-47-48-49-import-summary.json"
TERMS_REPORT = ROOT / "artifacts" / "guida-pratica" / "termini-processuali-import-2026-08-15-set42-49.json"
USER_MATERIAL_AUDIT = (
    ROOT / "artifacts" / "guida-pratica" / "guida-pratica-user-material-field-audit-2026-08-15-set42-49.json"
)
VALIDATION_REPORT = ROOT / "artifacts" / "guida-pratica" / "guida-pratica-audit-2026-08-15-set42-49.json"


def _records() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in SET42_49_MODULES:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(item for item in payload.get("codici_materia", []) if isinstance(item, dict))
    return rows


def test_set42_49_importa_tutti_i_moduli_nuovi_e_preserva_il_codice_di_deposito():
    rows = _records()
    report = json.loads(IMPORT_REPORT.read_text(encoding="utf-8"))

    assert len(SET42_49_MODULES) == 80
    assert len(rows) == 399
    assert sum(len(item.get("termini_processuali") or []) for item in rows) == 399
    assert report["records_received"] == 400
    assert report["records_integrated"] == 399
    assert report["termini_processuali_raw"] == 399
    assert report["official_depositable_kept"] == []
    assert len(report["internal_non_depositable_aliases"]) == 399
    assert all(item.get("guida_interna_non_depositabile") is True for item in rows)
    assert all(item.get("depositabile") is False for item in rows)
    assert all(item.get("codice_deposito_automatico") is False for item in rows)


def test_set42_49_deduplica_la_scheda_confliggente_sulla_guida_canonica():
    rows = _records()
    report = json.loads(IMPORT_REPORT.read_text(encoding="utf-8"))
    skipped = report["deduplicati_su_guida_esistente"]

    assert [item["source_codice"] for item in skipped] == ["415120"]
    assert skipped[0]["canonical_code"] == (
        "GUIDA_ESECUTORE_TESTAMENTARIO_NOMINA_POTERI_E_RESPONSABILIT_ARTT_700_712_C_C_415055"
    )
    assert all(item.get("codice_originale_ricevuto") != "415120" for item in rows)

    service = GuidaPraticaService()
    canonical = service.get_guidance(skipped[0]["canonical_code"])
    imported = service.get_guidance(
        "GUIDA_CONTRATTO_DI_PERMUTA_GARANZIA_PER_EVIZIONE_VIZI_DELLA_COSA_E_RISOLUZIONE_130370"
    )

    assert canonical["codice_deposito"]["depositabile"] is False
    assert imported["codice_deposito"]["depositabile"] is False
    assert imported["termini_processuali"]
    assert imported["fonti_verifica_web"]


def test_set42_49_propagano_termini_audit_e_copertura_guida():
    terms = collect_terms(SET42_49_MODULES)
    terms_report = json.loads(TERMS_REPORT.read_text(encoding="utf-8"))
    material_audit = json.loads(USER_MATERIAL_AUDIT.read_text(encoding="utf-8"))["summary"]
    validation = json.loads(VALIDATION_REPORT.read_text(encoding="utf-8"))

    assert len(terms) == 399
    assert terms_report["records"] == 4307
    assert material_audit["records_checked"] == 1145
    assert material_audit["lost_from_software"] == 0
    assert material_audit["missing_full_kb_when_source_present"] == 0
    assert material_audit["missing_service_when_source_present"] == 0
    assert material_audit["missing_lex_support_when_source_present"] == 0
    assert validation["ok"] is True
    assert validation["official_coverage"]["official_codes_curated"] == 1018
    assert validation["official_coverage"]["official_codes_without_curated_guidance"] == 0
