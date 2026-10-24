"""Importi monetari espliciti, con centesimi esatti; date e articoli non sono denaro."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

NUMERO = r"-?(?:[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)(?:,[0-9]{1,2})?"
EURO = re.compile(r"(?:€\s*|euro\s+)(" + NUMERO + r")|(" + NUMERO + r")\s*(?:€|euro\b)", re.I)


def centesimi(testo: str) -> int | None:
    try:
        value = Decimal(testo.replace(".", "").replace(",", "."))
        result = value * 100
        return int(result) if result.is_finite() and result == result.to_integral_value() else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def importi(testo: str) -> set[int]:
    values = (centesimi(m.group(1) or m.group(2)) for m in EURO.finditer(testo or ""))
    return {v for v in values if v is not None}
