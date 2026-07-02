"""Memoria durevole e ispezionabile dell'apprendimento di Lex.

Bounded context "knowledge": persistenza JSONL append-only (`KnowledgeBase`),
grafo dei concetti (`ConceptGraph`) e ontologia giuridica seed
(`LEGAL_ONTOLOGY`). Nessun modulo qui importa `lex.autonomy` (i record sono
dict generici): la direzione degli import resta learning/knowledge ← autonomy.
"""

from lex.knowledge.concept_graph import ConceptGraph
from lex.knowledge.knowledge_base import KnowledgeBase
from lex.knowledge.legal_ontology import (
    LEGAL_ONTOLOGY,
    is_known_concept,
    known_concepts,
    ontology_areas,
    primary_sources_for,
)

__all__ = [
    "LEGAL_ONTOLOGY",
    "ConceptGraph",
    "KnowledgeBase",
    "is_known_concept",
    "known_concepts",
    "ontology_areas",
    "primary_sources_for",
]
