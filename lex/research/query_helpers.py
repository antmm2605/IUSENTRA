"""Funzioni utility leggere per classificazione query — senza dipendenze pesanti.

Usate da assistente_studio_context, router, test suite e altri moduli.
"""

from __future__ import annotations

import re
from typing import Any


_CF_RE = re.compile(
    r"\b([A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z])\b",
    re.IGNORECASE,
)
_PIVA_RE = re.compile(r"\b(?:IT)?(\d{11})\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b")

_EXACT_LEGAL_REF_PATTERNS = (
    r"\bsentenza\b.{0,90}\bn[°\.\s]*\d{1,6}",
    r"\bordinanza\b.{0,90}\bn[°\.\s]*\d{1,6}",
    r"\bdecreto\b.{0,90}\bn[°\.\s]*\d{1,6}",
    r"\bn[°\.\s]*\d{1,6}\s+del\s+\d",
    r"\bn[°\.\s]*\d{1,6}/\d{4}",
    r"\bcass(?:azione)?\.?\s*(?:civ|pen|lav|sez)\.?\s*\d",
)


def extract_entity_hint(query: str) -> dict[str, str]:
    """Estrae CF, PIVA, email dalla query per ricerca mirata del cliente."""
    text = query or ""
    cf = _CF_RE.search(text)
    piva = _PIVA_RE.search(text)
    email = _EMAIL_RE.search(text)
    return {
        "codice_fiscale": cf.group(0).upper() if cf else "",
        "partita_iva": piva.group(1) if piva else "",
        "email": email.group(0).lower() if email else "",
    }


def is_exact_legal_reference_query(text: str) -> bool:
    """True se la query contiene un riferimento esatto a sentenza/ordinanza con numero."""
    for p in _EXACT_LEGAL_REF_PATTERNS:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False
