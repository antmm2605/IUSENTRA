"""Dati del calcolatore presi dalla domanda dell'avvocato, senza supporre nulla.

- date: al campo che la domanda nomina accanto («liquidazione 31/10/2026»); le
  altre nell'ordine in cui compaiono, ai campi data rimasti nell'ordine del modulo;
- importi in euro: al primo campo numerico che parla di somme (capitale, valore,
  importo, canone, retribuzione…), poi ai successivi;
- scelte: l'opzione il cui nome compare nella domanda; se non compare si usa la
  prima del modulo e la risposta lo dichiara come ipotesi da correggere;
- età, punti di invalidità e giorni: solo se la domanda li nomina in modo univoco
  («età 30 anni», «10 punti», «20 giorni di inabilità totale»); un numero che
  potrebbe andare a due campi resta fuori e lo chiede il calcolatore.

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
_ETA = (re.compile(r"\beta\b[^\d,;.]{0,15}?(\d{1,3})\b"), re.compile(r"\b(\d{1,3})\s*anni\s*(?:di|d')\s*eta\b"))
_PUNTI = re.compile(r"\b(\d{1,3}(?:,\d+)?)\s*punt[io]\b")
_GIORNI = r"\b(\d{1,4})\s*(?:gg|giorni)\b"
_GENERICHE = {"giorni", "di", "del", "della", "per", "art", "inabilita", "durata", "in"}


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
    _assegna_date(domanda, [c for c in visibili if c.get("type") == "date"], esito)
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
    _numeri_nominati(testo, visibili, esito)
    return esito


def _parole_chiave(campo: dict[str, Any]) -> list[str]:
    return [p for p in re.findall(r"[a-z]{5,}", _norm(campo.get("label", ""))) if p not in {"della", "dello", "data"}]


def _assegna_date(domanda: str, campi_data: list[dict[str, Any]], esito: DatiEstratti) -> None:
    chiavi = {c["name"]: _parole_chiave(c) for c in campi_data}
    senza_nome: list[Any] = []
    for segmento in re.split(r"[,;]|\s+e\s+", domanda):
        giorni = date_nella_domanda(segmento)
        if not giorni:
            continue
        testo = _norm(segmento)
        nominati = [c for c in campi_data if any(p in testo for p in chiavi[c["name"]])]
        if len(nominati) == 1 and len(giorni) == 1 and nominati[0]["name"] not in esito.valori:
            esito.valori[nominati[0]["name"]] = giorni[0].isoformat()
        else:
            senza_nome.extend(giorni)
    restanti = [c for c in campi_data if c["name"] not in esito.valori]
    for campo, giorno in zip(restanti, senza_nome):
        esito.valori[campo["name"]] = giorno.isoformat()


def _unico(valori: list[str]) -> str:
    distinti = sorted(set(valori))
    return distinti[0] if len(distinti) == 1 else ""


def _numeri_nominati(testo: str, visibili: list[dict[str, Any]], esito: DatiEstratti) -> None:
    liberi = [c for c in visibili if c.get("type") == "number" and c["name"] not in esito.valori]
    etichetta = {c["name"]: _norm(f"{c['name'].replace('_', ' ')} {c.get('label', '')}") for c in liberi}
    eta = [c for c in liberi if re.search(r"\beta\b", etichetta[c["name"]])]
    if len(eta) == 1:
        valore = _unico([m.group(1) for regola in _ETA for m in regola.finditer(testo)])
        if valore:
            esito.valori[eta[0]["name"]] = valore
    invalidita = [c for c in liberi if "invalidit" in etichetta[c["name"]] and c["name"] not in esito.valori]
    if len(invalidita) == 1:
        valore = _unico([_numero(m.group(1)) for m in _PUNTI.finditer(testo)])
        if valore:
            esito.valori[invalidita[0]["name"]] = valore
    giorni = [c for c in liberi if re.search(r"\bgiorn", etichetta[c["name"]])]
    if len(giorni) == 1:
        valore = _unico(re.findall(_GIORNI, testo))
        if valore:
            esito.valori[giorni[0]["name"]] = valore
        return
    for campo in giorni:
        parole = [p for p in re.findall(r"[a-z]{4,}", _norm(campo.get("label", ""))) if p not in _GENERICHE]
        if not parole:
            continue
        qualifica = re.escape(parole[-1])
        trovati = re.findall(_GIORNI + r"[^\d,;]{0,40}?\b" + qualifica, testo)
        if not trovati:
            trovati = re.findall(r"\b" + qualifica + r"\b[^\d,;]{0,20}?" + _GIORNI, testo)
        valore = _unico(trovati)
        if valore:
            esito.valori[campo["name"]] = valore


__all__ = ["DatiEstratti", "estrai"]
