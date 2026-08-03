"""Lettura del capo spese di una sentenza: importo liquidato + brano che lo prova.

Punto unico di verita' per due percorsi che prima leggevano in modo diverso lo
stesso dispositivo:

- l'automazione economica del fascicolo (`pct.fascicolo_sentenza_economica`);
- l'audit economico che parte dalla PEC (`pct.sentenza_economic_audit`), che
  prendeva l'importo piu' alto del testo e quindi confondeva il beneficio
  riconosciuto al cliente con il compenso liquidato all'avvocato.

Base normativa: art. 91 c.p.c. (condanna alle spese, liquidate dal giudice nel
dispositivo) e art. 93 c.p.c. (distrazione in favore del difensore
antistatario); tariffe forensi D.M. 55/2014 e D.M. 147/2022.

Modulo puro: nessuna dipendenza dal dominio o da Flask, cosi' resta importabile
anche dai motori deterministici.
"""

from __future__ import annotations

import re
from typing import Any

MOJIBAKE_EURO = "â‚¬"
MONEY_AMOUNT_PATTERN = r"(?:\d{1,3}(?:[.\s]\d{3})+|\d+)(?:[,.]\d{2})?"
MONEY_PREFIX_PATTERN = r"(?:€|EUR|euro|" + re.escape(MOJIBAKE_EURO) + r"|\?)"
MONEY_RE = re.compile(
    MONEY_PREFIX_PATTERN + r"\s*(?P<amount>" + MONEY_AMOUNT_PATTERN + r")",
    re.IGNORECASE,
)

# Forma con connettore esplicito: "liquida ... la somma di € 3.000,00".
_LIQUIDAZIONE_RE = re.compile(
    r"\bliquid(?:a|ando|ata|ato|ate|ati)\b.{0,160}?"
    r"(?:(?:complessiv[aoei]\s+)?(?:somma|importo)\s+(?:di\s+)?|(?:in\s+)?complessiv[aoei]\s+)"
    + MONEY_PREFIX_PATTERN
    + r"\s*"
    r"(?P<amount>" + MONEY_AMOUNT_PATTERN + r")",
    re.IGNORECASE | re.DOTALL,
)
# Forma diretta, la piu' frequente nei dispositivi italiani: "condanna ... alla
# rifusione delle spese di lite ... che liquida in euro 500,00 oltre spese
# generali, iva e cpa". Senza connettore "somma/importo/complessiva" il pattern
# sopra non aggancia nulla e il credito dell'avvocato non nasce.
_LIQUIDAZIONE_DIRETTA_RE = re.compile(
    r"\bliquid(?:a|ando|ata|ato|ate|ati)\b"
    r"(?:\s+(?:la\s+|le\s+|i\s+|il\s+)?(?:spese|competenze|compensi|onorari|somma|importo)"
    r"(?:\s+(?:di\s+lite|di\s+giudizio|legali|professionali|complessiv[aoei]|forfettari[ao]))?"
    r"(?:\s+di)?)?"
    r"(?:\s+(?:in|nella\s+misura\s+di|pari\s+a))?"
    r"[\s,:]*"
    + MONEY_PREFIX_PATTERN
    + r"\s*(?P<amount>"
    + MONEY_AMOUNT_PATTERN
    + r")",
    re.IGNORECASE,
)
_LIQUIDAZIONE_WORD_RE = re.compile(r"\bliquid(?:a|ando|ata|ato|ate|ati)\b", re.IGNORECASE)
_LIQUIDAZIONE_CONTEXT_RE = re.compile(
    r"\b(?:spese\s+di\s+lite|rifusione\s+delle\s+spese|compensi\s+professionali|onorari|"
    r"p\.?\s*q\.?\s*m\.?|definitivamente\s+pronunciando)\b",
    re.IGNORECASE,
)
_COMPENSI_AFTER_AMOUNT_RE = re.compile(
    r"^[\s,;:.]*(?:per|a\s+titolo\s+di)\s+(?:compensi(?:\s+professionali)?|onorari)\b",
    re.IGNORECASE | re.DOTALL,
)
# Un importo dichiarato "per esborsi" o "per contributo unificato" non e' il
# compenso del difensore: non deve diventare un credito da parcella.
_NON_COMPENSI_AFTER_AMOUNT_RE = re.compile(
    r"^[\s,;:.]*(?:per|a\s+titolo\s+di)\s+"
    r"(?:spese(?!\s+generali)|esbors[oi]|spese\s+vive|contribut[oi]\s+unificat[oi]|c\.?\s*u\.?)\b",
    re.IGNORECASE | re.DOTALL,
)


