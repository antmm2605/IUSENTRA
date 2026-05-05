"""Risoluzione template atti per generazione Editor AI."""

from __future__ import annotations

from typing import Any

from pct.template_catalog_service import build_template_catalog_items, get_template_catalog_item

from .validators import EditorAIValidationError, clean_text


def _template_to_dict(template: Any) -> dict[str, Any]:
    if template is None:
        return {}
    if isinstance(template, dict):
        return dict(template)
    to_dict = getattr(template, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    return dict(getattr(template, "__dict__", {}) or {})


class EditorAITemplateResolver:
    def __init__(self, template_repository: Any = None):
        self.template_repository = template_repository

    def list_available_templates_for_fascicolo(self, fascicolo: Any | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        if self.template_repository is not None:
            lister = getattr(self.template_repository, "tutti", None)
            if callable(lister):
                items.extend(_template_to_dict(item) for item in lister())
        if not items:
            items = list(build_template_catalog_items())

        area = clean_text(getattr(fascicolo, "tipo", "")).upper()
        if area:
            ranked = sorted(
                items,
                key=lambda item: (
                    0 if area and area.lower() in clean_text(item.get("area") or item.get("materia")).lower() else 1,
                    clean_text(item.get("titolo") or item.get("title")).casefold(),
                ),
            )
            return ranked
        return sorted(items, key=lambda item: clean_text(item.get("titolo") or item.get("title")).casefold())

    def resolve_template_for_tipo_atto(
        self,
        *,
        tipo_atto: str,
        template_id: str = "",
        fascicolo: Any | None = None,
    ) -> dict[str, Any]:
        requested_id = clean_text(template_id)
        if requested_id:
            template = self._get_template(requested_id)
            if not template:
                raise EditorAIValidationError("Template atto non trovato.")
            return template

        query = clean_text(tipo_atto)
        if not query:
            raise EditorAIValidationError("Tipo atto mancante.")

        candidates = self.list_available_templates_for_fascicolo(fascicolo)
        normalized_query = query.casefold()
        exact = next(
            (
                item
                for item in candidates
                if normalized_query
                in {
                    clean_text(item.get("id")).casefold(),
                    clean_text(item.get("codice")).casefold(),
                    clean_text(item.get("titolo")).casefold(),
                }
            ),
            None,
        )
        if exact:
            return exact
        scored = [
            item
            for item in candidates
            if normalized_query in clean_text(item.get("titolo") or item.get("name")).casefold()
            or normalized_query in clean_text(item.get("codice") or item.get("id")).casefold()
        ]
        if scored:
            return scored[0]
        fallback = next((item for item in candidates if clean_text(item.get("link_compilatore_code"))), None)
        if fallback:
            fallback = dict(fallback)
            fallback.setdefault("warnings", [])
            fallback["warnings"] = list(fallback.get("warnings") or []) + [
                "Template specifico non individuato: usata struttura generica governata del catalogo atti."
            ]
            return fallback
        raise EditorAIValidationError("Nessun template disponibile per il tipo atto richiesto.")

    def read_template_schema(self, template_id: str) -> dict[str, Any]:
        template = self._get_template(template_id)
        if not template:
            raise EditorAIValidationError("Template atto non trovato.")
        return {
            "id": clean_text(template.get("id") or template.get("codice") or template_id),
            "titolo": clean_text(template.get("titolo") or template.get("name")),
            "categoria": clean_text(template.get("categoria") or template.get("categoria_suite_label")),
            "area": clean_text(template.get("area") or template.get("materia")),
            "campi_guidati": list(template.get("campi_guidati") or template.get("campi_precompila") or []),
            "allegati_obbligatori": list(template.get("allegati_obbligatori") or template.get("allegati_essenziali") or []),
            "controlli_conformita": list(template.get("controlli_conformita") or template.get("checklist_conformita") or []),
            "corpo": str(template.get("corpo") or ""),
            "link_compilatore_code": clean_text(template.get("link_compilatore_code")),
            "depositabile": bool(template.get("depositabile", False)),
            "canale_telematico": clean_text(template.get("canale_telematico") or template.get("canale_deposito")),
        }

    def validate_template_requirements(self, template: dict[str, Any], context: dict[str, Any]) -> list[str]:
        missing: list[str] = []
        schema = self.read_template_schema(clean_text(template.get("id") or template.get("codice")))
        facts = context.get("facts") if isinstance(context, dict) else {}
        facts = facts if isinstance(facts, dict) else {}
        for field in schema.get("campi_guidati") or []:
            if not isinstance(field, dict):
                continue
            label = clean_text(field.get("label") or field.get("name"))
            name = clean_text(field.get("name"))
            required = bool(field.get("required") or field.get("obbligatorio"))
            if required and name and not clean_text(facts.get(name)):
                missing.append(label or name)
        if not clean_text(facts.get("cliente")):
            missing.append("Cliente")
        if not clean_text(facts.get("oggetto")):
            missing.append("Oggetto del fascicolo")
        return sorted(set(missing), key=str.casefold)

    def _get_template(self, template_id: str) -> dict[str, Any] | None:
        clean_id = clean_text(template_id)
        if not clean_id:
            return None
        if self.template_repository is not None:
            getter = getattr(self.template_repository, "get", None)
            if callable(getter):
                found = getter(clean_id)
                if found:
                    return _template_to_dict(found)
        catalog_item = get_template_catalog_item(clean_id)
        if catalog_item:
            return dict(catalog_item)
        for item in build_template_catalog_items():
            if clean_id.casefold() in {
                clean_text(item.get("id")).casefold(),
                clean_text(item.get("codice")).casefold(),
            }:
                return dict(item)
        return None
