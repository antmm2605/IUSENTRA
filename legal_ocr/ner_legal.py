"""Estrazione entità legali italiane dal testo OCR (NER leggero, deterministico).

Base normativa/operativa: i documenti giudiziari italiani contengono riferimenti
ricorrenti e formalizzati — numero di Ruolo Generale, ufficio giudiziario, parti,
date, riferimenti normativi — che seguono convenzioni stabili. Qui li estraiamo
con pattern + dizionario, senza modelli ML: è deterministico, testabile e non
"inventa" nulla (ogni entità riporta il testo sorgente effettivamente trovato).

Non sostituisce la validazione bloccante di `legal_regex`: è un arricchimento per
ricerca/indicizzazione e per pre-popolare i campi della pratica, sempre soggetto
a verifica umana (QC).
"""

from __future__ import annotations

import re
from typing import Any

_MESI = (
    "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|"
    "settembre|ottobre|novembre|dicembre"
)

_UFFICIO_TIPI = (
    "Corte di Cassazione",
    "Corte d'Appello",
    "Corte di Appello",
    "Corte d'Assise",
    "Tribunale per i Minorenni",
    "Tribunale di Sorveglianza",
    "Tribunale Amministrativo Regionale",
    "Tribunale",
    "Procura Generale",
    "Procura della Repubblica",
    "Giudice di Pace",
    "Consiglio di Stato",
    "TAR",
)

# R.G. / Ruolo Generale: numero/anno con molte varianti di scrittura.
_RG_RE = re.compile(
    r"\b(?:proc\.?\s*n\.?\s*)?(?:n\.?\s*)?(?:R\.?\s*G\.?\s*A\.?\s*C\.?|RGAC|"
    r"R\.?\s*G\.?(?:\s*N\.?\s*R\.?\s*)?|R\.?G\.?N\.?R\.?|"
    r"ruolo\s+generale|reg\.?\s*gen\.?)\s*(?:n\.?|numero)?\s*"
    r"(?P<num>\d{1,6})\s*/\s*(?P<anno>\d{2,4})\b",
    re.IGNORECASE,
)

_UFFICIO_RE = re.compile(
    r"\b(?P<tipo>" + "|".join(re.escape(t) for t in _UFFICIO_TIPI) + r")"
    r"(?:\s+(?:di|della|del|presso(?:\s+il)?)\s+(?P<sede>[A-Za-zÀ-Ù][A-Za-zÀ-ù'’.\- ]{1,40}?))?"
    r"(?=[\s,;.\n]|$)",
    re.IGNORECASE,
)

# Forma canonica del tipo ufficio (per normalizzare input maiuscolo/minuscolo).
_UFFICIO_CANONICO = {t.lower(): t for t in _UFFICIO_TIPI}

_PARTI_RE = re.compile(
    r"(?P<attore>[A-ZÀ-Ù][A-Za-zÀ-ù'’.\- ]{1,60}?)\s*"
    r"(?:\bc/\b|\bC/\b|\bcontro\b|\bc\.\s|\bvs\.?\b)\s*"
    r"(?P<convenuto>[A-ZÀ-Ù][A-Za-zÀ-ù'’.\- ]{1,60}?)(?=[\s,;.\n]|$)"
)
_PARTI_LABEL_RE = re.compile(
    r"\bparti\s*:\s*(?P<block>.{6,260}?)(?=\b(?:per\s+l['’]inoltro|tenuti|oggetto|"
    r"l['’]originale|il\s+funzionario|avviso|proc\.|ufficio)\b|$)",
    re.IGNORECASE | re.DOTALL,
)

_DATA_NUM_RE = re.compile(r"\b(?P<g>\d{1,2})[/\-.](?P<m>\d{1,2})[/\-.](?P<a>\d{2,4})\b")
_DATA_ESTESA_RE = re.compile(
    r"\b(?P<g>\d{1,2})\s+(?P<mese>" + _MESI + r")\s+(?P<a>\d{4})\b",
    re.IGNORECASE,
)

_RIF_ART_RE = re.compile(
    r"\bart(?:icol[oi]|t)?\.?\s*(?P<num>\d+(?:[\-\s]?(?:bis|ter|quater|quinquies|sexies))?)"
    r"(?:[,\s]*(?:c\.?\s*\d+))?"
    r"(?:[,\s]*(?P<codice>c\.p\.c\.|c\.p\.p\.|c\.c\.|c\.p\.|cost\.|disp\.\s*att\.))?",
    re.IGNORECASE,
)
_RIF_NORMA_RE = re.compile(
    r"\b(?P<tipo>L\.|Legge|D\.?\s*Lgs\.?|D\.?\s*L\.?|DPR|D\.?\s*P\.?\s*R\.?|"
    r"DM|D\.?\s*M\.?|DPCM|D\.?\s*P\.?\s*C\.?\s*M\.?)\s*(?:n\.?\s*)?"
    r"(?P<num>\d{1,4})\s*/\s*(?P<anno>\d{2,4})\b",
    re.IGNORECASE,
)
_IMPORTO_RE = re.compile(
    r"(?:(?:€|EUR|euro)\s*[\.,]?\s*\d{1,3}(?:[\.\s]\d{3})*(?:,\d{2})?|"
    r"\b\d{1,3}(?:[\.\s]\d{3})*,\d{2}\s*(?:€|EUR|euro)\b)",
    re.IGNORECASE,
)


