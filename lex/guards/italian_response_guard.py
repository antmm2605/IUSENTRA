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
    # Email/lettera in inglese
    "dear recipient",
    "dear sir",
    "dear madam",
    "dear mr.",
    "dear ms.",
    "subject:",
    "re: formal notice",
    "re: demand letter",
    "i am writing",
    "please be advised",
    "please note that",
    "please consult",
    "important disclaimer",
    "this letter serves",
    "failure to comply",
    "we hereby demand",
    "you are hereby notified",
    "sincerely yours",
    "yours faithfully",
    "yours sincerely",
    # Formule generiche inglesi
    "here's a draft",
    "here is a draft",
    "here's the draft",
    "as requested,",
    "as per your request",
    "please find below",
    "please find attached",
    "the following draft",
    "feel free to",
    "let me know if",
    "of course,",
    "certainly,",
    "sure, here",
    "happy to help",
)

_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("Okay, here's a breakdown", "Ecco la sintesi"),
    ("Okay, here's a draft", "Ecco la bozza"),
    ("Here's a draft", "Ecco la bozza"),
    ("Here is a draft", "Ecco la bozza"),
    ("Here's the draft", "Ecco la bozza"),
    ("Okay, here's", "Ecco"),
    ("Sure, here", "Ecco"),
    ("Of course,", "Naturalmente,"),
    ("Certainly,", "Certamente,"),
    ("Case Summary", "Sintesi del fascicolo"),
    ("Key Points", "Punti rilevanti"),
    ("Relevant Documents", "Documenti considerati"),
    ("In essence", "In sintesi"),
    ("As requested,", "Come richiesto,"),
    ("As per your request", "Come richiesto"),
    ("Please find below", "Di seguito"),
    ("Please find attached", "Si allega"),
    ("Feel free to", "Non esiti a"),
    ("Let me know if", "Mi faccia sapere se"),
    ("Happy to help", "A disposizione"),
    ("Do you have any specific questions", "Dimmi pure se vuoi approfondire un punto specifico"),
    ("breakdown", "sintesi"),
    ("claimant", "parte attrice o ricorrente"),
    ("dispute", "controversia"),
    ("legal basis", "base documentale"),
    ("Failure to comply", "In caso di inadempimento"),
    ("We hereby demand", "Con la presente si diffida formalmente"),
    ("You are hereby notified", "Con la presente si comunica formalmente"),
    ("This letter serves", "La presente ha lo scopo"),
    ("Sincerely yours", "Cordiali saluti"),
    ("Yours faithfully", "Distinti saluti"),
    ("Yours sincerely", "Cordiali saluti"),
    ("Dear Recipient", "Egregio/a"),
    ("Dear Sir", "Egregio"),
    ("Dear Madam", "Gentilissima"),
    ("Subject:", "Oggetto:"),
    ("Important Disclaimer", "Avvertenza"),
    ("Please be advised", "Si comunica formalmente"),
    ("Please note that", "Si rappresenta che"),
    ("Please consult", "Si raccomanda di consultare"),
    ("I am writing", "Con la presente"),
)


def detect_non_italian_response(text: str) -> bool:
    """Rileva formule inglesi non ammesse fuori dalle citazioni letterali."""

    body = _strip_citations(text)
    lowered = body.lower()
    if any(fragment in lowered for fragment in FORBIDDEN_ENGLISH_FRAGMENTS):
        return True
    # Rileva risposte prevalentemente in inglese anche senza formule note
    return _is_predominantly_english(lowered)


def _is_predominantly_english(text: str) -> bool:
    """Euristica rapida: true se il testo ha molti connettori inglesi tipici."""
    _STRONG_ENGLISH_MARKERS = (
        " the ", " this ", " that ", " with ", " from ", " have ", " will ",
        " your ", " their ", " which ", " would ", " should ", " could ",
        " been ", " they ", " must ", " upon ", " such ", " also ",
    )
    hits = sum(1 for marker in _STRONG_ENGLISH_MARKERS if marker in text)
    # Soglia: almeno 6 connettori inglesi distinti in un testo > 200 char
    return len(text) > 200 and hits >= 6


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
