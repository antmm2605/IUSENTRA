"""Determinazione della pena: attenuanti, continuazione e riti alternativi.

Base normativa (nessun valore soggetto ad aggiornamento periodico: solo
frazioni e soglie fissate dalla legge):

- Art. 132, comma 2, c.p.: nel computo della pena il giorno è di ventiquattro
  ore e l'anno è di trecentosessantacinque giorni. Il mese è computato in
  trenta giorni secondo la prassi applicativa costante.
- Art. 62-bis c.p.: circostanze attenuanti generiche; la diminuzione non può
  eccedere un terzo (art. 65, n. 3, c.p.).
- Art. 65, n. 3, c.p.: misura della diminuzione per una circostanza attenuante.
- Art. 81, comma 2, c.p.: reato continuato; la pena del reato più grave è
  aumentata fino al triplo.
- Art. 81, comma 4, c.p.: per i recidivi ex art. 99, comma 4, c.p. l'aumento
  non può essere inferiore a un terzo della pena stabilita per il reato più
  grave.
- Art. 442, comma 2, c.p.p.: giudizio abbreviato; diminuzione di un terzo per
  i delitti e della metà per le contravvenzioni.
- Art. 442, comma 2-bis, c.p.p. (introdotto dal D.Lgs. 150/2022): ulteriore
  riduzione di un sesto della pena in caso di mancata impugnazione.
- Art. 444, comma 1, c.p.p.: applicazione della pena su richiesta; diminuzione
  fino a un terzo.
- Art. 163 c.p.: limiti della sospensione condizionale della pena.
- Artt. 20-bis c.p. e 53 ss. L. 689/1981, come riformati dal D.Lgs. 150/2022:
  limiti di pena delle pene sostitutive delle pene detentive brevi.

Il modulo non decide se una circostanza o un rito siano applicabili al caso:
calcola l'effetto delle frazioni indicate dall'operatore e dichiara la norma
applicata ad ogni passaggio.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Tuple

from pct.calcolatori._base import clean_text, safe_bool, safe_int

GIORNI_ANNO = 365
GIORNI_MESE = 30

_RITI = {
    "ordinario": "Rito ordinario (nessuna diminuzione per il rito)",
    "abbreviato": "Giudizio abbreviato (art. 442, comma 2, c.p.p.)",
    "patteggiamento": "Applicazione della pena su richiesta (art. 444 c.p.p.)",
}

_FRAZIONI_PATTEGGIAMENTO = {
    "un_terzo": (1, 3),
    "un_quarto": (1, 4),
    "un_quinto": (1, 5),
}


def _in_giorni(anni: int, mesi: int, giorni: int) -> int:
    return anni * GIORNI_ANNO + mesi * GIORNI_MESE + giorni


def _da_giorni(totale: int) -> Dict[str, int]:
    totale = max(0, int(totale))
    anni, resto = divmod(totale, GIORNI_ANNO)
    mesi, giorni = divmod(resto, GIORNI_MESE)
    return {"anni": anni, "mesi": mesi, "giorni": giorni, "totale_giorni": totale}


def _formatta(totale_giorni: int) -> str:
    parti = _da_giorni(totale_giorni)
    pezzi: List[str] = []
    if parti["anni"]:
        pezzi.append(f"{parti['anni']} anno" if parti["anni"] == 1 else f"{parti['anni']} anni")
    if parti["mesi"]:
        pezzi.append(f"{parti['mesi']} mese" if parti["mesi"] == 1 else f"{parti['mesi']} mesi")
    if parti["giorni"]:
        pezzi.append(f"{parti['giorni']} giorno" if parti["giorni"] == 1 else f"{parti['giorni']} giorni")
    return " e ".join(pezzi) if pezzi else "nessuna pena residua"


def _riduci(totale: int, numeratore: int, denominatore: int) -> int:
    """Diminuzione per frazione, arrotondata per difetto in favore dell'imputato."""

    return int(totale - (totale * numeratore) // denominatore)


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    anni = max(0, safe_int(payload.get("pena_anni")))
    mesi = max(0, safe_int(payload.get("pena_mesi")))
    giorni = max(0, safe_int(payload.get("pena_giorni")))
    base = _in_giorni(anni, mesi, giorni)
    if base <= 0:
        raise ValueError("Indica la pena base determinata dal giudice in anni, mesi o giorni.")
    if mesi > 11 or giorni > 29:
        raise ValueError("Esprimi la pena base con mesi da 0 a 11 e giorni da 0 a 29.")

    tipo_reato = clean_text(payload.get("pena_tipo_reato")).lower() or "delitto"
    if tipo_reato not in {"delitto", "contravvenzione"}:
        raise ValueError("Il tipo di reato deve essere delitto o contravvenzione.")
    rito = clean_text(payload.get("pena_rito")).lower() or "ordinario"
    if rito not in _RITI:
        raise ValueError("Rito non riconosciuto: scegli ordinario, abbreviato o patteggiamento.")

    passaggi: List[Dict[str, Any]] = []
    notes: List[str] = []
    warnings: List[str] = []
    corrente = base
    passaggi.append(
        {
            "fase": "Pena base determinata",
            "riferimento": "Artt. 132-133 c.p.",
            "operazione": "punto di partenza indicato dall'operatore",
            "pena": _formatta(corrente),
            "giorni": corrente,
        }
    )

    if safe_bool(payload.get("pena_attenuanti_generiche")):
        num, den = 1, 3
        prima = corrente
        corrente = _riduci(corrente, num, den)
        passaggi.append(
            {
                "fase": "Attenuanti generiche",
                "riferimento": "Artt. 62-bis e 65, n. 3, c.p.",
                "operazione": f"diminuzione di {num}/{den} (misura massima consentita)",
                "pena": _formatta(corrente),
                "giorni": corrente,
                "differenza": prima - corrente,
            }
        )
        notes.append(
            "La diminuzione per una circostanza attenuante non può eccedere un terzo (art. 65, n. 3, c.p.): "
            "il calcolo applica la misura massima. Se il giudice concede una diminuzione minore, il risultato è più alto."
        )

    reati_satellite = max(0, safe_int(payload.get("pena_reati_satellite")))
    if reati_satellite:
        aumento_giorni_per_reato = max(0, safe_int(payload.get("pena_aumento_per_reato_giorni")))
        if aumento_giorni_per_reato <= 0:
            raise ValueError(
                "Con la continuazione indica l'aumento in giorni stabilito per ciascun reato satellite."
            )
        recidiva_reiterata = safe_bool(payload.get("pena_recidiva_reiterata"))
        aumento_totale = aumento_giorni_per_reato * reati_satellite
        limite_triplo = corrente * 3
        minimo_recidiva = corrente // 3 if recidiva_reiterata else 0

        if recidiva_reiterata and aumento_totale < minimo_recidiva:
            aumento_totale = minimo_recidiva
            warnings.append(
                "Aumento portato al minimo di legge: per i recidivi reiterati l'aumento per la continuazione "
                "non può essere inferiore a un terzo della pena del reato più grave (art. 81, comma 4, c.p.)."
            )
        prima = corrente
        corrente = corrente + aumento_totale
        if corrente > limite_triplo:
            corrente = limite_triplo
            warnings.append(
                "Aumento ridotto al limite di legge: la pena del reato più grave non può essere aumentata "
                "oltre il triplo (art. 81, comma 2, c.p.)."
            )
        passaggi.append(
            {
                "fase": f"Continuazione — {reati_satellite} reato satellite" if reati_satellite == 1 else f"Continuazione — {reati_satellite} reati satellite",
                "riferimento": "Art. 81, comma 2, c.p.",
                "operazione": f"aumento di {aumento_giorni_per_reato} giorni per reato",
                "pena": _formatta(corrente),
                "giorni": corrente,
                "differenza": corrente - prima,
            }
        )

    if rito == "abbreviato":
        if tipo_reato == "contravvenzione":
            num, den, testo = 1, 2, "diminuzione della metà (contravvenzione)"
        else:
            num, den, testo = 1, 3, "diminuzione di un terzo (delitto)"
        prima = corrente
        corrente = _riduci(corrente, num, den)
        passaggi.append(
            {
                "fase": "Diminuzione per il rito",
                "riferimento": "Art. 442, comma 2, c.p.p.",
                "operazione": testo,
                "pena": _formatta(corrente),
                "giorni": corrente,
                "differenza": prima - corrente,
            }
        )
        if safe_bool(payload.get("pena_mancata_impugnazione")):
            prima = corrente
            corrente = _riduci(corrente, 1, 6)
            passaggi.append(
                {
                    "fase": "Mancata impugnazione",
                    "riferimento": "Art. 442, comma 2-bis, c.p.p.",
                    "operazione": "ulteriore diminuzione di un sesto",
                    "pena": _formatta(corrente),
                    "giorni": corrente,
                    "differenza": prima - corrente,
                }
            )
            notes.append(
                "La riduzione di un sesto per mancata impugnazione è disposta dal giudice dell'esecuzione "
                "e presuppone che né l'imputato né il difensore propongano impugnazione (art. 442, comma 2-bis, c.p.p.)."
            )
    elif rito == "patteggiamento":
        chiave = clean_text(payload.get("pena_frazione_patteggiamento")).lower() or "un_terzo"
        if chiave not in _FRAZIONI_PATTEGGIAMENTO:
            raise ValueError("Frazione di diminuzione per il patteggiamento non riconosciuta.")
        num, den = _FRAZIONI_PATTEGGIAMENTO[chiave]
        prima = corrente
        corrente = _riduci(corrente, num, den)
        passaggi.append(
            {
                "fase": "Diminuzione per il rito",
                "riferimento": "Art. 444, comma 1, c.p.p.",
                "operazione": f"diminuzione concordata di {num}/{den}",
                "pena": _formatta(corrente),
                "giorni": corrente,
                "differenza": prima - corrente,
            }
        )
        notes.append(
            "L'art. 444, comma 1, c.p.p. consente una diminuzione *fino a* un terzo: la misura è oggetto "
            "dell'accordo tra le parti e resta soggetta al vaglio del giudice."
        )

    esiti = _valuta_benefici(corrente, payload)

    return {
        "pena_base_giorni": base,
        "pena_base_testo": _formatta(base),
        "pena_finale_giorni": corrente,
        "pena_finale_testo": _formatta(corrente),
        "pena_finale_dettaglio": _da_giorni(corrente),
        "riduzione_complessiva_giorni": base - corrente if corrente <= base else 0,
        "tipo_reato": tipo_reato,
        "rito": rito,
        "rito_label": _RITI[rito],
        "passaggi": passaggi,
        "benefici": esiti,
        "notes": notes
        + [
            "Computo della pena secondo l'art. 132, comma 2, c.p.: anno di 365 giorni, mese di 30 giorni. "
            "Le diminuzioni frazionarie sono arrotondate per difetto, in favore dell'imputato.",
            "Lo strumento calcola l'effetto delle frazioni indicate: non stabilisce se attenuanti, continuazione "
            "o rito siano in concreto applicabili, valutazione che resta del difensore e del giudice.",
        ],
        "warnings": warnings,
        "sources": [
            {
                "title": "Codice penale, artt. 62-bis, 65, 81, 132-133, 163 (Normattiva)",
                "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1930-10-19;1398",
            },
            {
                "title": "Codice di procedura penale, artt. 442 e 444 (Normattiva)",
                "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:presidente.repubblica:decreto:1988-09-22;447",
            },
            {
                "title": "D.Lgs. 10 ottobre 2022, n. 150 (riforma Cartabia)",
                "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2022-10-10;150",
            },
        ],
    }


def _valuta_benefici(pena_giorni: int, payload: Mapping[str, Any]) -> List[Dict[str, Any]]:
    """Soglie di legge dei benefici, valutate sulla pena finale calcolata."""

    eta = safe_int(payload.get("pena_eta_imputato"))
    limite_sospensione, riferimento_sospensione = _limite_sospensione_condizionale(eta)
    esiti: List[Dict[str, Any]] = [
        {
            "istituto": "Sospensione condizionale della pena",
            "riferimento": riferimento_sospensione,
            "limite": _formatta(limite_sospensione),
            "entro_limite": pena_giorni <= limite_sospensione,
            "nota": "Il beneficio presuppone anche i presupposti soggettivi degli artt. 164 e 165 c.p.",
        },
        {
            "istituto": "Pena pecuniaria sostitutiva",
            "riferimento": "Art. 53 L. 689/1981, come riformato dal D.Lgs. 150/2022",
            "limite": _formatta(1 * GIORNI_ANNO),
            "entro_limite": pena_giorni <= 1 * GIORNI_ANNO,
            "nota": "Sostituzione della pena detentiva non superiore a un anno.",
        },
        {
            "istituto": "Lavoro di pubblica utilità sostitutivo",
            "riferimento": "Art. 56-bis L. 689/1981, come riformato dal D.Lgs. 150/2022",
            "limite": _formatta(3 * GIORNI_ANNO),
            "entro_limite": pena_giorni <= 3 * GIORNI_ANNO,
            "nota": "Richiede il consenso dell'imputato.",
        },
        {
            "istituto": "Semilibertà o detenzione domiciliare sostitutive",
            "riferimento": "Artt. 55 e 56 L. 689/1981, come riformati dal D.Lgs. 150/2022",
            "limite": _formatta(4 * GIORNI_ANNO),
            "entro_limite": pena_giorni <= 4 * GIORNI_ANNO,
            "nota": "Sostituzione della pena detentiva non superiore a quattro anni.",
        },
    ]
    return esiti


def _limite_sospensione_condizionale(eta: int) -> Tuple[int, str]:
    """Limiti dell'art. 163 c.p. in funzione dell'età dell'imputato."""

    if 0 < eta < 18:
        return 3 * GIORNI_ANNO, "Art. 163, comma 3, c.p. (minore degli anni diciotto)"
    if 18 <= eta < 21 or eta > 70:
        return 2 * GIORNI_ANNO + 6 * GIORNI_MESE, "Art. 163, comma 2, c.p. (età 18-21 o superiore a 70)"
    return 2 * GIORNI_ANNO, "Art. 163, comma 1, c.p."


def opzioni() -> Dict[str, Any]:
    """Opzioni dichiarate per la UI, così il template non ripete le costanti."""

    return {
        "riti": [{"value": key, "label": label} for key, label in _RITI.items()],
        "frazioni_patteggiamento": [
            {"value": "un_terzo", "label": "Un terzo (misura massima)"},
            {"value": "un_quarto", "label": "Un quarto"},
            {"value": "un_quinto", "label": "Un quinto"},
        ],
        "tipi_reato": [
            {"value": "delitto", "label": "Delitto"},
            {"value": "contravvenzione", "label": "Contravvenzione"},
        ],
    }
