"""Qualita' del testo PDF estratto e riparazione segnaposto CID."""

from __future__ import annotations

import re
from dataclasses import dataclass


CID_WARNING = "Rilevati e riparati segnaposto CID nel testo PDF."
_CID_RE = re.compile(r"\(cid:(\d{1,6})\)")


@dataclass(slots=True)
class TextQualityScore:
    score: float
    length: int
    cid_placeholders: int
    printable_ratio: float
    has_text: bool


def repair_pdf_cid_placeholders(text: str) -> tuple[str, list[str]]:
    """Converte segnaposto PDF `(cid:NN)` in caratteri ASCII sicuri.

    La riparazione e' intenzionalmente prudente: converte solo codepoint
    stampabili ASCII 32-126 e lascia intatti gli altri token.
    """

    source = str(text or "")
    repaired_any = False

    def repl(match: re.Match[str]) -> str:
        nonlocal repaired_any
        try:
            value = int(match.group(1))
        except ValueError:
            return match.group(0)
        if 32 <= value <= 126:
            repaired_any = True
            return chr(value)
        return match.group(0)

    repaired = _CID_RE.sub(repl, source)
    return repaired, [CID_WARNING] if repaired_any else []


def score_extracted_text_quality(text: str) -> TextQualityScore:
    source = str(text or "")
    length = len(source.strip())
    cid_count = len(_CID_RE.findall(source))
    if not source:
        return TextQualityScore(score=0.0, length=0, cid_placeholders=0, printable_ratio=0.0, has_text=False)
    printable = sum(1 for char in source if char.isprintable() or char in "\n\r\t")
    printable_ratio = printable / max(len(source), 1)
    score = 0.0
    if length:
        score += 0.45
    score += min(printable_ratio, 1.0) * 0.45
    if cid_count:
        score -= min(0.55, cid_count * 0.04)
    score = max(0.0, min(1.0, round(score, 4)))
    return TextQualityScore(
        score=score,
        length=length,
        cid_placeholders=cid_count,
        printable_ratio=round(printable_ratio, 4),
        has_text=bool(length),
    )


__all__ = ["CID_WARNING", "TextQualityScore", "repair_pdf_cid_placeholders", "score_extracted_text_quality"]
