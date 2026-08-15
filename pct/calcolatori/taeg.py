"""TAEG — tasso annuo effettivo globale di un finanziamento.

Base normativa:
- Art. 121, comma 1, lett. e) e m), e comma 3, T.U.B. (D.Lgs. 385/1993);
  per il credito immobiliare ai consumatori art. 120-quinquies T.U.B.
  Direttiva 2008/48/CE (art. 19 e allegato I): il TAEG è il tasso che
  rende uguali, su base annua, i valori attualizzati di tutti gli impegni
  (prelievi, rimborsi, spese) tra creditore e consumatore. Dal 20/11/2026
  la fonte europea è la dir. (UE) 2023/2225 (art. 30 e allegato III),
  con equazione di base identica.
- Il costo totale del credito comprende interessi, commissioni, IMPOSTE
  e ogni altra spesa nota al finanziatore — inclusa l'imposta sostitutiva
  ex artt. 15-18 D.P.R. 601/1973 trattenuta sull'erogato e l'imposta di
  bollo — con la sola eccezione delle spese notarili e degli oneri da
  inadempimento (art. 121, c. 1, lett. e, T.U.B.; Disposizioni Banca
  d'Italia sulla trasparenza, sez. VII).

Il tool ricava la rata con il piano francese dal TAN dichiarato e risolve
l'equazione dei flussi attualizzati per bisezione; le spese annue
ricorrenti sono attualizzate come flussi separati a scadenza annuale,
come richiede l'allegato I della direttiva. Il risultato è uno strumento
di verifica difensiva: il TAEG contrattuale resta quello dichiarato
dall'intermediario nel documento di sintesi.
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from pct.calcolatori._base import safe_float, safe_int

_FONTE_BANKIT = {
    "code": "bankit_trasparenza",
    "title": "Banca d'Italia — Disposizioni sulla trasparenza (TAEG)",
    "url": "https://www.bancaditalia.it/compiti/vigilanza/normativa/archivio-norme/disposizioni/trasparenza_operazioni/",
}
_FONTE_TUB = {
    "code": "tub_art_121",
    "title": "Art. 121, c. 1, lett. e) e m), T.U.B. (D.Lgs. 385/1993) — TAEG e costo totale del credito",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:1993-09-01;385",
}


def _rata_francese(capitale: float, tasso_annuo: float, rate_totali: int, rate_anno: int) -> float:
    i = tasso_annuo / 100.0 / rate_anno
    if i <= 0:
        return capitale / rate_totali
    return capitale * i / (1.0 - (1.0 + i) ** (-rate_totali))


def _valore_attuale(
    flusso_periodico: float,
    spesa_annua: float,
    tasso_annuo: float,
    rate_totali: int,
    rate_anno: int,
) -> float:
    """Valore attuale dei flussi: rate periodiche più spese annue a scadenza annuale.

    L'allegato I della dir. 2008/48/CE impone di attualizzare ogni pagamento
    alla sua data effettiva: le spese annue sono flussi separati a t=1,2,...
    anni, non quote spalmate sulle rate.
    """

    totale = 0.0
    for k in range(1, rate_totali + 1):
        totale += flusso_periodico / (1.0 + tasso_annuo) ** (k / rate_anno)
    anni = rate_totali // rate_anno
    if spesa_annua > 0:
        for t in range(1, anni + 1):
            totale += spesa_annua / (1.0 + tasso_annuo) ** t
    return totale


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    capitale = safe_float(payload.get("taeg_capitale"))
    tan = safe_float(payload.get("taeg_tan"))
    durata_anni = safe_int(payload.get("taeg_durata_anni"))
    rate_anno = safe_int(payload.get("taeg_rate_anno"), 12)
    spese_iniziali = safe_float(payload.get("taeg_spese_iniziali"))
    spese_rata = safe_float(payload.get("taeg_spese_rata"))
    spese_annue = safe_float(payload.get("taeg_spese_annue"))

    if capitale <= 0:
        raise ValueError("Inserisci il capitale finanziato.")
    if tan < 0 or tan > 100:
        raise ValueError("Il TAN deve essere compreso tra 0 e 100.")
    if durata_anni <= 0 or durata_anni > 50:
        raise ValueError("La durata deve essere compresa tra 1 e 50 anni.")
    if rate_anno not in (1, 2, 4, 6, 12):
        raise ValueError("Rate per anno ammesse: 1, 2, 4, 6, 12.")
    if spese_iniziali < 0 or spese_rata < 0 or spese_annue < 0:
        raise ValueError("Le spese non possono essere negative.")
    if spese_iniziali >= capitale:
        raise ValueError("Le spese iniziali non possono assorbire l'intero capitale.")

    rate_totali = durata_anni * rate_anno
    rata = _rata_francese(capitale, tan, rate_totali, rate_anno)
    flusso_periodico = rata + spese_rata
    erogato_netto = capitale - spese_iniziali

    # Bisezione sul tasso annuo effettivo: PV(flussi) = erogato netto.
    basso, alto = 0.0, 10.0  # 0% .. 1000% annuo
    if _valore_attuale(flusso_periodico, spese_annue, alto, rate_totali, rate_anno) > erogato_netto:
        raise ValueError("Flussi incoerenti: il TAEG risultante supera il limite di calcolo.")
    for _ in range(200):
        medio = (basso + alto) / 2.0
        if _valore_attuale(flusso_periodico, spese_annue, medio, rate_totali, rate_anno) > erogato_netto:
            basso = medio
        else:
            alto = medio
    taeg = round((basso + alto) / 2.0 * 100.0, 4)

    totale_rate = flusso_periodico * rate_totali + spese_annue * durata_anni
    costo_totale = round(totale_rate + spese_iniziali - capitale, 2)

    return {
        "taeg": round(taeg, 2),
        "taeg_preciso": taeg,
        "tan": round(tan, 2),
        "rata": round(rata, 2),
        "rata_con_spese": round(flusso_periodico, 2),
        "erogato_netto": round(erogato_netto, 2),
        "numero_rate": rate_totali,
        "costo_totale_credito": costo_totale,
        "totale_rimborsato": round(totale_rate + spese_iniziali, 2),
        "notes": [
            "Il TAEG comprende interessi, commissioni, IMPOSTE e ogni costo noto al "
            "finanziatore — inclusa l'imposta sostitutiva ex artt. 15-18 D.P.R. 601/1973 "
            "trattenuta sull'erogato (da sommare alle spese iniziali) e l'imposta di "
            "bollo; restano escluse le sole spese notarili e gli oneri da inadempimento "
            "(art. 121, c. 1, lett. e, T.U.B.).",
        ],
        "warnings": [
            "Strumento di verifica difensiva: fa fede il TAEG dichiarato dall'intermediario "
            "nel documento di sintesi; scostamenti rilevanti meritano approfondimento "
            "(art. 125-bis T.U.B. sulle conseguenze del TAEG errato).",
            "Per la verifica antiusura usare il tool dedicato: il TEG ai fini L. 108/1996 "
            "segue le Istruzioni specifiche della Banca d'Italia, non coincide col TAEG.",
        ],
        "sources": [_FONTE_TUB, _FONTE_BANKIT],
    }
