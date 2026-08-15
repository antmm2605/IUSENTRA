"""Riparto di spese condominiali e utenze pro-quota.

Base normativa:
- Art. 1123 c.c.: le spese condominiali sono ripartite in misura
  proporzionale al valore della proprietà di ciascuno (millesimi), salvo
  diversa convenzione; per le cose destinate a servire i condomini in
  misura diversa, in proporzione dell'uso.
- Art. 1118 c.c.: il diritto di ciascun condomino sulle parti comuni è
  proporzionale al valore dell'unità immobiliare.
- Per le utenze tra più occupanti il riparto per persone o per giorni di
  occupazione è il criterio aritmetico dichiarato dalle parti.

Fuori perimetro (dichiarato in output): il riparto degli oneri accessori
tra locatore e conduttore ex art. 9 L. 392/1978 (portineria al 90%, spese
integralmente a carico del conduttore) e il riparto del riscaldamento
centralizzato, vincolato ai consumi effettivi ex art. 9, c. 5, lett. d),
D.Lgs. 102/2014 (UNI 10200).

L'elenco delle quote si inserisce come testo, una voce per riga o
separata da punto e virgola, nel formato «nome: valore» (es. millesimi,
numero persone o giorni). Il tool non conosce le tabelle millesimali del
condominio: usa quelle fornite. La quadratura al centesimo usa il metodo
del resto maggiore, che distribuisce gli arrotondamenti mantenendo la
proporzionalità.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float

# «1.500» in un campo di testo italiano è quasi certamente millecinquecento
# (separatore delle migliaia), non 1,5: il pattern richiede prima cifra non
# zero così «0.125» resta un decimale.
_MIGLIAIA_IT = re.compile(r"^[1-9]\d{0,2}(\.\d{3})+$")


def _valore_quota(raw: str) -> float:
    testo = raw.strip()
    if _MIGLIAIA_IT.match(testo):
        return float(testo.replace(".", ""))
    return safe_float(testo)

_FONTE_CC_1123 = {
    "code": "cc_art_1123",
    "title": "Art. 1123 c.c. — ripartizione delle spese condominiali",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262",
}

_CRITERI = {
    "millesimi": {"label": "Millesimi di proprietà (art. 1123 c.c.)", "base_attesa": 1000.0},
    "persone": {"label": "Numero di persone (utenze)", "base_attesa": None},
    "giorni": {"label": "Giorni di occupazione (utenze)", "base_attesa": None},
}


def _parse_quote(testo: str) -> List[Dict[str, Any]]:
    quote: List[Dict[str, Any]] = []
    grezze = testo.replace(";", "\n").splitlines()
    for riga in grezze:
        riga = riga.strip()
        if not riga:
            continue
        if ":" not in riga:
            raise ValueError(
                f"Riga «{riga}» non valida: usare il formato «nome: valore» "
                "(una voce per riga o separata da punto e virgola)."
            )
        nome, _, valore_raw = riga.partition(":")
        nome = nome.strip()
        valore = _valore_quota(valore_raw)
        if not nome:
            raise ValueError("Ogni quota deve avere un nome prima dei due punti.")
        if valore <= 0:
            raise ValueError(f"La quota di «{nome}» deve essere un numero positivo.")
        quote.append({"nome": nome, "quota": valore})
    if len(quote) < 2:
        raise ValueError("Servono almeno due quote per il riparto.")
    if len(quote) > 200:
        raise ValueError("Riparto gestito fino a 200 quote.")
    nomi = [q["nome"].casefold() for q in quote]
    if len(set(nomi)) != len(nomi):
        raise ValueError("Ci sono nomi duplicati nell'elenco delle quote.")
    return quote


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    importo = safe_float(payload.get("rip_importo"))
    criterio = clean_text(payload.get("rip_criterio")) or "millesimi"
    quote_testo = clean_text(payload.get("rip_quote"))

    if importo <= 0:
        raise ValueError("Inserisci l'importo da ripartire.")
    if criterio not in _CRITERI:
        raise ValueError("Criterio ammesso: millesimi, persone o giorni.")
    if not quote_testo:
        raise ValueError(
            "Inserisci le quote nel formato «nome: valore», una per riga "
            "(es. «Interno 1: 120»)."
        )

    quote = _parse_quote(quote_testo)
    totale_quote = sum(q["quota"] for q in quote)

    # Metodo del resto maggiore: si assegna a ognuno il floor in centesimi
    # della propria parte esatta, poi i centesimi residui vanno alle voci con
    # frazione più alta — la quadratura non grava su un solo condomino.
    importo_cent = round(importo * 100)
    esatti = [importo_cent * q["quota"] / totale_quote for q in quote]
    assegnati = [int(v) for v in esatti]
    residuo = importo_cent - sum(assegnati)
    per_frazione = sorted(range(len(quote)), key=lambda i: esatti[i] - assegnati[i], reverse=True)
    for i in per_frazione[:residuo]:
        assegnati[i] += 1

    righe: List[Dict[str, Any]] = []
    for voce, centesimi in zip(quote, assegnati):
        righe.append(
            {
                "nome": voce["nome"],
                "quota": voce["quota"],
                "incidenza": round(voce["quota"] / totale_quote * 100.0, 4),
                "importo": centesimi / 100.0,
            }
        )

    warnings: List[str] = []
    voce_criterio = _CRITERI[criterio]
    base_attesa = voce_criterio["base_attesa"]
    if base_attesa and abs(totale_quote - base_attesa) > 0.01:
        warnings.append(
            f"I millesimi inseriti sommano a {totale_quote:g} invece di 1000: il riparto "
            "resta proporzionale ai valori forniti, ma verificare la tabella millesimale."
        )
    if criterio in ("persone", "giorni"):
        warnings.append(
            "Per riscaldamento e raffrescamento centralizzati il riparto è vincolato "
            "ai consumi effettivi ex art. 9, c. 5, lett. d), D.Lgs. 102/2014 (UNI "
            "10200) e non può essere sostituito da persone o giorni."
        )

    return {
        "criterio": voce_criterio["label"],
        "importo_totale": round(importo, 2),
        "totale_quote": round(totale_quote, 4),
        "numero_quote": len(quote),
        "riparto": righe,
        "notes": [
            "Riparto proporzionale ex art. 1123 c.c. (o criterio d'uso dichiarato); "
            "quadratura al centesimo col metodo del resto maggiore.",
            "La deroga al criterio millesimale richiede una convenzione approvata da "
            "tutti i condomini (regolamento contrattuale o accordo unanime): una "
            "delibera a maggioranza che modifichi i criteri di riparto è nulla "
            "(Cass. SS.UU. 9839/2021).",
            "Il riparto locatore/conduttore ex art. 9 L. 392/1978 (portineria 90%, "
            "spese a carico del conduttore) NON è applicato da questo calcolo e va "
            "operato separatamente.",
        ],
        "warnings": warnings,
        "sources": [_FONTE_CC_1123],
    }


def opzioni_criteri() -> list[dict]:
    return [{"value": chiave, "label": voce["label"]} for chiave, voce in _CRITERI.items()]
