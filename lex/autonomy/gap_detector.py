"""Rilevatore deterministico delle lacune di conoscenza di Lex.

Cinque regole (R1-R5), tutte spiegabili e con evidenze (record_id della
memoria). Nessuna euristica opaca: ogni UnknownConcept dichiara la regola che
lo ha generato e perché. Ordinamento stabile per (-priority, stable_id).
"""

from __future__ import annotations

from collections import Counter

from lex.autonomy.models import UnknownConcept
from lex.knowledge.concept_graph import ConceptGraph
from lex.knowledge.knowledge_base import KnowledgeBase

# Tipi di citazione che indicano una NORMA da leggere alla fonte.
_NORM_REFERENCE_TYPES = frozenset({"article", "act", "eu_act", "celex"})
_MIN_NORM_CONFIDENCE = 0.85
_MIN_TERM_OCCURRENCES = 2
_WEAK_OFFICIAL_RATIO = 0.42  # RELIABILITY_THRESHOLDS["medium"] del Source Policy System


def detect_gaps(
    knowledge: KnowledgeBase,
    graph: ConceptGraph,
    *,
    min_sources_per_area: int = 2,
) -> list[UnknownConcept]:
    """Applica R1-R5 alla memoria corrente e restituisce le lacune ordinate."""

    citations = knowledge.load("citations")
    readings = knowledge.load("source_readings")
    terms = knowledge.load("legal_terms")
    trust = knowledge.load("trust_assessments")

    read_norms = {
        str(normalized).casefold()
        for record in readings
        for normalized in (record.get("payload") or {}).get("citations_normalized") or []
    }
    readings_ok_by_area: Counter[str] = Counter()
    for record in readings:
        payload = record.get("payload") or {}
        if str(payload.get("status") or "") == "ok":
            readings_ok_by_area[str(payload.get("area") or "")] += 1

    gaps: list[UnknownConcept] = []
    gaps.extend(_r1_norme_citate_non_lette(citations, read_norms))
    gaps.extend(_r2_termini_ricorrenti_sconosciuti(terms, graph))
    gaps.extend(_r3_aree_scoperte(citations, terms, readings_ok_by_area, min_sources_per_area))
    gaps.extend(_r4_fonti_deboli(trust))
    gaps.extend(_r5_concetti_isolati(graph))

    deduped: dict[str, UnknownConcept] = {}
    for gap in gaps:
        deduped.setdefault(gap.stable_id(), gap)
    return sorted(deduped.values(), key=lambda item: (-item.priority, item.stable_id()))


def _r1_norme_citate_non_lette(citations: list[dict], read_norms: set[str]) -> list[UnknownConcept]:
    """R1: norma citata con confidenza alta ma mai letta alla fonte ufficiale."""

    gaps: list[UnknownConcept] = []
    seen: set[str] = set()
    for record in citations:
        payload = record.get("payload") or {}
        reference_type = str(payload.get("reference_type") or "")
        normalized = str(payload.get("normalized_text") or "").strip()
        confidence = float(payload.get("confidence") or 0.0)
        key = normalized.casefold()
        if (
            reference_type not in _NORM_REFERENCE_TYPES
            or confidence < _MIN_NORM_CONFIDENCE
            or not normalized
            or key in seen
            or key in read_norms
        ):
            continue
        seen.add(key)
        gaps.append(
            UnknownConcept(
                concept=normalized,
                kind="norma_non_letta",
                area=str(payload.get("area") or ""),
                reason="Norma citata nei testi analizzati ma mai letta da una fonte ufficiale.",
                priority=0.9,
                confidence=confidence,
                evidence=[str(record.get("record_id") or "")],
            )
        )
    return gaps


