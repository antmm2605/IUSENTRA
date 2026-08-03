"""Patrocinio a spese dello Stato — verifica dei limiti di reddito.

Base normativa:
- Art. 76, comma 1, D.P.R. 30 maggio 2002, n. 115: può essere ammesso al
  patrocinio chi è titolare di un reddito imponibile ai fini dell'imposta
  personale sul reddito, risultante dall'ultima dichiarazione, non superiore
  all'importo indicato dalla norma.
- Art. 76, comma 2: salvo quanto previsto dall'art. 92, se l'interessato convive
  con il coniuge o con altri familiari il reddito è costituito dalla somma dei
  redditi conseguiti nel medesimo periodo da ogni componente della famiglia,
  compreso l'istante.
- Art. 76, comma 3: si tiene conto anche dei redditi che per legge sono esenti
  da IRPEF o che sono soggetti a ritenuta alla fonte a titolo d'imposta, ovvero
  ad imposta sostitutiva.
- Art. 76, comma 4: si tiene conto del solo reddito personale quando sono
  oggetto della causa diritti della personalità, ovvero nei processi in cui gli
  interessi del richiedente sono in conflitto con quelli degli altri componenti
  il nucleo familiare con lui conviventi.
- Art. 92: nel processo penale, se l'interessato convive con il coniuge o con
  altri familiari si applica l'art. 76, comma 2, ma i limiti di reddito indicati
  dall'art. 76, comma 1, sono elevati di euro 1.032,91 per ognuno dei familiari
  conviventi.
- Art. 77: l'importo dell'art. 76, comma 1, è adeguato ogni due anni con decreto
  del Ministero della giustizia di concerto con il Ministero dell'economia, in
  relazione alla variazione ISTAT dell'indice dei prezzi al consumo per le
  famiglie di operai e impiegati.

L'importo vigente non è cablato qui: vive nella tabella normativa versionata
``patrocinio_limiti_reddito``, una riga per decreto di adeguamento. Se la data
di riferimento precede la copertura delle righe caricate il calcolo si
interrompe (fail-closed) invece di applicare una soglia non vigente.

Perimetro dichiarato: il modulo verifica i soli limiti di reddito degli artt. 76
e 92. Le ulteriori condizioni, le cause di esclusione e le ipotesi di ammissione
in deroga previste dal testo unico restano da controllare a parte.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping, Optional

from pct.calcolatori._base import clean_text, fmt_date_it, parse_date, safe_bool, safe_float, safe_int

TABELLA_LIMITI = "patrocinio_limiti_reddito"

_PROCESSI = {
    "civile": "Processo civile, amministrativo, contabile o tributario",
    "penale": "Processo penale",
}


def _limite_vigente(norme: Any, riferimento: date) -> Dict[str, Any]:
    """Riga del decreto di adeguamento vigente alla data, oppure errore bloccante."""

    righe = [riga for riga in norme.rows(TABELLA_LIMITI) if riga.get("effective_from")]
    applicabili = [
        riga
        for riga in righe
        if (parse_date(riga.get("effective_from")) or date.max) <= riferimento
    ]
    if not applicabili:
        prima = min((clean_text(riga.get("effective_from")) for riga in righe), default="")
        raise ValueError(
            "Nessun decreto di adeguamento caricato per la data indicata "
            f"({fmt_date_it(riferimento)}). Le soglie disponibili partono dal "
            f"{fmt_date_it(prima) or 'periodo non coperto'}: verifica in Gazzetta Ufficiale il "
            "decreto vigente alla data e aggiorna la tabella normativa."
        )
    return max(applicabili, key=lambda riga: clean_text(riga.get("effective_from")))


def _incremento_penale(norme: Any) -> float:
    tabella = norme.get_table(TABELLA_LIMITI)
    valore = safe_float((tabella.get("defaults") or {}).get("incremento_familiare_penale"))
    if valore <= 0:
        raise ValueError(
            "Incremento per familiare convivente non disponibile nella tabella normativa "
            "(art. 92 D.P.R. 115/2002)."
        )
    return valore


def calcola(payload: Mapping[str, Any], norme: Any) -> Dict[str, Any]:
    processo = clean_text(payload.get("pat_processo")).lower() or "civile"
    if processo not in _PROCESSI:
        raise ValueError("Tipo di processo non riconosciuto.")

    reddito_richiedente = safe_float(payload.get("pat_reddito_richiedente"))
    if reddito_richiedente < 0:
        raise ValueError("Il reddito del richiedente non può essere negativo.")

    redditi_conviventi = safe_float(payload.get("pat_redditi_conviventi"))
    if redditi_conviventi < 0:
        raise ValueError("Il reddito dei familiari conviventi non può essere negativo.")

    familiari = max(0, safe_int(payload.get("pat_familiari_conviventi")))
    solo_personale = safe_bool(payload.get("pat_solo_reddito_personale"))

    riferimento: Optional[date] = parse_date(payload.get("pat_data_riferimento"))
    if riferimento is None:
        raise ValueError(
            "Indica la data di riferimento dell'istanza: la soglia di reddito cambia con i "
            "decreti di adeguamento biennale (art. 77 D.P.R. 115/2002)."
        )

    if familiari == 0 and redditi_conviventi > 0 and not solo_personale:
        raise ValueError(
            "Hai indicato redditi di familiari conviventi ma nessun convivente: "
            "correggi il numero dei familiari conviventi."
        )

    riga = _limite_vigente(norme, riferimento)
    limite_base = round(safe_float(riga.get("amount")), 2)
    if limite_base <= 0:
        raise ValueError("Soglia di reddito non valida nella tabella normativa caricata.")

    note: List[str] = []
    avvisi: List[str] = []

    if solo_personale:
        reddito_rilevante = round(reddito_richiedente, 2)
        note.append(
            "Valutato il solo reddito personale del richiedente (art. 76, comma 4, D.P.R. 115/2002): "
            "la causa ha per oggetto diritti della personalità oppure gli interessi del richiedente "
            "sono in conflitto con quelli dei conviventi."
        )
    else:
        reddito_rilevante = round(reddito_richiedente + redditi_conviventi, 2)
        if familiari > 0:
            note.append(
                "Cumulo dei redditi del nucleo familiare convivente (art. 76, comma 2, D.P.R. 115/2002): "
                f"{familiari} familiare/i convivente/i oltre al richiedente."
            )

    incremento = 0.0
    incremento_unitario = 0.0
    if processo == "penale" and familiari > 0 and not solo_personale:
        incremento_unitario = _incremento_penale(norme)
        incremento = round(incremento_unitario * familiari, 2)
        note.append(
            "Processo penale: il limite è elevato di "
            f"{incremento_unitario:.2f} euro per ognuno dei {familiari} familiari conviventi "
            "(art. 92 D.P.R. 115/2002)."
        )
    elif processo == "penale" and solo_personale:
        avvisi.append(
            "L'elevazione dell'art. 92 presuppone il cumulo dei redditi dei conviventi ex art. 76, "
            "comma 2: valutando il solo reddito personale non è stata applicata."
        )

    limite_applicabile = round(limite_base + incremento, 2)
    ammissibile = reddito_rilevante <= limite_applicabile
    margine = round(limite_applicabile - reddito_rilevante, 2)

    note.append(
        "Il reddito da confrontare è quello imponibile ai fini IRPEF risultante dall'ultima "
        "dichiarazione, comprensivo dei redditi esenti da IRPEF o soggetti a ritenuta alla fonte a "
        "titolo d'imposta o a imposta sostitutiva (art. 76, commi 1 e 3, D.P.R. 115/2002)."
    )
    note.append(
        f"Soglia applicata: {limite_base:.2f} euro, fissata dal {clean_text(riga.get('decreto'))} "
        f"({clean_text(riga.get('gazzetta'))})."
    )
    avvisi.append(
        "La verifica riguarda i soli limiti di reddito degli artt. 76 e 92 D.P.R. 115/2002: "
        "le ulteriori condizioni, le cause di esclusione e le ipotesi di ammissione in deroga "
        "previste dal testo unico vanno controllate a parte."
    )
    avvisi.append(
        "La soglia è aggiornata ogni due anni con decreto ministeriale pubblicato in Gazzetta "
        "Ufficiale (art. 77 D.P.R. 115/2002): l'efficacia è riferita alla data di pubblicazione, "
        "quindi per le istanze a cavallo dell'adeguamento va verificato il decreto applicabile."
    )

    dettaglio: List[Dict[str, Any]] = [
        {"voce": "Reddito del richiedente", "importo": round(reddito_richiedente, 2), "riferimento": "Art. 76, comma 1"},
    ]
    if not solo_personale:
        dettaglio.append(
            {
                "voce": "Redditi dei familiari conviventi",
                "importo": round(redditi_conviventi, 2),
                "riferimento": "Art. 76, comma 2",
            }
        )
    dettaglio.append({"voce": "Reddito rilevante", "importo": reddito_rilevante, "riferimento": "Somma delle voci"})
    dettaglio.append({"voce": "Limite base", "importo": limite_base, "riferimento": clean_text(riga.get("decreto"))})
    if incremento:
        dettaglio.append({"voce": "Elevazione per conviventi", "importo": incremento, "riferimento": "Art. 92"})
    dettaglio.append({"voce": "Limite applicabile", "importo": limite_applicabile, "riferimento": "Art. 76 e art. 92"})

    fonti: List[Dict[str, str]] = []
    for voce in norme.get_table(TABELLA_LIMITI).get("sources") or []:
        fonti.append({"title": voce.get("title", ""), "url": voce.get("url", "")})

    return {
        "processo": processo,
        "processo_label": _PROCESSI[processo],
        "data_riferimento": fmt_date_it(riferimento),
        "reddito_richiedente": round(reddito_richiedente, 2),
        "redditi_conviventi": round(redditi_conviventi, 2),
        "familiari_conviventi": familiari,
        "solo_reddito_personale": solo_personale,
        "reddito_rilevante": reddito_rilevante,
        "limite_base": limite_base,
        "incremento_familiari": incremento,
        "incremento_unitario": round(incremento_unitario, 2),
        "limite_applicabile": limite_applicabile,
        "ammissibile": ammissibile,
        "esito": "Ammissibile per reddito" if ammissibile else "Non ammissibile per reddito",
        "margine": margine,
        "decreto_soglia": clean_text(riga.get("decreto")),
        "gazzetta_soglia": clean_text(riga.get("gazzetta")),
        "soglia_in_vigore_dal": fmt_date_it(riga.get("effective_from")),
        "dettaglio": dettaglio,
        "notes": note,
        "warnings": avvisi,
        "sources": fonti,
    }
