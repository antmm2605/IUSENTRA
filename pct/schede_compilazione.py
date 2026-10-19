"""Schede di compilazione degli atti: da dove viene ogni dato e chi lo scrive.

Ogni scheda (``pct/template_atti_schede/<ID>.json``) dichiara, per un modello di atto, i campi con la
loro base normativa e la fonte: ``database`` (gestionale), ``archivio_letture`` (fatti letti dai documenti
e dalle PEC), ``documento``, ``calcolo`` (regola deterministica del software), ``avvocato`` (dato da
chiedere) o ``lex`` (proposta da confermare). Le parti narrative che Lex può redigere e i casi in cui
deve astenersi sono elencati nella scheda. Base normativa: c.p.c. e leggi citate in ciascuna scheda.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

CARTELLA = Path(__file__).with_name("template_atti_schede")
FONTI = ("database", "archivio_letture", "documento", "calcolo", "avvocato", "lex")


@lru_cache(maxsize=1)
def carica_schede() -> dict[str, dict[str, Any]]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(CARTELLA.glob("*.json"))}


def scheda_per_template(template_id: str) -> dict[str, Any] | None:
    """La scheda che copre il modello indicato (anche come variante), se esiste."""
    return next((s for s in carica_schede().values() if template_id in s["template"]), None)


def campi_da_chiedere(scheda: dict[str, Any], valori: dict[str, Any]) -> list[dict[str, Any]]:
    """Campi obbligatori ancora vuoti dopo la precompilazione, nell'ordine della scheda.

    I campi a calcolo li produce il software e non si chiedono; gli altri si propongono all'avvocato
    con la domanda della scheda o, se manca, con l'etichetta del campo.
    """
    mancanti = []
    for campo in scheda["campi"]:
        if not campo["obbligatorio"] or campo["fonte"]["tipo"] == "calcolo":
            continue
        if str(valori.get(campo["campo"]) or "").strip():
            continue
        mancanti.append({"campo": campo["campo"], "domanda": campo["fonte"].get("domanda") or campo["etichetta"],
                         "se_manca": campo.get("se_manca", "")})
    return mancanti
