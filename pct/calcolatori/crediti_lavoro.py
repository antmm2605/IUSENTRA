"""Crediti di lavoro — rivalutazione e interessi ex art. 429, comma 3, c.p.c.

Base normativa:
- Art. 429, comma 3, c.p.c.: nella condanna al pagamento di somme di denaro per
  crediti di lavoro il giudice determina, oltre agli interessi legali, il
  maggior danno da diminuzione di valore del credito, con decorrenza dal giorno
  della maturazione del diritto. A differenza dell'art. 1224, comma 2, c.c. il
  maggior danno non deve essere provato dal lavoratore: è riconosciuto in via
  automatica.
- Art. 22, comma 36, L. 23 dicembre 1994, n. 724: per i crediti di lavoro dei
  dipendenti delle pubbliche amministrazioni, a decorrere dal 1° gennaio 1995,
  si applica il regime dell'art. 16, comma 6, L. 30 dicembre 1991, n. 412:
  rivalutazione monetaria e interessi legali NON sono cumulabili. La legittimità
  costituzionale della norma è stata scrutinata da Corte cost. 2 novembre 2000,
  n. 459, che ha dichiarato la questione non fondata.
- Art. 1284 c.c. per la misura del saggio legale, nelle serie già versionate nel
  progetto (``GestioneTabelleNormative.interest_periods('legali')``).
- Indici ISTAT dei prezzi al consumo per le famiglie di operai e impiegati
  (FOI), nella serie già caricata dalle tabelle normative del progetto.
- Cass. SS.UU. 17 febbraio 1995, n. 1712, per il criterio di calcolo degli
  interessi sul capitale progressivamente rivalutato, anziché sul capitale
  rivalutato finale.

Il modulo non introduce alcun dato nuovo: usa gli indici ISTAT e i saggi legali
già versionati. Se il periodo richiesto non è coperto dalle basi ufficiali il
calcolo si interrompe (fail-closed) anziché stimare.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import (
    clean_text,
    days_inclusive,
    fmt_date_it,
    parse_date,
    safe_float,
    year_denominator,
)

_REGIMI = {
    "privato": "Lavoro privato — cumulo di rivalutazione e interessi (art. 429, comma 3, c.p.c.)",
    "pubblico": "Pubblico impiego — divieto di cumulo (art. 22, comma 36, L. 724/1994)",
}

_BASI_INTERESSI = {
    "rivalutato_progressivo": "Interessi sul capitale progressivamente rivalutato (Cass. SS.UU. 1712/1995)",
    "semisomma": "Interessi sulla semisomma tra capitale originario e capitale rivalutato",
    "originario": "Interessi sul capitale originario",
}

_FONTE_ART_429 = {
    "title": "Art. 429 c.p.c. (Normattiva)",
    "url": "https://www.normattiva.it",
}
_FONTE_L724 = {
    "title": "Art. 22, comma 36, L. 724/1994 (Normattiva)",
    "url": "https://www.normattiva.it",
}


def _indice(norme: Any, tipo: str, giorno: date, contesto: str) -> float:
    """Indice ISTAT del mese indicato, oppure errore bloccante."""

    indice = norme.istat_index(tipo, giorno.year, giorno.month)
    if indice is None:
        ultimo = norme.istat_last_available(tipo) or {}
        raise ValueError(
            f"Indice ISTAT {tipo.upper()} non disponibile per {giorno.month:02d}/{giorno.year} ({contesto}). "
            f"Dati disponibili fino a {ultimo.get('month', '?')}/{ultimo.get('year', '?')}. "
            f"Aggiorna la tabella normativa da /legal-intelligence."
        )
    return float(indice)


def calcola(payload: Mapping[str, Any], norme: Any) -> Dict[str, Any]:
    importo = safe_float(payload.get("lav_importo"))
    if importo <= 0:
        raise ValueError("Inserisci l'importo del credito di lavoro maturato.")

    maturazione = parse_date(payload.get("lav_data_maturazione"))
    liquidazione = parse_date(payload.get("lav_data_liquidazione"))
    if maturazione is None:
        raise ValueError("Indica la data di maturazione del diritto (art. 429, comma 3, c.p.c.).")
    if liquidazione is None:
        raise ValueError("Indica la data di liquidazione o di pagamento del credito.")
    if liquidazione < maturazione:
        raise ValueError("La data di liquidazione deve essere successiva alla maturazione del diritto.")

    regime = clean_text(payload.get("lav_regime")).lower() or "privato"
    if regime not in _REGIMI:
        raise ValueError("Regime del rapporto di lavoro non riconosciuto.")

    tipo_indice = clean_text(payload.get("lav_tipo_indice")).lower() or "foi"
    if tipo_indice not in ("foi", "nic"):
        tipo_indice = "foi"

    base_interessi = clean_text(payload.get("lav_base_interessi")) or "rivalutato_progressivo"
    if base_interessi not in _BASI_INTERESSI:
        raise ValueError("Base di calcolo degli interessi non riconosciuta.")

    indice_base = _indice(norme, tipo_indice, maturazione, "maturazione del diritto")
    indice_fine = _indice(norme, tipo_indice, liquidazione, "liquidazione del credito")
    capitale_rivalutato = round(importo * (indice_fine / indice_base), 2)
    rivalutazione = round(capitale_rivalutato - importo, 2)
    semisomma = round((importo + capitale_rivalutato) / 2.0, 2)

    segmenti: List[Dict[str, Any]] = []
    fonti: Dict[str, Dict[str, str]] = {}
    totale_interessi = 0.0
    giorni_coperti = 0

    for periodo in norme.interest_periods("legali"):
        inizio = max(maturazione, periodo.start)
        fine = min(liquidazione, periodo.end)
        if inizio > fine:
            continue
        if base_interessi == "originario":
            base = round(importo, 2)
        elif base_interessi == "semisomma":
            base = semisomma
        else:
            indice_segmento = _indice(norme, tipo_indice, inizio, f"segmento {inizio.year}")
            base = round(importo * (indice_segmento / indice_base), 2)
        giorni = days_inclusive(inizio, fine)
        interesse = round(base * (periodo.rate / 100.0) * (giorni / year_denominator(inizio)), 2)
        totale_interessi += interesse
        giorni_coperti += giorni
        fonte = periodo.source.to_dict()
        segmenti.append(
            {
                "label": periodo.label,
                "from": inizio.isoformat(),
                "to": fine.isoformat(),
                "days": giorni,
                "rate": periodo.rate,
                "base": base,
                "interest": interesse,
                "source": fonte,
            }
        )
        fonti[fonte["url"]] = fonte

    giorni_totali = days_inclusive(maturazione, liquidazione)
    if giorni_coperti == 0:
        raise ValueError(
            "Il periodo richiesto non è coperto dalle tabelle dei saggi legali attualmente caricate."
        )

    totale_interessi = round(totale_interessi, 2)
    avvisi: List[str] = []
    if giorni_coperti < giorni_totali:
        avvisi.append(
            "I saggi legali coprono solo i giorni mappati dalle tabelle ufficiali caricate: "
            "il periodo residuo va integrato manualmente."
        )

    note = [
        "Crediti di lavoro ex art. 429, comma 3, c.p.c.: il maggior danno da svalutazione è "
        "riconosciuto in via automatica, senza onere di prova a carico del lavoratore.",
        "Decorrenza dal giorno della maturazione del diritto, come impone l'art. 429, comma 3, c.p.c.",
        "Criterio interessi: " + _BASI_INTERESSI[base_interessi] + ".",
    ]

    fonti[_FONTE_ART_429["url"] + "#429"] = _FONTE_ART_429

    if regime == "pubblico":
        voce_prevalente = "rivalutazione" if rivalutazione >= totale_interessi else "interessi"
        accessorio = max(rivalutazione, totale_interessi)
        totale = round(importo + accessorio, 2)
        rivalutazione_riconosciuta = rivalutazione if voce_prevalente == "rivalutazione" else 0.0
        interessi_riconosciuti = totale_interessi if voce_prevalente == "interessi" else 0.0
        note.append(
            "Pubblico impiego: rivalutazione monetaria e interessi legali non sono cumulabili "
            "(art. 22, comma 36, L. 724/1994, che richiama l'art. 16, comma 6, L. 412/1991); "
            "è riconosciuta la sola voce di importo maggiore."
        )
        avvisi.append(
            "Il divieto di cumulo opera per i crediti di lavoro dei dipendenti pubblici maturati "
            "dal 1° gennaio 1995: per le quote anteriori va verificata l'applicabilità del regime ordinario."
        )
        fonti[_FONTE_L724["url"] + "#724"] = _FONTE_L724
    else:
        voce_prevalente = ""
        rivalutazione_riconosciuta = rivalutazione
        interessi_riconosciuti = totale_interessi
        totale = round(importo + rivalutazione + totale_interessi, 2)

    return {
        "importo_originale": round(importo, 2),
        "data_maturazione": fmt_date_it(maturazione),
        "data_liquidazione": fmt_date_it(liquidazione),
        "giorni": giorni_totali,
        "regime": regime,
        "regime_label": _REGIMI[regime],
        "tipo_indice": tipo_indice,
        "indice_base": indice_base,
        "indice_fine": indice_fine,
        "capitale_rivalutato": capitale_rivalutato,
        "rivalutazione_calcolata": rivalutazione,
        "interessi_calcolati": totale_interessi,
        "rivalutazione_riconosciuta": round(rivalutazione_riconosciuta, 2),
        "interessi_riconosciuti": round(interessi_riconosciuti, 2),
        "voce_prevalente": voce_prevalente,
        "cumulo_ammesso": regime == "privato",
        "base_interessi": base_interessi,
        "base_interessi_label": _BASI_INTERESSI[base_interessi],
        "semisomma": semisomma,
        "totale": totale,
        "segments": segmenti,
        "notes": note,
        "warnings": avvisi,
        "sources": list(fonti.values()),
    }
