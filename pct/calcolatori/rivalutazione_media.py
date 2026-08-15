"""Rivalutazione monetaria su media annua degli indici ISTAT.

Base metodologica:
- Il criterio della «variazione media annua» ISTAT è quello usato da
  clausole contrattuali e rendite indicizzate e da adeguamenti normativi
  su base annua (es. perequazione ex art. 11 D.Lgs. 503/1992). Per i
  crediti di lavoro ex art. 429, c. 3, c.p.c. e art. 150 disp. att.
  c.p.c. il criterio corretto è invece quello PUNTUALE mese-su-mese con
  indice FOI: usare il tool «Rivalutazione ISTAT».
- Gli indici FOI (al netto dei tabacchi, L. 81/1992) e NIC provengono dal
  dataset ISTAT versionato nelle tabelle normative del progetto: nessun
  valore viene stimato; se un anno non ha indici il calcolo si ferma
  (fail-closed).
- Principio nominalistico (art. 1277 c.c.): in caso di deflazione la
  rivalutazione liquidatoria non riduce il credito sotto il nominale —
  il tool espone sia il valore statistico sia l'importo liquidabile.

Coefficiente = media aritmetica degli indici mensili dell'anno di arrivo
diviso la media dell'anno di partenza. L'anno di partenza deve avere la
media definitiva (12 mesi); per l'anno di arrivo in corso la media
parziale è marcata come stima provvisoria.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float, safe_int

_FONTE_ISTAT = {
    "code": "istat_foi",
    "title": "ISTAT — Indici dei prezzi al consumo (FOI al netto dei tabacchi ex L. 81/1992 / NIC)",
    "url": "https://www.istat.it/dati/banche-dati/",
}


def _media_annua(norme: Any, tipo: str, anno: int) -> tuple[float, int]:
    indici: List[float] = []
    for mese in range(1, 13):
        indice = norme.istat_index(tipo, anno, mese)
        if indice is not None:
            indici.append(float(indice))
    if not indici:
        raise ValueError(
            f"Nessun indice ISTAT {tipo.upper()} disponibile per l'anno {anno} nel dataset versionato."
        )
    return sum(indici) / len(indici), len(indici)


def calcola(payload: Mapping[str, Any], norme: Any) -> Dict[str, Any]:
    importo = safe_float(payload.get("rivm_importo"))
    anno_base = safe_int(payload.get("rivm_anno_base"))
    anno_target = safe_int(payload.get("rivm_anno_target"))
    tipo = (clean_text(payload.get("rivm_tipo")) or "FOI").lower()

    if importo <= 0:
        raise ValueError("Inserisci l'importo da rivalutare.")
    if tipo not in ("foi", "nic"):
        raise ValueError("Indice ammesso: FOI oppure NIC.")
    if anno_base < 1947 or anno_target < 1947:
        raise ValueError("Gli anni devono essere dal 1947 in poi.")
    if anno_target < anno_base:
        raise ValueError("L'anno di arrivo deve essere uguale o successivo all'anno di partenza.")
    if anno_target - anno_base > 120:
        raise ValueError("Intervallo massimo gestito: 120 anni.")

    media_base, mesi_base = _media_annua(norme, tipo, anno_base)
    if mesi_base < 12:
        raise ValueError(
            f"L'anno di partenza {anno_base} ha solo {mesi_base} mesi di indice nel "
            "dataset: la media annua di partenza deve essere definitiva (12 mesi)."
        )
    media_target, mesi_target = _media_annua(norme, tipo, anno_target)

    coefficiente = media_target / media_base
    rivalutato = round(importo * coefficiente, 2)
    liquidabile = max(rivalutato, round(importo, 2))

    warnings: List[str] = []
    provvisoria = mesi_target < 12
    if provvisoria:
        warnings.append(
            f"L'anno di arrivo {anno_target} ha solo {mesi_target} mesi di indice "
            "pubblicati: STIMA PROVVISORIA, da ricalcolare alla pubblicazione della "
            "media annua definitiva ISTAT."
        )
    if coefficiente < 1:
        warnings.append(
            "Variazione media negativa (deflazione): ai fini liquidatori la "
            "rivalutazione non riduce il credito sotto il nominale (principio "
            "nominalistico, art. 1277 c.c.) — vedere «importo liquidabile»."
        )

    return {
        "importo_base": round(importo, 2),
        "importo_rivalutato": rivalutato,
        "importo_liquidabile": liquidabile,
        "differenza": round(rivalutato - importo, 2),
        "coefficiente": round(coefficiente, 6),
        "variazione_percentuale": round((coefficiente - 1) * 100.0, 2),
        "indice": tipo.upper(),
        "media_anno_base": round(media_base, 3),
        "media_anno_target": round(media_target, 3),
        "anno_base": anno_base,
        "anno_target": anno_target,
        "stima_provvisoria": provvisoria,
        "notes": [
            "Rivalutazione su medie annue degli indici mensili versionati (criterio "
            "pattizio/contrattuale); per i crediti di lavoro e la rivalutazione "
            "puntuale mese-su-mese usare il tool «Rivalutazione ISTAT».",
        ],
        "warnings": warnings,
        "sources": [_FONTE_ISTAT],
    }
