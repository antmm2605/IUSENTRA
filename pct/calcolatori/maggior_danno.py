"""Maggior danno da svalutazione monetaria — art. 1224, comma 2, c.c.

Base normativa e giurisprudenziale:
- Art. 1224, comma 2, c.c.: al creditore che dimostra di aver subito un danno
  maggiore spetta l'ulteriore risarcimento oltre gli interessi moratori.
- Cass. SS.UU. 17/02/1995 n. 1712: per i crediti di valore gli interessi si
  calcolano sul capitale rivalutato anno per anno (o su una base intermedia),
  non sul capitale rivalutato finale.
- Indici ISTAT FOI/NIC dalle tabelle normative versionate del progetto.

Il modulo rivaluta il capitale con gli indici ISTAT caricati e somma gli
interessi legali del periodo sulla base scelta dall'operatore (capitale
originario, semisomma o capitale rivalutato anno per anno). Periodi o indici
non coperti dalle basi ufficiali interrompono il calcolo (fail-closed).
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import (
    clean_text,
    days_inclusive,
    safe_float,
    safe_int,
    year_denominator,
)

_BASI = {
    "rivalutato_annuale": "Interessi sul capitale rivalutato anno per anno (Cass. SS.UU. 1712/1995)",
    "semisomma": "Interessi sulla semisomma tra capitale originario e capitale rivalutato",
    "originario": "Interessi sul capitale originario",
}


def _indice(norme: Any, tipo: str, anno: int, mese: int, contesto: str) -> float:
    indice = norme.istat_index(tipo, anno, mese)
    if indice is None:
        last = norme.istat_last_available(tipo) or {}
        raise ValueError(
            f"Indice ISTAT {tipo.upper()} non disponibile per {mese:02d}/{anno} ({contesto}). "
            f"Dati disponibili fino a {last.get('month', '?')}/{last.get('year', '?')}. "
            f"Aggiorna la tabella normativa da /legal-intelligence."
        )
    return float(indice)


def calcola(payload: Mapping[str, Any], norme: Any) -> Dict[str, Any]:
    importo = safe_float(payload.get("md_importo"))
    tipo = clean_text(payload.get("md_tipo_indice")).lower() or "foi"
    if tipo not in ("foi", "nic"):
        tipo = "foi"
    base_interessi = clean_text(payload.get("md_base_interessi")) or "rivalutato_annuale"
    if base_interessi not in _BASI:
        raise ValueError("Base di calcolo degli interessi non riconosciuta.")
    anno_base = safe_int(payload.get("md_anno_base"))
    mese_base = safe_int(payload.get("md_mese_base"))
    anno_fine = safe_int(payload.get("md_anno_fine"))
    mese_fine = safe_int(payload.get("md_mese_fine"))

    if importo <= 0:
        raise ValueError("Inserisci un importo positivo.")
    if not (anno_base and 1 <= mese_base <= 12):
        raise ValueError("Indica anno e mese iniziali validi.")
    if not (anno_fine and 1 <= mese_fine <= 12):
        raise ValueError("Indica anno e mese finali validi.")
    inizio = date(anno_base, mese_base, 1)
    fine = date(anno_fine, mese_fine, 1)
    if fine < inizio:
        raise ValueError("Il periodo finale deve essere successivo a quello iniziale.")

    indice_base = _indice(norme, tipo, anno_base, mese_base, "mese iniziale")
    indice_fine = _indice(norme, tipo, anno_fine, mese_fine, "mese finale")
    importo_rivalutato = round(importo * (indice_fine / indice_base), 2)
    rivalutazione = round(importo_rivalutato - importo, 2)

    periods = norme.interest_periods("legali")
    segments: List[Dict[str, Any]] = []
    sources: Dict[str, Dict[str, str]] = {}
    totale_interessi = 0.0
    covered = 0

    semisomma = round((importo + importo_rivalutato) / 2.0, 2)
    for period in periods:
        overlap_start = max(inizio, period.start)
        overlap_end = min(fine, period.end)
        if overlap_start > overlap_end:
            continue
        if base_interessi == "originario":
            base = importo
        elif base_interessi == "semisomma":
            base = semisomma
        else:
            indice_anno = _indice(norme, tipo, overlap_start.year, overlap_start.month, f"anno {overlap_start.year}")
            base = round(importo * (indice_anno / indice_base), 2)
        days = days_inclusive(overlap_start, overlap_end)
        interesse = round(base * (period.rate / 100.0) * (days / year_denominator(overlap_start)), 2)
        totale_interessi += interesse
        covered += days
        segments.append(
            {
                "label": period.label,
                "from": overlap_start.isoformat(),
                "to": overlap_end.isoformat(),
                "days": days,
                "rate": period.rate,
                "base": base,
                "interest": interesse,
                "source": period.source.to_dict(),
            }
        )
        sources[period.source.to_dict()["url"]] = period.source.to_dict()

    total_days = days_inclusive(inizio, fine)
    if covered == 0:
        raise ValueError("Il periodo richiesto non è coperto dalle tabelle dei tassi legali attualmente caricate.")

    warnings: List[str] = []
    if covered < total_days:
        warnings.append(
            "Gli interessi legali coprono solo i giorni mappati dalle tabelle ufficiali caricate: "
            "il maggior danno per il periodo residuo va integrato manualmente."
        )

    totale_interessi = round(totale_interessi, 2)
    totale = round(importo_rivalutato + totale_interessi, 2)
    sources["https://www.normattiva.it"] = {
        "title": "Art. 1224 c.c. (Normattiva)",
        "url": "https://www.normattiva.it",
    }

    return {
        "importo_originale": round(importo, 2),
        "importo_rivalutato": importo_rivalutato,
        "rivalutazione": rivalutazione,
        "indice_base": indice_base,
        "indice_fine": indice_fine,
        "tipo_indice": tipo,
        "base_interessi": base_interessi,
        "base_interessi_label": _BASI[base_interessi],
        "semisomma": semisomma,
        "totale_interessi": totale_interessi,
        "totale": totale,
        "segments": segments,
        "notes": [
            "Maggior danno ex art. 1224, comma 2, c.c. per i crediti di valore: capitale rivalutato ISTAT più interessi legali del periodo.",
            "Criterio interessi: " + _BASI[base_interessi] + ".",
        ],
        "warnings": warnings,
        "sources": list(sources.values()),
    }
