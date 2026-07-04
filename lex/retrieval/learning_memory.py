"""Ricerca deterministica sulla memoria di apprendimento autonomo (read-only).

Serve la sorgente retrieval `lex_memory`: ciò che il ciclo autonomo ha LETTO
da fonti ufficiali (con estratto governato) diventa evidenza per le risposte,
ancorato all'URL ufficiale. Governance fail-closed:

- entrano SOLO letture `status=ok` con URL http(s) e con estratto non vuoto;
- l'URL deve avere una valutazione di fiducia persistita (`trust_assessments`)
  con `allowed_for_learning=true` e tier `tier_1`/`tier_2` — niente
  valutazione → niente evidenza;
- lo scoring è overlap di token tra domanda e citazioni/titolo/estratto,
  nessuna invenzione: se nulla combacia, lista vuota.

La memoria è conoscenza PUBBLICA di fonti ufficiali (mai PII per costruzione:
le query del ciclo nascono solo da campi strutturati), condivisa tra i tenant
come i cataloghi normativi.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"[a-zà-ù0-9]+(?:[-./][a-zà-ù0-9]+)*", re.IGNORECASE)
_STOPWORDS = frozenset(
    "il lo la le gli un una uno di del della dei delle da dal dalla in nel nella con su per tra fra che cosa quali quale come sono e o a al alla ai secondo previsti prevede stabilisce".split()
)
_TIER_TO_TRUST = {"tier_1": ("A", 1), "tier_2": ("B", 2)}


def _tokens(text: str) -> set[str]:
    return {
        token.casefold()
        for token in _TOKEN_RE.findall(str(text or ""))
        if len(token) > 1 and token.casefold() not in _STOPWORDS
    }


def _payload(record: Any) -> dict[str, Any]:
    payload = record.get("payload") if isinstance(record, dict) else None
    return payload if isinstance(payload, dict) else {}


def _trusted_urls(assessments: list[dict[str, Any]]) -> dict[str, tuple[str, int]]:
    trusted: dict[str, tuple[str, int]] = {}
    for record in assessments:
        payload = _payload(record)
        url = str(payload.get("url") or "").strip()
        tier = str(payload.get("tier") or "").strip().lower()
        if not url or not payload.get("allowed_for_learning") or tier not in _TIER_TO_TRUST:
            continue
        trusted[url.casefold()] = _TIER_TO_TRUST[tier]
    return trusted


def search_learning_memory(
    query: str,
    *,
    memory_dir: str | Path | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    """Righe-evidenza dalla memoria di apprendimento, fail-closed e ordinate."""

    query_tokens = _tokens(query)
    if not query_tokens or limit <= 0:
        return []
    from lex.knowledge.knowledge_base import KnowledgeBase

    try:
        kb = KnowledgeBase(memory_dir) if memory_dir else KnowledgeBase()
        readings = kb.load("source_readings")
        trusted = _trusted_urls(kb.load("trust_assessments"))
    except Exception:
        return []

    scored: list[tuple[float, str, dict[str, Any]]] = []
    for record in readings:
        payload = _payload(record)
        url = str(payload.get("url") or "").strip()
        excerpt = str(payload.get("excerpt") or "").strip()
        if payload.get("status") != "ok" or not excerpt:
            continue
        if not url.casefold().startswith(("http://", "https://")):
            continue
        trust = trusted.get(url.casefold())
        if trust is None:
            continue
        citations = [str(item) for item in payload.get("citations_normalized") or []]
        title = str(payload.get("title") or "")
        citation_tokens = _tokens(" ".join(citations))
        title_tokens = _tokens(title)
        excerpt_tokens = _tokens(excerpt)
        score = (
            3.0 * len(query_tokens & citation_tokens)
            + 2.0 * len(query_tokens & title_tokens)
            + 1.0 * len(query_tokens & excerpt_tokens)
        )
        if score <= 0:
            continue
        trust_class, source_level = trust
        fetched_at = str(payload.get("fetched_at") or "")
        scored.append(
            (
                score,
                fetched_at,
                {
                    "source_type": "lex_memory",
                    "id": str(record.get("record_id") or ""),
                    "title": title or url,
                    "content": excerpt,
                    "score": min(1.0, score / (3.0 * max(1, len(query_tokens)))),
                    "official_url": url,
                    "trust_class": trust_class,
                    "source_level": source_level,
                    "authority": url.split("/")[2] if "//" in url else "",
                    "area": str(payload.get("area") or ""),
                    "published_at": fetched_at,
                    "citations_normalized": citations[:20],
                    "learned_by": str(payload.get("source_id") or "apprendimento_autonomo"),
                },
            )
        )
    # Punteggio decrescente; a parità vince la lettura più recente.
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _score, _fetched, row in scored[:limit]]


__all__ = ["search_learning_memory"]
