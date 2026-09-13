"""Danno da mancato o carente consenso informato — Milano 2024.

Base normativa e giurisprudenziale:
- Art. 32 Cost.; artt. 1 e 3 L. 22 dicembre 2017 n. 219 (consenso informato).
- Cass. civ. n. 28985/2019: il danno da lesione del diritto di autodeterminarsi
  e' autonomo rispetto al danno alla salute e va allegato e provato.
- Criteri orientativi dell'Osservatorio sulla giustizia civile di Milano,
  edizione 2024, su un campione di 102 sentenze di merito: quattro fasce di
  gravita' con la relativa forbice di liquidazione.

Il modulo colloca l'importo dentro la fascia scelta e riporta le circostanze
che la tabella associa a quella fascia; la valutazione dell'an e della fascia
resta dell'avvocato o del giudice.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_bool, safe_float
from pct.calcolatori.danno_biologico import fasce as _fasce
from pct.calcolatori.danno_biologico import tabelle

TABELLA = tabelle.MILANO_2024_CONSENSO


def opzioni_fasce() -> List[tuple]:
    return _fasce.opzioni(TABELLA)


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    nome = clean_text(payload.get("ci_fascia")) or "media"
    voce = _fasce.fascia(TABELLA, nome)
    posizione = safe_float(payload.get("ci_posizione"), 50.0)
    oltre = safe_float(payload.get("ci_importo_eccezionale"))
    esito = _fasce.posiziona(voce, posizione, oltre_massimo=oltre)

    dati = tabelle.carica(TABELLA)
    estetico = safe_bool(payload.get("ci_trattamento_estetico"))

    note: List[str] = [
        "Quattro fasce di gravita' ricavate dall'Osservatorio di Milano su 102 sentenze di "
        "merito, secondo l'intensita' del vulnus al diritto di autodeterminarsi.",
        f"Fascia «{voce['label']}»: {voce['sentenze']} sentenze del campione, "
        f"pari a circa il {voce['quota_campione_pct']} per cento.",
        "Il danno da lesione del diritto all'autodeterminazione e' autonomo rispetto al danno "
        "alla salute e va allegato e provato (Cass. civ. n. 28985/2019): la liquidazione qui "
        "riguarda solo la prima voce.",
        str(dati["nota_rivalutazione"]),
    ]
    if estetico:
        note.append(str(dati["nota_estetica"]))

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
        "importo_proposto": esito["proposto"],
        "trattamento_estetico": estetico,
        "fasce_disponibili": [
            {"id": f["id"], "label": f["label"], "minimo": f["minimo"], "massimo": f.get("massimo")}
            for f in _fasce.fasce(TABELLA)
        ],
        "tabelle_applicate": [fonte.come_dizionario()],
        "notes": note,
        "warnings": avvisi,
        "sources": [fonte.come_sorgente()],
    }
