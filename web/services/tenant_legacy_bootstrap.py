"""Bootstrap compatibilita' per dati legacy root -> tenant."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from flask import Flask

from pct.legal_update_repository import LegalUpdateDbConfig
from pct.tenant import GestioneTenant


LEGACY_RUNTIME_DATA_MAPPING: dict[str, str] = {
    "CLIENTI_DB": "CLIENTI_DB",
    "CONDIVISIONI_DB": "CONDIVISIONI_DB",
    "NOTE_FALDONE_DB": "NOTE_FALDONE_DB",
    "FASCICOLI_DB": "FASCICOLI_DB",
    "FASCICOLI_DOCS": "FASCICOLI_DOCS",
    "FASCICOLI_ARCH": "FASCICOLI_ARCH",
    "AGENDA_DB": "AGENDA_DB",
    "SCADENZIARIO_DB": "SCADENZIARIO_DB",
    "TIMESHEET_DB": "TIMESHEET_DB",
    "MESSAGGI_DB": "MESSAGGI_DB",
    "EMAIL_CASELLA_DB": "EMAIL_CASELLA_DB",
    "EMAIL_ORDINARIA_DB": "EMAIL_ORDINARIA_DB",
    "PRIVACY_DB": "PRIVACY_DB",
    "PORTALE_DB": "PORTALE_DB",
    "FATTURAZIONE_DB": "FATTURAZIONE_DB",
    "PREVENTIVI_DB": "PREVENTIVI_DB",
    "SOGGETTI_DB": "SOGGETTI_DB",
    "SOGGETTI_PARTI_DB": "SOGGETTI_PARTI_DB",
    "TEMPLATE_ATTI_DB": "TEMPLATE_ATTI_DB",
    "TEMPLATE_ATTI_PREFS_DB": "TEMPLATE_ATTI_PREFS_DB",
    "WIZARD_PRO_DB": "WIZARD_PRO_DB",
    "CONFIG_STUDIO_DB": "STUDIO_CONFIG",
    "SEARCH_INDEX": "SEARCH_INDEX",
    "LEGAL_INTELLIGENCE_DB": "LEGAL_INTELLIGENCE_DB",
    "NORMATIVE_TABLES_DB": "NORMATIVE_TABLES_DB",
    "GIURISPRUDENZA_DB": "GIURISPRUDENZA_DB",
    "WORKSPACE_INTELLIGENCE_DB": "WORKSPACE_INTELLIGENCE_DB",
    "VALIDATION_RUNS_DB": "VALIDATION_RUNS_DB",
    "REDACTION_ASSISTANT_DB": "REDACTION_ASSISTANT_DB",
}


def legacy_root_data_paths(config: Mapping[str, Any]) -> dict[str, str]:
    paths = {
        target_key: str(config.get(source_key, "") or "")
        for target_key, source_key in LEGACY_RUNTIME_DATA_MAPPING.items()
        if str(config.get(source_key, "") or "").strip()
    }
    intelligence_anchor = str(config.get("LEGAL_INTELLIGENCE_DB", "") or "").strip()
    if intelligence_anchor:
        cfg = LegalUpdateDbConfig.from_anchor(intelligence_anchor)
        paths["LEGAL_UPDATES_DB"] = cfg.db_path
        paths["LEGAL_UPDATES_JSON"] = cfg.json_path
    return paths


def bootstrap_legacy_tenant_runtime_data(
    app: Flask,
    *,
    tenant_slug: str | None = None,
) -> dict[str, Any]:
    if not app.config.get("MULTI_TENANT"):
        return {"ok": False, "reason": "single-tenant", "target_slug": ""}

    tenants = GestioneTenant(registry_path=app.config["TENANTS_REGISTRY"])
    legacy_paths = legacy_root_data_paths(app.config)
    resolved_target = tenants.resolve_legacy_bootstrap_target_slug(legacy_paths)
    requested_tenant = str(tenant_slug or "").strip().lower()

    if not resolved_target:
        return {"ok": False, "reason": "no-target", "target_slug": ""}
    if requested_tenant and requested_tenant != resolved_target:
        return {
            "ok": False,
            "reason": "target-mismatch",
            "target_slug": resolved_target,
        }

    result = tenants.bootstrap_legacy_runtime_data(resolved_target, legacy_paths)
    return {
        **result,
        "target_slug": resolved_target,
    }
