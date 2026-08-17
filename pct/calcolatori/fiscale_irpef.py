"""IRPEF lorda, acconti e rateazione delle imposte da dichiarazione.

Base normativa:
- Scaglioni e aliquote: art. 11 TUIR (D.P.R. 917/1986). Dal periodo
  d'imposta 2024 tre scaglioni (D.Lgs. 216/2023, resi strutturali
  dall'art. 1, c. 2, L. 207/2024): 23% fino a 28.000; 35% da 28.000 a
  50.000; 43% oltre. Dal periodo d'imposta 2026 la seconda aliquota è
  ridotta al 33% dall'art. 1, c. 3, L. 30/12/2025, n. 199 (legge di
  bilancio 2026). Gli scaglioni sono versionati per anno: anni non
  coperti vengono rifiutati (fail-closed).
- Acconti: art. 17 D.P.R. 435/2001 (metodo storico: 100% dell'imposta
  del rigo differenza; nessun acconto se non superiore a 51,65 euro;
  unica soluzione a novembre se INFERIORE a 257,52 euro; due rate se
  pari o superiore — il 40% di 257,52 supera i 103 euro della soglia di
  legge sulla prima rata); per i soggetti ISA e i forfettari le due rate
  sono al 50% (art. 58 D.L. 124/2019). Le stesse regole valgono per la
  cedolare secca (art. 3, c. 4, D.Lgs. 23/2011, acconto al 100%).
- Rateazione: art. 20 D.Lgs. 241/1997, come modificato dall'art. 8
  D.Lgs. 1/2024 — saldo e primo acconto rateizzabili in rate mensili di
  pari importo con ultima rata entro il 16 dicembre; interessi al 4%
  annuo (0,33% mensile) sulle rate successive alla prima. La rateazione
  degli avvisi bonari (art. 3-bis D.Lgs. 462/1997) segue regole diverse
  e non è gestita qui.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float, safe_int

_FONTE_TUIR_11 = {
    "code": "tuir_art_11",
    "title": "Art. 11 TUIR (D.P.R. 917/1986) — determinazione dell'imposta",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1986-12-22;917",
}
_FONTE_BILANCIO_2026 = {
    "code": "l_199_2025_art1_c3",
    "title": "Art. 1, c. 3, L. 199/2025 (bilancio 2026) — seconda aliquota IRPEF al 33%",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2025-12-30;199",
}
_FONTE_ACCONTI = {
    "code": "dpr_435_2001_art17",
    "title": "Art. 17 D.P.R. 435/2001 — versamento degli acconti",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:2001-12-07;435",
}
_FONTE_RATE = {
    "code": "dlgs_241_1997_art20",
    "title": "Art. 20 D.Lgs. 241/1997 — rateazione delle somme da dichiarazione",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:1997-07-09;241",
}

# Scaglioni versionati per anno d'imposta: [(limite superiore, aliquota %)].
_SCAGLIONI: Dict[int, List[tuple[float, float]]] = {
    2024: [(28_000.0, 23.0), (50_000.0, 35.0), (float("inf"), 43.0)],
    2025: [(28_000.0, 23.0), (50_000.0, 35.0), (float("inf"), 43.0)],
    2026: [(28_000.0, 23.0), (50_000.0, 33.0), (float("inf"), 43.0)],
}

_SOGLIA_NO_ACCONTO = 51.65
_SOGLIA_UNICA_SOLUZIONE = 257.52
_INTERESSE_RATEAZIONE_MENSILE = 0.33  # percento per mese, art. 20, c. 2, D.Lgs. 241/1997


def calcola_irpef(payload: Mapping[str, Any]) -> Dict[str, Any]:
    reddito = safe_float(payload.get("irpef_reddito"))
    anno = safe_int(payload.get("irpef_anno"), 2026)

    if reddito < 0:
        raise ValueError("Il reddito imponibile non può essere negativo.")
    if reddito > 50_000_000:
        raise ValueError("Reddito fuori range gestito.")
    if anno not in _SCAGLIONI:
        anni = ", ".join(str(a) for a in sorted(_SCAGLIONI))
        raise ValueError(
            f"Anno d'imposta {anno} non coperto dagli scaglioni versionati ({anni}): "
            "il tool non ipotizza aliquote non ancora recepite."
        )

    dettaglio: List[Dict[str, Any]] = []
    imposta = 0.0
    precedente = 0.0
    for limite, aliquota in _SCAGLIONI[anno]:
        if reddito <= precedente:
            break
        quota = min(reddito, limite) - precedente
        tassa = quota * aliquota / 100.0
        imposta += tassa
        dettaglio.append(
            {
                "scaglione": (
                    f"oltre {precedente:,.0f}".replace(",", ".")
                    if limite == float("inf")
                    else f"{precedente:,.0f} - {limite:,.0f}".replace(",", ".")
                ),
                "aliquota": aliquota,
                "imponibile": round(quota, 2),
                "imposta": round(tassa, 2),
            }
        )
        precedente = limite

    aliquota_media = round(imposta / reddito * 100.0, 2) if reddito else 0.0
    marginale = dettaglio[-1]["aliquota"] if dettaglio else 0.0

    return {
        "anno": anno,
        "reddito": round(reddito, 2),
        "irpef_lorda": round(imposta, 2),
        "aliquota_media": aliquota_media,
        "aliquota_marginale": marginale,
        "dettaglio": dettaglio,
        "notes": [
            f"Scaglioni dell'anno d'imposta {anno} (art. 11 TUIR; D.Lgs. 216/2023 e "
            "art. 1, c. 2, L. 207/2024; per il 33% dal 2026: art. 1, c. 3, L. "
            "199/2025).",
            "Imposta LORDA: detrazioni (artt. 12, 13, 15, 16 TUIR), addizionali "
            "regionali e comunali e crediti d'imposta vanno applicati a parte — "
            "vedere i tool dedicati alle detrazioni.",
        ],
        "warnings": [
            "La no tax area opera tramite le detrazioni per tipo di reddito, non "
            "tramite gli scaglioni: un'imposta lorda positiva può azzerarsi con le "
            "detrazioni spettanti.",
        ]
        + (
            [
                "Per i redditi complessivi oltre 200.000 euro il beneficio del taglio "
                "al 33% è sterilizzato da una riduzione di 440 euro delle detrazioni "
                "dall'imposta lorda (L. 199/2025): tenerne conto nel tool detrazioni."
            ]
            if anno >= 2026 and reddito > 200_000
            else []
        ),
        "sources": [_FONTE_TUIR_11] + ([_FONTE_BILANCIO_2026] if anno >= 2026 else []),
    }


def calcola_acconto(payload: Mapping[str, Any]) -> Dict[str, Any]:
    rigo_differenza = safe_float(payload.get("acc_rigo_differenza"))
    imposta = clean_text(payload.get("acc_imposta")) or "irpef"
    soggetto_isa = clean_text(payload.get("acc_isa")) == "1"

    if rigo_differenza < 0:
        raise ValueError(
            "Il rigo differenza non può essere negativo: con saldo a credito "
            "l'acconto si calcola comunque sull'imposta dovuta dell'anno."
        )
    if imposta not in ("irpef", "cedolare"):
        raise ValueError("Imposta ammessa: IRPEF oppure cedolare secca.")

    etichetta = "IRPEF" if imposta == "irpef" else "cedolare secca"
    acconto_totale = rigo_differenza  # metodo storico: 100%

    if rigo_differenza <= _SOGLIA_NO_ACCONTO:
        esito = "non dovuto"
        prima_rata = seconda_rata = 0.0
        note_rate = f"Importo del rigo differenza non superiore a {_SOGLIA_NO_ACCONTO:.2f} euro: acconto non dovuto."
    elif rigo_differenza < _SOGLIA_UNICA_SOLUZIONE:
        # A 257,52 esatti sono dovute due rate: il 40% (103,008) supera la
        # soglia di 103 euro sulla prima rata (art. 17, c. 3, D.P.R. 435/2001).
        esito = "unica soluzione a novembre"
        prima_rata = 0.0
        seconda_rata = round(acconto_totale, 2)
        note_rate = (
            f"Rigo differenza inferiore a {_SOGLIA_UNICA_SOLUZIONE:.2f} euro: "
            "acconto in unica soluzione entro il 30 novembre."
        )
    else:
        esito = "due rate"
        if soggetto_isa:
            prima_rata = round(acconto_totale * 0.50, 2)
            seconda_rata = round(acconto_totale - prima_rata, 2)
            note_rate = (
                "Soggetto ISA o forfettario: due rate del 50% ciascuna "
                "(art. 58 D.L. 124/2019)."
            )
        else:
            prima_rata = round(acconto_totale * 0.40, 2)
            seconda_rata = round(acconto_totale - prima_rata, 2)
            note_rate = "Prima rata 40% col saldo, seconda rata 60% entro il 30 novembre."

    return {
        "imposta": etichetta,
        "rigo_differenza": round(rigo_differenza, 2),
        "acconto_totale": round(acconto_totale if esito != "non dovuto" else 0.0, 2),
        "esito": esito,
        "prima_rata": prima_rata,
        "seconda_rata": seconda_rata,
        "notes": [
            "Metodo storico: acconto pari al 100% dell'imposta dell'anno precedente "
            "(art. 17 D.P.R. 435/2001; per la cedolare secca art. 3, c. 4, D.Lgs. "
            "23/2011).",
            note_rate,
        ],
        "warnings": [
            "Il metodo previsionale (acconto sull'imposta stimata dell'anno in corso) "
            "è ammesso ma espone a sanzioni se la stima risulta insufficiente: "
            "valutarlo col professionista.",
        ],
        "sources": [_FONTE_ACCONTI],
    }


def calcola_rateazione(payload: Mapping[str, Any]) -> Dict[str, Any]:
    importo = safe_float(payload.get("rate_importo"))
    numero_rate = safe_int(payload.get("rate_numero"))

    if importo <= 0:
        raise ValueError("Inserisci l'importo da rateizzare (saldo e/o primo acconto).")
    if numero_rate < 2 or numero_rate > 7:
        raise ValueError(
            "Numero di rate tra 2 e 7: la rateazione ex art. 20 D.Lgs. 241/1997 "
            "deve completarsi entro il 16 dicembre (rate mensili dal versamento di "
            "giugno/luglio)."
        )

    quota = importo / numero_rate
    righe: List[Dict[str, Any]] = []
    totale_interessi = 0.0
    for n in range(1, numero_rate + 1):
        interessi = 0.0 if n == 1 else quota * _INTERESSE_RATEAZIONE_MENSILE / 100.0 * (n - 1)
        totale_interessi += interessi
        righe.append(
            {
                "rata": n,
                "quota_capitale": round(quota, 2),
                "interessi": round(interessi, 2),
                "totale_rata": round(quota + interessi, 2),
            }
        )

    return {
        "importo": round(importo, 2),
        "numero_rate": numero_rate,
        "totale_interessi": round(totale_interessi, 2),
        "totale_versato": round(importo + totale_interessi, 2),
        "piano": righe,
        "notes": [
            "Rateazione delle somme da dichiarazione (art. 20 D.Lgs. 241/1997, come "
            "modificato dall'art. 8 D.Lgs. 1/2024): rate mensili di pari importo con "
            "interessi al 4% annuo dalla seconda rata; ultima rata entro il 16 "
            "dicembre.",
            "Le rate successive alla prima scadono il giorno 16 di ciascun mese per "
            "tutti i contribuenti; verificare gli slittamenti per giorni festivi sul "
            "calendario dell'anno.",
        ],
        "warnings": [
            "Interessi calcolati a mesi interi (0,33% per mese di distanza dalla "
            "prima rata): stima per ECCESSO rispetto alle tabelle ufficiali "
            "dell'Agenzia delle Entrate, che computano i giorni commerciali "
            "effettivi tra le scadenze (la prima frazione 30/6-16/7 vale circa "
            "0,18%). Per gli importi F24 esatti usare le tabelle AE dell'anno.",
            "La rateazione degli avvisi bonari (art. 3-bis D.Lgs. 462/1997, fino a "
            "20 rate trimestrali) segue regole e interessi diversi e non è gestita "
            "da questo calcolo.",
        ],
        "sources": [_FONTE_RATE],
    }
