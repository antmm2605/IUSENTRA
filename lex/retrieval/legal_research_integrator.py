"""Integratore ricerca legale pubblica per il RetrievalOrchestrator - IUSENTRA Lex.

Questo modulo connette il Privacy-Safe Query Rewriter e il Public Legal
Research Gateway al flusso di retrieval esistente.

Viene chiamato dal RetrievalOrchestrator quando:
- il workflow è normativa/giurisprudenza/prassi/research/fonti (strict legal)
- l'evidenza interna è insufficiente
- la richiesta consente fonti esterne (allow_external_research=True)

Il modulo NON sostituisce il retrieval interno: lo integra con fonti
pubbliche anonimizzate dopo che il contesto privato è stato consultato.
"""

from __future__ import annotations

import os
from typing import Any

_STRICT_LEGAL_WORKFLOWS = frozenset(
    {"normativa", "giurisprudenza", "prassi", "research", "fonti", "giurisprudenza_specifica"}
)


def _env_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name, "")
    return val.strip().lower() in {"1", "true", "yes", "si", "on"} if val.strip() else default


def should_run_public_research(
    workflow: str,
    evidence_sufficient: bool,
    allow_external: bool,
    *,
    force: bool = False,
    exact_reference: bool = False,
    local_case_law_incomplete: bool = False,
    user_requested_public_source: bool = False,
) -> bool:
    """Decide se eseguire la ricerca legale pubblica.

    Criteri:
    - Workflow strict legal (normativa, giurisprudenza, giurisprudenza_specifica, ecc.)
    - Per giurisprudenza_specifica: sempre True (ricerca esatta su fonti ufficiali)
    - allow_external_research=True
    - LEX_GOVERNED_ONLY non disabilita l'uso di fonti ufficiali esterne
      (le fonti ufficiali web rientrano nel perimetro governato)
    """
    if not allow_external:
        return False
    # Ricerca sentenza specifica: sempre pubblica, il frammento locale non basta
    if workflow == "giurisprudenza_specifica":
        return True
    if force:
        return workflow != "studio_data_lookup"
    # Flag espliciti di override: riferimento esatto, frammento incompleto, fonte pubblica richiesta
    if exact_reference or local_case_law_incomplete or user_requested_public_source:
        return workflow != "studio_data_lookup"
    return workflow in _STRICT_LEGAL_WORKFLOWS and not evidence_sufficient


def run_public_research_for_request(
    request: Any,
    context: Any,
    workflow: str,
    *,
    source_mode: str = "balanced",
    max_results: int = 6,
) -> dict[str, Any]:
    """Esegue ricerca legale pubblica per una LexRequest.

    Richiama il PrivacySafeQueryRewriter sulla query originale e poi
    il PublicLegalResearchGateway.

    Args:
        request: LexRequest con query, fascicolo_id, metadata.
        context: Contesto studio (dict).
        workflow: Nome workflow Lex.
        source_mode: strict | balanced | broad
        max_results: Numero massimo di risultati.

    Returns:
        Dict con i campi extra da mergiare nel payload evidence:
        - public_research_query
        - private_context_query
        - removed_sensitive_tokens_count
        - ldr_used, ldr_blocked_reason
        - web_used, web_blocked_reason
        - public_sources (lista di NormalizedSource come dict)
        - public_official_sources (lista nomi)
        - public_coverage_gaps (lista)
        - public_missing_evidence (lista)
        - public_warnings (lista)
        - public_next_actions (lista)
        - public_confidence_seed (float)
        - public_research_log (lista)
    """
    try:
        from lex.research.privacy_safe_query_rewriter import rewrite_query_for_legal_research
    except ImportError:
        return {"public_research_error": "Modulo privacy_safe_query_rewriter non disponibile."}

    try:
        from lex.research.public_legal_research_gateway import run_public_legal_research
    except ImportError:
        return {"public_research_error": "Modulo public_legal_research_gateway non disponibile."}

    query_text = str(getattr(request, "query", "") or "").strip()
    fascicolo_id = str(getattr(request, "fascicolo_id", "") or "")
    metadata = dict(getattr(request, "metadata", {}) or {})
    request_profile = dict(metadata.get("request_profile") or {})
    studio_context = dict(context or {})

    if not query_text:
        return {"public_research_error": "Query vuota."}

    # Step 1: Riscrittura privacy-safe
    try:
        rewritten = rewrite_query_for_legal_research(
            query_text,
            request_profile=request_profile,
            studio_context=studio_context,
            fascicolo_id=fascicolo_id or None,
        )
    except Exception as exc:
        return {"public_research_error": f"Errore query rewriter: {exc}"}

    if not rewritten.can_use_official_web and not rewritten.can_use_ldr:
        return {
            "public_research_query": rewritten.public_research_query,
            "private_context_query": "(redatto)",
            "removed_sensitive_tokens_count": len(rewritten.removed_sensitive_tokens),
            "web_used": False,
            "web_blocked_reason": rewritten.reason or "Sensitivity troppo alta per ricerca pubblica.",
            "ldr_used": False,
            "ldr_blocked_reason": rewritten.reason or "Sensitivity troppo alta per LDR.",
            "public_sources": [],
            "public_official_sources": [],
            "public_coverage_gaps": [],
            "public_missing_evidence": ["Query non idonea per ricerca pubblica (dati sensibili)."],
            "public_warnings": rewritten.warnings,
            "public_next_actions": ["Usa il retrieval interno o riformula la domanda senza dati personali."],
            "public_confidence_seed": 0.0,
            "public_research_log": [],
        }

    # Step 2: Ricerca pubblica coordinata
    try:
        gateway_result = run_public_legal_research(
            rewritten,
            source_mode=source_mode,
            max_results=max_results,
        )
    except Exception as exc:
        return {
            "public_research_query": rewritten.public_research_query,
            "public_research_error": f"Errore gateway: {exc}",
            "web_used": False,
            "ldr_used": False,
            "public_sources": [],
            "public_official_sources": [],
            "public_coverage_gaps": [],
            "public_missing_evidence": [],
            "public_warnings": [f"Ricerca pubblica fallita: {exc}"],
            "public_next_actions": [],
            "public_confidence_seed": 0.0,
            "public_research_log": [],
        }

    return {
        "public_research_query": gateway_result.query_used,
        "private_context_query": "(redatto)",
        "removed_sensitive_tokens_count": len(rewritten.removed_sensitive_tokens),
        "ldr_used": gateway_result.ldr_used,
        "ldr_blocked_reason": gateway_result.ldr_blocked_reason,
        "web_used": gateway_result.web_used,
        "web_blocked_reason": gateway_result.web_blocked_reason,
        "public_sources": [vars(s) for s in gateway_result.sources],
        "public_official_sources": [s.source_name for s in gateway_result.official_sources],
        "public_coverage_gaps": gateway_result.coverage_gaps,
        "public_missing_evidence": gateway_result.missing_evidence,
        "public_warnings": gateway_result.warnings,
        "public_next_actions": gateway_result.next_actions,
        "public_confidence_seed": gateway_result.confidence_seed,
        "public_research_log": gateway_result.research_log,
        "fallback_triggered": gateway_result.fallback_triggered,
    }


