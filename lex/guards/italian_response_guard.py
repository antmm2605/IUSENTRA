"""Guardia linguistica per impedire risposte Lex in inglese."""

from __future__ import annotations

import re
from typing import Any


FORBIDDEN_ENGLISH_FRAGMENTS: tuple[str, ...] = (
    "okay, here's",
    "case summary",
    "key points",
    "relevant documents",
    "in essence",
    "do you have any specific questions",
    "breakdown",
    "claimant",
    "dispute",
    "legal basis",
)

_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Okay, here's a breakdown", "Ecco la sintesi"),
    ("Okay, here's", "Ecco"),
    ("Case Summary", "Sintesi del fascicolo"),
    ("Key Points", "Punti rilevanti"),
    ("Relevant Documents", "Documenti considerati"),
    ("In essence", "In sintesi"),
    ("Do you have any specific questions", "Dimmi pure se vuoi approfondire un punto specifico"),
    ("breakdown", "sintesi"),
    ("claimant", "parte attrice o ricorrente"),
    ("dispute", "controversia"),
    ("legal basis", "base documentale"),
)


def detect_non_italian_response(text: str) -> bool:
    """Rileva formule inglesi non ammesse fuori dalle citazioni letterali."""

    body = _strip_citations(text)
    lowered = body.lower()
    return any(fragment in lowered for fragment in FORBIDDEN_ENGLISH_FRAGMENTS)


def rewrite_or_reject_non_italian_response(text: str, context: dict[str, Any] | None = None) -> str:
    """Riscrive formule inglesi note; se resta inglese significativo, blocca in italiano."""

    original = str(text or "")
    if not detect_non_italian_response(original):
        return original

    rewritten = original
    for source, target in _REPLACEMENTS:
        rewritten = _replace_case_insensitive(rewritten, source, target)

    if not detect_non_italian_response(rewritten):
        return rewritten

    workflow = str((context or {}).get("workflow") or "fascicolo").strip() or "fascicolo"
    if workflow in {"fascicolo", "documento", "udienza"}:
        return (
            "La risposta generata non era conforme alla lingua italiana e non viene mostrata. "
            "Riformulo sul fascicolo: uso solo i documenti e i dati disponibili; dove manca un'informazione, "
            "la risposta corretta e' \"Non risulta dai documenti disponibili nel fascicolo.\""
        )
    return (
        "La risposta generata non era conforme alla lingua italiana e non viene mostrata. "
        "Riformula la richiesta oppure riprova: Lex deve rispondere sempre in italiano."
    )


def _strip_citations(text: str) -> str:
    """Rimuove blocchi citati o tra virgolette per non tradurre citazioni reali."""

    lines: list[str] = []
    in_fenced_block = False
    for line in str(text or "").splitlines():
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fenced_block = not in_fenced_block
            continue
        if in_fenced_block or stripped.startswith(">"):
            continue
        lines.append(line)
    body = "\n".join(lines)
    body = re.sub(r'"[^"\n]{1,400}"', "", body)
    body = re.sub(r"'[^'\n]{1,400}'", "", body)
    return body


def _replace_case_insensitive(text: str, source: str, target: str) -> str:
    return re.sub(re.escape(source), target, text, flags=re.IGNORECASE)


__all__ = [
    "FORBIDDEN_ENGLISH_FRAGMENTS",
    "detect_non_italian_response",
    "rewrite_or_reject_non_italian_response",
]
