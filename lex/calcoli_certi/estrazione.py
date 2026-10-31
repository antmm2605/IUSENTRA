"""Dati del calcolatore presi dalla domanda dell'avvocato, senza supporre nulla.

- date: nell'ordine in cui compaiono, ai campi data nell'ordine del modulo;
- importi in euro: al primo campo numerico che parla di somme (capitale, valore,
  importo, canone, retribuzione…), poi ai successivi;
- scelte: l'opzione il cui nome compare nella domanda; se non compare si usa la
  prima del modulo e la risposta lo dichiara come ipotesi da correggere.

Ciò che manca resta vuoto: lo segnala il calcolatore con il suo messaggio.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from lex.risposte_certe import date_nella_domanda

_IMPORTI = re.compile(
    r"(?:€|euro)\s*(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)"
    r"|(\d{1,3}(?:\.\d{3})+(?:,\d{1,2})?|\d+(?:,\d{1,2})?)\s*(?:€|euro)"
)
_PERCENTUALI = re.compile(r"(\d+(?:,\d+)?)\s*(?:%|per ?cento)")
_SOMME = re.compile(r"capital|valore|importo|somma|canone|retribu|compens|reddit|prezzo|rendita|credito|stipendio|pension|asse|patrimon|spese|onorar")
_PERCENTUALE = re.compile(r"percentual|tasso|aliquota|invalidit|%")


def _norm(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c))


def _numero(grezzo: str) -> str:
    return grezzo.replace(".", "").replace(",", ".")


@dataclass
class DatiEstratti:
    valori: dict[str, str] = field(default_factory=dict)
    ipotesi: list[str] = field(default_factory=list)


def _visibile(campo: dict[str, Any], valori: dict[str, str], campi: list[dict[str, Any]]) -> bool:
    condizione = campo.get("quando")
    if not isinstance(condizione, dict):
        return True
    controllo = str(condizione.get("campo") or "")
    attuale = valori.get(controllo)
    if attuale is None:
        primo = next((c for c in campi if c.get("name") == controllo), {})
        opzioni = primo.get("options") or []
        attuale = str(opzioni[0]["value"]) if opzioni else ""
    return attuale in [str(v) for v in condizione.get("valori") or []]


def estrai(domanda: str, campi: list[dict[str, Any]]) -> DatiEstratti:
    testo = _norm(domanda)
    esito = DatiEstratti()
    # 1. scelte: prima, perché decidono quali altri campi sono visibili
    for campo in campi:
        if campo.get("type") != "select" or not campo.get("options"):
            continue
        opzioni = campo["options"]
        trovata = next((o for o in opzioni if _norm(o.get("label", "")) and _norm(o.get("label", "")) in testo), None)
        if trovata is None:
            trovata = next((o for o in opzioni if str(o.get("value", "")) and _norm(str(o["value"])).replace("_", " ") in testo), None)
        if trovata is not None:
            esito.valori[campo["name"]] = str(trovata["value"])
        else:
            esito.valori[campo["name"]] = str(opzioni[0]["value"])
            if len(opzioni) > 1:
                esito.ipotesi.append(f"{campo.get('label', campo['name'])}: {opzioni[0].get('label', opzioni[0]['value'])}")
    visibili = [c for c in campi if _visibile(c, esito.valori, campi)]
    # 2. date nell'ordine del modulo
    date_ = date_nella_domanda(domanda)
    for campo, giorno in zip([c for c in visibili if c.get("type") == "date"], date_):
        esito.valori[campo["name"]] = giorno.isoformat()
    # 3. importi in euro ai campi che parlano di somme
    importi = [_numero(m.group(1) or m.group(2)) for m in _IMPORTI.finditer(testo)]
    campi_somma = [c for c in visibili if c.get("type") == "number" and _SOMME.search(_norm(f"{c['name']} {c.get('label', '')}"))]
    for campo, valore in zip(campi_somma, importi):
        esito.valori[campo["name"]] = valore
    # 4. percentuali ai campi percentuali
    percentuali = [_numero(m.group(1)) for m in _PERCENTUALI.finditer(testo)]
    campi_percento = [c for c in visibili if c.get("type") == "number" and c["name"] not in esito.valori
                      and _PERCENTUALE.search(_norm(f"{c['name']} {c.get('label', '')}"))]
    for campo, valore in zip(campi_percento, percentuali):
        esito.valori[campo["name"]] = valore
    return esito


__all__ = ["DatiEstratti", "estrai"]
