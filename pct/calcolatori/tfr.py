"""Trattamento di fine rapporto: accantonamento e rivalutazione annua.

Base normativa (testo vigente):
- art. 2120, comma 1, c.c.: per ogni anno la quota è la retribuzione annua
  divisa per 13,5; per le frazioni d'anno la quota è proporzionale e la
  frazione di mese uguale o superiore a 15 giorni conta come mese intero;
- art. 2120, comma 4, c.c.: al 31 dicembre di ogni anno il fondo, esclusa la
  quota maturata nell'anno, si incrementa su base composta dell'1,5% fisso
  più il 75% dell'aumento dell'indice ISTAT dei prezzi al consumo per le
  famiglie di operai e impiegati (FOI) rispetto al dicembre precedente;
- art. 2120, comma 5, c.c.: per le frazioni d'anno l'aumento dell'indice è
  quello del mese di cessazione rispetto al dicembre precedente;
- art. 3, comma 15, L. 297/1982: il contributo dello 0,50% della retribuzione
  imponibile, dovuto al fondo pensioni dei lavoratori dipendenti, si detrae
  dall'accantonamento del TFR;
- art. 11, comma 3, D.Lgs. 47/2000: sulla rivalutazione si applica
  l'imposta sostitutiva del 17% (indicata per informazione: il TFR resta lordo).

Gli indici FOI vengono dalla tabella normativa ufficiale (serie ISTAT). Se un
indice serve e non è pubblicato, l'anno si calcola solo con l'inflazione
indicata dall'avvocato come ipotesi, e il risultato lo dichiara; senza ipotesi
il calcolo si ferma con il motivo.
"""
from __future__ import annotations

import calendar
from datetime import date
from typing import Any, Dict, List, Mapping, Optional, Tuple

from pct.calcolatori._base import clean_text, fmt_date_it, fmt_eur, parse_date, safe_float

TASSO_FISSO = 1.5  # art. 2120, comma 4, c.c.
QUOTA_INDICE = 0.75  # art. 2120, comma 4, c.c.
TRATTENUTA_L297 = 0.005  # art. 3, comma 15, L. 297/1982
IMPOSTA_SOSTITUTIVA = 0.17  # art. 11, comma 3, D.Lgs. 47/2000


def _si(valore: Any, predefinito: bool) -> bool:
    testo = clean_text(valore).lower()
    if not testo:
        return predefinito
    return testo in {"1", "si", "sì", "true", "on", "yes"}


def _mesi_utili(inizio: date, fine: date, anno: int) -> int:
    """Mesi dell'anno che contano per la quota (frazioni >= 15 giorni = mese intero)."""
    mesi = 0
    for mese in range(1, 13):
        primo = date(anno, mese, 1)
        ultimo = date(anno, mese, calendar.monthrange(anno, mese)[1])
        dal, al = max(inizio, primo), min(fine, ultimo)
        if dal <= al and (al - dal).days + 1 >= 15:
            mesi += 1
    return mesi


def _variazione_foi(norme: Any, anno: int, mese: int) -> Optional[float]:
    """Variazione % del FOI del mese indicato rispetto al dicembre dell'anno precedente."""
    if norme is None:
        return None
    dicembre = norme.istat_index("foi", anno - 1, 12)
    corrente = norme.istat_index("foi", anno, mese)
    if not dicembre or not corrente:
        return None
    return (corrente / dicembre - 1.0) * 100.0


def _tasso_anno(
    norme: Any, anno: int, mese_riferimento: int, mesi_fisso: int, ipotesi: Optional[float]
) -> Tuple[float, Optional[float], str]:
    """Tasso di rivalutazione %, variazione FOI usata e origine del dato."""
    variazione = _variazione_foi(norme, anno, mese_riferimento)
    origine = "ISTAT"
    if variazione is None:
        if ipotesi is None:
            raise ValueError(
                f"Indice ISTAT FOI di {mese_riferimento:02d}/{anno} (o di dicembre {anno - 1}) non ancora "
                "pubblicato: la rivalutazione dell'anno non si può calcolare sui dati ufficiali. "
                "Indica un'inflazione ipotetica per avere una stima dichiarata."
            )
        variazione = ipotesi * mesi_fisso / 12.0
        origine = "ipotesi"
    # «aumento dell'indice»: una variazione negativa non riduce il fondo.
    tasso = TASSO_FISSO * mesi_fisso / 12.0 + QUOTA_INDICE * max(0.0, variazione)
    return round(tasso, 6), round(variazione, 4), origine


