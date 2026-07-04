"""Analizzatore linguistico-giuridico deterministico (nessun LLM).

Produce un `LegalLanguageProfile` da un testo: metriche linguistiche, citazioni
(via `citation_extractor`) e osservazioni di termini giuridici. I termini noti
vengono dall'ontologia seed (`lex.knowledge.legal_ontology`, import pigro per
mantenere `lex.learning` foglia); i termini CANDIDATI vengono raccolti in modo
deterministico attorno a parole-testa giuridiche curate, così il gap detector
può accorgersi di concetti ricorrenti non ancora classificati.
"""

from __future__ import annotations

import re
from collections import Counter

from lex.learning.citation_extractor import extract_citations
from lex.learning.models import LegalCitation, LegalLanguageProfile, LegalTermObservation

# Parole-testa giuridiche per la raccolta di termini candidati (bigrammi
# deterministici "vicino + testa" / "testa + vicino"). Curata, non esaustiva.
_MARKER_WORDS = frozenset(
    {
        "responsabilità",
        "danno",
        "risarcimento",
        "contratto",
        "obbligazione",
        "inadempimento",
        "nullità",
        "annullabilità",
        "prescrizione",
        "decadenza",
        "possesso",
        "proprietà",
        "successione",
        "consenso",
        "trattamento",
        "interesse",
        "informativa",
        "profilazione",
        "portabilità",
        "provvedimento",
        "procedimento",
        "ricorso",
        "accesso",
        "autotutela",
        "giurisdizione",
        "motivazione",
        "reato",
        "dolo",
        "colpa",
        "querela",
        "pena",
        "imposta",
        "tributo",
        "accertamento",
        "sanzione",
        "detrazione",
        "deduzione",
        "licenziamento",
        "notificazione",
        "impugnazione",
        "appello",
        "opposizione",
        "termine",
        "udienza",
        "deposito",
    }
)
_NEIGHBOR_STOPWORDS = frozenset(
    {
        "il",
        "lo",
        "la",
        "i",
        "gli",
        "le",
        "un",
        "uno",
        "una",
        "di",
        "del",
        "della",
        "dello",
        "dei",
        "degli",
        "delle",
        "al",
        "alla",
        "allo",
        "ai",
        "agli",
        "alle",
        "da",
        "dal",
        "dalla",
        "in",
        "nel",
        "nella",
        "con",
        "su",
        "sul",
        "sulla",
        "per",
        "tra",
        "fra",
        "che",
        "non",
        "come",
        "ogni",
        "sensi",
        "art",
        "artt",
        "cui",
        "essere",
        "viene",
        "sono",
        # Estensione post prova web reale (2026-07-04): i testi normativi
        # integrali producevano bigrammi rumorosi ("trattamento tale",
        # "trattamento nonché", "qualsiasi pena"). Congiunzioni, dimostrativi
        # e aggettivi generici del legalese non formano concetti.
        "tale",
        "tali",
        "nonché",
        "nonche",
        "qualsiasi",
        "qualunque",
        "ciascuno",
        "ciascuna",
        "presente",
        "presenti",
        "seguente",
        "seguenti",
        "medesimo",
        "medesima",
        "medesimi",
        "medesime",
        "stesso",
        "stessa",
        "stessi",
        "stesse",
        "detto",
        "detta",
        "detti",
        "dette",
        "predetto",
        "predetta",
        "suddetto",
        "suddetta",
        "relativo",
        "relativa",
        "relativi",
        "relative",
        "eventuale",
        "eventuali",
        "altro",
        "altra",
        "altri",
        "altre",
        "quale",
        "quali",
        "questo",
        "questa",
        "questi",
        "queste",
        "quello",
        "quella",
        "quelli",
        "quelle",
        "essa",
        "esso",
        "esse",
        "essi",
        "loro",
        "salvo",
        "salva",
        "senza",
        "sotto",
        "sopra",
        "dopo",
        "durante",
        "mediante",
        "secondo",
        "conformemente",
        "informa",
        "riguarda",
        "riguardante",
        "riguardanti",
        "concernente",
        "concernenti",
        "avente",
        "aventi",
        "comunque",
        "inoltre",
        "tuttavia",
        "pertanto",
        "qualora",
        "laddove",
        "ovvero",
        "oppure",
        "anche",
        "solo",
        "circa",
    }
)
# Niente apostrofo nel token: l'elisione italiana ("l'accesso", "dell'atto")
# deve produrre il sostantivo pulito, altrimenti i marker non matchano.
_TOKEN_RE = re.compile(r"[a-zA-Zàèéìòù0-9]+")
_SENTENCE_SPLIT_RE = re.compile(r"[.!?;]+\s+")


