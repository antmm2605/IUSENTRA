"""Elenco dei debitori da CSV (Excel: «Salva con nome» → CSV): una riga per documento del credito.

Le righe con lo stesso debitore (codice fiscale/partita IVA o, in mancanza, denominazione) formano una
posizione. Nessun dato viene inventato: una riga senza debitore, importo o data resta fra gli errori con
il numero di riga.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime
from typing import Any

from pct.recupero_crediti.modello import DocumentoCredito, Posizione

ALIAS = {
    "debitore": ("debitore", "denominazione", "ragione sociale", "cliente", "nominativo"),
    "codice": ("codice fiscale", "partita iva", "cf", "piva", "p.iva", "cf/piva", "codice"),
    "indirizzo": ("indirizzo", "sede", "residenza"),
    "pec": ("pec", "email pec", "domicilio digitale"),
    "numero": ("numero documento", "numero fattura", "fattura", "documento", "numero"),
    "data": ("data documento", "data fattura", "data"),
    "scadenza": ("scadenza", "data scadenza"),
    "importo": ("importo", "importo residuo", "totale", "da pagare"),
    "commerciale": ("commerciale", "transazione commerciale", "b2b"),
}
MASSIMO_RIGHE = 5000


def _chiave(intestazione: str) -> str:
    pulita = re.sub(r"\s+", " ", str(intestazione or "").strip().lower().replace("_", " "))
    for campo, nomi in ALIAS.items():
        if pulita in nomi:
            return campo
    return ""


def _data(valore: str) -> str:
    testo = str(valore or "").strip()
    for formato in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(testo, formato).date().isoformat()
        except ValueError:
            continue
    return ""


def _importo(valore: str) -> float | None:
    testo = str(valore or "").replace("€", "").replace(" ", "").strip()
    if not testo:
        return None
    if "," in testo:
        testo = testo.replace(".", "").replace(",", ".")
    try:
        numero = round(float(testo), 2)
    except ValueError:
        return None
    return numero if numero > 0 else None


def leggi_csv(contenuto: bytes, *, creditore_id: str, creditore: str, lotto: str) -> tuple[list[Posizione], list[str]]:
    testo = contenuto.decode("utf-8-sig", errors="replace")
    separatore = ";" if testo.count(";") >= testo.count(",") else ","
    lettore = csv.reader(io.StringIO(testo), delimiter=separatore)
    righe = list(lettore)
    if not righe:
        return [], ["Il file è vuoto."]
    colonne = [_chiave(c) for c in righe[0]]
    mancanti = [c for c in ("debitore", "importo", "data") if c not in colonne]
    if mancanti:
        return [], [f"Mancano le colonne: {', '.join(mancanti)} (intestazioni ammesse, es. «Debitore», «Importo», «Data fattura»)."]
    if len(righe) - 1 > MASSIMO_RIGHE:
        return [], [f"Il file supera {MASSIMO_RIGHE} righe: dividilo in più lotti."]
    posizioni: dict[str, Posizione] = {}
    errori: list[str] = []
    for numero_riga, riga in enumerate(righe[1:], start=2):
        if not any(c.strip() for c in riga):
            continue
        valori = {colonne[i]: v.strip() for i, v in enumerate(riga) if i < len(colonne) and colonne[i]}
        debitore = valori.get("debitore", "")
        importo = _importo(valori.get("importo", ""))
        data_doc = _data(valori.get("data", ""))
        if not debitore or importo is None or not data_doc:
            errori.append(f"Riga {numero_riga}: servono debitore, importo positivo e data valida.")
            continue
        if data_doc > date.today().isoformat():
            errori.append(f"Riga {numero_riga}: la data del documento è nel futuro.")
            continue
        codice = re.sub(r"\s", "", valori.get("codice", "")).upper()
        chiave = codice or debitore.casefold()
        posizione = posizioni.get(chiave)
        if posizione is None:
            posizione = Posizione(lotto=lotto, creditore_id=creditore_id, creditore=creditore, debitore=debitore,
                                  debitore_codice=codice, debitore_indirizzo=valori.get("indirizzo", ""),
                                  debitore_pec=valori.get("pec", ""),
                                  commerciale=str(valori.get("commerciale", "sì")).strip().lower() not in {"no", "0", "false"})
            posizioni[chiave] = posizione
        posizione.documenti.append(DocumentoCredito(numero=valori.get("numero", ""), data=data_doc,
                                                    scadenza=_data(valori.get("scadenza", "")), importo=importo))
    return list(posizioni.values()), errori


__all__ = ["ALIAS", "leggi_csv"]
