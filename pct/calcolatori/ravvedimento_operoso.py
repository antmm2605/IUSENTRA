"""Ravvedimento operoso — sanzione ridotta e interessi sul tardivo versamento.

Base normativa:
- Art. 13 D.Lgs. 18 dicembre 1997, n. 472: riduzioni della sanzione minima in
  base al momento della regolarizzazione (un decimo, un nono, un ottavo, un
  settimo, un sesto, un quinto e, dal 1° settembre 2024, un quarto).
- Art. 13 D.Lgs. 18 dicembre 1997, n. 471: misura della sanzione per omesso o
  tardivo versamento, nel testo vigente pro tempore.
- D.Lgs. 14 giugno 2024, n. 87 (GU n. 150 del 28 giugno 2024), che ha riscritto
  entrambe le discipline; l'art. 5 dello stesso decreto stabilisce che le
  modifiche si applicano **alle violazioni commesse a partire dal 1° settembre
  2024**. Il calcolatore sceglie il regime in base alla data di scadenza del
  versamento, che è il momento in cui la violazione si consuma.
- Art. 1284 c.c. per il saggio degli interessi legali, nella serie già
  versionata nel progetto: gli interessi si calcolano al tasso legale annuo dal
  giorno in cui il versamento avrebbe dovuto essere eseguito a quello in cui è
  effettivamente eseguito (formula: imposta x tasso x giorni / 36500).

Le misure e le riduzioni dei due regimi sono quelle pubblicate dall'Agenzia
delle entrate nella scheda «Ravvedimento — Come regolarizzare», che riepiloga il
testo pro tempore dei due articoli.

Perimetro dichiarato: il modulo copre il ravvedimento sui tributi amministrati
dall'Agenzia delle entrate per omesso o tardivo versamento e, in alternativa,
per una violazione di cui l'utente indica la sanzione minima edittale. Non
calcola il cumulo giuridico ex art. 12 D.Lgs. 472/1997 né le sanzioni proprie
dei singoli tributi.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, days_inclusive, fmt_date_it, parse_date, safe_float

# Art. 5 D.Lgs. 87/2024: spartiacque fra i due regimi sanzionatori.
DATA_RIFORMA_SANZIONI = date(2024, 9, 1)

# Art. 13 D.Lgs. 471/1997, testo pro tempore: misura della sanzione base.
_SANZIONI_VERSAMENTO = {
    "ante_2024": {
        "label": "Violazione commessa prima del 1° settembre 2024",
        "giornaliera_percent": 1.0,
        "entro_90_percent": 15.0,
        "oltre_90_percent": 30.0,
    },
    "dal_2024": {
        "label": "Violazione commessa dal 1° settembre 2024",
        "giornaliera_percent": 0.83,
        "entro_90_percent": 12.5,
        "oltre_90_percent": 25.0,
    },
}

# Art. 13, comma 1, D.Lgs. 472/1997: riduzioni legate al tempo della
# regolarizzazione. Il regime dal 1° settembre 2024 anticipa a «oltre un anno»
# la soglia della lettera b-bis) e non prevede più il gradino biennale.
_RIDUZIONI_TEMPORALI = {
    "ante_2024": [
        {"giorni_max": 30, "denominatore": 10, "lettera": "a", "descrizione": "Entro 30 giorni dalla scadenza"},
        {"giorni_max": 90, "denominatore": 9, "lettera": "a-bis", "descrizione": "Entro 90 giorni"},
        {"giorni_max": 365, "denominatore": 8, "lettera": "b", "descrizione": "Entro un anno"},
        {"giorni_max": 730, "denominatore": 7, "lettera": "b-bis", "descrizione": "Entro due anni"},
        {"giorni_max": None, "denominatore": 6, "lettera": "b-ter", "descrizione": "Oltre due anni"},
    ],
    "dal_2024": [
        {"giorni_max": 30, "denominatore": 10, "lettera": "a", "descrizione": "Entro 30 giorni dalla scadenza"},
        {"giorni_max": 90, "denominatore": 9, "lettera": "a-bis", "descrizione": "Entro 90 giorni"},
        {"giorni_max": 365, "denominatore": 8, "lettera": "b", "descrizione": "Entro un anno"},
        {"giorni_max": None, "denominatore": 7, "lettera": "b-bis", "descrizione": "Oltre un anno"},
    ],
}

# Riduzioni legate a un evento del procedimento, non al tempo trascorso.
_RIDUZIONI_EVENTO = {
    "dopo_pvc": {
        "denominatore": 5,
        "lettera": "b-quater",
        "descrizione": "Dopo la constatazione con processo verbale (art. 24 L. 4/1929)",
        "regimi": ("ante_2024", "dal_2024"),
    },
    "dopo_schema_atto": {
        "denominatore": 6,
        "lettera": "b-ter",
        "descrizione": "Dopo la comunicazione dello schema di atto non preceduta da verbale",
        "regimi": ("dal_2024",),
    },
    "dopo_schema_atto_su_pvc": {
        "denominatore": 4,
        "lettera": "b-quinquies",
        "descrizione": "Dopo lo schema di atto relativo a violazione constatata con verbale",
        "regimi": ("dal_2024",),
    },
}

_FONTI = [
    {
        "title": "Art. 13 D.Lgs. 472/1997 e art. 13 D.Lgs. 471/1997 — scheda Agenzia delle entrate",
        "url": "https://www.agenziaentrate.gov.it/portale/schede/accertamenti/ravvedimento-operoso/come-regolarizzare-versimpo",
    },
    {
        "title": "D.Lgs. 87/2024 — revisione del sistema sanzionatorio tributario (Gazzetta Ufficiale)",
        "url": "https://www.gazzettaufficiale.it/eli/id/2024/06/28/24G00103/sg",
    },
]


def _regime(scadenza: date) -> str:
    return "dal_2024" if scadenza >= DATA_RIFORMA_SANZIONI else "ante_2024"


def _sanzione_base_percent(regime: str, giorni: int) -> Dict[str, Any]:
    misure = _SANZIONI_VERSAMENTO[regime]
    if giorni <= 15:
        percentuale = round(misure["giornaliera_percent"] * giorni, 4)
        criterio = (
            f"{misure['giornaliera_percent']}% per ciascuno dei {giorni} giorni di ritardo "
            "(ritardo non superiore a 15 giorni)"
        )
    elif giorni <= 90:
        percentuale = float(misure["entro_90_percent"])
        criterio = f"{percentuale}% per ritardo non superiore a 90 giorni"
    else:
        percentuale = float(misure["oltre_90_percent"])
        criterio = f"{percentuale}% per ritardo superiore a 90 giorni"
    return {"percentuale": percentuale, "criterio": criterio}


def _riduzione(regime: str, giorni: int, evento: str) -> Dict[str, Any]:
    if evento and evento != "nessuno":
        voce = _RIDUZIONI_EVENTO.get(evento)
        if not voce:
            raise ValueError("Evento del procedimento non riconosciuto.")
        if regime not in voce["regimi"]:
            raise ValueError(
                f"La riduzione «{voce['descrizione']}» non è prevista per le violazioni "
                f"{_SANZIONI_VERSAMENTO[regime]['label'].lower()}."
            )
        return dict(voce)
    for scaglione in _RIDUZIONI_TEMPORALI[regime]:
        limite = scaglione["giorni_max"]
        if limite is None or giorni <= limite:
            return dict(scaglione)
    raise ValueError("Scaglione di riduzione non determinabile.")


def _interessi(norme: Any, imposta: float, scadenza: date, versamento: date) -> Dict[str, Any]:
    """Interessi legali giorno per giorno: imposta x tasso x giorni / 36500."""

    segmenti: List[Dict[str, Any]] = []
    totale = 0.0
    giorni_coperti = 0
    inizio_decorrenza = scadenza
    fine_decorrenza = versamento
    for periodo in norme.interest_periods("legali"):
        inizio = max(inizio_decorrenza, periodo.start)
        fine = min(fine_decorrenza, periodo.end)
        if inizio > fine:
            continue
        giorni = (fine - inizio).days
        if giorni <= 0:
            continue
        quota = round(imposta * periodo.rate * giorni / 36500.0, 2)
        totale += quota
        giorni_coperti += giorni
        segmenti.append(
            {
                "periodo": periodo.label,
                "dal": fmt_date_it(inizio),
                "al": fmt_date_it(fine),
                "giorni": giorni,
                "tasso": periodo.rate,
                "interessi": quota,
            }
        )
    return {"totale": round(totale, 2), "segmenti": segmenti, "giorni_coperti": giorni_coperti}


def calcola(payload: Mapping[str, Any], norme: Any) -> Dict[str, Any]:
    scadenza = parse_date(payload.get("rav_data_scadenza"))
    versamento = parse_date(payload.get("rav_data_versamento"))
    if scadenza is None:
        raise ValueError("Indica la data di scadenza originaria del versamento.")
    if versamento is None:
        raise ValueError("Indica la data in cui il versamento viene regolarizzato.")
    if versamento <= scadenza:
        raise ValueError("La data di regolarizzazione deve essere successiva alla scadenza.")

    tipo = clean_text(payload.get("rav_tipo_violazione")).lower() or "omesso_versamento"
    if tipo not in {"omesso_versamento", "altra_violazione"}:
        raise ValueError("Tipo di violazione non riconosciuto.")

    imposta = safe_float(payload.get("rav_imposta"))
    if imposta <= 0:
        raise ValueError("Inserisci l'imposta o il tributo da versare.")

    evento = clean_text(payload.get("rav_evento")).lower() or "nessuno"
    giorni_ritardo = (versamento - scadenza).days
    regime = _regime(scadenza)

    note: List[str] = []
    avvisi: List[str] = []

    if tipo == "omesso_versamento":
        base = _sanzione_base_percent(regime, giorni_ritardo)
        sanzione_percent = base["percentuale"]
        sanzione_piena = round(imposta * sanzione_percent / 100.0, 2)
        criterio_sanzione = base["criterio"]
        note.append(
            "Sanzione base per omesso o tardivo versamento ex art. 13 D.Lgs. 471/1997: "
            + criterio_sanzione
            + "."
        )
    else:
        sanzione_piena = safe_float(payload.get("rav_sanzione_minima"))
        if sanzione_piena <= 0:
            raise ValueError(
                "Per una violazione diversa dall'omesso versamento indica la sanzione minima edittale."
            )
        sanzione_percent = round(sanzione_piena / imposta * 100.0, 4) if imposta else 0.0
        criterio_sanzione = "Sanzione minima edittale indicata dall'utente"
        avvisi.append(
            "La sanzione minima edittale è stata inserita manualmente: va verificata sulla norma "
            "che disciplina la singola violazione."
        )

    riduzione = _riduzione(regime, giorni_ritardo, evento)
    denominatore = int(riduzione["denominatore"])
    sanzione_ridotta = round(sanzione_piena / denominatore, 2)

    interessi = _interessi(norme, imposta, scadenza, versamento)
    if not interessi["segmenti"]:
        raise ValueError(
            "Il periodo richiesto non è coperto dalle tabelle dei saggi legali attualmente caricate: "
            "aggiorna la tabella normativa da /legal-intelligence."
        )
    giorni_totali = (versamento - scadenza).days
    if interessi["giorni_coperti"] < giorni_totali:
        avvisi.append(
            "I saggi legali coprono solo una parte del periodo: il residuo va integrato manualmente."
        )

    totale = round(imposta + sanzione_ridotta + interessi["totale"], 2)

    note.append(
        f"Riduzione applicata: 1/{denominatore} del minimo — art. 13, comma 1, lett. {riduzione['lettera']}), "
        f"D.Lgs. 472/1997 ({riduzione['descrizione']})."
    )
    note.append(
        "Regime sanzionatorio: "
        + _SANZIONI_VERSAMENTO[regime]["label"]
        + " (art. 5 D.Lgs. 87/2024, che àncora la disciplina alla data di commissione della violazione)."
    )
    note.append(
        "Interessi legali calcolati con la formula imposta x tasso legale x giorni / 36500, "
        "dal giorno della scadenza a quello del versamento (art. 1284 c.c.)."
    )
    avvisi.append(
        "Per i tributi con dichiarazione periodica gli scaglioni delle lettere b) e b-bis) si "
        "misurano sul termine di presentazione della dichiarazione, non sull'anno solare: qui è "
        "usato il criterio temporale in giorni, da verificare sul singolo tributo."
    )
    avvisi.append(
        "Il modulo non calcola il cumulo giuridico ex art. 12 D.Lgs. 472/1997 né le cause di "
        "esclusione del ravvedimento."
    )

    dettaglio: List[Dict[str, Any]] = [
        {"voce": "Imposta dovuta", "importo": round(imposta, 2), "riferimento": "Tributo da versare"},
        {"voce": "Sanzione piena", "importo": sanzione_piena, "riferimento": criterio_sanzione},
        {
            "voce": f"Sanzione ridotta (1/{denominatore})",
            "importo": sanzione_ridotta,
            "riferimento": f"Art. 13, comma 1, lett. {riduzione['lettera']}), D.Lgs. 472/1997",
        },
        {"voce": "Interessi legali", "importo": interessi["totale"], "riferimento": "Art. 1284 c.c."},
        {"voce": "Totale da versare", "importo": totale, "riferimento": "Imposta + sanzione ridotta + interessi"},
    ]

    return {
        "tipo_violazione": tipo,
        "regime": regime,
        "regime_label": _SANZIONI_VERSAMENTO[regime]["label"],
        "data_scadenza": fmt_date_it(scadenza),
        "data_versamento": fmt_date_it(versamento),
        "giorni_ritardo": giorni_ritardo,
        "giorni_inclusivi": days_inclusive(scadenza, versamento),
        "imposta": round(imposta, 2),
        "sanzione_percent": sanzione_percent,
        "sanzione_piena": sanzione_piena,
        "riduzione_denominatore": denominatore,
        "riduzione_lettera": riduzione["lettera"],
        "riduzione_descrizione": riduzione["descrizione"],
        "sanzione_ridotta": sanzione_ridotta,
        "interessi": interessi["totale"],
        "totale_da_versare": totale,
        "dettaglio": dettaglio,
        "segmenti_interessi": interessi["segmenti"],
        "notes": note,
        "warnings": avvisi,
        "sources": list(_FONTI),
    }
