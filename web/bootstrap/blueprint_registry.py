"""Registro dichiarativo dei blueprint Flask del gestionale."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module

from flask import Blueprint


@dataclass(frozen=True)
class BlueprintRegistration:
    """Definisce un blueprint registrabile e la sua policy minima."""

    name: str
    module_path: str
    attribute_name: str
    url_prefix: str = ""
    feature_flag: str = ""

    def is_enabled(self, config: dict[str, object] | None = None) -> bool:
        if not self.feature_flag:
            return True
        return bool((config or {}).get(self.feature_flag, False))

    def load_blueprint(self) -> Blueprint:
        module = import_module(self.module_path)
        blueprint = getattr(module, self.attribute_name)
        if not isinstance(blueprint, Blueprint):  # pragma: no cover - guardrail difensivo
            raise TypeError(
                f"{self.module_path}.{self.attribute_name} non espone un Blueprint Flask valido."
            )
        return blueprint


BLUEPRINT_REGISTRY: tuple[BlueprintRegistration, ...] = (
    BlueprintRegistration("api_v1", "web.blueprints.api_v1", "api_v1", "/api/v1"),
    BlueprintRegistration("legal_audit", "audit.routes", "audit_blueprint", ""),
    BlueprintRegistration("api_v1_react", "web.blueprints.api_v1_react", "api_v1_react", "/api/v1/ui"),
    BlueprintRegistration("pec_pipeline_api", "web.blueprints.pec_pipeline_api", "pec_pipeline_api", "/api/pec"),
    BlueprintRegistration(
        "api_v1_legal_skills",
        "web.blueprints.api_v1_legal_skills",
        "api_v1_legal_skills",
        "/api/v1/legal-skills",
    ),
    BlueprintRegistration("api_v1_documenti_ai", "web.blueprints.api_v1_documenti_ai", "api_v1_documenti_ai", "/api/v1/ui"),
    BlueprintRegistration("api_v1_editor_ai", "web.blueprints.api_v1_editor_ai", "api_v1_editor_ai", "/api/v1/ui"),
    BlueprintRegistration("react_shell", "web.blueprints.react_shell", "react_shell", ""),
    BlueprintRegistration("portale", "web.blueprints.portale", "portale", "/portale"),
    BlueprintRegistration("fatturazione", "web.blueprints.fatturazione", "fatturazione", "/fatturazione"),
    BlueprintRegistration("notifiche", "web.blueprints.notifiche", "notifiche", "/notifiche"),
    BlueprintRegistration("template_atti", "web.blueprints.template_atti", "template_atti", "/template-atti"),
    BlueprintRegistration("statistiche", "web.blueprints.statistiche", "statistiche", "/statistiche"),
    BlueprintRegistration("legal_intelligence", "web.blueprints.legal_intelligence", "legal_intelligence", "/legal-intelligence"),
    BlueprintRegistration("ricerca_legale", "web.blueprints.legal_intelligence", "legal_intelligence", "/ricerca-legale"),
    BlueprintRegistration("giurisprudenza", "web.blueprints.giurisprudenza", "giurisprudenza", "/giurisprudenza"),
    BlueprintRegistration("export_csv", "web.blueprints.export_csv", "export_csv", "/export"),
    BlueprintRegistration("pagamenti", "web.blueprints.pagamenti", "pagamenti", "/pagamenti"),
    BlueprintRegistration("admin", "web.blueprints.admin", "admin_bp", "/admin"),
    BlueprintRegistration(
        "installation_pack_admin",
        "web.blueprints.installation_pack_admin",
        "installation_pack_admin",
        "",
    ),
    BlueprintRegistration(
        "operational_resilience_admin",
        "web.blueprints.operational_resilience_admin",
        "operational_resilience_admin",
        "",
    ),
    BlueprintRegistration(
        "server_maintenance_admin",
        "web.blueprints.server_maintenance_admin",
        "server_maintenance_admin",
        "",
    ),
    BlueprintRegistration("scheduler_admin", "web.blueprints.scheduler_admin", "scheduler_admin", ""),
    BlueprintRegistration("support_remote", "web.blueprints.support_remote", "support_remote", ""),
    BlueprintRegistration("studio_site_admin", "web.blueprints.studio_site_admin", "studio_site_admin", ""),
    BlueprintRegistration("studio_site", "web.blueprints.studio_site", "studio_site", ""),
    BlueprintRegistration("studio_site_builder", "web.blueprints.studio_site_builder", "studio_site_builder", ""),
    BlueprintRegistration("studio_site_public", "web.blueprints.studio_site_public", "studio_site_public", ""),
    BlueprintRegistration("global_search", "web.blueprints.global_search", "global_search", ""),
    BlueprintRegistration("api_topbar", "web.blueprints.topbar", "topbar", ""),
    BlueprintRegistration("api_push_notifications", "web.blueprints.push_notifications", "push_notifications", ""),
    BlueprintRegistration("terminology_aliases", "web.blueprints.terminology_aliases", "terminology_aliases", ""),
    BlueprintRegistration("legal_coverage_admin", "web.blueprints.legal_coverage_admin", "legal_coverage_admin", "/admin/copertura-ai"),
    BlueprintRegistration("legal_updates_admin", "web.blueprints.legal_updates_admin", "legal_updates_admin", "/admin/aggiornamenti-legali"),
    BlueprintRegistration("impostazioni", "web.blueprints.impostazioni", "impostazioni", ""),
    BlueprintRegistration("email_client", "web.blueprints.email_client", "email_client", "/email"),
    BlueprintRegistration("email_ordinaria", "web.blueprints.email_ordinaria", "email_ordinaria", "/email-ordinaria"),
    BlueprintRegistration("assistente", "web.blueprints.assistente", "assistente", ""),
    BlueprintRegistration("preventivi", "web.blueprints.preventivi", "preventivi", "/preventivi"),
    BlueprintRegistration("strumenti_legali", "web.blueprints.strumenti_legali", "strumenti_legali", "/strumenti-legali"),
    BlueprintRegistration("sigp_redirects", "web.blueprints.sigp_redirects", "sigp_redirects", ""),
    BlueprintRegistration("applicazioni", "web.blueprints.applicazioni", "applicazioni", "/applicazioni"),
    BlueprintRegistration("wizard_pro", "web.blueprints.wizard_pro", "wizard_pro_bp", "/wizard-pro"),
)
