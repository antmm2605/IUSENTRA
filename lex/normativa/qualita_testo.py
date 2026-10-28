"""Distingue il corpo acquisito da intestazioni e avvisi sostitutivi.

Non valuta vigenza o applicabilità: un articolo contenente una vera disciplina
abrogativa resta testo normativo. Un avviso che sostituisce il testo storico
non dimostra invece il contenuto della norma anteriore.
"""
from __future__ import annotations
import re


def qualita_testo(testo: str, *, solo_rubrica: bool = False) -> str:
    if not isinstance(testo,str) or not testo.strip():return "assente"
    compact=" ".join(testo.split())
    remainder=compact
    for _ in range(6):
        after=re.sub(r"^\s*(?:ART\.?\s*\d+(?:[-./](?:\d+|BIS|TER|QUATER))*[. :]?\s*|\d+[.)]?\s+)","",remainder,count=1,flags=re.I)
        if after==remainder:break
        remainder=after
    if re.match(r"^[ (]*?(?:PROVVEDIMENTO|ARTICOLO)\s+ABROGAT[OA]\b",remainder,re.I):
        return "avviso_abrogazione"
    if solo_rubrica is True:return "sola_intestazione"
    return "testo_acquisito"
