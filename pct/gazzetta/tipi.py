"""Tipo dell'atto letto dall'intestazione ufficiale del sommario («LEGGE 29 ottobre 2026, n. 201»).

La regola legge solo l'intestazione, l'ente emanante e la serie dichiarati dal sommario: nessuna parola del
testo dell'atto. L'ordine conta (prima le denominazioni più lunghe: «DECRETO-LEGGE» prima di «DECRETO»).
"""

from __future__ import annotations

import re

_MESI = {
    "gennaio": 1, "febbraio": 2, "marzo": 3, "aprile": 4, "maggio": 5, "giugno": 6, "luglio": 7,
    "agosto": 8, "settembre": 9, "ottobre": 10, "novembre": 11, "dicembre": 12,
}
_DATA = re.compile(r"\b(\d{1,2})[°º]?\s+(" + "|".join(_MESI) + r")\s+(\d{4})\b", re.IGNORECASE)
_NUMERO = re.compile(r",\s*n\.\s*([0-9]+(?:[/-][0-9A-Za-z]+)?)")
_NUMERO_CORTE = re.compile(r"^n\.\s*(\d+)\s+", re.IGNORECASE)

# chiave → etichetta mostrata nel filtro «Tipo di atto», nell'ordine del filtro
ETICHETTE: dict[str, str] = {
    "legge": "Legge",
    "decreto_legge": "Decreto-legge",
    "decreto_legislativo": "Decreto legislativo",
    "dpr": "D.P.R.",
    "dpcm": "D.P.C.M.",
    "dm": "Decreto ministeriale (D.M.)",
    "decreto_altro": "Altro decreto",
    "delibera": "Delibera",
    "ordinanza": "Ordinanza",
    "determina": "Determina o provvedimento",
    "testo_coordinato": "Testo coordinato",
    "comunicato": "Comunicato",
    "rettifica": "Rettifica o errata-corrige",
    "sentenza_corte": "Sentenza della Corte costituzionale",
    "ordinanza_corte": "Ordinanza della Corte costituzionale",
    "atto_promovimento": "Atto di promovimento (ricorso o ordinanza di rimessione)",
    "atto_ue": "Atto dell'Unione europea",
    "legge_regionale": "Legge regionale o provinciale",
    "atto_regionale": "Altro atto regionale",
    "concorso": "Concorso o avviso",
    "contratto": "Bando, avviso o esito di gara",
    "altro": "Altro atto",
}

# (prefisso dell'intestazione in maiuscolo, chiave): il primo che corrisponde vale
_PREFISSI: tuple[tuple[str, str], ...] = (
    ("TESTO COORDINATO", "testo_coordinato"),
    ("TESTO AGGIORNATO", "testo_coordinato"),
    ("ERRATA-CORRIGE", "rettifica"),
    ("ERRATA CORRIGE", "rettifica"),
    ("AVVISO DI RETTIFICA", "rettifica"),
    ("LEGGE COSTITUZIONALE", "legge"),
    ("LEGGE REGIONALE", "legge_regionale"),
    ("LEGGE PROVINCIALE", "legge_regionale"),
    ("LEGGE", "legge"),
    ("DECRETO-LEGGE", "decreto_legge"),
    ("DECRETO LEGISLATIVO", "decreto_legislativo"),
    ("DECRETO DEL PRESIDENTE DELLA REPUBBLICA", "dpr"),
    ("DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI", "dpcm"),
    ("DELIBERA", "delibera"),
    ("DELIBERAZIONE", "delibera"),
    ("ORDINANZA", "ordinanza"),
    ("DETERMINA", "determina"),
    ("DETERMINAZIONE", "determina"),
    ("PROVVEDIMENTO", "determina"),
    ("COMUNICATO", "comunicato"),
)


def tipo_atto(serie: str, intestazione: str, emittente: str = "") -> str:
    testo = " ".join(str(intestazione or "").split()).upper()
    testo = _NUMERO_CORTE.sub("", testo)
    if serie == "S4":
        return "concorso"
    if serie == "S5":
        return "contratto"
    if serie == "S1":
        if "PROMOVIMENTO" in testo or testo.startswith("RICORSO"):
            return "atto_promovimento"
        if testo.startswith("SENTENZA"):
            return "sentenza_corte"
        if testo.startswith("ORDINANZA"):
            return "ordinanza_corte"
    if serie == "S2" and re.match(r"^(REGOLAMENTO|DIRETTIVA|DECISIONE|RACCOMANDAZIONE)\b", testo):
        return "atto_ue"
    for prefisso, chiave in _PREFISSI:
        if testo == prefisso or testo.startswith(prefisso + " ") or testo.startswith(prefisso + ","):
            if serie == "S3" and chiave not in {"legge_regionale", "rettifica"}:
                return "atto_regionale"
            return chiave
    if testo.startswith("DECRETO"):
        if serie == "S3":
            return "atto_regionale"
        return "dm" if str(emittente or "").upper().startswith("MINISTERO") else "decreto_altro"
    return "atto_regionale" if serie == "S3" else "altro"


def data_atto(intestazione: str) -> str:
    """Ultima data «gg mese aaaa» dell'intestazione (per le pronunce: la data di deposito), in AAAA-MM-GG.

    Nei concorsi la data fra parentesi è la scadenza della domanda, non la data dell'atto: si lascia vuota.
    """
    if "(scad." in str(intestazione or "").lower():
        return ""
    trovate = list(_DATA.finditer(str(intestazione or "")))
    if not trovate:
        return ""
    giorno, mese, anno = trovate[-1].groups()
    try:
        from datetime import date

        return date(int(anno), _MESI[mese.lower()], int(giorno)).isoformat()
    except ValueError:
        return ""


def numero_atto(intestazione: str) -> str:
    testo = " ".join(str(intestazione or "").split())
    corte = _NUMERO_CORTE.match(testo)
    if corte:
        return corte.group(1)
    trovato = _NUMERO.search(testo)
    return trovato.group(1) if trovato else ""


__all__ = ["ETICHETTE", "data_atto", "numero_atto", "tipo_atto"]
