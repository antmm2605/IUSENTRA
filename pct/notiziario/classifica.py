"""Tipo, materia e atti citati di una notizia, ricavati solo dal testo pubblicato dall'ente.

- Il tipo parte da quello del canale e si precisa con l'intestazione ufficiale
  (es. nella 1a Serie speciale della Gazzetta una «SENTENZA» è una pronuncia,
  un «RICORSO» o un'«ORDINANZA (Atto di promovimento)» è un atto di promovimento).
- La materia è quella della classificazione deterministica della biblioteca
  (`lex.normativa.materie.materia`); se il testo non ne indica una si usa quella
  dichiarata per il canale, altrimenti resta «non indicata».
- Gli atti citati sono chiavi normalizzate «tipo:numero:anno» (es. «dlgs:165:2001»)
  usate per collegare la notizia ai fascicoli che citano lo stesso atto.
"""

from __future__ import annotations

import re

from lex.normativa import materie as m
from pct.notiziario import fonti as f

_TIPI_ATTO: tuple[tuple[str, str], ...] = (
    (r"decreto\s+legislativo|d\.\s*lgs\.?|dlgs", "dlgs"),
    (r"decreto[\s-]+legge|d\.\s*l\.", "dl"),
    (r"decreto\s+del\s+presidente\s+della\s+repubblica|d\.\s*p\.\s*r\.", "dpr"),
    (r"legge\s+costituzionale", "lcost"),
    (r"legge|l\.", "legge"),
)
_MESI = r"(?:gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)"
_ATTO = re.compile(
    r"\b(?P<tipo>decreto\s+legislativo|d\.\s*lgs\.?|decreto[\s-]+legge|d\.\s*l\.|"
    r"decreto\s+del\s+presidente\s+della\s+repubblica|d\.\s*p\.\s*r\.|legge\s+costituzionale|legge|l\.)\s*"
    r"(?:(?:del\s+)?\d{1,2}\s+" + _MESI + r"\s+(?P<anno_esteso>\d{4}),?\s*)?"
    r"(?:n\.|numero|nr\.)?\s*(?P<numero>\d{1,5})"
    r"(?:\s*/\s*(?P<anno_breve>\d{4})|\s+del\s+(?P<anno_del>\d{4}))?",
    re.IGNORECASE,
)
_REGOLAMENTO_UE = re.compile(r"\b(?P<tipo>regolamento|direttiva)\s+(?:di\s+esecuzione\s+|delegato\s+)?\(?UE\)?\s+(?P<anno>\d{4})/(?P<numero>\d{1,5})", re.IGNORECASE)

_S1_PROMOVIMENTO = re.compile(r"\bRICORSO\b|Atto di promovimento", re.IGNORECASE)
_PCT = re.compile(r"telematic|DGSIA|specifiche tecniche|PST\b|portale dei servizi", re.IGNORECASE)


def tipo_della_notizia(fonte: f.Fonte, titolo: str) -> str:
    if fonte.id == "gu_corte_costituzionale" and _S1_PROMOVIMENTO.search(titolo):
        return f.NOTIZIA
    if fonte.id == "giustizia" and _PCT.search(titolo):
        return f.AVVISO_PCT
    return fonte.tipo


def materia_della_notizia(fonte: f.Fonte, testo: str) -> str:
    """Materia della biblioteca; stringa vuota quando né il testo né il canale la indicano."""
    if fonte.materia_certa:
        return fonte.materia
    urn = "eur-lex" if fonte.materia == m.UE else ""
    trovata = m.materia("", urn, testo)
    if trovata != m.ALTRO:
        return trovata
    return fonte.materia


def atti_citati(testo: str) -> list[str]:
    """Chiavi normalizzate degli atti citati per estremi (numero e anno), senza ripetizioni."""
    chiavi: list[str] = []
    for trovato in _ATTO.finditer(testo or ""):
        anno = trovato.group("anno_esteso") or trovato.group("anno_breve") or trovato.group("anno_del")
        if not anno:
            continue
        tipo_testo = trovato.group("tipo").lower()
        tipo = next(codice for schema, codice in _TIPI_ATTO if re.fullmatch(schema, tipo_testo.strip(), re.IGNORECASE))
        chiave = f"{tipo}:{int(trovato.group('numero'))}:{anno}"
        if chiave not in chiavi:
            chiavi.append(chiave)
    for trovato in _REGOLAMENTO_UE.finditer(testo or ""):
        tipo = "regue" if trovato.group("tipo").lower().startswith("reg") else "dirue"
        chiave = f"{tipo}:{int(trovato.group('numero'))}:{trovato.group('anno')}"
        if chiave not in chiavi:
            chiavi.append(chiave)
    return chiavi


__all__ = ["atti_citati", "materia_della_notizia", "tipo_della_notizia"]
