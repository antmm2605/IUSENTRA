"""Generatore di proposte di miglioramento verificabili (mai applicate).

Catalogo deterministico P1-P5: ogni proposta indica modulo bersaglio, evidenze
(record_id della memoria), test suggerito e resta `requires_human_review=True`.
L'unica "apply" del sistema (`safety.refuse_apply`) solleva sempre: le proposte
si applicano solo a mano, con revisione.
"""

from __future__ import annotations

import re
from collections import Counter

from lex.autonomy.models import ImprovementProposal
from lex.autonomy.safety import assert_no_autonomous_code_write
from lex.knowledge.knowledge_base import KnowledgeBase

# P1: atti citati con sigle non ancora coperte dagli estrattori deterministici.
_UNRECOGNIZED_ACT_RE = re.compile(
    r"\b(?:D\.?\s*P\.?\s*C\.?\s*M\.?|T\.?U\.?[A-Z]{0,4})\s*(?:n\.?\s*)?[0-9]{1,4}(?:/[0-9]{2,4})?\b"
)
_MIN_ONTOLOGY_OCCURRENCES = 3


def propose_improvements(knowledge: KnowledgeBase) -> list[ImprovementProposal]:
    """Applica il catalogo P1-P5 alla memoria e restituisce le proposte."""

    assert_no_autonomous_code_write("improvement_proposer")

    readings = knowledge.load("source_readings")
    terms = knowledge.load("legal_terms")
    trust = knowledge.load("trust_assessments")
    questions = knowledge.load("research_questions")

    proposals: list[ImprovementProposal] = []
    proposals.extend(_p1_pattern_citazione(readings))
    proposals.extend(_p2_dominio_ufficiale_fuori_policy(trust))
    proposals.extend(_p3_area_keywords(questions))
    proposals.extend(_p4_ontologia(terms))
    proposals.extend(_p5_robots_su_tier1(readings, trust))

    deduped: dict[str, ImprovementProposal] = {}
    for proposal in proposals:
        deduped.setdefault(proposal.stable_id(), proposal)
    return sorted(deduped.values(), key=lambda item: (-item.confidence, item.stable_id()))


def _p1_pattern_citazione(readings: list[dict]) -> list[ImprovementProposal]:
    proposals: list[ImprovementProposal] = []
    seen: set[str] = set()
    for record in readings:
        payload = record.get("payload") or {}
        haystack = " ".join(
            [
                *(str(item) for item in payload.get("warnings") or []),
                str(payload.get("title") or ""),
            ]
        )
        recognized = " ".join(str(item) for item in payload.get("citations_normalized") or []).casefold()
        for match in _UNRECOGNIZED_ACT_RE.finditer(haystack):
            token = " ".join(match.group(0).split())
            key = token.casefold()
            if key in seen or key in recognized:
                continue
            seen.add(key)
            proposals.append(
                ImprovementProposal(
                    kind="pattern_citazione",
                    title=f"Estendere il riconoscimento citazioni al pattern '{token}'",
                    description=(
                        f"Il riferimento '{token}' compare nelle fonti lette ma non è coperto né da "
                        "pct/legal_reference_extractor.py né da NAMED_ACT_ALIASES: valutare l'aggiunta "
                        "del pattern (upstream in pct con regressioni PEC dedicate, oppure alias in "
                        "lex/learning/citation_extractor.py)."
                    ),
                    target_module="lex/learning/citation_extractor.py",
                    confidence=0.8,
                    evidence=[str(record.get("record_id") or "")],
                    suggested_tests=["lex/tests/unit/test_learning_citation_extractor.py::test_named_act_aliases"],
                )
            )
    return proposals


