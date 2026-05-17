from __future__ import annotations

import re
from typing import Any

_DRAFT_MARKERS = re.compile(
    r"\bBOZZA\b[\s\S]{0,180}\b(diffida|messa in mora|lettera|pec|sollecito|contestazione)\b"
    r"|\bDIFFIDA E MESSA IN MORA\b"
    r"|\bDati da completare prima dell['\u2019]invio\b",
    re.IGNORECASE,
)
_TITLE_RE = re.compile(
    r"^\*{0,2}\s*(BOZZA\s*(?:[\u2014\u2013-]\s*)?"
    r"(?:DIFFIDA E MESSA IN MORA|LETTERA[^.\n]{0,80}|PEC[^.\n]{0,80}|"
    r"SOLLECITO[^.\n]{0,80}|CONTESTAZIONE[^.\n]{0,80}))\s*\*{0,2}\s*(?:\n{0,2}-{3,})?",
    re.IGNORECASE,
)


def looks_like_legal_draft(value: Any) -> bool:
    text = str(value or "").replace("\r", "").strip()
    return bool(text and _DRAFT_MARKERS.search(text))


def strip_draft_source_appendix(value: Any) -> str:
    clean = str(value or "").replace("\r", "").strip()
    if not looks_like_legal_draft(clean):
        return clean
    clean = re.sub(r"\s+Fonti consultate[\s\S]*$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+Dato certo[\s\S]*$", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+Qualit(?:\u00e0|a) della risposta[\s\S]*$", "", clean, flags=re.IGNORECASE)
    return clean.strip()


def normalize_legal_draft_layout(value: Any) -> str:
    """Impagina una bozza legale Lex anche quando il modello la restituisce piatta."""

    clean = strip_draft_source_appendix(value)
    if not looks_like_legal_draft(clean):
        return clean

    clean = re.sub(r"^Sintesi operativa\s+", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"^Risposta:\s*", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s*---\s*", "\n\n---\n\n", clean)
    clean = _TITLE_RE.sub(lambda match: f"**{match.group(1).strip()}**\n\n---\n\n", clean, count=1)

    clean = _normalize_checklist(clean)
    clean = _split_flat_draft_sections(clean)
    clean = _normalize_checklist(clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = re.sub(r"(\*\*Dati da completare prima dell'invio\*\*)\n(?=- )", r"\1\n\n", clean)
    clean = re.sub(r"[ \t]+\n", "\n", clean)
    return clean.strip()


def _normalize_checklist(value: str) -> str:
    clean = re.sub(
        r"\n?>\s*\*\*Dati da completare prima dell['\u2019]invio:\*\*",
        "\n\n**Dati da completare prima dell'invio**",
        value,
        flags=re.IGNORECASE,
    )
    clean = re.sub(
        r"\s+Dati da completare prima dell['\u2019]invio:\s*",
        "\n\n**Dati da completare prima dell'invio**\n\n",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(r"\s+>\s*-\s+", "\n- ", clean)
    clean = re.sub(r"\n>\s*-\s+", "\n- ", clean)
    return clean


def _split_flat_draft_sections(value: str) -> str:
    clean = value
    clean = re.sub(r"\s+(\d{1,2}/\d{1,2}/\d{4})(?=\s+Spett\.le\b)", r"\n\n\1\n\n", clean)
    clean = re.sub(r"\s+(Spett\.le)\s+", "\n\n**Spett.le**\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+(Oggetto:\s*)", "\n\n**Oggetto:** ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+(Con la presente,)", r"\n\n\1", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+Fatto\s+", "\n\n**Fatto**\n\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+Diritto\s+", "\n\n**Diritto**\n\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+Richiesta formale\s+", "\n\n**Richiesta formale**\n\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+Si diffida\s+", "\n\nSi diffida ", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+([1-9][.)]\s+)", r"\n\1", clean)
    clean = re.sub(r"\s+Avvertenza\s+", "\n\n**Avvertenza**\n\n", clean, flags=re.IGNORECASE)
    clean = re.sub(r"\s+(Con osservanza,)", r"\n\n---\n\n\1", clean, flags=re.IGNORECASE)
    clean = re.sub(
        r"(\*\*Spett\.le\*\*\n[^\n]+?)\s+(\[[Ii]ndirizzo[^\]]+\])",
        r"\1\n\2",
        clean,
    )
    clean = re.sub(r"(Con osservanza,)\s+(Avv\.[^\n]+)", r"\1\n\n\2", clean)
    return clean
