"""Estrazione deterministica di riferimenti normativi da testo gia' recuperato.

Nessun LLM costruisce struttura: le citazioni nascono solo da pattern espliciti
nel testo delle fonti governate (regex su atto/articolo/comma). L'eventuale
riassunto e' un troncamento controllato del passaggio originale.
"""

from __future__ import annotations

import re
from typing import Any

from pct.procedure_completion.models import ProcedureCompletionCitation

_MAX_SNIPPET = 320

# "artt. 57-64" / "art. 633" / "art. 163-bis, comma 2"
_ART_RE = re.compile(
    r"artt?\.\s*(?P<articoli>\d+(?:[\-/]\w+)?(?:\s*[,e\-]\s*\d+(?:[\-/]\w+)?)*)"
    r"(?:\s*,?\s*comma\s*(?P<comma>[\divxIVX]+))?"
    r"\s*(?P<atto>"
    r"c\.p\.c\.|c\.c\.|c\.p\.|c\.p\.p\.|c\.p\.a\.|disp\.\s*att\.\s*c\.p\.c\.|"
    r"d\.?\s*lgs\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"d\.?\s*l\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"d\.?p\.?r\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"d\.?m\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"l\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"r\.?d\.?\s*(?:n\.\s*)?\d+/\d{4}"
    r")",
    re.IGNORECASE,
)

# Ordine inverso, comune nei titoli delle fonti: "D.Lgs. 14/2019, artt. 57-64"
# o "Codice di procedura civile - art. 633".
_ATTO_FIRST_RE = re.compile(
    r"(?P<atto>"
    r"codice di procedura civile|codice civile|codice penale|"
    r"codice di procedura penale|codice del processo amministrativo|"
    r"d\.?\s*lgs\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"d\.?\s*l\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"d\.?p\.?r\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"d\.?m\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"l\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"r\.?d\.?\s*(?:n\.\s*)?\d+/\d{4}"
    r")"
    r"\s*[-,;]?\s*artt?\.\s*(?P<articoli>\d+(?:[\-/]?\w+)?(?:\s*[,e\-]\s*\d+(?:[\-/]?\w+)?)*)"
    r"(?:\s*,?\s*comma\s*(?P<comma>[\divxIVX]+))?",
    re.IGNORECASE,
)

_NOMI_ESTESI = {
    "codice di procedura civile": "c.p.c.",
    "codice civile": "c.c.",
    "codice penale": "c.p.",
    "codice di procedura penale": "c.p.p.",
    "codice del processo amministrativo": "c.p.a.",
}

_ATTO_LABELS = {
    "c.p.c.": "Codice di procedura civile",
    "c.c.": "Codice civile",
    "c.p.": "Codice penale",
    "c.p.p.": "Codice di procedura penale",
    "c.p.a.": "Codice del processo amministrativo",
}


def _normalizza_atto(raw: str) -> str:
    atto = re.sub(r"\s+", " ", str(raw or "").strip())
    esteso = _NOMI_ESTESI.get(atto.lower())
    if esteso:
        return esteso
    compatto = atto.lower().replace(" ", "")
    if compatto in _ATTO_LABELS:
        return compatto
    atto = re.sub(r"(?i)^d\.?\s*lgs\.?\s*(?:n\.\s*)?", "D.Lgs. ", atto)
    atto = re.sub(r"(?i)^d\.?\s*l\.?\s*(?:n\.\s*)?(?=\d)", "D.L. ", atto)
    atto = re.sub(r"(?i)^d\.?p\.?r\.?\s*(?:n\.\s*)?", "D.P.R. ", atto)
    atto = re.sub(r"(?i)^d\.?m\.?\s*(?:n\.\s*)?", "D.M. ", atto)
    atto = re.sub(r"(?i)^l\.?\s*(?:n\.\s*)?(?=\d)", "L. ", atto)
    atto = re.sub(r"(?i)^r\.?d\.?\s*(?:n\.\s*)?", "R.D. ", atto)
    return atto


def _split_articoli(raw: str) -> list[str]:
    testo = str(raw or "").strip()
    intervallo = re.match(r"^(\d+)\s*-\s*(\d+)$", testo)
    if intervallo:
        inizio, fine = int(intervallo.group(1)), int(intervallo.group(2))
        if 0 < fine - inizio <= 30:
            return [str(n) for n in range(inizio, fine + 1)]
    parti = re.split(r"\s*[,e]\s*", testo)
    return [parte.strip() for parte in parti if parte.strip()]


def _snippet_intorno(testo: str, start: int, end: int) -> str:
    inizio = max(0, start - 80)
    fine = min(len(testo), end + 160)
    frammento = re.sub(r"\s+", " ", testo[inizio:fine]).strip()
    return frammento[:_MAX_SNIPPET]


def extract_normative_references(
    text: str,
    *,
    source_id: str = "",
    url: str = "",
    versione: str = "",
) -> list[ProcedureCompletionCitation]:
    """Citazioni puntuali (atto + articolo) trovate nel testo della fonte."""
    testo = str(text or "")
    if not testo.strip():
        return []
    citazioni: list[ProcedureCompletionCitation] = []
    visti: set[str] = set()

    def _aggiungi(atto_raw: str, articoli_raw: str, comma_raw: str, start: int, end: int) -> None:
        atto = _normalizza_atto(atto_raw)
        comma = str(comma_raw or "").strip()
        for articolo in _split_articoli(articoli_raw):
            chiave = f"{atto.lower()}|{articolo.lower()}|{comma}"
            if chiave in visti:
                continue
            visti.add(chiave)
            riferimento = f"art. {articolo} {atto}"
            if comma:
                riferimento = f"art. {articolo}, comma {comma}, {atto}"
            citazioni.append(
                ProcedureCompletionCitation(
                    riferimento=riferimento,
                    atto_normativo=atto,
                    articolo=articolo,
                    comma=comma,
                    versione=versione,
                    url=url,
                    source_id=source_id,
                    snippet=_snippet_intorno(testo, start, end),
                )
            )

    for match in _ART_RE.finditer(testo):
        _aggiungi(match.group("atto"), match.group("articoli"), match.group("comma"), match.start(), match.end())
    for match in _ATTO_FIRST_RE.finditer(testo):
        _aggiungi(match.group("atto"), match.group("articoli"), match.group("comma"), match.start(), match.end())
    return citazioni


def summarize_passage(text: str, *, max_chars: int = 400) -> str:
    """Riassunto deterministico: troncamento del passaggio originale, mai riscrittura."""
    pulito = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(pulito) <= max_chars:
        return pulito
    troncato = pulito[: max_chars - 3]
    ultimo_spazio = troncato.rfind(" ")
    if ultimo_spazio > max_chars // 2:
        troncato = troncato[:ultimo_spazio]
    return troncato + "..."


def references_from_rows(rows: list[dict[str, Any]]) -> list[ProcedureCompletionCitation]:
    """Citazioni da righe di evidenza gia' strutturate (principio + url + titolo)."""
    citazioni: list[ProcedureCompletionCitation] = []
    for row in rows or []:
        testo = " ".join(
            str(row.get(chiave) or "")
            for chiave in ("extracted_principle", "source_title", "title", "excerpt", "snippet")
        )
        citazioni.extend(
            extract_normative_references(
                testo,
                source_id=str(row.get("source_id") or row.get("id") or ""),
                url=str(row.get("source_url") or row.get("url") or ""),
                versione=str(row.get("last_checked_at") or ""),
            )
        )
    return citazioni


__all__ = ["extract_normative_references", "summarize_passage", "references_from_rows"]
