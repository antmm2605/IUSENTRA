from __future__ import annotations

from dataclasses import dataclass

import pytest

from pct.editor_ai.template_resolver import EditorAITemplateResolver
from pct.editor_ai.validators import EditorAIValidationError


@dataclass
class FakeFascicolo:
    tipo: str = "civile"


class FakeTemplateRepository:
    def __init__(self):
        self.rows = [
            {
                "id": "ricorso_civile",
                "titolo": "Ricorso civile",
                "area": "civile",
                "campi_guidati": [{"name": "cliente", "label": "Cliente", "required": True}],
                "link_compilatore_code": "ricorso",
            }
        ]

    def tutti(self):
        return list(self.rows)

    def get(self, template_id):
        return next((dict(row) for row in self.rows if row["id"] == template_id), None)


def test_lista_template_reali_da_repository():
    resolver = EditorAITemplateResolver(FakeTemplateRepository())

    templates = resolver.list_available_templates_for_fascicolo(FakeFascicolo())

    assert templates
    assert templates[0]["id"] == "ricorso_civile"


def test_template_mancante_produce_errore_controllato():
    resolver = EditorAITemplateResolver(FakeTemplateRepository())

    with pytest.raises(EditorAIValidationError):
        resolver.resolve_template_for_tipo_atto(tipo_atto="", template_id="non_esiste")


def test_requirements_template_validati_senza_inventare_dati():
    resolver = EditorAITemplateResolver(FakeTemplateRepository())
    template = resolver.resolve_template_for_tipo_atto(tipo_atto="Ricorso civile", template_id="ricorso_civile")

    missing = resolver.validate_template_requirements(template, {"facts": {"oggetto": "Opposizione"}})

    assert "Cliente" in missing
