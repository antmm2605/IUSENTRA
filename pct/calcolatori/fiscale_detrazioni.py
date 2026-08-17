"""Detrazioni IRPEF per familiari a carico, tipo di reddito e canoni.

Base normativa:
- Art. 12 TUIR (familiari a carico, come modificato dal D.Lgs. 230/2021
  sull'assegno unico e dalla L. 207/2024): la detrazione per figli spetta
  solo per i figli dai 21 ai 30 anni non compiuti (senza limite di età se
  disabili) — sotto i 21 anni opera l'assegno unico universale; 950 euro
  teorici per figlio con degressione su 95.000 (soglia aumentata di
  15.000 per ogni figlio oltre il primo); coniuge non separato: 800 euro
  con le tre fasce del comma 1, lett. a); altri familiari conviventi ex
  art. 433 c.c. (dal 2025 solo ascendenti conviventi, L. 207/2024): 750
  euro teorici con degressione su 80.000. Familiare a carico se reddito
  ≤ 2.840,51 euro (4.000 per figli fino a 24 anni).
- Art. 13 TUIR (detrazioni per tipo di reddito, come modificato dal
  D.Lgs. 216/2023 e dalla L. 207/2024): lavoro dipendente 1.955 euro
  fino a 15.000 (minimo 690, o 1.380 per i tempi determinati); pensione
  1.955 fino a 8.500 (minimo 713); redditi assimilati/autonomi/altri
  1.265 fino a 5.500; all'assegno periodico dal coniuge si applica la
  detrazione da pensione senza ragguaglio (c. 5-bis).
- Art. 16 TUIR (canoni di locazione dell'abitazione principale): importi
  fissi per fasce di reddito, con le maggiorazioni per canone concordato,
  giovani fino a 31 anni e lavoratori trasferiti.

Tutti gli importi sono su base annua e vanno ragguagliati ai giorni/mesi
di spettanza; il calcolo restituisce il valore teorico annuo.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float, safe_int

_FONTE_TUIR_12 = {
    "code": "tuir_art_12",
    "title": "Art. 12 TUIR — detrazioni per carichi di famiglia",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1986-12-22;917",
}
_FONTE_TUIR_13 = {
    "code": "tuir_art_13",
    "title": "Art. 13 TUIR — altre detrazioni per tipo di reddito",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1986-12-22;917",
}
_FONTE_TUIR_16 = {
    "code": "tuir_art_16",
    "title": "Art. 16 TUIR — detrazioni per canoni di locazione",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1986-12-22;917",
}

_LIMITE_CARICO = 2_840.51
_LIMITE_CARICO_FIGLI_GIOVANI = 4_000.0


def _tronca4(quoziente: float) -> float:
    """Tronca il quoziente alle prime quattro cifre decimali.

    Art. 12, c. 4, e art. 13, c. 6, TUIR: «il risultato dei predetti
    rapporti si assume nelle prime quattro cifre decimali» — troncamento,
    non arrotondamento, prima della moltiplicazione per l'importo teorico.
    """

    return int(max(quoziente, 0.0) * 10_000) / 10_000.0


def calcola_familiari(payload: Mapping[str, Any]) -> Dict[str, Any]:
    reddito = safe_float(payload.get("detfam_reddito"))
    coniuge = clean_text(payload.get("detfam_coniuge")) == "1"
    figli = safe_int(payload.get("detfam_figli"))
    figli_totali = safe_int(payload.get("detfam_figli_totali")) or figli
    altri = safe_int(payload.get("detfam_altri"))

    if reddito <= 0:
        raise ValueError("Inserisci il reddito complessivo del contribuente.")
    if figli < 0 or figli > 15 or altri < 0 or altri > 10:
        raise ValueError("Verifica i contatori dei familiari a carico.")
    if figli_totali < figli or figli_totali > 20:
        raise ValueError(
            "Il totale dei figli a carico non può essere inferiore ai figli 21-30 "
            "con diritto alla detrazione."
        )
    if not coniuge and figli == 0 and altri == 0:
        raise ValueError("Indica almeno un familiare a carico.")

    righe: List[Dict[str, Any]] = []
    totale = 0.0

    if coniuge:
        if reddito <= 15_000:
            det = 800.0 - 110.0 * _tronca4(reddito / 15_000.0)
        elif reddito <= 40_000:
            det = 690.0
            # Maggiorazioni fisse del c. 1, lett. b): da 10 a 30 euro per sottofasce.
            if 29_000 < reddito <= 29_200:
                det += 10.0
            elif 29_200 < reddito <= 34_700:
                det += 20.0
            elif 34_700 < reddito <= 35_000:
                det += 30.0
            elif 35_000 < reddito <= 35_100:
                det += 20.0
            elif 35_100 < reddito <= 35_200:
                det += 10.0
        elif reddito < 80_000:
            det = 690.0 * _tronca4((80_000.0 - reddito) / 40_000.0)
        else:
            det = 0.0
        det = max(round(det, 2), 0.0)
        totale += det
        righe.append({"voce": "Coniuge a carico", "detrazione": det, "riferimento": "art. 12, c. 1, lett. a-b, TUIR"})

    if figli > 0:
        # La soglia cresce di 15.000 per ogni figlio a carico oltre il primo
        # contando TUTTI i figli a carico (anche gli under-21 coperti
        # dall'assegno unico); la detrazione spetta solo per i figli 21-30
        # (Circ. AE 4/E/2022).
        soglia = 95_000.0 + 15_000.0 * (figli_totali - 1)
        quoziente = _tronca4((soglia - reddito) / soglia)
        det_unitaria = 950.0 * quoziente
        det_figli = round(det_unitaria * figli, 2)
        totale += det_figli
        righe.append(
            {
                "voce": f"Figli a carico 21-30 anni ({figli})",
                "detrazione": det_figli,
                "riferimento": (
                    f"art. 12, c. 1, lett. c, TUIR — soglia {soglia:,.0f}".replace(",", ".")
                    + f" ({figli_totali} figli a carico totali)"
                ),
            }
        )

    if altri > 0:
        quoziente = _tronca4((80_000.0 - reddito) / 80_000.0)
        det_altri = round(750.0 * quoziente * altri, 2)
        totale += det_altri
        righe.append(
            {
                "voce": f"Ascendenti conviventi a carico ({altri})",
                "detrazione": det_altri,
                "riferimento": "art. 12, c. 1, lett. d, TUIR (dal 2025 solo ascendenti conviventi, L. 207/2024)",
            }
        )

    return {
        "reddito": round(reddito, 2),
        "totale_detrazioni": round(totale, 2),
        "dettaglio": righe,
        "notes": [
            f"Familiare a carico con reddito proprio non superiore a "
            f"{_LIMITE_CARICO:,.2f} euro ({_LIMITE_CARICO_FIGLI_GIOVANI:,.0f} per i "
            "figli fino a 24 anni).".replace(",", "X").replace(".", ",").replace("X", "."),
            "Per i figli la detrazione spetta dai 21 ai 30 anni non compiuti — il "
            "limite superiore dei 30 anni non opera per i figli con disabilità "
            "accertata (art. 3 L. 104/1992); sotto i 21 anni opera in ogni caso "
            "l'assegno unico universale (D.Lgs. 230/2021). Spetta anche per i figli "
            "conviventi del coniuge deceduto (art. 12, c. 1, lett. c, TUIR).",
            "La detrazione per i figli è ripartita al 50% tra i genitori; previo "
            "accordo può essere attribuita per intero al genitore col reddito "
            "complessivo più elevato. I 750 euro per ascendente vanno ripartiti pro "
            "quota tra tutti i conviventi che ne hanno diritto.",
            "Quozienti di degressione troncati alle prime quattro cifre decimali "
            "(art. 12, c. 4, TUIR). Reddito complessivo al netto dell'abitazione "
            "principale (art. 12, c. 4-ter, TUIR).",
        ],
        "warnings": [
            "Importi teorici annui: vanno ragguagliati ai mesi di spettanza e "
            "confrontati con l'imposta lorda capiente.",
            "Dal 2025 le detrazioni non spettano ai contribuenti non cittadini "
            "italiani, UE o SEE per i familiari residenti all'estero (art. 12, "
            "c. 2-bis, TUIR).",
        ],
        "sources": [_FONTE_TUIR_12],
    }


def calcola_tipo_reddito(payload: Mapping[str, Any]) -> Dict[str, Any]:
    reddito = safe_float(payload.get("detred_reddito"))
    tipo = clean_text(payload.get("detred_tipo")) or "dipendente"
    tempo_determinato = clean_text(payload.get("detred_determinato")) == "1"
    reddito_dipendente = safe_float(payload.get("detred_reddito_dipendente")) or reddito

    if reddito <= 0:
        raise ValueError("Inserisci il reddito complessivo.")
    tipi = ("dipendente", "pensione", "assegno_coniuge", "altri_redditi")
    if tipo not in tipi:
        raise ValueError("Tipo di reddito non riconosciuto.")
    if reddito_dipendente > reddito:
        raise ValueError(
            "Il reddito di lavoro dipendente non può superare il reddito complessivo."
        )

    notes: List[str] = []
    warnings: List[str] = []
    extra: List[Dict[str, Any]] = []

    if tipo == "dipendente":
        if reddito <= 15_000:
            det = 1_955.0
            minimo = 1_380.0 if tempo_determinato else 690.0
            det = max(det, minimo)
        elif reddito <= 28_000:
            det = 1_910.0 + 1_190.0 * _tronca4((28_000.0 - reddito) / 13_000.0)
        elif reddito <= 50_000:
            det = 1_910.0 * _tronca4((50_000.0 - reddito) / 22_000.0)
        else:
            det = 0.0
        if 25_000 < reddito <= 35_000:
            det += 65.0
            notes.append(
                "Compresa la maggiorazione fissa di 65 euro per redditi tra 25.001 e "
                "35.000 (art. 13, c. 1, ultimo periodo, TUIR)."
            )
        riferimento = "art. 13, c. 1, TUIR (lavoro dipendente)"
        # Misure sul cuneo fiscale ex art. 1, cc. 4-9, L. 207/2024: il gate
        # opera sul reddito complessivo, base e percentuale sul reddito di
        # lavoro dipendente.
        if reddito <= 20_000:
            if reddito_dipendente <= 8_500:
                perc = 7.1
            elif reddito_dipendente <= 15_000:
                perc = 5.3
            else:
                perc = 4.8
            extra.append(
                {
                    "voce": "Somma integrativa (non tassata)",
                    "detrazione": round(reddito_dipendente * perc / 100.0, 2),
                    "riferimento": f"art. 1, cc. 4-5, L. 207/2024 — {perc:g}% del reddito di lavoro dipendente",
                }
            )
            warnings.append(
                "Somma integrativa determinata sul reddito di lavoro dipendente "
                "(percentuale scelta sul dipendente rapportato ad anno intero, art. "
                "1, c. 5, L. 207/2024) ed erogata dal sostituto: importo indicativo."
            )
        elif reddito <= 32_000:
            extra.append(
                {
                    "voce": "Ulteriore detrazione (rapportata al periodo di lavoro)",
                    "detrazione": 1_000.0,
                    "riferimento": "art. 1, c. 6, L. 207/2024",
                }
            )
        elif reddito <= 40_000:
            extra.append(
                {
                    "voce": "Ulteriore detrazione (rapportata al periodo di lavoro)",
                    "detrazione": round(1_000.0 * (40_000.0 - reddito) / 8_000.0, 2),
                    "riferimento": "art. 1, c. 6, L. 207/2024 (a scalare fino a 40.000)",
                }
            )
        if reddito <= 15_000:
            notes.append(
                "Per redditi fino a 15.000 può spettare anche il trattamento "
                "integrativo fino a 1.200 euro (D.L. 3/2020, con la condizione di "
                "capienza adeguata dall'art. 1, c. 3, L. 207/2024), non calcolato qui."
            )
    elif tipo in ("pensione", "assegno_coniuge"):
        if reddito <= 8_500:
            det = 1_955.0
        elif reddito <= 28_000:
            det = 700.0 + 1_255.0 * _tronca4((28_000.0 - reddito) / 19_500.0)
        elif reddito <= 50_000:
            det = 700.0 * _tronca4((50_000.0 - reddito) / 22_000.0)
        else:
            det = 0.0
        if tipo == "pensione" and 25_000 < reddito <= 29_000:
            det += 50.0
            notes.append(
                "Compresa la maggiorazione fissa di 50 euro per redditi tra 25.001 e "
                "29.000 (art. 13, c. 3, ultimo periodo, TUIR)."
            )
        if tipo == "assegno_coniuge":
            riferimento = "art. 13, c. 5-bis, TUIR (assegno periodico dal coniuge: detrazione in misura pari al c. 3, non ragguagliata al periodo)"
            notes.append(
                "All'assegno periodico dal coniuge separato/divorziato si applica la "
                "detrazione del comma 3 senza ragguaglio al periodo; la maggiorazione "
                "di 50 euro del c. 3, ultimo periodo, non è richiamata dal rinvio e "
                "non viene applicata."
            )
        else:
            riferimento = "art. 13, c. 3, TUIR (redditi da pensione)"
    else:
        if reddito <= 5_500:
            det = 1_265.0
        elif reddito <= 28_000:
            det = 500.0 + 765.0 * _tronca4((28_000.0 - reddito) / 22_500.0)
        elif reddito <= 50_000:
            det = 500.0 * _tronca4((50_000.0 - reddito) / 22_000.0)
        else:
            det = 0.0
        if 11_000 < reddito <= 17_000:
            det += 50.0
            notes.append(
                "Compresa la maggiorazione fissa di 50 euro per redditi tra 11.001 e "
                "17.000 (art. 13, c. 5, ultimo periodo, TUIR)."
            )
        riferimento = "art. 13, c. 5, TUIR (redditi assimilati, di lavoro autonomo e altri)"

    det = max(round(det, 2), 0.0)
    dettaglio = [{"voce": "Detrazione per tipo di reddito", "detrazione": det, "riferimento": riferimento}]
    dettaglio.extend(extra)

    notes.append(
        "Detrazione teorica annua da ragguagliare al periodo di lavoro o pensione "
        "nell'anno (i minimi di legge — 690/1.380 dipendente, 713 pensione — "
        "operano sul valore ragguagliato). Quozienti troncati a quattro decimali "
        "(art. 13, c. 6, TUIR); reddito complessivo al netto dell'abitazione "
        "principale (art. 13, c. 6-bis, TUIR)."
    )

    return {
        "reddito": round(reddito, 2),
        "tipo": tipo,
        "detrazione": det,
        "totale_con_misure_cuneo": round(det + sum(v["detrazione"] for v in extra), 2),
        "dettaglio": dettaglio,
        "notes": notes,
        "warnings": warnings,
        "sources": [_FONTE_TUIR_13],
    }


_CANONI: Dict[str, Dict[str, Any]] = {
    "ordinario": {
        "label": "Contratto ordinario (art. 16, c. 01)",
        "fasce": [(15_493.71, 300.0), (30_987.41, 150.0)],
        "riferimento": "art. 16, c. 01, TUIR",
    },
    "concordato": {
        "label": "Canone concordato 3+2 (art. 16, c. 1)",
        "fasce": [(15_493.71, 495.80), (30_987.41, 247.90)],
        "riferimento": "art. 16, c. 1, TUIR",
    },
    "trasferimento_lavoro": {
        "label": "Lavoratore trasferito (art. 16, c. 1-bis)",
        "fasce": [(15_493.71, 991.60), (30_987.41, 495.80)],
        "riferimento": "art. 16, c. 1-bis, TUIR (primi tre anni dal trasferimento)",
    },
}


def calcola_canone(payload: Mapping[str, Any]) -> Dict[str, Any]:
    reddito = safe_float(payload.get("detcan_reddito"))
    tipologia = clean_text(payload.get("detcan_tipo")) or "ordinario"
    canone_annuo = safe_float(payload.get("detcan_canone"))
    giovane = tipologia == "giovani"

    if reddito <= 0:
        raise ValueError("Inserisci il reddito complessivo.")
    if not giovane and tipologia not in _CANONI:
        raise ValueError("Tipologia di contratto non riconosciuta.")

    if giovane:
        if reddito > 15_493.71:
            det = 0.0
            spiegazione = "reddito oltre 15.493,71 euro: detrazione giovani non spettante"
        else:
            det = 991.60
            if canone_annuo > 0:
                det = max(det, min(canone_annuo * 0.20, 2_000.0))
            spiegazione = (
                "991,60 euro, elevati al 20% del canone fino a 2.000 euro "
                "(primi quattro anni, età 20-31 non compiuti)"
            )
        riferimento = "art. 16, c. 1-ter, TUIR (L. 234/2021)"
        label = "Giovani 20-31 anni (art. 16, c. 1-ter)"
    else:
        voce = _CANONI[tipologia]
        det = 0.0
        spiegazione = "reddito oltre 30.987,41 euro: detrazione non spettante"
        for limite, importo in voce["fasce"]:
            if reddito <= limite:
                det = importo
                spiegazione = f"reddito fino a {limite:,.2f} euro".replace(",", "X").replace(".", ",").replace("X", ".")
                break
        riferimento = voce["riferimento"]
        label = voce["label"]

    return {
        "reddito": round(reddito, 2),
        "tipologia": label,
        "detrazione": round(det, 2),
        "spiegazione": spiegazione,
        "riferimento": riferimento,
        "notes": [
            "Detrazione annua per l'abitazione principale condotta in locazione, da "
            "ragguagliare ai giorni di locazione; le tipologie non sono cumulabili.",
            "Se la detrazione supera l'imposta lorda, la parte incapiente è "
            "riconosciuta come credito (art. 16, c. 1-sexies, TUIR).",
        ],
        "warnings": [],
        "sources": [_FONTE_TUIR_16],
    }
