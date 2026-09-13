"""Danno da diffamazione a mezzo stampa e altri mezzi di comunicazione — Milano 2024.

Base normativa e giurisprudenziale:
- Artt. 2043 e 2059 c.c.; art. 595 c.p.; L. 8 febbraio 1948 n. 47.
- Criteri orientativi dell'Osservatorio sulla giustizia civile di Milano,
  edizione 2024, su 89 sentenze degli anni 2014-2017, approvati dall'Assemblea
  nazionale degli Osservatori (Roma, maggio 2017): cinque fasce di gravita' con
  la relativa forbice di liquidazione.

Il modulo calcola anche la riparazione pecuniaria dell'art. 12 della legge
sulla stampa, che il campione mostra liquidata fra un ottavo e un terzo del
danno riconosciuto.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_bool, safe_float
from pct.calcolatori.danno_biologico import fasce as _fasce
from pct.calcolatori.danno_biologico import tabelle

TABELLA = tabelle.MILANO_2024_DIFFAMAZIONE


def opzioni_fasce() -> List[tuple]:
    return _fasce.opzioni(TABELLA)


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    nome = clean_text(payload.get("df_fascia")) or "media"
    voce = _fasce.fascia(TABELLA, nome)
    posizione = safe_float(payload.get("df_posizione"), 50.0)
    oltre = safe_float(payload.get("df_importo_eccezionale"))
    esito = _fasce.posiziona(voce, posizione, oltre_massimo=oltre)

    dati = tabelle.carica(TABELLA)
    importo = esito["proposto"]
    chiede_riparazione = safe_bool(payload.get("df_riparazione"))

    quota_min = float(dati["riparazione_pecuniaria_quota_minima"])
    quota_max = float(dati["riparazione_pecuniaria_quota_massima"])
    riparazione = {
        "richiesta": chiede_riparazione,
        "minimo": round(importo * quota_min, 2),
        "massimo": round(importo * quota_max, 2),
    }

    note: List[str] = [
        "Cinque fasce di gravita' ricavate dall'Osservatorio di Milano su 89 sentenze degli "
        "anni 2014-2017 di Milano, Roma e altri dodici tribunali.",
        f"Importo medio liquidato nel campione: {dati['importo_medio_liquidato']:.2f} € "
        "(valore all'1.1.2024).",
        str(dati["nota_rivalutazione"]),
    ]
    if chiede_riparazione:
        note.append(str(dati["nota_riparazione"]))

    avvisi: List[str] = []
    if esito["aperta"]:
        avvisi.append(
            "La fascia eccezionale non ha un tetto tabellare: l'importo va motivato sulle "
            f"circostanze del caso, partendo dalla soglia di {esito['minimo']:.2f} €."
        )

    fonte = tabelle.fonte(TABELLA)
    return {
        "fascia": nome,
        "fascia_label": voce["label"],
        "criteri": list(voce["criteri"]),
        "importo_minimo": esito["minimo"],
        "importo_massimo": esito["massimo"],
        "posizione_pct": None if esito["aperta"] else max(0.0, min(posizione, 100.0)),
        "importo_proposto": importo,
        "importo_medio_campione": float(dati["importo_medio_liquidato"]),
        "riparazione_pecuniaria": riparazione,
        "parametri_giurisprudenziali": list(dati["parametri"]),
        "fasce_disponibili": [
            {"id": f["id"], "label": f["label"], "minimo": f["minimo"], "massimo": f.get("massimo")}
            for f in _fasce.fasce(TABELLA)
        ],
        "tabelle_applicate": [fonte.come_dizionario()],
        "notes": note,
        "warnings": avvisi,
        "sources": [fonte.come_sorgente()],
    }
