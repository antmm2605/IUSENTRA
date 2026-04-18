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
    BlueprintRegistration("portale", "web.blueprints.portale", "portale", "/portale"),
    BlueprintRegistration("fatturazione", "web.blueprints.fatturazione", "fatturazione", "/fatturazione"),
    BlueprintRegistration("notifiche", "web.blueprints.notifiche", "notifiche", "/notifiche"),
    BlueprintRegistration("template_atti", "web.blueprints.template_atti", "template_atti", "/template-atti"),
    BlueprintRegistration("statistiche", "web.blueprints.statistiche", "statistiche", "/statistiche"),
    BlueprintRegistration("legal_intelligence", "web.blueprints.legal_intelligence", "legal_intelligence", "/legal-intelligence"),
    BlueprintRegistration("giurisprudenza", "web.blueprints.giurisprudenza", "giurisprudenza", "/giurisprudenza"),
    BlueprintRegistration("export_csv", "web.blueprints.export_csv", "export_csv", "/export"),
    BlueprintRegistration("pagamenti", "web.blueprints.pagamenti", "pagamenti", "/pagamenti"),
    BlueprintRegistration("admin", "web.blueprints.admin", "admin_bp", "/admin"),
    BlueprintRegistration("legal_coverage_admin", "web.blueprints.legal_coverage_admin", "legal_coverage_admin", "/admin/copertura-ai"),
    BlueprintRegistration("legal_updates_admin", "web.blueprints.legal_updates_admin", "legal_updates_admin", "/admin/aggiornamenti-legali"),
    BlueprintRegistration("impostazioni", "web.blueprints.impostazioni", "impostazioni", "/impostazioni"),
    BlueprintRegistration("email_client", "web.blueprints.email_client", "email_client", "/email"),
    BlueprintRegistration("assistente", "web.blueprints.assistente", "assistente", ""),
    BlueprintRegistration("preventivi", "web.blueprints.preventivi", "preventivi", "/preventivi"),
    BlueprintRegistration("strumenti_legali", "web.blueprints.strumenti_legali", "strumenti_legali", "/strumenti-legali"),
    BlueprintRegistration("applicazioni", "web.blueprints.applicazioni", "applicazioni", "/applicazioni"),
    BlueprintRegistration("wizard_pro", "web.blueprints.wizard_pro", "wizard_pro_bp", "/wizard-pro"),
)
