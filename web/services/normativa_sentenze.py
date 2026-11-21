"""Sentenze sull'articolo aperto in «Codici e leggi», dagli archivi del software in sola lettura.

Si riusa la fase giurisprudenza dell'harness di Lex (``lex/harness/giurisprudenza.py``): prima le pronunce
precalcolate per norma (lettura istantanea), poi la ricerca dal vivo negli archivi (Corte costituzionale
dell'archivio dello studio e Cassazione SentenzeWeb dal 2021) con un tempo massimo. L'esito dichiara sempre da
dove vengono le pronunce e cosa non ha risposto: gli estremi si leggono prima di citarli.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

# Codici per i quali esiste la sigla d'uso e la chiave delle norme dell'harness.
_CODICI = {
    "urn:nir:stato:regio.decreto:1942-03-16;262": ("cc", "c.c."),
    "urn:nir:stato:regio.decreto:1940-10-28;1443": ("cpc", "c.p.c."),
    "urn:nir:stato:regio.decreto:1930-10-19;1398": ("cp", "c.p."),
    "urn:nir:presidente.repubblica:decreto:1988-09-22;447": ("cpp", "c.p.p."),
}
SECONDI = 8.0


def _citazione(item: Mapping[str, Any]) -> tuple[str, str]:
    numero = str(item.get("number") or "").strip().rstrip(".")
    urn = str(item.get("urn") or "")
    for prefisso, (chiave, sigla) in _CODICI.items():
        if urn.startswith(prefisso):
            return f"art. {numero} {sigla}", f"{chiave}:{re.sub(r'[^0-9a-z]', '', numero.lower())}"
    estremi = f"{item.get('numero')}/{str(item.get('data_atto') or '')[:4]}" if item.get("numero") else ""
    return (f"art. {numero} {estremi}".strip(), "")


def sentenze_per_articolo(item: Mapping[str, Any], *, secondi: float = SECONDI, utente: str = "") -> dict[str, Any]:
    from lex.harness.giurisprudenza import cerca, per_norme

    citazione, chiave = _citazione(item)
    esito = per_norme([chiave]) if chiave else None
    fonte = "pronunce precalcolate per questa norma"
    if esito is None:
        esito = cerca(citazione, limite=5, secondi=secondi, utente=utente)
        fonte = "ricerca negli archivi"
    dati = esito.to_dict()
    return {"citazione": citazione, "fonte": fonte, "stato": dati["stato"], "archivi": dati["archivi"],
            "errori": dati["errori"], "pronunce": dati["pronunce"],
            "avvertenza": "Estremi trovati negli archivi del software: leggi la pronuncia prima di citarla."}
