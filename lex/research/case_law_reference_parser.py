"""Parser per riferimenti legali esatti — sentenze, ordinanze, decreti.

Estrae struttura precisa da query come:
  "mi puoi trovare questa Sentenza n. 7919 del 31/03/2026"

e produce un ExactLegalReference con:
  - numero sentenza
  - data deposito/pubblicazione
  - anno
  - organo (Cassazione, TAR, Consiglio di Stato, Corte Costituzionale...)
  - sezione (civile, penale, amministrativa, tributaria...)
  - tipo atto (sentenza, ordinanza, decreto...)
  - is_exact_reference: True se numero+data/anno presenti
  - query web da usare per ricerca Cassazione

Quando is_exact_reference=True, Lex DEVE:
1. forzare workflow = giurisprudenza_specifica
2. forzare source_scope = public_legal_source
3. cercare sul web ufficiale (cortedicassazione.it prioritario)
4. non restituire elenco di sentenze diverse
5. se non trovato esatto → dire "non ho trovato conferma ufficiale esatta"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Tipi atto
# ---------------------------------------------------------------------------

TIPO_SENTENZA = "sentenza"
TIPO_ORDINANZA = "ordinanza"
TIPO_DECRETO = "decreto"
TIPO_PROVVEDIMENTO = "provvedimento"
TIPO_MASSIMA = "massima"

# ---------------------------------------------------------------------------
# Organi giudiziari riconosciuti
# ---------------------------------------------------------------------------

_ORGANO_PATTERNS: list[tuple[str, str]] = [
    (r"\bcass(?:azione)?\.?\s+(?:civ\.?|pen\.?|sez\.?|sezione)\b", "Corte di Cassazione"),
    (r"\bcorte\s+di\s+cassazione\b", "Corte di Cassazione"),
    (r"\bcassazione\b", "Corte di Cassazione"),
    (r"\bcorte\s+cost(?:ituzionale)?\b", "Corte Costituzionale"),
    (r"\bcons(?:iglio)?\s+di\s+stato\b", "Consiglio di Stato"),
    (r"\btar\s+[a-z]", "TAR"),
    (r"\btribunale\s+amministrativo\b", "TAR"),
    (r"\bcorte\s+d[i']\s+appello\b", "Corte d'Appello"),
    (r"\btribunale\s+di\s+[a-z]", "Tribunale"),
    (r"\btribunale\b", "Tribunale"),
    (r"\bgiudice\s+di\s+pace\b", "Giudice di Pace"),
]

# ---------------------------------------------------------------------------
# Pattern sezione/materia
# ---------------------------------------------------------------------------

_SEZIONE_PATTERNS: list[tuple[str, str]] = [
    (r"\bsezione\s+civile\b", "civile"),
    (r"\bsezione\s+penale\b", "penale"),
    (r"\bsezione\s+(?:lavoro|lavoristica)\b", "lavoro"),
    (r"\bsezione\s+tributaria\b", "tributaria"),
    (r"\bsezione\s+amministrativa\b", "amministrativa"),
    (r"\bsezione\s+fallimentare\b", "fallimentare"),
    (r"\bciv(?:ile)?\b", "civile"),
    (r"\bpen(?:ale)?\b", "penale"),
    (r"\blavoro\b", "lavoro"),
    (r"\btribut\b", "tributaria"),
    (r"\bamministrativ\b", "amministrativa"),
]

# ---------------------------------------------------------------------------
# Pattern numero atto
# ---------------------------------------------------------------------------

_NUMBER_PATTERNS = (
    r"n[°\.\s]*(\d{1,6})[/\-](\d{4})",        # n. NNNNN/YYYY
    r"n[°\.\s]*(\d{1,6})\s+del\s+\d",          # n. NNNNN del ...
    r"n[°\.\s]*(\d{1,6})",                       # n. NNNNN
    r"(\d{1,6})/(\d{4})",                        # NNNNN/YYYY
    r"#\s*(\d{1,6})",                            # #NNNNN
)

# Pattern data
_DATE_PATTERNS = (
    r"del\s+(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})",   # del GG/MM/AAAA
    r"(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})",             # GG/MM/AAAA
    r"del\s+(\d{1,2})\s+(\w+)\s+(\d{4})",                   # del GG Mese AAAA
    r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})",                 # AAAA-MM-GG
)

_MONTH_MAP = {
    "gennaio": "01", "febbraio": "02", "marzo": "03", "aprile": "04",
    "maggio": "05", "giugno": "06", "luglio": "07", "agosto": "08",
    "settembre": "09", "ottobre": "10", "novembre": "11", "dicembre": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
    "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


# ---------------------------------------------------------------------------
# Dataclass risultato
# ---------------------------------------------------------------------------

@dataclass
class ExactLegalReference:
    """Riferimento legale estratto dalla query utente."""

    kind: str                       # sentenza | ordinanza | decreto | provvedimento
    number: str                     # numero atto
    date: str                       # data in formato GG/MM/AAAA
    year: str                       # anno
    court: str                      # Corte di Cassazione | TAR | etc.
    section: str                    # civile | penale | tributaria | etc.
    jurisdiction: str               # civile | penale | amministrativa
    is_exact_reference: bool        # True se numero+anno/data presenti
    raw_query: str                  # query originale
    cassazione_query_variants: list[str] = field(default_factory=list)
    all_query_variants: list[str] = field(default_factory=list)
    confidence: float = 0.0
    debug_log: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "number": self.number,
            "date": self.date,
            "year": self.year,
            "court": self.court,
            "section": self.section,
            "jurisdiction": self.jurisdiction,
            "is_exact_reference": self.is_exact_reference,
            "cassazione_query_variants": self.cassazione_query_variants,
            "all_query_variants": self.all_query_variants,
            "confidence": round(self.confidence, 3),
        }


def _no_reference(raw_query: str) -> ExactLegalReference:
    """Ritorna un riferimento vuoto — query non contiene un riferimento esatto."""
    return ExactLegalReference(
        kind="", number="", date="", year="", court="", section="",
        jurisdiction="", is_exact_reference=False, raw_query=raw_query,
        confidence=0.0, debug_log=["no exact legal reference found"],
    )


# ---------------------------------------------------------------------------
# Parser principale
# ---------------------------------------------------------------------------

def parse_case_law_reference(question: str) -> ExactLegalReference:
    """Analizza una query e ritorna un ExactLegalReference.

    Ritorna is_exact_reference=True solo se numero E (anno O data) sono presenti.
    """
    raw = question
    text = " ".join(str(question or "").lower().split()).strip()
    debug: list[str] = []

    # ── 1. Tipo atto ─────────────────────────────────────────────────────────
    kind = _extract_kind(text, debug)
    if not kind:
        debug.append("kind: nessun tipo atto trovato → not exact reference")
        return _no_reference(raw)

    # ── 2. Organo ─────────────────────────────────────────────────────────────
    court = _extract_court(text, debug)

    # ── 3. Numero ─────────────────────────────────────────────────────────────
    number, year_from_number = _extract_number(text, debug)
    if not number:
        debug.append(f"number: non trovato nel testo: {text!r}")
        return _no_reference(raw)

    # ── 4. Data ───────────────────────────────────────────────────────────────
    date_str, year_from_date = _extract_date(text, debug)

    # ── 5. Anno definitivo ────────────────────────────────────────────────────
    year = year_from_date or year_from_number
    debug.append(f"year={year!r} (from_date={year_from_date!r}, from_number={year_from_number!r})")

    # ── 6. Sezione ────────────────────────────────────────────────────────────
    section = _extract_section(text, debug)

    # ── 7. Giurisdizione ─────────────────────────────────────────────────────
    jurisdiction = _infer_jurisdiction(court, section, text, debug)

    # ── 8. is_exact_reference ─────────────────────────────────────────────────
    is_exact = bool(number and (year or date_str))
    debug.append(f"is_exact_reference={is_exact} (number={number!r}, year={year!r}, date={date_str!r})")

    # ── 9. Confidence ─────────────────────────────────────────────────────────
    confidence = _calc_confidence(number, year, date_str, court, is_exact)

    # ── 10. Query variants ───────────────────────────────────────────────────
    cassazione_variants, all_variants = _build_query_variants(
        kind=kind, number=number, date=date_str, year=year, court=court, section=section
    )

    return ExactLegalReference(
        kind=kind,
        number=number,
        date=date_str,
        year=year,
        court=court,
        section=section,
        jurisdiction=jurisdiction,
        is_exact_reference=is_exact,
        raw_query=raw,
        cassazione_query_variants=cassazione_variants,
        all_query_variants=all_variants,
        confidence=confidence,
        debug_log=debug,
    )


# ---------------------------------------------------------------------------
# Helper privati
# ---------------------------------------------------------------------------

def _extract_kind(text: str, debug: list[str]) -> str:
    for word, kind in [
        ("sentenza", TIPO_SENTENZA),
        ("ordinanza", TIPO_ORDINANZA),
        ("decreto", TIPO_DECRETO),
        ("provvedimento", TIPO_PROVVEDIMENTO),
        ("massima", TIPO_MASSIMA),
    ]:
        if word in text:
            debug.append(f"kind={kind}")
            return kind
    return ""


def _extract_court(text: str, debug: list[str]) -> str:
    for pattern, court in _ORGANO_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            debug.append(f"court={court!r} (pattern={pattern!r})")
            return court
    debug.append("court: non trovato")
    return ""


def _extract_number(text: str, debug: list[str]) -> tuple[str, str]:
    """Ritorna (numero, anno_se_presente_nel_pattern)."""
    for pattern in _NUMBER_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            groups = [g for g in m.groups() if g]
            if len(groups) >= 2 and len(groups[1]) == 4:
                number = groups[0].lstrip("0") or groups[0]
                year = groups[1]
                debug.append(f"number={number!r} year_from_number={year!r} (pattern={pattern!r})")
                return number, year
            elif groups:
                number = groups[0].lstrip("0") or groups[0]
                debug.append(f"number={number!r} no year in pattern (pattern={pattern!r})")
                return number, ""
    return "", ""


def _extract_date(text: str, debug: list[str]) -> tuple[str, str]:
    """Ritorna (data_GG/MM/AAAA, anno)."""
    # Pattern del GG/MM/AAAA
    m = re.search(r"del\s+(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{2,4})", text)
    if m:
        day, month, yr = m.group(1), m.group(2), m.group(3)
        yr = _normalize_year(yr)
        date = f"{day.zfill(2)}/{month.zfill(2)}/{yr}"
        debug.append(f"date={date!r} (pattern del GG/MM/AAAA)")
        return date, yr

    # Pattern GG/MM/AAAA senza "del"
    m = re.search(r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b", text)
    if m:
        day, month, yr = m.group(1), m.group(2), m.group(3)
        date = f"{day.zfill(2)}/{month.zfill(2)}/{yr}"
        debug.append(f"date={date!r} (pattern GG/MM/AAAA)")
        return date, yr

    # Pattern testuale: del GG Mese AAAA
    m = re.search(r"del\s+(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    if m:
        day, month_text, yr = m.group(1), m.group(2).lower(), m.group(3)
        month = _MONTH_MAP.get(month_text, "")
        if month:
            date = f"{day.zfill(2)}/{month}/{yr}"
            debug.append(f"date={date!r} (pattern testuale)")
            return date, yr

    # Solo anno
    m = re.search(r"\b(20\d{2}|19\d{2})\b", text)
    if m:
        yr = m.group(1)
        debug.append(f"date: solo anno={yr!r}")
        return "", yr

    debug.append("date: non trovata")
    return "", ""


def _extract_section(text: str, debug: list[str]) -> str:
    for pattern, section in _SEZIONE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            debug.append(f"section={section!r}")
            return section
    return ""


def _infer_jurisdiction(court: str, section: str, text: str, debug: list[str]) -> str:
    if section:
        return section
    if "tar" in court.lower() or "consiglio di stato" in court.lower():
        return "amministrativa"
    if "penale" in text or "pen." in text:
        return "penale"
    if "civile" in text or "civ." in text:
        return "civile"
    if "tributaria" in text or "tribut" in text:
        return "tributaria"
    if "lavoro" in text:
        return "lavoro"
    return ""


def _normalize_year(yr: str) -> str:
    if len(yr) == 2:
        yr_int = int(yr)
        return str(2000 + yr_int) if yr_int <= 50 else str(1900 + yr_int)
    return yr


def _calc_confidence(number: str, year: str, date: str, court: str, is_exact: bool) -> float:
    if not is_exact:
        return 0.0
    score = 0.7
    if year:
        score += 0.1
    if date:
        score += 0.1
    if court:
        score += 0.1
    return min(round(score, 2), 1.0)


def _build_query_variants(
    *,
    kind: str,
    number: str,
    date: str,
    year: str,
    court: str,
    section: str,
) -> tuple[list[str], list[str]]:
    """Genera varianti di query per la ricerca sul web ufficiale."""
    cassazione_variants: list[str] = []
    all_variants: list[str] = []

    if not number:
        return [], []

    # Query Cassazione
    if court in ("", "Corte di Cassazione"):
        # Query più precisa con data
        if date:
            cassazione_variants.append(
                f'"{kind} n. {number}" "{date}" site:cortedicassazione.it'
            )
            cassazione_variants.append(
                f'"sentenza" "{number}" "{date}" cortedicassazione.it'
            )
        if year:
            cassazione_variants.append(
                f'site:cortedicassazione.it "{number}" "{year}"'
            )
        cassazione_variants.append(
            f'site:cortedicassazione.it/it/ "{number}"'
        )
        # DuckDuckGo-friendly
        if date:
            cassazione_variants.append(
                f'"{kind}" "{number}" "{date}" "cortedicassazione.it"'
            )
        if year:
            cassazione_variants.append(
                f'"{kind} n. {number}" "{year}" cassazione'
            )

    # Query generiche per tutti i domini legali
    if date:
        all_variants.append(f'"{kind}" "n. {number}" "{date}"')
    if year:
        all_variants.append(f'"{kind}" "n. {number}/{year}"')
    all_variants.append(f'"{kind} n. {number}"')
    if court and court != "Corte di Cassazione":
        if date:
            all_variants.append(f'"{kind}" "{number}" "{date}" {court}')
        if year:
            all_variants.append(f'"{kind} n. {number}/{year}" "{court}"')

    return cassazione_variants[:5], (cassazione_variants + all_variants)[:8]