def _p2_dominio_ufficiale_fuori_policy(trust: list[dict]) -> list[ImprovementProposal]:
    rejected: Counter[tuple[str, str]] = Counter()
    evidence: dict[tuple[str, str], list[str]] = {}
    for record in trust:
        payload = record.get("payload") or {}
        if bool(payload.get("official")) and str(payload.get("tier")) == "unknown" and not payload.get("allowed_for_learning"):
            key = (str(payload.get("domain") or ""), str(payload.get("area") or ""))
            rejected[key] += 1
            evidence.setdefault(key, []).append(str(record.get("record_id") or ""))
    proposals: list[ImprovementProposal] = []
    for (domain, area), count in rejected.items():
        if count < 2 or not domain:
            continue
        proposals.append(
            ImprovementProposal(
                kind="source_policy",
                title=f"Valutare l'aggiunta di {domain} ai tier dell'area {area or 'generale'}",
                description=(
                    f"Il dominio '{domain}' risulta ufficiale nel registro fonti ma non è classificato "
                    f"nei tier dell'area '{area}': respinto {count} volte dal ciclo. Valutare l'aggiunta "
                    "a SOURCE_POLICIES (tier_2) in lex/research/source_policy/catalog.py."
                ),
                target_module="lex/research/source_policy/catalog.py",
                confidence=0.7,
                evidence=evidence.get((domain, area), [])[:5],
                suggested_tests=["lex/tests/unit/test_source_policy.py"],
            )
        )
    return proposals


def _p3_area_keywords(questions: list[dict]) -> list[ImprovementProposal]:
    senza_area = [record for record in questions if not str((record.get("payload") or {}).get("area") or "").strip()]
    if len(senza_area) < 2:
        return []
    return [
        ImprovementProposal(
            kind="area_keywords",
            title="Estendere AREA_KEYWORDS: domande di ricerca senza area inferita",
            description=(
                f"{len(senza_area)} domande di ricerca non hanno un'area inferita: valutare nuove "
                "keyword in AREA_KEYWORDS (lex/research/source_policy/catalog.py) per coprire i temi emersi."
            ),
            target_module="lex/research/source_policy/catalog.py",
            confidence=0.6,
            evidence=[str(record.get("record_id") or "") for record in senza_area[:5]],
            suggested_tests=["lex/tests/unit/test_source_policy.py"],
        )
    ]


def _p4_ontologia(terms: list[dict]) -> list[ImprovementProposal]:
    proposals: list[ImprovementProposal] = []
    for record in terms:
        payload = record.get("payload") or {}
        if str(payload.get("kind") or "") != "candidato":
            continue
        occurrences = int(payload.get("occurrences") or 0)
        normalized = str(payload.get("normalized") or "").strip()
        if occurrences < _MIN_ONTOLOGY_OCCURRENCES or not normalized:
            continue
        proposals.append(
            ImprovementProposal(
                kind="ontologia",
                title=f"Aggiungere il concetto '{normalized}' all'ontologia giuridica",
                description=(
                    f"Il termine '{normalized}' ricorre {occurrences} volte nei testi analizzati "
                    f"(area {payload.get('area') or 'n.d.'}) ma non è nell'ontologia: aggiungerlo a "
                    "LEGAL_ONTOLOGY con sinonimi e fonti primarie verificate."
                ),
                target_module="lex/knowledge/legal_ontology.py",
                confidence=0.7,
                evidence=[str(record.get("record_id") or "")],
                suggested_tests=["lex/tests/unit/test_knowledge_base.py"],
            )
        )
    return proposals


def _p5_robots_su_tier1(readings: list[dict], trust: list[dict]) -> list[ImprovementProposal]:
    tier1_domains = {
        str((record.get("payload") or {}).get("domain") or "")
        for record in trust
        if str((record.get("payload") or {}).get("tier")) == "tier_1"
    }
    proposals: list[ImprovementProposal] = []
    seen: set[str] = set()
    for record in readings:
        payload = record.get("payload") or {}
        if str(payload.get("status") or "") != "robots_blocked":
            continue
        url = str(payload.get("url") or "")
        domain = url.split("/")[2].casefold() if url.count("/") >= 2 else ""
        if not domain or domain in seen or not any(domain.endswith(t1) for t1 in tier1_domains if t1):
            continue
        seen.add(domain)
        proposals.append(
            ImprovementProposal(
                kind="connettore_dedicato",
                title=f"Valutare un connettore dedicato per {domain} (robots.txt restrittivo)",
                description=(
                    f"Il dominio ufficiale tier_1 '{domain}' blocca il crawling generico via robots.txt: "
                    "valutare un connettore dedicato in lex/sources/connectors (API/feed ufficiale), "
                    "senza mai bypassare robots.txt."
                ),
                target_module="lex/sources/connectors",
                confidence=0.65,
                evidence=[str(record.get("record_id") or "")],
                suggested_tests=["lex/tests/unit/test_sources_polite_fetcher.py"],
            )
        )
    return proposals


__all__ = ["propose_improvements"]
