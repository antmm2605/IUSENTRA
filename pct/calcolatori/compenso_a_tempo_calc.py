"""Compenso a tempo dell'avvocato — art. 22-bis D.M. 55/2014.

Base normativa:
- Art. 22-bis D.M. 55/2014, introdotto dal D.M. 147/2022: compenso determinato
  a tempo, con il parametro indicativo di tariffa oraria fra 200 e 500 euro.

Il calcolo non è riscritto qui: passa dal motore già versionato in
``pct.compensi_a_tempo``, usato anche dal preventivatore, così la suite e il
preventivo restituiscono lo stesso importo a parità di dati. Questo modulo si
limita a normalizzare l'input della suite e a tradurre gli errori del motore in
``ValueError``, come gli altri calcolatori.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float, safe_int
from pct.compensi_a_tempo import (
    FONTE_NORMATIVA_COMPENSO_A_TEMPO,
    RANGE_TARIFFA_MAX,
    RANGE_TARIFFA_MIN,
    calcola_compenso_a_tempo_art22bis,
)

_CRITERI = {
    "ora_frazione_oltre_30": "Ora intera, con arrotondamento della frazione oltre 30 minuti",
    "effettivo_minuti": "Tempo effettivo al minuto",
    "scatti_15": "Scatti di 15 minuti",
    "scatti_30": "Scatti di 30 minuti",
}

_FONTI = [
    {
        "title": "D.M. 55/2014, art. 22-bis (introdotto dal D.M. 147/2022) — Gazzetta Ufficiale",
        "url": "https://www.gazzettaufficiale.it/eli/id/2022/10/12/22G00157/sg",
    },
]


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    criterio = clean_text(payload.get("cat_criterio")) or "ora_frazione_oltre_30"
    if criterio not in _CRITERI:
        raise ValueError("Criterio di arrotondamento non riconosciuto.")

    esito = calcola_compenso_a_tempo_art22bis(
        tariffa_oraria=safe_float(payload.get("cat_tariffa_oraria")),
        ore_stimate=safe_float(payload.get("cat_ore")),
        minuti_stimati=safe_int(payload.get("cat_minuti")),
        criterio_arrotondamento=criterio,
        massimale_ore=safe_float(payload.get("cat_massimale_ore")),
        soglia_preapprovazione_ore=safe_float(payload.get("cat_soglia_ore")),
    )
    if esito.get("errors"):
        raise ValueError(" ".join(esito["errors"]))

    spese_generali_percent = safe_float(payload.get("cat_spese_generali_percent"), 15.0)
    if spese_generali_percent < 0:
        raise ValueError("La percentuale di spese generali non può essere negativa.")

    compenso_base = float(esito["compenso_base"])
    spese_generali = round(compenso_base * spese_generali_percent / 100.0, 2)
    imponibile = round(compenso_base + spese_generali, 2)

    note: List[str] = [
        f"Criterio di arrotondamento: {_CRITERI[criterio]}.",
        f"Fonte del parametro: {FONTE_NORMATIVA_COMPENSO_A_TEMPO}.",
        "Il compenso a tempo va concordato per iscritto con il cliente prima dell'incarico "
        "(preventivo scritto obbligatorio).",
    ]
    if spese_generali_percent:
        note.append(
            f"Spese generali applicate al {spese_generali_percent:g}% sul compenso, come voce separata."
        )

    avvisi: List[str] = list(esito.get("warnings") or [])
    avvisi.append(
        "L'importo non comprende CPA, IVA e spese documentate: vanno aggiunti in fattura secondo "
        "il regime dello studio."
    )

    return {
        "tariffa_oraria": esito["tariffa_oraria"],
        "totale_minuti": esito["totale_minuti"],
        "ore_fatturabili": esito["ore_fatturabili"],
        "criterio": criterio,
        "criterio_label": _CRITERI[criterio],
        "compenso_base": compenso_base,
        "spese_generali_percent": spese_generali_percent,
        "spese_generali": spese_generali,
        "imponibile": imponibile,
        "parametro_min": RANGE_TARIFFA_MIN,
        "parametro_max": RANGE_TARIFFA_MAX,
        "massimale_ore": esito["massimale_ore"],
        "soglia_preapprovazione_ore": esito["soglia_preapprovazione_ore"],
        "richiede_consenso": esito["richiede_consenso"],
        "notes": note,
        "warnings": avvisi,
        "sources": list(_FONTI),
    }