def _dedupe(values: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        key = re.sub(r"\s+", " ", value).strip()
        if key and key not in seen:
            seen[key] = None
    return list(seen)


def _norm_anno(anno: str) -> str:
    anno = anno.strip()
    if len(anno) == 2:
        # Euristica conservativa: anni '00-'79 -> 2000+, '80-'99 -> 1900+.
        return ("20" if int(anno) < 80 else "19") + anno
    return anno


def extract_numero_ruolo(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in _RG_RE.finditer(text or ""):
        num = match.group("num")
        anno = _norm_anno(match.group("anno"))
        key = (num, anno)
        if key in seen:
            continue
        seen.add(key)
        out.append({"numero": num, "anno": anno, "testo": re.sub(r"\s+", " ", match.group(0)).strip()})
    return out


def _norm_sede(sede: str) -> str:
    # "MILANO" -> "Milano", "reggio emilia" -> "Reggio Emilia"; preserva apostrofi.
    return " ".join(part[:1].upper() + part[1:].lower() if part else part for part in sede.split(" ")).strip()


def extract_uffici(text: str) -> list[str]:
    out: list[str] = []
    for match in _UFFICIO_RE.finditer(text or ""):
        tipo = _UFFICIO_CANONICO.get(match.group("tipo").strip().lower(), match.group("tipo").strip())
        sede = _norm_sede((match.group("sede") or "").strip(" .,;"))
        out.append(f"{tipo} di {sede}" if sede else tipo)
    return _dedupe(out)


def extract_parti(text: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for match in _PARTI_RE.finditer(text or ""):
        attore = re.sub(r"\s+", " ", match.group("attore")).strip(" .,;")
        convenuto = re.sub(r"\s+", " ", match.group("convenuto")).strip(" .,;")
        if len(attore) < 2 or len(convenuto) < 2:
            continue
        key = (attore.lower(), convenuto.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"attore": attore, "convenuto": convenuto})
    for match in _PARTI_LABEL_RE.finditer(text or ""):
        names = _party_names_from_labeled_block(match.group("block"))
        if len(names) < 2:
            continue
        attore = names[0]
        convenuto = "; ".join(names[1:])
        key = (attore.lower(), convenuto.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append({"attore": attore, "convenuto": convenuto, "testo": "Parti: " + "; ".join(names)})
    return out


def _party_names_from_labeled_block(block: str) -> list[str]:
    raw = re.sub(r"\s+", " ", str(block or " ")).strip(" .,;:/")
    raw = re.sub(r"\b(?:dos|dott\.?|dott\.ssa|avv\.?|sig\.?|sig\.ra|sigg\.?)\b", " ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s+(?:e|contro|c/|vs\.?)\s+", " / ", raw, flags=re.IGNORECASE)
    pieces = re.split(r"\s*(?:/|;|,)\s*", raw)
    names: list[str] = []
    seen: set[str] = set()
    for piece in pieces:
        clean = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ'’.\- ]+", " ", piece)
        clean = re.sub(r"\s+", " ", clean).strip(" .,-")
        clean = re.sub(r"\b(?:l['’]?originale|per|tenuti|oggetto|ufficio)\b.*$", "", clean, flags=re.IGNORECASE).strip()
        if not _looks_like_party_name(clean):
            continue
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            names.append(clean)
    return names


def _looks_like_party_name(value: str) -> bool:
    clean = str(value or "").strip()
    if not (4 <= len(clean) <= 90):
        return False
    words = [word for word in re.split(r"\s+", clean) if re.search(r"[A-Za-zÀ-ÖØ-öø-ÿ]", word)]
    if len(words) < 2:
        return False
    stop_words = {"parti", "proc", "ufficio", "tribunale", "originale", "inoltro"}
    return not any(word.lower().strip(".") in stop_words for word in words[:2])


def extract_date(text: str) -> list[str]:
    out: list[str] = []
    for match in _DATA_NUM_RE.finditer(text or ""):
        out.append(match.group(0))
    for match in _DATA_ESTESA_RE.finditer(text or ""):
        out.append(re.sub(r"\s+", " ", match.group(0)).strip())
    return _dedupe(out)


def extract_riferimenti(text: str) -> list[str]:
    # Niente strip dei punti: le abbreviazioni legali finiscono in punto
    # (c.p.c., c.c., cost.); si rimuovono solo spazi/virgole/punti e virgola.
    out: list[str] = []
    for match in _RIF_ART_RE.finditer(text or ""):
        out.append(re.sub(r"\s+", " ", match.group(0)).strip(" ,;"))
    for match in _RIF_NORMA_RE.finditer(text or ""):
        out.append(re.sub(r"\s+", " ", match.group(0)).strip(" ,;"))
    return _dedupe(out)


def extract_importi(text: str) -> list[str]:
    return _dedupe([re.sub(r"\s+", " ", match.group(0)).strip(" ,;") for match in _IMPORTO_RE.finditer(text or "")])


def extract_legal_entities(text: str) -> dict[str, Any]:
    """Estrae le entità legali principali dal testo. Mai inventate: solo match reali."""

    clean = str(text or "")
    entities = {
        "numero_ruolo": extract_numero_ruolo(clean),
        "uffici": extract_uffici(clean),
        "parti": extract_parti(clean),
        "date": extract_date(clean),
        "riferimenti": extract_riferimenti(clean),
        "importi": extract_importi(clean),
    }
    entities["counts"] = {key: len(value) for key, value in entities.items()}
    return entities


__all__ = [
    "extract_legal_entities",
    "extract_numero_ruolo",
    "extract_uffici",
    "extract_parti",
    "extract_date",
    "extract_riferimenti",
    "extract_importi",
]
