"""Sentenza citata nella Ricerca legale: «Cass. S.U. 5425/2021» cerca quella pronuncia, non i numeri da soli.

Collaudo del 21/11/2026: la ricerca «Cass. S.U. 5425/2021» confrontava 5425 e 2021 come numeri qualsiasi e
proponeva la legge di bilancio 2021 e l'art. 2021 c.c. Quando la domanda indica un organo giudicante
(Cassazione, Corte costituzionale) e gli estremi numero/anno, i risultati restano le pronunce con quegli
estremi; la sezione, se indicata (S.U., sez. lav., sez. 3), deve coincidere.

L'estrazione degli estremi è quella condivisa dell'archivio (``pct.giurisprudenza_corpus.estremi_dalla_domanda``):
«legge n. 40/2004» o «d.lgs. 23/2015» non sono estremi di pronunce.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

_SEZIONI = (
    (re.compile(r"\bs\.?\s*u\.?(?![a-z])|sezioni\s+unite", re.IGNORECASE), "U"),
    (re.compile(r"\bsez(?:ione)?\.?\s*lav|\blavoro\b", re.IGNORECASE), "L"),
    (re.compile(r"\bsez(?:ione)?\.?\s*(?P<n>[1-6])\b", re.IGNORECASE), ""),
)


def estremi_sentenza(domanda: str) -> dict[str, str] | None:
    from pct.giurisprudenza_corpus import estremi_dalla_domanda

    testo = " ".join(str(domanda or "").split())
    dati = estremi_dalla_domanda(testo)
    if not dati["organo"] or len(dati["coppie"]) != 1:
        return None
    numero, anno = dati["coppie"][0]
    sezione = ""
    for regola, valore in _SEZIONI:
        trovato = regola.search(testo)
        if trovato:
            sezione = valore or trovato.group("n")
            break
    return {"organo": dati["organo"], "numero": str(numero), "anno": str(anno), "sezione": sezione}


def _numero(valore: Any) -> str:
    return str(valore or "").strip().lstrip("0")


def corrisponde(record: Mapping[str, Any], estremi: Mapping[str, str]) -> bool:
    """La scheda è la pronuncia citata: stessi numero e anno, dell'organo indicato, nella sezione indicata."""
    registro = str(record.get("registryNumber") or "")
    trovato = re.fullmatch(r"\s*0*(\d{1,6})\s*/\s*(\d{4})\s*", registro)
    if trovato:
        numero, anno = trovato.groups()
    else:
        testo = " ".join(str(record.get(k) or "") for k in ("title", "subtitle"))
        coppia = re.search(rf"(?<!\d)0*{re.escape(estremi['numero'])}\s*(?:/|del\s+)\s*{estremi['anno']}(?!\d)", testo)
        if not coppia:
            return False
        numero, anno = estremi["numero"], estremi["anno"]
    if _numero(numero) != _numero(estremi["numero"]) or anno != estremi["anno"]:
        return False
    fonte = " ".join(str(record.get(k) or "") for k in ("sourceLabel", "sourceKind", "title", "branch")).lower()
    if estremi["organo"] == "cassazione" and "cassazione" not in fonte:
        return False
    if estremi["organo"] == "costituzionale" and "costituzional" not in fonte:
        return False
    sezione = str(record.get("courtSection") or "").upper()
    return not (estremi["sezione"] and sezione and sezione not in {estremi["sezione"], "SU" if estremi["sezione"] == "U" else ""})


def filtra(records: list[dict[str, Any]], domanda: str) -> tuple[list[dict[str, Any]], dict[str, str] | None]:
    estremi = estremi_sentenza(domanda)
    if estremi is None:
        return records, None
    return [r for r in records if corrisponde(r, estremi)], estremi


def avviso_assente(estremi: Mapping[str, str]) -> str:
    organo = "Cassazione" if estremi["organo"] == "cassazione" else "Corte costituzionale"
    sezione = {"U": ", Sezioni Unite", "L": ", sezione lavoro"}.get(estremi["sezione"], f", sez. {estremi['sezione']}" if estremi["sezione"] else "")
    return (f"La pronuncia {organo}{sezione} n. {estremi['numero']}/{estremi['anno']} non è negli archivi del software "
            "consultati da questa ricerca. Aprila dal sito ufficiale della Corte oppure dall'Archivio sentenze per corte.")
