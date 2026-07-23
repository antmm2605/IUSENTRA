"""Stima orientativa dell'assegno di mantenimento (separazione e divorzio).

Base normativa e giurisprudenziale:
- Artt. 337-ter e 316-bis c.c. (mantenimento dei figli, proporzionalità ai
  redditi e ai tempi di permanenza).
- Art. 156 c.c. (mantenimento del coniuge separato).
- Art. 5, comma 6, L. 898/1970 (assegno divorzile).
- Cass. SS.UU. 11/07/2018 n. 18287 (natura assistenziale-compensativa
  dell'assegno divorzile).

La legge non fissa alcuna formula: questo modulo produce una STIMA
orientativa fondata su criteri diffusi nella prassi dei tribunali, sempre
dichiarati nel risultato. Non sostituisce la valutazione del giudice.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_bool, safe_float, safe_int

_QUOTE_FIGLI = {1: 0.25, 2: 0.35, 3: 0.45}


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    tipo = clean_text(payload.get("man_tipo")) or "figli"
    if tipo not in ("figli", "coniuge"):
        raise ValueError("Tipo di assegno non riconosciuto.")
    reddito_obbligato = safe_float(payload.get("man_reddito_obbligato"))
    reddito_beneficiario = safe_float(payload.get("man_reddito_beneficiario"))
    if reddito_obbligato <= 0:
        raise ValueError("Indica il reddito mensile netto dell'obbligato.")

    criteri: List[Dict[str, Any]] = []
    warnings: List[str] = [
        "Stima orientativa basata su criteri di prassi giudiziaria: la misura dell'assegno è sempre "
        "rimessa alla valutazione del giudice sul caso concreto.",
    ]
    notes: List[str] = []

    if tipo == "figli":
        figli = max(1, safe_int(payload.get("man_figli"), 1))
        paritetico = safe_bool(payload.get("man_collocamento_paritetico"))
        casa_assegnata = safe_bool(payload.get("man_casa_assegnata"))

        quota = _QUOTE_FIGLI.get(min(figli, 3), 0.45)
        if figli > 3:
            quota = 0.50
        base = reddito_obbligato * quota
        criteri.append({"label": f"Quota di prassi per {figli} figli", "detail": f"{quota * 100:.0f}% del reddito dell'obbligato", "importo": round(base, 2)})

        stima = base
        if paritetico:
            stima *= 0.60
            criteri.append({"label": "Collocamento paritetico", "detail": "Riduzione del 40% per tempi di permanenza equivalenti (art. 337-ter c.c.)", "importo": round(stima, 2)})
        if casa_assegnata:
            stima *= 0.90
            criteri.append({"label": "Casa familiare assegnata al collocatario", "detail": "Riduzione del 10% per il godimento dell'immobile", "importo": round(stima, 2)})
        if reddito_beneficiario > 0:
            fattore = reddito_obbligato / (reddito_obbligato + reddito_beneficiario)
            stima *= max(0.5, fattore * 2 - 0.5) if fattore < 0.75 else 1.0
            criteri.append({"label": "Proporzione tra i redditi dei genitori", "detail": "Ripartizione proporzionale ex art. 316-bis c.c.", "importo": round(stima, 2)})

        notes.append(
            "Il mantenimento dei figli è dovuto in proporzione al reddito di ciascun genitore e ai tempi "
            "di permanenza (art. 337-ter, comma 4, c.c.); le spese straordinarie restano da ripartire a parte."
        )
        label = f"Mantenimento per {figli} figli"
    else:
        durata = max(0, safe_int(payload.get("man_durata_matrimonio")))
        divario = max(0.0, reddito_obbligato - reddito_beneficiario)
        if divario <= 0:
            stima = 0.0
            criteri.append({"label": "Divario reddituale", "detail": "Il beneficiario ha redditi pari o superiori: nessun assegno stimato", "importo": 0.0})
            notes.append("Con redditi equivalenti l'assegno ha di regola natura solo compensativa, da provare in concreto (Cass. SS.UU. 18287/2018).")
        else:
            base = divario * 0.25
            criteri.append({"label": "Quota del divario reddituale", "detail": "25% della differenza tra i redditi mensili netti", "importo": round(base, 2)})
            fattore_durata = min(durata / 20.0, 1.0) if durata else 0.5
            stima = base * fattore_durata
            criteri.append({"label": "Durata del matrimonio", "detail": f"{durata} anni (fattore {fattore_durata:.2f})", "importo": round(stima, 2)})
            notes.append(
                "Assegno con funzione assistenziale-compensativa: rilevano il contributo alla vita familiare, "
                "la durata del matrimonio e le rinunce professionali (Cass. SS.UU. 18287/2018)."
            )
        label = "Assegno al coniuge"

    stima = round(max(0.0, stima), 2)
    return {
        "tipo": tipo,
        "label": label,
        "reddito_obbligato": round(reddito_obbligato, 2),
        "reddito_beneficiario": round(reddito_beneficiario, 2),
        "criteri": criteri,
        "stima_mensile": stima,
        "stima_annua": round(stima * 12, 2),
        "notes": notes,
        "warnings": warnings,
        "sources": [
            {"title": "Art. 337-ter c.c. e art. 5 L. 898/1970 (Normattiva)", "url": "https://www.normattiva.it"},
            {"title": "Cass. SS.UU. 18287/2018", "url": "https://www.italgiure.giustizia.it"},
        ],
    }
