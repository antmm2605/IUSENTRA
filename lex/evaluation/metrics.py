"""Metriche pure per valutare risposte legal-AI.

Le funzioni sono volutamente leggere: servono come harness CI interno e come
contratto minimo per testare fedelta' delle citazioni, estrazione e rifiuto.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from typing import Any


_REFUSAL_MARKERS = (
    "non posso",
    "non determinabile",
    "non ho elementi sufficienti",
    "richiede verifica",
    "non posso completare",
    "non e' possibile",
    "non posso fornire",
)


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _tokens(value: Any) -> list[str]:
    return normalize_text(value).split()


def exact_match(expected: Any, actual: Any) -> bool:
    """Exact match normalizzato per campi estratti."""

    return normalize_text(expected) == normalize_text(actual)


def token_f1(expected: Any, actual: Any) -> dict[str, float]:
    """Token-level precision/recall/F1, utile per metadati multi-parola."""

    expected_tokens = _tokens(expected)
    actual_tokens = _tokens(actual)
    if not expected_tokens and not actual_tokens:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not expected_tokens or not actual_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    expected_counter = Counter(expected_tokens)
    actual_counter = Counter(actual_tokens)
    overlap = sum((expected_counter & actual_counter).values())
    precision = overlap / len(actual_tokens) if actual_tokens else 0.0
    recall = overlap / len(expected_tokens) if expected_tokens else 0.0
    f1 = 0.0 if precision + recall == 0 else (2 * precision * recall) / (precision + recall)
    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
    }


def citation_fidelity(claims: list[str], evidence_texts: list[str]) -> dict[str, Any]:
    """Stima deterministica del supporto delle fonti rispetto ai claim.

    Non sostituisce un judge umano/LLM, ma impedisce regressioni grossolane:
    ogni claim deve condividere termini significativi con almeno una evidenza.
    """

    evidence_tokens = [set(_tokens(text)) for text in evidence_texts if _tokens(text)]
    supported: list[dict[str, Any]] = []
    unsupported: list[str] = []
    for claim in claims:
        claim_tokens = {tok for tok in _tokens(claim) if len(tok) > 3}
        if not claim_tokens:
            unsupported.append(str(claim))
            continue
        best_overlap = 0.0
        for tokens in evidence_tokens:
            if not tokens:
                continue
            overlap = len(claim_tokens & tokens) / max(len(claim_tokens), 1)
            best_overlap = max(best_overlap, overlap)
        if best_overlap >= 0.35:
            supported.append({"claim": str(claim), "support_score": round(best_overlap, 4)})
        else:
            unsupported.append(str(claim))
    total = len(claims)
    precision = len(supported) / total if total else 1.0
    return {
        "supported": supported,
        "unsupported": unsupported,
        "precision": round(precision, 4),
        "supported_count": len(supported),
        "claim_count": total,
    }


def refusal_correctness(*, expected_refusal: bool, answer: str) -> dict[str, Any]:
    """Misura se Lex rifiuta quando deve e non rifiuta quando puo' aiutare."""

    normalized = normalize_text(answer)
    refused = any(marker.replace("'", " ") in normalized for marker in _REFUSAL_MARKERS)
    correct = refused is bool(expected_refusal)
    false_accept = bool(expected_refusal) and not refused
    false_reject = not bool(expected_refusal) and refused
    return {
        "expected_refusal": bool(expected_refusal),
        "refused": refused,
        "correct": correct,
        "false_accept": false_accept,
        "false_reject": false_reject,
    }
