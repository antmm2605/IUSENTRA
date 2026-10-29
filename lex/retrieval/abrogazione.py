"""Marcatura degli articoli il cui testo archiviato e' soltanto un avviso di abrogazione.

Non decide l'applicabilita' temporale: segnala che il testo restituito dalla biblioteca non e' disciplina
operativa ma l'avviso «ARTICOLO ABROGATO DAL ...», cosi' che ricerca e guardie non lo presentino come norma
vigente. L'atto abrogante e' copiato dal testo dell'avviso, mai dedotto.
"""
from __future__ import annotations

import re
from typing import Any

from lex.normativa.qualita_testo import qualita_testo

_ABROGATO_INTERO = re.compile(r"^\s*Art\.?\s*[\w\-.]+\s*(?:\([^)]*\))?\s*\(*\s*ARTICOLO\s+ABROGATO", re.I)
_ABROGATO_DA = re.compile(r"ABROGAT[OA]\s+DA(?:L|LLA|LL'|GLI|I)?\s+([^()]{5,160}?)\s*(?:\)\)|\)\s*$|$)", re.I)


def abrogazione(testo: Any) -> dict | None:
    """``{"abrogato": True, "abrogato_da": "..."}`` se il testo e' un avviso di abrogazione, altrimenti None."""
    if not isinstance(testo, str) or not testo.strip():
        return None
    if qualita_testo(testo) != "avviso_abrogazione" and not _ABROGATO_INTERO.search(testo):
        return None
    da = _ABROGATO_DA.search(testo[:400])
    return {"abrogato": True, "abrogato_da": " ".join(da.group(1).split()) if da else ""}


def tagga_abrogazione(row: dict) -> dict:
    """Restituisce la riga con ``abrogato``/``abrogato_da`` (anche in ``metadata``) quando il testo e' un avviso."""
    if not isinstance(row, dict):
        return row
    testo = row.get("normative_full_text") or row.get("testo") or row.get("content") or row.get("text") or ""
    esito = abrogazione(testo)
    if esito is None:
        return row
    out = dict(row, **esito, qualita_testo="avviso_abrogazione")
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        out["metadata"] = dict(metadata, **esito)
    return out


__all__ = ["abrogazione", "tagga_abrogazione"]