def _r2_termini_ricorrenti_sconosciuti(terms: list[dict], graph: ConceptGraph) -> list[UnknownConcept]:
    """R2: termine candidato ricorrente, assente da ontologia e grafo."""

    gaps: list[UnknownConcept] = []
    for record in terms:
        payload = record.get("payload") or {}
        if str(payload.get("kind") or "") != "candidato":
            continue
        occurrences = int(payload.get("occurrences") or 0)
        normalized = str(payload.get("normalized") or "").strip()
        if occurrences < _MIN_TERM_OCCURRENCES or not normalized:
            continue
        if graph.has_node("concetto", normalized):
            continue
        gaps.append(
            UnknownConcept(
                concept=normalized,
                kind="termine_sconosciuto",
                area=str(payload.get("area") or ""),
                reason=f"Termine ricorrente ({occurrences} occorrenze) non classificato nell'ontologia.",
                priority=min(0.9, 0.6 + 0.1 * min(occurrences, 3)),
                confidence=float(payload.get("confidence") or 0.6),
                evidence=[str(record.get("record_id") or "")],
            )
        )
    return gaps


def _r3_aree_scoperte(
    citations: list[dict],
    terms: list[dict],
    readings_ok_by_area: Counter[str],
    min_sources_per_area: int,
) -> list[UnknownConcept]:
    """R3: area rilevata nei testi con meno letture ufficiali del minimo."""

    areas: Counter[str] = Counter()
    evidence_by_area: dict[str, list[str]] = {}
    for record in [*citations, *terms]:
        payload = record.get("payload") or {}
        area = str(payload.get("area") or "").strip()
        if area:
            areas[area] += 1
            evidence_by_area.setdefault(area, []).append(str(record.get("record_id") or ""))
    gaps: list[UnknownConcept] = []
    for area, _mentions in areas.items():
        letture = int(readings_ok_by_area.get(area, 0))
        if letture >= min_sources_per_area:
            continue
        gaps.append(
            UnknownConcept(
                concept=f"copertura area {area}",
                kind="area_scoperta",
                area=area,
                reason=(
                    f"Area '{area}' presente nei testi ma con {letture} letture ufficiali "
                    f"(minimo richiesto: {min_sources_per_area})."
                ),
                priority=0.7,
                confidence=0.8,
                evidence=evidence_by_area.get(area, [])[:5],
            )
        )
    return gaps


def _r4_fonti_deboli(trust: list[dict]) -> list[UnknownConcept]:
    """R4: area con rapporto di ufficialità pesato sotto la soglia media."""

    from lex.research.source_policy.catalog import SOURCE_WEIGHTS  # dati puri

    weights_by_area: dict[str, list[float]] = {}
    evidence_by_area: dict[str, list[str]] = {}
    for record in trust:
        payload = record.get("payload") or {}
        area = str(payload.get("area") or "").strip()
        if not area:
            continue
        tier = str(payload.get("tier") or "unknown")
        weights_by_area.setdefault(area, []).append(float(SOURCE_WEIGHTS.get(tier, 0.0)))
        evidence_by_area.setdefault(area, []).append(str(record.get("record_id") or ""))
    gaps: list[UnknownConcept] = []
    for area, weights in weights_by_area.items():
        ratio = sum(weights) / len(weights)
        if ratio >= _WEAK_OFFICIAL_RATIO:
            continue
        gaps.append(
            UnknownConcept(
                concept=f"affidabilità fonti area {area}",
                kind="fonte_debole",
                area=area,
                reason=f"Rapporto di ufficialità pesato {ratio:.2f} sotto la soglia {_WEAK_OFFICIAL_RATIO}.",
                priority=0.5,
                confidence=0.75,
                evidence=evidence_by_area.get(area, [])[:5],
            )
        )
    return gaps


def _r5_concetti_isolati(graph: ConceptGraph) -> list[UnknownConcept]:
    """R5: nodo del grafo osservato più volte ma senza alcuna relazione."""

    gaps: list[UnknownConcept] = []
    nodes = graph.nodes()
    for identifier in graph.isolated_nodes(min_observations=_MIN_TERM_OCCURRENCES):
        node = nodes.get(identifier) or {}
        if str(node.get("kind") or "") != "concetto":
            continue
        label = str(node.get("label") or identifier)
        gaps.append(
            UnknownConcept(
                concept=label,
                kind="concetto_isolato",
                area=str(node.get("area") or ""),
                reason="Concetto osservato più volte ma privo di relazioni con norme o fonti.",
                priority=0.4,
                confidence=0.7,
                evidence=[identifier],
            )
        )
    return gaps


__all__ = ["detect_gaps"]