def analyze_language(text: str, *, sample_id: str = "", area_hint: str = "") -> LegalLanguageProfile:
    """Profilo deterministico del testo: metriche + citazioni + termini."""

    normalized = " ".join(str(text or "").split())
    citations = extract_citations(normalized)
    area = area_hint or _infer_area(normalized)
    terms = extract_term_observations(normalized, area, source_ids=[sample_id] if sample_id else [])

    tokens = _TOKEN_RE.findall(normalized)
    sentences = [chunk for chunk in _SENTENCE_SPLIT_RE.split(normalized) if chunk.strip()]
    sentence_count = max(1, len(sentences)) if normalized else 0
    avg_sentence = (len(tokens) / sentence_count) if sentence_count else 0.0
    term_occurrences = sum(item.occurrences for item in terms)
    legal_density = ((len(citations) + term_occurrences) / len(tokens)) if tokens else 0.0
    complexity = _complexity_index(
        avg_sentence_length=avg_sentence,
        citation_count=len(citations),
        term_occurrences=term_occurrences,
        token_count=len(tokens),
    )
    return LegalLanguageProfile(
        sample_id=sample_id,
        area=area,
        characters=len(normalized),
        tokens=len(tokens),
        sentence_count=sentence_count,
        average_sentence_length=avg_sentence,
        legal_density=legal_density,
        complexity_index=complexity,
        citations=citations,
        terms=terms,
    )


def extract_term_observations(
    text: str,
    area: str,
    *,
    source_ids: list[str] | None = None,
    citations: list[LegalCitation] | None = None,
) -> list[LegalTermObservation]:
    """Osserva termini giuridici: noti (ontologia) e candidati (parole-testa)."""

    # Import pigro: mantiene lex.learning senza dipendenze verso lex.knowledge
    # a livello di modulo (l'ontologia è un modulo di soli dati).
    from lex.knowledge.legal_ontology import is_known_concept, known_concepts

    normalized = " ".join(str(text or "").split())
    lowered = normalized.casefold()
    if not lowered:
        return []
    sources = [item for item in (source_ids or []) if item]
    near_citation_bonus = 0.05 if citations or extract_citations(normalized, limit=4) else 0.0

    counts: Counter[str] = Counter()
    # 1) Concetti noti dell'area (nome, sinonimi, correlati): match a frase intera.
    for concept in sorted(known_concepts(area), key=len, reverse=True):
        occurrences = len(re.findall(rf"\b{re.escape(concept)}\b", lowered))
        if occurrences:
            counts[concept] += occurrences
    # 2) Candidati deterministici: bigrammi attorno alle parole-testa giuridiche.
    tokens = _TOKEN_RE.findall(lowered)
    for index, token in enumerate(tokens):
        if token not in _MARKER_WORDS:
            continue
        for neighbor_index in (index - 1, index + 1):
            if not 0 <= neighbor_index < len(tokens):
                continue
            neighbor = tokens[neighbor_index]
            if neighbor in _NEIGHBOR_STOPWORDS or neighbor in _MARKER_WORDS:
                continue
            if len(neighbor) <= 2 or neighbor.isdigit():
                continue
            bigram = f"{neighbor} {token}" if neighbor_index < index else f"{token} {neighbor}"
            # I concetti noti sono già contati al passo 1 come frase intera:
            # il bigramma equivalente non deve raddoppiare le occorrenze.
            if is_known_concept(bigram, area) or is_known_concept(bigram):
                continue
            counts[bigram] += 1

    observations: list[LegalTermObservation] = []
    for term, occurrences in counts.items():
        known = is_known_concept(term, area) or is_known_concept(term)
        confidence = min(0.95, (0.7 if known else 0.55) + 0.1 * min(occurrences, 3) + near_citation_bonus)
        observations.append(
            LegalTermObservation(
                normalized=term,
                label=term,
                kind="concetto" if known else "candidato",
                area=area,
                occurrences=occurrences,
                confidence=confidence,
                contexts=_contexts(normalized, term),
                source_ids=list(sources),
            )
        )
    observations.sort(key=lambda item: (-item.occurrences, item.normalized))
    return observations


def _contexts(text: str, term: str, *, radius: int = 60, limit: int = 2) -> list[str]:
    contexts: list[str] = []
    for match in re.finditer(re.escape(term), text, flags=re.IGNORECASE):
        left = max(0, match.start() - radius)
        right = min(len(text), match.end() + radius)
        contexts.append(" ".join(text[left:right].split()))
        if len(contexts) >= limit:
            break
    return contexts


def _complexity_index(
    *,
    avg_sentence_length: float,
    citation_count: int,
    term_occurrences: int,
    token_count: int,
) -> float:
    """Indice 0..1: frasi lunghe, citazioni e densità terminologica pesano di più."""

    if token_count <= 0:
        return 0.0
    sentence_factor = min(1.0, avg_sentence_length / 40.0)
    citation_factor = min(1.0, citation_count / 8.0)
    term_factor = min(1.0, term_occurrences / max(1.0, token_count / 12.0))
    length_factor = min(1.0, token_count / 400.0)
    return round(0.4 * sentence_factor + 0.25 * citation_factor + 0.2 * term_factor + 0.15 * length_factor, 3)


def _infer_area(text: str) -> str:
    # Import pigro del Source Policy System (modulo dati+funzioni pure).
    from lex.research.source_policy.inference import infer_area

    return infer_area(text)


__all__ = ["analyze_language", "extract_term_observations"]
