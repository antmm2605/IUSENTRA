"""Modulo Guida Pratica per codice materia / codice oggetto PST.

Il modulo tiene separata la conoscenza giuridica dal codice applicativo:
- `legal_knowledge_base.json` contiene le guide curate/revisionate;
- il catalogo PST/XSD esistente copre tutti i codici disponibili;
- i codici senza guida curata ricevono un profilo operativo base, marcato come da revisionare.
"""

from .service import GuidaPraticaService, GuidaPraticaError, normalize_codice_materia

__all__ = ["GuidaPraticaService", "GuidaPraticaError", "normalize_codice_materia"]