def calcola(payload: Mapping[str, Any], norme: Any = None) -> Dict[str, Any]:
    retribuzione = safe_float(payload.get("tfr_retribuzione_annua"))
    if retribuzione <= 0:
        raise ValueError("Inserisci una retribuzione annua lorda positiva.")
    montante = safe_float(payload.get("tfr_montante_pregresso"))
    anticipazioni = safe_float(payload.get("tfr_anticipazioni"))
    trattenuta = _si(payload.get("tfr_trattenuta_050"), True)
    grezza = clean_text(payload.get("tfr_inflazione_perc"))
    ipotesi = safe_float(grezza) if grezza else None
    assunzione = parse_date(payload.get("tfr_data_assunzione"))
    cessazione = parse_date(payload.get("tfr_data_cessazione"))

    quota_annua = round(retribuzione / 13.5, 2)
    trattenuta_annua = round(retribuzione * TRATTENUTA_L297, 2) if trattenuta else 0.0

    # Anni di calcolo: (anno, mesi utili, mese dell'indice, chiusura al 31/12?)
    anni: List[Tuple[int, int, int, bool]] = []
    if assunzione and cessazione:
        if cessazione < assunzione:
            raise ValueError("La data di cessazione precede quella di assunzione.")
        for anno in range(assunzione.year, cessazione.year + 1):
            mesi = _mesi_utili(assunzione, cessazione, anno)
            ultimo = anno == cessazione.year
            anni.append((anno, mesi, cessazione.month if ultimo else 12, not ultimo))
        modalita = "date"
    else:
        anni_servizio = max(0, int(safe_float(payload.get("tfr_anni_servizio"))))
        mesi_servizio = max(0, int(safe_float(payload.get("tfr_mesi_servizio"))))
        anni_servizio += mesi_servizio // 12
        mesi_servizio %= 12
        if anni_servizio == 0 and mesi_servizio == 0:
            raise ValueError("Indica le date del rapporto oppure anni e mesi di servizio.")
        if ipotesi is None:
            raise ValueError(
                "Senza le date del rapporto non si possono usare gli indici ISTAT: indica le date "
                "di assunzione e cessazione, oppure un'inflazione annua ipotetica."
            )
        anni = [(index, 12, 12, True) for index in range(1, anni_servizio + 1)]
        if mesi_servizio:
            anni.append((anni_servizio + 1, mesi_servizio, mesi_servizio, False))
        modalita = "ipotesi"

    fondo = round(montante, 2)
    totale_quote = 0.0
    totale_quote_lorde = 0.0
    totale_trattenute = 0.0
    totale_rivalutazione = 0.0
    righe: List[Dict[str, Any]] = []
    stime = 0
    for indice, (anno, mesi, mese_rif, chiusura) in enumerate(anni):
        quota = round(quota_annua * mesi / 12.0, 2)
        detrazione = round(trattenuta_annua * mesi / 12.0, 2)
        quota_netta = round(quota - detrazione, 2)
        # La rivalutazione riguarda il fondo esistente all'inizio dell'anno.
        mesi_fisso = 12 if chiusura else mesi
        if fondo > 0:
            if modalita == "date":
                tasso, variazione, origine = _tasso_anno(norme, anno, mese_rif, mesi_fisso, ipotesi)
            else:
                variazione = round((ipotesi or 0.0) * mesi_fisso / 12.0, 4)
                tasso = round(TASSO_FISSO * mesi_fisso / 12.0 + QUOTA_INDICE * max(0.0, variazione), 6)
                origine = "ipotesi"
        else:
            tasso, variazione, origine = 0.0, None, "nessun fondo da rivalutare"
        rivalutazione = round(fondo * tasso / 100.0, 2)
        stime += 1 if origine == "ipotesi" and fondo > 0 else 0
        fondo = round(fondo + rivalutazione + quota_netta, 2)
        totale_quote += quota_netta
        totale_quote_lorde += quota
        totale_trattenute += detrazione
        totale_rivalutazione += rivalutazione
        righe.append(
            {
                "anno": anno if modalita == "date" else f"{indice + 1}° anno",
                "mesi": mesi,
                "quota_lorda": quota,
                "trattenuta_0_50": detrazione,
                "quota_accantonata": quota_netta,
                "tasso_rivalutazione_perc": tasso,
                "variazione_foi_perc": variazione,
                "origine_indice": origine,
                "rivalutazione": rivalutazione,
                "fondo_fine_periodo": fondo,
            }
        )

    totale_quote = round(totale_quote, 2)
    totale_rivalutazione = round(totale_rivalutazione, 2)
    totale_lordo = round(fondo - anticipazioni, 2)
    imposta = round(totale_rivalutazione * IMPOSTA_SOSTITUTIVA, 2)

    note = [
        f"Quota annua: retribuzione {fmt_eur(retribuzione)} / 13,5 = {fmt_eur(quota_annua)} (art. 2120, comma 1, c.c.).",
        "Rivalutazione al 31 dicembre del fondo esistente, esclusa la quota dell'anno: 1,5% fisso + 75% "
        "dell'aumento dell'indice FOI rispetto al dicembre precedente (art. 2120, comma 4, c.c.); "
        "nell'anno di cessazione si usa l'indice del mese di cessazione (comma 5).",
    ]
    if trattenuta:
        note.append(
            f"Dalla quota si detrae lo 0,50% della retribuzione ({fmt_eur(trattenuta_annua)} annui), "
            "contributo dovuto al fondo pensioni (art. 3, comma 15, L. 297/1982)."
        )
    note.append(
        f"Imposta sostitutiva del 17% sulla rivalutazione (art. 11, comma 3, D.Lgs. 47/2000): "
        f"{fmt_eur(imposta)}, trattenuta dal datore di lavoro; il totale indicato resta lordo."
    )
    avvisi: List[str] = [
        "La retribuzione annua va intesa come quella utile ai fini del TFR (art. 2120, comma 2, c.c.) e si "
        "assume costante per tutto il periodo: con retribuzioni diverse anno per anno il calcolo va rifatto per anno."
    ]
    if modalita == "ipotesi":
        avvisi.append(
            f"Calcolo senza date: la rivalutazione usa l'inflazione ipotetica del {ipotesi:g}% annuo, non gli indici "
            "ISTAT. Per il conteggio ufficiale indica le date di assunzione e cessazione."
        )
    elif stime:
        avvisi.append(
            f"Per {stime} anno/i l'indice ISTAT necessario non è ancora pubblicato: la rivalutazione è stimata con "
            f"l'inflazione ipotetica del {ipotesi:g}% e andrà rifatta quando l'ISTAT pubblicherà l'indice."
        )
    if anticipazioni > 0:
        avvisi.append(
            f"Anticipazioni ({fmt_eur(anticipazioni)}) detratte dal fondo finale: la rivalutazione degli anni "
            "successivi all'anticipazione si calcola sul fondo ridotto, quindi il risultato è approssimato per eccesso."
        )
    if totale_lordo < 0:
        avvisi.append("Il totale risulta negativo dopo le anticipazioni indicate: verificare i dati di partenza.")

    risultato: Dict[str, Any] = {
        "retribuzione_annua": round(retribuzione, 2),
        "modalita": modalita,
        "quota_annua": quota_annua,
        "trattenuta_annua_0_50": trattenuta_annua,
        # Quota maturata ex art. 2120, comma 1 (lorda), trattenuta dello 0,50% e quota accantonata.
        "quota_periodo": round(totale_quote_lorde, 2),
        "trattenuta_periodo": round(totale_trattenute, 2),
        "quota_accantonata_periodo": totale_quote,
        "montante_pregresso": round(montante, 2),
        "rivalutazione": totale_rivalutazione,
        "imposta_sostitutiva_rivalutazione": imposta,
        "anticipazioni": round(anticipazioni, 2),
        "totale_lordo": totale_lordo,
        "dettaglio_annuale": righe,
        "notes": note,
        "warnings": avvisi,
    }
    if modalita == "date":
        risultato["data_assunzione"] = assunzione.isoformat()
        risultato["data_cessazione"] = cessazione.isoformat()
        risultato["periodo"] = f"dal {fmt_date_it(assunzione)} al {fmt_date_it(cessazione)}"
    else:
        risultato["inflazione_perc"] = round(ipotesi or 0.0, 2)
        risultato["anni_servizio"] = anni_servizio
        risultato["mesi_servizio"] = mesi_servizio
        risultato["anni_equivalenti"] = round(anni_servizio + mesi_servizio / 12.0, 4)
        # Coefficiente annuo con l'inflazione ipotetica (1,5% + 75% dell'inflazione).
        risultato["coeff_rivalutazione"] = round(TASSO_FISSO + QUOTA_INDICE * max(0.0, ipotesi or 0.0), 6)
    return risultato