def compatta_testo(value: str) -> str:
    """Testo su una riga: l'OCR spezza il dispositivo su piu' righe."""

    return re.sub(r"\s+", " ", str(value or "")).strip()


def parse_importo(value: Any) -> float | None:
    """Legge un importo in formato italiano (1.234,56) tollerando spazi da OCR."""

    raw = str(value if value is not None else "").strip().replace(" ", "")
    if not raw:
        return None
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(?:\.\d{3})+", raw):
        raw = raw.replace(".", "")
    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def estratto_testo(text: str, start: int, end: int, *, window: int = 90) -> str:
    """Brano attorno alla corrispondenza: e' la fonte mostrata all'avvocato."""

    left = max(0, start - window)
    right = min(len(text), end + window)
    return compatta_testo(text[left:right])[:360]


def estrai_spese_liquidate(testo: str) -> tuple[float | None, str]:
    """Importo liquidato a titolo di compensi e brano del dispositivo che lo prova.

    Ritorna `(None, "")` quando il dispositivo non liquida compensi (spese
    compensate, importi solo per esborsi o per contributo unificato): meglio
    nessun credito che un credito inventato.
    """

    text = compatta_testo(testo)

    # Priorita' all'importo qualificato "per compensi": e' il piu' esplicito.
    compensi: list[tuple[int, re.Match[str]]] = []
    for money in MONEY_RE.finditer(text):
        if parse_importo(money.group("amount")) is None:
            continue
        after = text[money.end() : min(len(text), money.end() + 120)]
        if not _COMPENSI_AFTER_AMOUNT_RE.match(after):
            continue
        context = text[max(0, money.start() - 260) : min(len(text), money.end() + 180)]
        if not (_LIQUIDAZIONE_WORD_RE.search(context) or _LIQUIDAZIONE_CONTEXT_RE.search(context)):
            continue
        before = text[max(0, money.start() - 260) : money.start()]
        parole = list(_LIQUIDAZIONE_WORD_RE.finditer(before))
        distanza = money.start() - parole[-1].start() if parole else 9999
        compensi.append((distanza, money))
    if compensi:
        _, match = min(compensi, key=lambda item: (item[0], item[1].start()))
        return parse_importo(match.group("amount")), estratto_testo(text, match.start(), match.end(), window=180)

    for pattern in (_LIQUIDAZIONE_RE, _LIQUIDAZIONE_DIRETTA_RE):
        candidati: list[tuple[int, re.Match[str]]] = []
        for match in pattern.finditer(text):
            if parse_importo(match.group("amount")) is None:
                continue
            fine = match.end("amount")
            if _NON_COMPENSI_AFTER_AMOUNT_RE.match(text[fine : min(len(text), fine + 90)]):
                continue
            candidati.append((match.start(), match))
        if candidati:
            _, match = min(candidati, key=lambda item: item[0])
            return parse_importo(match.group("amount")), estratto_testo(text, match.start(), match.end(), window=90)
    return None, ""


__all__ = [
    "MOJIBAKE_EURO",
    "MONEY_AMOUNT_PATTERN",
    "MONEY_PREFIX_PATTERN",
    "MONEY_RE",
    "compatta_testo",
    "estrai_spese_liquidate",
    "estratto_testo",
    "parse_importo",
]
