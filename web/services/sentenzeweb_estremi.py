"""Estremi e intestazione leggibile delle pronunce della Cassazione (archivio SentenzeWeb).

La fonte ufficiale (ItalgiureWeb, campo ``kind``) distingue «snciv» (civile) e «snpen» (penale) e indica la sezione
con ``szdec``: un numero romano per le sezioni ordinarie, «U» per le Sezioni Unite, «L» per la Sezione lavoro e «F»
per la Sezione feriale. Qui quelle sigle diventano l'intestazione che l'avvocato cita («Cass. civ., Sez. II,
ordinanza n. 26870/2026») e la domanda «5425 2021 sezioni unite» diventa una ricerca per estremi sull'indice
(anno, numero), senza scorrere i testi.
"""
from __future__ import annotations

import re
from typing import Any

_ROMANI = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI", "7": "VII"}
_DA_ROMANO = {valore: chiave for chiave, valore in _ROMANI.items()}

_NUMERO_ANNO = re.compile(
    r"(?<![\d/])(?:n(?:r|um(?:ero)?)?\.?\s*)?(\d{1,6})\s*(?:/|-|,|\s+del(?:l'anno)?\s+|\s+anno\s+|\s+)\s*((?:19|20)\d{2})(?!\d)",
    re.IGNORECASE,
)
_SEZIONI_UNITE = re.compile(r"\bsez(?:ioni|\.)?\s*un(?:ite|\.)?|\bs\.\s*u\.|\bss\.\s*uu\.|\bsezioni\s+unite\b", re.IGNORECASE)
_LAVORO = re.compile(r"\b(?:sez(?:ione|\.)?\s*)?lav(?:oro|\.)", re.IGNORECASE)
_FERIALE = re.compile(r"\bferiale\b", re.IGNORECASE)
_SEZIONE = re.compile(r"\bsez(?:ione|\.)?\s*(vii|vi|v|iv|iii|ii|i|[1-7])\b", re.IGNORECASE)
_CIVILE = re.compile(r"\bciv(?:ile|\.)?(?!\w)", re.IGNORECASE)
_PENALE = re.compile(r"\bpen(?:ale|\.)?(?!\w)", re.IGNORECASE)


def estremi_cassazione(domanda: str, numero: str = "", anno: str = "") -> dict[str, Any] | None:
    """Numero, anno, sezione e ramo (civile/penale) indicati dall'avvocato; ``None`` se manca la coppia numero/anno."""

    testo = " ".join(str(domanda or "").split())
    numero = str(numero or "").strip()
    anno = str(anno or "").strip()
    if not (numero.isdigit() and re.fullmatch(r"(?:19|20)\d{2}", anno)):
        trovato = _NUMERO_ANNO.search(testo)
        if not trovato:
            return None
        numero, anno = trovato.group(1), trovato.group(2)
    sezione = ""
    if _SEZIONI_UNITE.search(testo):
        sezione = "U"
    elif _LAVORO.search(testo):
        sezione = "L"
    elif _FERIALE.search(testo):
        sezione = "F"
    else:
        indicata = _SEZIONE.search(testo)
        if indicata:
            valore = indicata.group(1).upper()
            sezione = _DA_ROMANO.get(valore, valore)
    ramo = "civile" if _CIVILE.search(testo) else "penale" if _PENALE.search(testo) else ""
    return {"numero": str(int(numero)), "anno": int(anno), "sezione": sezione, "ramo": ramo}


def ramo(organo: str) -> str:
    organo = str(organo or "").lower()
    return "civile" if "civile" in organo else "penale" if "penale" in organo else ""


def sezione_leggibile(codice: str, organo: str) -> str:
    """«Sezioni Unite civili», «Sezione lavoro», «Sezione II penale»; vuoto se la fonte non indica la sezione."""

    codice = str(codice or "").strip().upper()
    branca = ramo(organo)
    if not codice:
        return ""
    if codice == "U":
        return "Sezioni Unite " + ("civili" if branca == "civile" else "penali" if branca == "penale" else "")
    if codice == "L":
        return "Sezione lavoro"
    if codice == "F":
        return ("Sezione feriale " + branca).strip()
    if codice == "T" or (codice == "5" and branca == "civile"):
        # La V sezione civile della Cassazione è la sezione tributaria (tabelle di organizzazione della Corte).
        return "Sezione V civile (tributaria)" if codice == "5" else "Sezione tributaria"
    if codice in _ROMANI:
        return (f"Sezione {_ROMANI[codice]} " + branca).strip()
    return (f"Sezione {codice} " + branca).strip()


def _sezione_breve(codice: str) -> str:
    codice = str(codice or "").strip().upper()
    return {"U": "Sez. Un.", "L": "Sez. lav.", "F": "Sez. fer."}.get(codice) or (f"Sez. {_ROMANI.get(codice, codice)}" if codice else "")


def materia_leggibile(valore: Any) -> str:
    """La materia della fonte è in maiuscolo con l'apostrofo al posto dell'accento («RESPONSABILITA' CIVILE»)."""

    testo = " ".join(str(valore or "").split())
    if not testo:
        return ""
    if testo.upper() == testo:
        testo = testo.lower()
        testo = re.sub(r"([aeiou])'(?=\s|$|[,;.])", lambda m: {"a": "à", "e": "è", "i": "ì", "o": "ò", "u": "ù"}[m.group(1)], testo)
        testo = testo[:1].upper() + testo[1:]
    return testo


def intestazione(row: dict[str, Any]) -> str:
    """«Cass. civ., Sez. Un., sentenza n. 5425/2021»: gli estremi da citare, senza le sigle interne della fonte."""

    branca = ramo(row.get("organo_giudicante"))
    parti = ["Cass. civ." if branca == "civile" else "Cass. pen." if branca == "penale" else "Cass."]
    breve = _sezione_breve(row.get("sezione"))
    if breve:
        parti.append(breve)
    tipo = str(row.get("tipo_provvedimento") or "").strip().lower()
    numero = str(row.get("numero_sentenza") or "").lstrip("0") or str(row.get("numero_sentenza") or "")
    anno = str(row.get("anno_sentenza") or "")
    estremi = f"n. {numero}/{anno}" if numero and anno else ""
    if tipo and tipo != "provvedimento":
        estremi = f"{tipo} {estremi}".strip()
    if estremi:
        parti.append(estremi)
    return ", ".join(parti)
