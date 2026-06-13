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
_MAX_CANDIDATE_WINDOW = 180
_ARTICLE_MARK_RE = re.compile(r"artt?\.", re.IGNORECASE)
_ARTICLE_TOKEN_RE = re.compile(r"\d{1,4}(?:[\-/][A-Za-z0-9]{1,12})?")
_COMMA_RE = re.compile(r"\s*,?\s*comma\s*(?P<comma>[\divxIVX]+)", re.IGNORECASE)
_ATTO_PATTERN = (
    r"c\.p\.c\.|c\.c\.|c\.p\.|c\.p\.p\.|c\.p\.a\.|disp\.\s*att\.\s*c\.p\.c\.|"
    r"codice di procedura civile|codice civile|codice penale|"
    r"codice di procedura penale|codice del processo amministrativo|"
    r"d\.?\s*lgs\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"d\.?\s*l\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"d\.?p\.?r\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"d\.?m\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"l\.?\s*(?:n\.\s*)?\d+/\d{4}|"
    r"r\.?d\.?\s*(?:n\.\s*)?\d+/\d{4}"
)
_ATTO_AFTER_RE = re.compile(rf"\s*[,;]?\s*(?P<atto>{_ATTO_PATTERN})", re.IGNORECASE)
_ATTO_BEFORE_RE = re.compile(rf"(?P<atto>{_ATTO_PATTERN})\s*[-,;]?\s*$", re.IGNORECASE)

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


def _parse_articoli(window: str, start: int) -> tuple[str, int] | None:
    pos = start
    tokens = 0
    last_token_end = start
    while tokens <= 20:
        while pos < len(window) and window[pos].isspace():
            pos += 1
        match = _ARTICLE_TOKEN_RE.match(window, pos)
        if not match:
            break
        tokens += 1
        pos = match.end()
        last_token_end = pos

        after_token = pos
        while pos < len(window) and window[pos].isspace():
            pos += 1
        separator_start = pos
        if pos < len(window) and window[pos] in ",-":
            pos += 1
        elif window[pos:pos + 1].lower() == "e" and (
            pos + 1 == len(window) or window[pos + 1].isspace()
        ):
            pos += 1
        else:
            pos = after_token
            break

        while pos < len(window) and window[pos].isspace():
            pos += 1
        if not _ARTICLE_TOKEN_RE.match(window, pos):
            pos = after_token
            break
        if separator_start == after_token and pos == separator_start:
            break

    if tokens == 0:
        return None
    return window[start:last_token_end].strip(" \t\r\n,;-"), last_token_end


def _parse_comma_e_atto(window: str, start: int) -> tuple[str, str, int] | None:
    pos = start
    comma = ""
    comma_match = _COMMA_RE.match(window, pos)
    if comma_match:
        comma = str(comma_match.group("comma") or "").strip()
        pos = comma_match.end()
    atto_match = _ATTO_AFTER_RE.match(window, pos)
    if not atto_match:
        return None
    return atto_match.group("atto"), comma, atto_match.end()


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

    for marker in _ARTICLE_MARK_RE.finditer(testo):
        marker_start = marker.start()
        forward_end = min(len(testo), marker_start + _MAX_CANDIDATE_WINDOW)
        forward_window = testo[marker_start:forward_end]
        articoli = _parse_articoli(forward_window, marker.end() - marker_start)
        if articoli:
            articoli_raw, articoli_end = articoli
            direct = _parse_comma_e_atto(forward_window, articoli_end)
        else:
            direct = None
        if direct:
            atto_raw, comma_raw, end_offset = direct
            _aggiungi(
                atto_raw,
                articoli_raw,
                comma_raw,
                marker_start,
                marker_start + end_offset,
            )

        reverse_start = max(0, marker_start - 160)
        atto_before = _ATTO_BEFORE_RE.search(testo[reverse_start:marker_start])
        if atto_before and articoli:
            _aggiungi(
                atto_before.group("atto"),
                articoli_raw,
                "",
                reverse_start + atto_before.start(),
                marker_start + articoli_end,
            )
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
