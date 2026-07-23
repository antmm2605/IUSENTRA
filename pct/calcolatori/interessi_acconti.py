"""Interessi con imputazione degli acconti — art. 1194 c.c.

Base normativa:
- Art. 1194 c.c.: il debitore non può imputare il pagamento al capitale
  piuttosto che agli interessi senza il consenso del creditore; ogni acconto
  si imputa quindi prima agli interessi maturati e poi al capitale.
- Art. 1284 c.c. (interessi legali) e D.Lgs. 231/2002 (mora commerciale);
  art. 1284, comma 4, c.c. (tasso della legislazione speciale sui ritardi di
  pagamento dalla domanda giudiziale).

I tassi provengono dalle tabelle normative versionate del progetto
(``GestioneTabelleNormative.interest_periods``): i periodi non coperti dalle
basi ufficiali caricate non vengono mai stimati (fail-closed).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Mapping, Tuple

from pct.calcolatori._base import (
    clean_text,
    days_inclusive,
    fmt_date_it,
    parse_date,
    safe_float,
    year_denominator,
)

_MODE_LABELS = {
    "legali": "Interessi legali ex art. 1284 c.c.",
    "mora_commerciale": "Interessi moratori ex D.Lgs. 231/2002",
    "legali_1284_4": "Interessi ex art. 1284, comma 4, c.c. (tasso D.Lgs. 231/2002)",
}


def _parse_acconti(raw: Any) -> List[Tuple[date, float]]:
    """Ogni riga: data e importo separati da ';' o spazio (ISO o gg/mm/aaaa)."""
    acconti: List[Tuple[date, float]] = []
    for line in str(raw or "").replace("\r", "").split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = [part for part in line.replace(";", " ").split() if part]
        if len(parts) < 2:
            raise ValueError(f"Riga acconto non valida: '{line}'. Usa 'data importo' (es. 15/03/2025 500,00).")
        giorno = parse_date(parts[0])
        importo = safe_float(" ".join(parts[1:]))
        if not giorno:
            raise ValueError(f"Data acconto non riconosciuta nella riga: '{line}'.")
        if importo <= 0:
            raise ValueError(f"Importo acconto non positivo nella riga: '{line}'.")
        acconti.append((giorno, importo))
    acconti.sort(key=lambda item: item[0])
    return acconti


def _interest_between(capitale: float, start: date, end: date, periods: List[Any]) -> Tuple[float, int, List[Dict[str, Any]]]:
    """Interessi su ``capitale`` per i giorni [start, end] con i periodi tariffari coperti."""
    total = 0.0
    covered = 0
    segments: List[Dict[str, Any]] = []
    if end < start or capitale <= 0:
        return 0.0, 0, segments
    for period in periods:
        overlap_start = max(start, period.start)
        overlap_end = min(end, period.end)
        if overlap_start > overlap_end:
            continue
        days = days_inclusive(overlap_start, overlap_end)
        interest = round(capitale * (period.rate / 100.0) * (days / year_denominator(overlap_start)), 2)
        total += interest
        covered += days
        segments.append(
            {
                "label": period.label,
                "from": overlap_start.isoformat(),
                "to": overlap_end.isoformat(),
                "days": days,
                "rate": period.rate,
                "capital": round(capitale, 2),
                "interest": interest,
                "source": period.source.to_dict(),
            }
        )
    return round(total, 2), covered, segments


def calcola(payload: Mapping[str, Any], norme: Any) -> Dict[str, Any]:
    mode = clean_text(payload.get("acc_tipo")) or "legali"
    if mode not in _MODE_LABELS:
        raise ValueError("Regime di interessi non riconosciuto.")
    capitale = safe_float(payload.get("acc_capitale"))
    data_inizio = parse_date(payload.get("acc_data_inizio"))
    data_fine = parse_date(payload.get("acc_data_fine"))

    if capitale <= 0:
        raise ValueError("Inserisci un capitale positivo.")
    if not data_inizio or not data_fine:
        raise ValueError("Inserisci una data iniziale e finale valide.")
    if data_fine < data_inizio:
        raise ValueError("La data finale deve essere successiva o uguale alla data iniziale.")

    acconti = _parse_acconti(payload.get("acc_acconti"))
    for giorno, _ in acconti:
        if giorno < data_inizio or giorno > data_fine:
            raise ValueError(f"L'acconto del {fmt_date_it(giorno)} è fuori dal periodo di calcolo.")

    table_mode = "mora_commerciale" if mode in {"mora_commerciale", "legali_1284_4"} else "legali"
    periods = norme.interest_periods(table_mode)

    residuo_capitale = capitale
    interessi_non_pagati = 0.0
    cursore = data_inizio
    covered_total = 0
    expected_total = 0
    segments: List[Dict[str, Any]] = []
    imputazioni: List[Dict[str, Any]] = []
    sources: Dict[str, Dict[str, str]] = {}

    eventi = list(acconti) + [(data_fine, 0.0)]
    for giorno_evento, importo_acconto in eventi:
        fine_tratto = giorno_evento if importo_acconto > 0 else giorno_evento
        # Interessi maturati fino al giorno dell'evento incluso.
        if fine_tratto >= cursore and residuo_capitale > 0:
            interesse, covered, tratti = _interest_between(residuo_capitale, cursore, fine_tratto, periods)
            interessi_non_pagati = round(interessi_non_pagati + interesse, 2)
            covered_total += covered
            expected_total += days_inclusive(cursore, fine_tratto)
            segments.extend(tratti)
            for tratto in tratti:
                sources[tratto["source"]["url"]] = tratto["source"]
        if importo_acconto > 0:
            quota_interessi = round(min(importo_acconto, interessi_non_pagati), 2)
            quota_capitale = round(min(importo_acconto - quota_interessi, residuo_capitale), 2)
            eccedenza = round(importo_acconto - quota_interessi - quota_capitale, 2)
            interessi_non_pagati = round(interessi_non_pagati - quota_interessi, 2)
            residuo_capitale = round(residuo_capitale - quota_capitale, 2)
            imputazioni.append(
                {
                    "data": giorno_evento.isoformat(),
                    "importo": round(importo_acconto, 2),
                    "quota_interessi": quota_interessi,
                    "quota_capitale": quota_capitale,
                    "eccedenza": eccedenza,
                    "residuo_capitale": residuo_capitale,
                    "residuo_interessi": interessi_non_pagati,
                }
            )
            cursore = giorno_evento + timedelta(days=1)
        else:
            cursore = giorno_evento

    if expected_total > 0 and covered_total == 0:
        raise ValueError("Il periodo richiesto non è coperto dalle basi ufficiali attualmente caricate.")

    warnings: List[str] = []
    if covered_total < expected_total:
        warnings.append(
            "Il periodo indicato è coperto solo parzialmente dalle tabelle ufficiali caricate: "
            "il risultato riguarda i giorni effettivamente mappati."
        )
    eccedenze = round(sum(item["eccedenza"] for item in imputazioni), 2)
    if eccedenze > 0:
        warnings.append(
            f"Gli acconti superano il dovuto per {eccedenze:.2f} euro: l'eccedenza non è imputata."
        )

    totale_residuo = round(residuo_capitale + interessi_non_pagati, 2)
    return {
        "mode": mode,
        "label": _MODE_LABELS[mode],
        "capitale_iniziale": round(capitale, 2),
        "start_date": data_inizio.isoformat(),
        "end_date": data_fine.isoformat(),
        "acconti_totali": round(sum(importo for _, importo in acconti), 2),
        "numero_acconti": len(acconti),
        "residuo_capitale": residuo_capitale,
        "residuo_interessi": interessi_non_pagati,
        "totale_residuo": totale_residuo,
        "imputazioni": imputazioni,
        "segments": segments,
        "notes": [
            "Imputazione ex art. 1194 c.c.: ogni acconto copre prima gli interessi maturati e poi il capitale.",
            "Calcolo pro-rata die su giorni effettivi con denominatore 365/366.",
        ],
        "warnings": warnings,
        "sources": list(sources.values()),
    }