def merge_public_research_into_evidence(
    evidence: dict[str, Any],
    public_research: dict[str, Any],
) -> dict[str, Any]:
    """Fonde i risultati della ricerca pubblica nell'evidence pack esistente.

    Le fonti pubbliche vengono aggiunte DOPO le fonti interne, con priorità
    inferiore nel ranking ma visibili nel payload debug.

    Regole:
    - Le fonti interne (fascicolo, studio) mantengono la precedenza
    - Le fonti pubbliche ufficiali sono tracciate separatamente
    - I coverage_gaps pubblici vengono aggiunti ai coverage_gaps esistenti
    - Il metadata viene arricchito con i campi di debug della ricerca pubblica
    """
    if not public_research or public_research.get("public_research_error"):
        return evidence

    merged = dict(evidence or {})

    # Aggiungi fonti pubbliche agli items esistenti
    existing_items = list(merged.get("items") or [])
    public_sources = list(public_research.get("public_sources") or [])
    if public_sources:
        # Converti NormalizedSource dicts in EvidenceItem-like dicts
        public_items = [
            {
                "source_type": s.get("source_type", "web_ufficiale"),
                "source_id": s.get("id", ""),
                "title": s.get("title", ""),
                "content": s.get("excerpt", ""),
                "score": s.get("trust_score", 0.5),
                "trust_score": s.get("trust_score", 0.5),
                "freshness_score": s.get("freshness_score", 0.5),
                "context_fit_score": 0.6,
                "verified_reference": s.get("official", False) and not s.get("source_restricted", False),
                "authority": s.get("source_name", ""),
                "official_url": s.get("url", ""),
                "from_public_research": True,
            }
            for s in public_sources
            if not s.get("source_restricted", False)
        ]
        merged["items"] = [*existing_items, *public_items]

    # Aggiungi fonti ufficiali pubbliche alla lista ufficiali
    existing_official = list(merged.get("official_sources") or [])
    public_official = list(public_research.get("public_official_sources") or [])
    merged["official_sources"] = list(dict.fromkeys([*existing_official, *public_official]))

    # Aggiungi coverage_gaps pubblici
    existing_gaps = list(merged.get("coverage_gaps") or [])
    public_gaps = list(public_research.get("public_coverage_gaps") or [])
    merged["coverage_gaps"] = list(dict.fromkeys([*existing_gaps, *public_gaps]))

    # Aggiorna fallback_triggered
    if public_research.get("fallback_triggered"):
        merged["fallback_triggered"] = True

    # Arricchisci metadata con info debug ricerca pubblica
    existing_meta = dict((merged.get("evidence_pack") or {}).get("metadata") or {})
    existing_meta.update(
        {
            "public_research_query": public_research.get("public_research_query", ""),
            "private_context_query": "(redatto)",
            "removed_sensitive_tokens_count": public_research.get("removed_sensitive_tokens_count", 0),
            "ldr_used": public_research.get("ldr_used", False),
            "ldr_blocked_reason": public_research.get("ldr_blocked_reason", ""),
            "web_used": public_research.get("web_used", False),
            "web_blocked_reason": public_research.get("web_blocked_reason", ""),
            "public_confidence_seed": public_research.get("public_confidence_seed", 0.0),
            "external_sources_used": public_research.get("web_used", False) or public_research.get("ldr_used", False),
            "external_sources_reason": (
                "Ricerca legale pubblica governata su fonti ufficiali anonimizzate."
                if (public_research.get("web_used") or public_research.get("ldr_used"))
                else ""
            ),
        }
    )

    # Aggiorna evidence_pack
    ep = dict(merged.get("evidence_pack") or {})
    ep["metadata"] = existing_meta
    # Ricalcola sufficient se ora abbiamo fonti pubbliche ufficiali
    if public_official and not ep.get("sufficient"):
        ep["sufficient"] = True
    merged["evidence_pack"] = ep

    # Aggiungi warnings e next_actions pubblici
    merged["_public_warnings"] = list(public_research.get("public_warnings") or [])
    merged["_public_next_actions"] = list(public_research.get("public_next_actions") or [])
    merged["_public_research_log"] = list(public_research.get("public_research_log") or [])

    return merged
