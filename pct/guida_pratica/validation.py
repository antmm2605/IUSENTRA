"""Validazione business della Guida Pratica.

Questo modulo non sostituisce la validazione XSD ministeriale già presente nel prodotto.
Produce errori applicativi leggibili da usare prima della generazione/deposito dell'atto.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .service import GuidaPraticaService


@dataclass(slots=True)
class GuidaValidationResult:
    valid: bool
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    def to_payload(self) -> dict[str, Any]:
        return {"valid": self.valid, "errors": self.errors, "warnings": self.warnings}


class GuidaPraticaValidationEngine:
    """Validazione dei requisiti pratici prima di generazione/deposito."""

    def __init__(self, service: GuidaPraticaService | None = None) -> None:
        self.service = service or GuidaPraticaService()

    def validate_business_rules(self, codice_materia: str, atto_data: dict[str, Any]) -> GuidaValidationResult:
        checklist = self.service.get_checklist(codice_materia, atto_data)
        errors = [item for item in checklist.get("blockers", []) if item.get("bloccante")]
        warnings = [item for item in checklist.get("blockers", []) if not item.get("bloccante")]
        return GuidaValidationResult(valid=not errors, errors=errors, warnings=warnings)
