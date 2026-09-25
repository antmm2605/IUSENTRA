"""Riconoscimento degli elenchi esportati dal PDP (.xlsx o .csv).

Colonne verificate sul portale (versione 6.11.10, 25/09/2026):

- procedimenti autorizzati: «Data Nomina», «Numero Registro», «Ufficio»,
  «Magistrato», «Soggetti Rappresentati»;
- depositi: «Ident. Invio», «Data Invio», «Data Arrivo», «Num. Registro»,
  «Ufficio», «Magistrato», «Soggetti Rappr.», «Tipo Atto», «Stato»;
- storico udienze (manuale PDP): data e ora, tipo ufficio, aula, luogo, causale.

Il numero di registro il PDP lo scrive come protocollo RegeWeb
«PM: N2023/1096» (ufficio, registro N/I, anno/numero): si legge così.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any

from . import stati
from .xlsx import XlsxError, leggi

# Sigla del protocollo -> codice tipo ufficio (codificati/ufficio-registro-riesame).
SIGLE_UFFICIO = {
    "PM": "PM-U", "GIP": "GIP-U", "DIB": "DIB-U", "CAS": "CAS-U", "PGCAP": "PGCAP-U", "CAP": "CAP-U",
    "CASAP": "CASAP-U", "PMGDP": "PM-G", "GDPC": "GP-C", "GDP": "GP-G", "APPGDP": "DIB-G", "RIE": "RIE",
}
_PROTOCOLLO = re.compile(r"(?:\b([A-Z]{2,6})\s*:\s*)?\b([NIBS])?\s*((?:19|20)\d{2})\s*/\s*(\d{1,8})\b")
_PAROLE = ("ufficio", "numero", "num", "registro", "magistrato", "soggett", "ident", "stato", "tipo atto",
           "data", "aula", "luogo", "causale")


def leggi_protocolli(testo: str) -> list[dict[str, str]]:
    """«PM: N2023/1096 GIP: N2023/1317» -> [{sigla, ufficio, registro, anno, numero}, …]."""
    esito = []
    for sigla, registro, anno, numero in _PROTOCOLLO.findall(str(testo or "").upper()):
        esito.append({"sigla": sigla, "ufficio": SIGLE_UFFICIO.get(sigla, ""), "registro": registro,
                      "anno": anno, "numero": str(int(numero))})
    return esito


def _norma(testo: str) -> str:
    return " ".join(re.sub(r"[^\w/ ]+", " ", str(testo or "").casefold()).split())


def _righe(dati: bytes) -> list[list[str]]:
    if dati[:2] == b"PK":
        return leggi(dati)
    for codifica in ("utf-8-sig", "cp1252"):
        try:
            testo = dati.decode(codifica)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise XlsxError("File non leggibile: usa l'export .xlsx o .csv del PDP.")
    separatore = ";" if testo.split("\n", 1)[0].count(";") > testo.split("\n", 1)[0].count(",") else ","
    return [[" ".join(c.split()) for c in riga] for riga in csv.reader(io.StringIO(testo), delimiter=separatore)]


def _riga_intestazione(righe: list[list[str]]) -> int:
    for indice, riga in enumerate(righe[:15]):
        if sum(1 for cella in riga if any(p in _norma(cella) for p in _PAROLE)) >= 3:
            return indice
    raise ValueError("Non trovo le intestazioni delle colonne: usa il file ottenuto con il tasto «Esporta» del PDP.")


def _colonna(intestazioni: list[str], *chiavi: str, escludi: tuple[str, ...] = ()) -> int:
    for chiave in chiavi:
        for i, testo in enumerate(intestazioni):
            if chiave in testo and not any(e in testo for e in escludi):
                return i
    return -1


def _tipo(intestazioni: list[str]) -> str:
    unione = " | ".join(intestazioni)
    if "ident" in unione and "invio" in unione:
        return "depositi"
    if "causale" in unione or "aula" in unione:
        return "udienze"
    if "magistrato" in unione and "soggett" in unione:
        return "procedimenti"
    return ""


def _data_iso(testo: str) -> str:
    trovata = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-]((?:19|20)\d{2})(?:\D+(\d{1,2})[:.](\d{2}))?", testo or "")
    if not trovata:
        return ""
    giorno, mese, anno, ora, minuti = trovata.groups()
    base = f"{anno}-{int(mese):02d}-{int(giorno):02d}"
    return f"{base}T{int(ora):02d}:{minuti}" if ora else base


def _cella(riga: list[str], indice: int) -> str:
    return riga[indice].strip() if 0 <= indice < len(riga) else ""


def leggi_export(dati: bytes) -> dict[str, Any]:
    """Tipo di elenco e righe normalizzate di un export del PDP."""
    righe = _righe(dati)
    if not righe:
        raise ValueError("Il file è vuoto.")
    posizione = _riga_intestazione(righe)
    intestazioni = [_norma(c) for c in righe[posizione]]
    tipo = _tipo(intestazioni)
    if not tipo:
        raise ValueError("Elenco non riconosciuto: importa l'export dei procedimenti autorizzati, dei depositi o dello storico udienze.")
    col = {
        "registro": _colonna(intestazioni, "numero registro", "num registro"),
        "ufficio": _colonna(intestazioni, "ufficio", escludi=("tipo ufficio", "registro")),
        "tipoUfficio": _colonna(intestazioni, "tipo ufficio"),
        "magistrato": _colonna(intestazioni, "magistrato"),
        "soggetti": _colonna(intestazioni, "soggett"),
        "dataNomina": _colonna(intestazioni, "data nomina"),
        "identificativo": _colonna(intestazioni, "ident"),
        "dataInvio": _colonna(intestazioni, "data invio"),
        "dataArrivo": _colonna(intestazioni, "data arrivo"),
        "tipoAtto": _colonna(intestazioni, "tipo atto"),
        "stato": _colonna(intestazioni, "stato"),
        "data": _colonna(intestazioni, "data e ora", "data"),
        "ora": _colonna(intestazioni, "ora", escludi=("data",)),
        "aula": _colonna(intestazioni, "aula"),
        "luogo": _colonna(intestazioni, "luogo"),
        "causale": _colonna(intestazioni, "causale"),
    }
    voci: list[dict[str, Any]] = []
    for riga in righe[posizione + 1:]:
        if not any(c.strip() for c in riga):
            continue
        voce: dict[str, Any] = {
            "protocolli": leggi_protocolli(_cella(riga, col["registro"])),
            "registroLetto": _cella(riga, col["registro"]),
            "ufficio": _cella(riga, col["ufficio"]),
            "magistrato": _cella(riga, col["magistrato"]),
            "soggetti": _cella(riga, col["soggetti"]),
        }
        if tipo == "procedimenti":
            voce["dataNomina"] = _data_iso(_cella(riga, col["dataNomina"]))
        elif tipo == "depositi":
            voce.update({
                "identificativo": _cella(riga, col["identificativo"]),
                "dataInvio": _data_iso(_cella(riga, col["dataInvio"])),
                "dataArrivo": _data_iso(_cella(riga, col["dataArrivo"])),
                "tipoAtto": _cella(riga, col["tipoAtto"]),
                "stato": stati.normalizza(_cella(riga, col["stato"])),
                "statoLetto": _cella(riga, col["stato"]),
            })
        else:
            quando = _data_iso(" ".join(filter(None, (_cella(riga, col["data"]), _cella(riga, col["ora"])))))
            if not quando:
                continue
            voce.update({"quando": quando, "tipoUfficio": _cella(riga, col["tipoUfficio"]), "aula": _cella(riga, col["aula"]),
                         "luogo": _cella(riga, col["luogo"]), "causale": _cella(riga, col["causale"])})
        voci.append(voce)
    return {"tipo": tipo, "righe": voci, "intestazioni": righe[posizione]}


__all__ = ["SIGLE_UFFICIO", "leggi_export", "leggi_protocolli"]
