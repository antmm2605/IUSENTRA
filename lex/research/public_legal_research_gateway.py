"""Gateway coordinato per ricerca legale pubblica - IUSENTRA Lex.

Coordina tutti i canali di ricerca pubblica disponibili:
1. Fonti ufficiali interne (SQLite / JSONL indicizzati)
2. Ricerca web su domini ufficiali allowlist
3. Local Deep Research (solo per query pubbliche e non sensibili)

Normalizza le evidenze, calcola ranking e coverage_gaps.
Non inventa mai risultati: se le fonti sono vuote, lo dichiara.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from typing import Any

from .privacy_safe_query_rewriter import PrivacySafeResearchQuery


# ---------------------------------------------------------------------------
# Disponibilità moduli opzionali
# ---------------------------------------------------------------------------

try:
    from lex.retrieval.official_web import search_recognized_official_web as _search_web
    _WEB_AVAILABLE = True
except Exception:  # pragma: no cover
    _WEB_AVAILABLE = False

try:
    from lex.retrieval.official_web import search_free_public_web as _search_free_web
    _FREE_WEB_AVAILABLE = True
except Exception:  # pragma: no cover
    _FREE_WEB_AVAILABLE = False


try:
    from lex.retrieval.official_sources_retriever import search_official_sources as _search_official
    _OFFICIAL_RETRIEVAL_AVAILABLE = True
except Exception:  # pragma: no cover
    _OFFICIAL_RETRIEVAL_AVAILABLE = False


try:
    from lex.integrations.local_deep_research_client import LocalDeepResearchClient
    _LDR_AVAILABLE = True
except Exception:  # pragma: no cover
    _LDR_AVAILABLE = False


# ---------------------------------------------------------------------------
# Modelli dati
# ---------------------------------------------------------------------------

@dataclass
class NormalizedSource:
    """Fonte normalizzata dopo il retrieval pubblico."""

    id: str
    title: str
    source_name: str
    source_type: str                  # normativa | giurisprudenza | web_ufficiale | ldr | interno
    official: bool
    url: str
    date: str
    excerpt: str
    trust_score: float
    freshness_score: float
    source_access_status: str         # open | requires_auth | restricted
    source_access_label: str
    source_requires_credentials: bool
    source_restricted: bool
    source_supports_web_search: bool

    def to_evidence_dict(self) -> dict[str, Any]:
        return {
            "source_type": self.source_type,
            "source_id": self.id,
            "title": self.title,
            "content": self.excerpt,
            "score": self.trust_score,
            "trust_score": self.trust_score,
            "freshness_score": self.freshness_score,
            "context_fit_score": 0.7 if self.official else 0.4,
            "verified_reference": self.official and not self.source_restricted,
            "authority": self.source_name,
            "official_url": self.url or None,
        }


@dataclass
class PublicLegalResearchResult:
    """Risultato della ricerca legale pubblica coordinata."""

    query_used: str
    sources: list[NormalizedSource] = field(default_factory=list)
    official_sources: list[NormalizedSource] = field(default_factory=list)
    ldr_sources: list[NormalizedSource] = field(default_factory=list)
    compared_sources: list[dict[str, Any]] = field(default_factory=list)
    coverage_gaps: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)
    fallback_triggered: bool = False
    confidence_seed: float = 0.0
    research_log: list[str] = field(default_factory=list)
    ldr_used: bool = False
    ldr_blocked_reason: str = ""
    web_used: bool = False
    web_blocked_reason: str = ""
    free_web_used: bool = False
    professional_practice_used: bool = False

    def to_evidence_pack_dict(self) -> dict[str, Any]:
        """Converte in formato compatibile con EvidencePack per il pipeline Lex."""
        items = [s.to_evidence_dict() for s in self.sources]
        official_names = [s.source_name for s in self.official_sources]
        return {
            "items": items,
            "citations": [],
            "official_sources": official_names,
            "trusted_sources": [s.source_name for s in self.sources if s.trust_score >= 0.6],
            "coverage_gaps": self.coverage_gaps,
            "evidence_sufficient": bool(self.official_sources) and self.confidence_seed >= 0.4,
            "fallback_triggered": self.fallback_triggered,
            "compared_sources": self.compared_sources,
            "evidence_pack": {
                "sufficient": bool(self.official_sources) and self.confidence_seed >= 0.4,
                "aggregate_trust_score": _avg([s.trust_score for s in self.sources]) if self.sources else 0.0,
                "aggregate_freshness_score": _avg([s.freshness_score for s in self.sources]) if self.sources else 0.0,
                "aggregate_context_fit_score": 0.7 if self.official_sources else 0.3,
                "aggregate_consensus_score": min(0.9, len(self.sources) * 0.15),
                "coverage_gaps": self.coverage_gaps,
                "metadata": {
                    "ldr_used": self.ldr_used,
                    "ldr_blocked_reason": self.ldr_blocked_reason,
                    "web_used": self.web_used,
                    "web_blocked_reason": self.web_blocked_reason,
                    "free_web_used": self.free_web_used,
                    "professional_practice_used": self.professional_practice_used,
                    "professional_practice_non_binding": self.professional_practice_used,
                    "professional_practice_can_contradict_lawyer": False,
                    "professional_practice_usage_rules": (
                        [
                            "Usare come spunti di prassi, lessico, struttura e controllo operativo.",
                            "Non usare come fonte ufficiale o prova del diritto vigente.",
                            "Non contraddire l'avvocato senza fonte primaria verificata al 99%.",
                            "Non pubblicare automaticamente nel corpus o negli aggiornamenti legali.",
                        ]
                        if self.professional_practice_used
                        else []
                    ),
                    "professional_practice_source_count": (
                        len([s for s in self.sources if s.source_type == "knowhow_professionale"])
                        if self.professional_practice_used
                        else 0
                    ),
                    "public_research_query": self.query_used,
                    "external_sources_used": self.web_used or self.ldr_used,
                    "external_sources_reason": (
                        "Ricerca web libera attivata manualmente dall'utente."
                        if self.free_web_used
                        else "Pratica web professionale non vincolante su siti e contenuti per avvocati."
                        if self.professional_practice_used
                        else "Ricerca pubblica governata su fonti ufficiali." if self.web_used else ""
                    ),
                },
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _make_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def _trust_score_for_row(row: dict[str, Any]) -> float:
    """Calcola trust score da una riga di retrieval."""
    level = str(row.get("reliability_level") or row.get("trust_class") or "").lower()
    if level in {"a", "a1", "tier_1", "1"}:
        return 0.92
    if level in {"b", "b2", "tier_2", "2"}:
        return 0.68
    if level in {"c", "tier_3", "3"}:
        return 0.35
    score = float(row.get("score") or row.get("trust_score") or 0.0)
    return min(0.95, max(0.1, score))


def _freshness_score_for_row(row: dict[str, Any]) -> float:
    """Stima freshness score da data pubblicazione."""
    date_str = str(row.get("published_at") or row.get("date") or "")
    if not date_str:
        return 0.5
    try:
        import datetime
        year = int(date_str[:4])
        current_year = datetime.datetime.now().year
        age = current_year - year
        return max(0.1, 1.0 - age * 0.08)
    except Exception:
        return 0.5


def _normalize_row(row: dict[str, Any], source_type: str = "web_ufficiale") -> NormalizedSource:
    """Normalizza una riga di retrieval in NormalizedSource."""
    raw_id = str(row.get("id") or row.get("source_id") or row.get("document_id") or "")
    title = str(row.get("title") or row.get("nome") or "Fonte senza titolo")
    url = str(row.get("url") or row.get("link") or "")
    excerpt = str(row.get("excerpt") or row.get("content") or row.get("text") or "")[:500]
    source_name = str(row.get("source_name") or row.get("authority") or row.get("sorgente") or "")
    date = str(row.get("published_at") or row.get("date") or "")
    official_domains = (
        "giustizia.it",
        "cortedicassazione.it",
        "cortecostituzionale.it",
        "normattiva.it",
        "giustizia-amministrativa.it",
        "eur-lex.europa.eu",
    )
    official = bool(
        row.get("official")
        or row.get("verified_reference")
        or row.get("tier") == "tier_1"
        or any(domain in url.lower() for domain in official_domains)
    )
    restricted = bool(row.get("restricted") or row.get("source_restricted"))
    requires_auth = bool(row.get("requires_credentials") or row.get("source_requires_credentials"))

    if restricted:
        access_status = "restricted"
        access_label = "Riservato (richiede accesso dedicato)"
    elif requires_auth:
        access_status = "requires_auth"
        access_label = "Richiede autenticazione"
    else:
        access_status = "open"
        access_label = "Accesso libero"

    return NormalizedSource(
        id=raw_id or _make_id(title + url),
        title=title,
        source_name=source_name,
        source_type=source_type,
        official=official,
        url=url,
        date=date,
        excerpt=excerpt,
        trust_score=_trust_score_for_row(row),
        freshness_score=_freshness_score_for_row(row),
        source_access_status=access_status,
        source_access_label=access_label,
        source_requires_credentials=requires_auth,
        source_restricted=restricted,
        source_supports_web_search=bool(row.get("source_supports_web_search", True)),
    )


def _deduplicate_sources(sources: list[NormalizedSource]) -> list[NormalizedSource]:
    """Rimuove duplicati per URL o ID."""
    seen: set[str] = set()
    result: list[NormalizedSource] = []
    for src in sources:
        if not _is_meaningful_source(src):
            continue
        key = src.url or src.id
        if key and key not in seen:
            seen.add(key)
            result.append(src)
    return result


def _is_meaningful_source(source: NormalizedSource) -> bool:
    title = str(source.title or "").strip().lower()
    return bool(
        source.url
        or source.excerpt
        or source.source_name
        or (title and title != "fonte senza titolo")
    )


def _rank_sources(sources: list[NormalizedSource]) -> list[NormalizedSource]:
    """Ordina: fonti ufficiali prima, poi per trust_score desc."""
    return sorted(
        sources,
        key=lambda s: (int(s.official), s.trust_score, s.freshness_score),
        reverse=True,
    )


def _compute_confidence_seed(
    official_sources: list[NormalizedSource],
    total_sources: list[NormalizedSource],
) -> float:
    """Calcola confidence_seed da proporzione fonti ufficiali e diversità."""
    if not total_sources:
        return 0.0
    official_ratio = len(official_sources) / len(total_sources)
    diversity = min(1.0, len(total_sources) / 5)
    avg_trust = _avg([s.trust_score for s in total_sources])
    return round(official_ratio * 0.5 + diversity * 0.2 + avg_trust * 0.3, 4)


_FREE_WEB_MODES = {"free", "free_web", "web_libero", "web libero", "ricerca_libera", "ricerca libera", "libera"}
_PROFESSIONAL_PRACTICE_MODES = {
    "pratica_professionale",
    "pratica professionale",
    "knowhow_professionale",
    "know-how professionale",
    "lawyer_practice",
    "professional_practice",
    "studi_legali",
}


def _is_free_web_mode(source_mode: str) -> bool:
    return str(source_mode or "").strip().lower() in _FREE_WEB_MODES


def _is_professional_practice_mode(source_mode: str) -> bool:
    return str(source_mode or "").strip().lower() in _PROFESSIONAL_PRACTICE_MODES


def _professional_practice_query(public_query: str) -> str:
    base = str(public_query or "").strip()
    if not base:
        return ""
    return (
        f'{base} "studio legale" avvocati prassi operativa '
        "commento professionale guida pratica"
    )


# ---------------------------------------------------------------------------
# Gateway principale
# ---------------------------------------------------------------------------

def run_public_legal_research(
    query: PrivacySafeResearchQuery,
    source_mode: str = "balanced",
    max_results: int = 8,
    ldr_client: Any = None,
) -> PublicLegalResearchResult:
    """Esegue ricerca legale pubblica coordinata.

    Coordina:
    1. Fonti ufficiali interne (se disponibili)
    2. Ricerca web su domini allowlist (se can_use_official_web)
    3. Local Deep Research (se can_use_ldr e ldr_client configurato)

    Non inventa mai risultati: se le fonti sono vuote, lo dichiara esplicitamente.

    Args:
        query: Risultato del PrivacySafeResearchQuery (già anonimizzato).
        source_mode: strict | balanced | broad
        max_results: Numero massimo di risultati totali.
        ldr_client: Istanza LocalDeepResearchClient (opzionale).

    Returns:
        PublicLegalResearchResult con fonti, gap, warning e log.
    """
    public_query = str(query.public_research_query or query.original_query or "").strip()
    free_web_mode = _is_free_web_mode(source_mode)
    professional_practice_mode = _is_professional_practice_mode(source_mode)
    if not public_query:
        return PublicLegalResearchResult(
            query_used="",
            warnings=["Query pubblica vuota: impossibile cercare fonti."],
            next_actions=["Riformula la domanda in termini giuridici pubblici."],
            research_log=["BLOCCO: query pubblica vuota."],
        )

    result = PublicLegalResearchResult(query_used=public_query)
    all_sources: list[NormalizedSource] = []
    log: list[str] = []

    # ------------------------------------------------------------------
    # Step 1: Fonti ufficiali interne (SQLite / JSONL)
    # ------------------------------------------------------------------
    log.append(f"[1] Ricerca fonti ufficiali interne per: «{public_query[:80]}»")
    if _OFFICIAL_RETRIEVAL_AVAILABLE:
        try:
            rows = _search_official(public_query) or []
            for row in rows[:max_results]:
                row_dict = row if isinstance(row, dict) else vars(row)
                normalized = _normalize_row(row_dict, source_type="normativa")
                if row_dict.get("restricted"):
                    result.coverage_gaps.append(
                        f"Fonte riservata non accessibile: {normalized.title}"
                    )
                    result.next_actions.append(
                        f"Accedi manualmente a: {normalized.url or normalized.source_name}"
                    )
                else:
                    all_sources.append(normalized)
            log.append(f"  → {len(all_sources)} fonti interne trovate.")
        except Exception as exc:  # pragma: no cover
            log.append(f"  → Errore retrieval interno: {exc}")
            result.warnings.append(f"Retrieval fonti interne non disponibile: {exc}")
    else:
        log.append("  → Retrieval fonti interne non disponibile (modulo assente).")

    # ------------------------------------------------------------------
    # Step 2: Ricerca web su domini ufficiali allowlist
    # ------------------------------------------------------------------
    if query.can_use_official_web and _WEB_AVAILABLE:
        log.append(f"[2] Ricerca web ufficiale per: «{public_query[:80]}»")
        result.web_used = True
        try:
            web_rows = _search_web(public_query, limit_results=max_results) or []
            for row in web_rows[:max_results]:
                row_dict = row if isinstance(row, dict) else vars(row)
                normalized = _normalize_row(row_dict, source_type="web_ufficiale")
                if not normalized.source_restricted:
                    all_sources.append(normalized)
                else:
                    result.coverage_gaps.append(
                        f"Fonte web riservata non accessibile: {normalized.title}"
                    )
            log.append(f"  → {len(web_rows)} risultati web trovati.")
        except Exception as exc:  # pragma: no cover
            log.append(f"  → Errore ricerca web: {exc}")
            result.warnings.append(f"Ricerca web non disponibile: {exc}")
            result.web_blocked_reason = str(exc)
    elif not query.can_use_official_web:
        result.web_blocked_reason = (
            "Query non idonea per ricerca web (dati sensibili non rimossi o sensitivity troppo alta)."
        )
        log.append(f"[2] Ricerca web BLOCCATA: {result.web_blocked_reason}")
    elif not _WEB_AVAILABLE:
        result.web_blocked_reason = "Modulo ricerca web ufficiale non disponibile."
        log.append("[2] Ricerca web non disponibile.")

    # ------------------------------------------------------------------
    # Step 2b: ricerca web libera manuale (solo flag esplicito utente)
    # ------------------------------------------------------------------
    if free_web_mode or professional_practice_mode:
        if _FREE_WEB_AVAILABLE:
            search_query = _professional_practice_query(public_query) if professional_practice_mode else public_query
            label = "pratica professionale" if professional_practice_mode else "web libera manuale"
            log.append(f"[2b] Ricerca {label} per: «{search_query[:80]}»")
            result.web_used = True
            result.free_web_used = bool(free_web_mode)
            result.professional_practice_used = bool(professional_practice_mode)
            result.web_blocked_reason = ""
            try:
                free_rows = _search_free_web(search_query, limit_results=max_results) or []
                for row in free_rows[:max_results]:
                    row_dict = row if isinstance(row, dict) else vars(row)
                    normalized = _normalize_row(
                        row_dict,
                        source_type="knowhow_professionale" if professional_practice_mode else "web_libero",
                    )
                    if professional_practice_mode:
                        normalized.official = False
                        normalized.trust_score = min(normalized.trust_score, 0.58)
                    if not normalized.source_restricted:
                        all_sources.append(normalized)
                    else:
                        result.coverage_gaps.append(
                            f"Fonte web riservata non accessibile: {normalized.title}"
                        )
                log.append(f"  → {len(free_rows)} risultati {label} trovati.")
            except Exception as exc:  # pragma: no cover
                log.append(f"  → Errore ricerca {label}: {exc}")
                result.warnings.append(f"Ricerca {label} non disponibile: {exc}")
                result.web_blocked_reason = str(exc)
        else:
            result.web_blocked_reason = "Modulo ricerca web libera/pratica professionale non disponibile."
            log.append("[2b] Ricerca web libera/pratica professionale non disponibile.")

    # ------------------------------------------------------------------
    # Step 3: Local Deep Research (solo se consentito e configurato)
    # ------------------------------------------------------------------
    if query.can_use_ldr:
        if ldr_client is None and _LDR_AVAILABLE:
            # Prova a costruire il client dalle variabili d'ambiente
            try:
                ldr_client = LocalDeepResearchClient()
            except Exception:
                ldr_client = None

        if ldr_client is not None and _LDR_AVAILABLE:
            ldr_configured = getattr(ldr_client, "is_configured", lambda: False)()
            if ldr_configured:
                log.append(f"[3] Local Deep Research per: «{query.local_deep_research_query[:80]}»")
                result.ldr_used = True
                try:
                    ldr_query = query.local_deep_research_query or public_query
                    ldr_result = ldr_client.research_and_wait(
                        ldr_query,
                        iterations=2,
                        max_wait_seconds=int(os.getenv("LDR_TIMEOUT_SECONDS", "30")) * 30,
                    )
                    ldr_rows = ldr_result.get("sources") or ldr_result.get("results") or []
                    for row in ldr_rows[:max_results]:
                        row_dict = row if isinstance(row, dict) else vars(row)
                        normalized = _normalize_row(row_dict, source_type="ldr")
                        result.ldr_sources.append(normalized)
                        all_sources.append(normalized)
                    log.append(f"  → {len(result.ldr_sources)} risultati LDR trovati.")
                except Exception as exc:
                    result.ldr_used = False
                    result.ldr_blocked_reason = f"Errore LDR: {exc}"
                    result.warnings.append(f"Local Deep Research non completato: {exc}")
                    result.fallback_triggered = True
                    log.append(f"  → LDR fallito: {exc}")
            else:
                result.ldr_blocked_reason = "LDR non configurato (LDR_BASE_URL, LDR_USERNAME, LDR_PASSWORD mancanti)."
                result.warnings.append(result.ldr_blocked_reason)
                log.append(f"[3] LDR BLOCCATO: {result.ldr_blocked_reason}")
        elif not _LDR_AVAILABLE:
            result.ldr_blocked_reason = "Modulo LocalDeepResearchClient non disponibile."
            log.append("[3] LDR non disponibile (modulo assente).")
        else:
            result.ldr_blocked_reason = "Client LDR non fornito."
            log.append("[3] LDR non usato (client non fornito).")
    else:
        result.ldr_blocked_reason = str(query.reason or "Query non idonea per LDR (dati sensibili o sensitivity alta).")
        log.append(f"[3] LDR BLOCCATO per policy privacy: {result.ldr_blocked_reason}")

    # ------------------------------------------------------------------
    # Step 4: Deduplicazione, ranking, calcolo confidence
    # ------------------------------------------------------------------
    log.append("[4] Deduplicazione e ranking fonti...")
    all_sources = _deduplicate_sources(all_sources)
    all_sources = _rank_sources(all_sources)[:max_results]

    result.sources = all_sources
    result.official_sources = [s for s in all_sources if s.official]

    # Confronto fonti
    if len(result.official_sources) >= 2:
        result.compared_sources = [
            {
                "title": s.title,
                "source_name": s.source_name,
                "trust_score": s.trust_score,
                "url": s.url,
                "official": s.official,
            }
            for s in result.official_sources[:4]
        ]

    result.confidence_seed = _compute_confidence_seed(result.official_sources, all_sources)
    log.append(
        f"  → Totale fonti: {len(all_sources)}, "
        f"ufficiali: {len(result.official_sources)}, "
        f"confidence_seed: {result.confidence_seed}"
    )

    # ------------------------------------------------------------------
    # Step 5: Missing evidence e next_actions finali
    # ------------------------------------------------------------------
    if not all_sources:
        result.missing_evidence.append(
            "Nessuna fonte trovata per la query pubblica fornita."
        )
        result.warnings.append(
            "Nessuna evidenza pubblica trovata. Verifica manualmente le fonti ufficiali."
        )
        result.next_actions.append(
            "Cerca direttamente su Normattiva.it, Gazzetta Ufficiale o Cassazione.it."
        )
        log.append("[5] Nessuna fonte trovata.")

    elif professional_practice_mode:
        result.next_actions.append(
            "Usa le fonti professionali come spunti di prassi e stile; per affermare il diritto cerca una fonte ufficiale."
        )
        log.append("[5] Fonti professionali non vincolanti acquisite come know-how, senza pubblicazione automatica.")

    elif not result.official_sources:
        if free_web_mode:
            result.next_actions.append(
                "Se un risultato web libero è utile, acquisisci pagina o allegato nell'archivio dello studio."
            )
            log.append("[5] Risultati web liberi trovati senza promozione automatica a fonte ufficiale.")
        else:
            result.missing_evidence.append(
                "Trovate solo fonti non ufficiali: verifica manualmente su fonti primarie."
            )
            result.next_actions.append(
                "Valida le fonti trovate consultando direttamente le sedi ufficiali."
            )
            log.append("[5] Solo fonti non ufficiali trovate.")

    if result.coverage_gaps and not any("riservata" in a for a in result.next_actions):
        result.next_actions.append(
            "Per le fonti riservate usa le credenziali del portale dedicato o il registro studio."
        )

    result.research_log = log
    return result
