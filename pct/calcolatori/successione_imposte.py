"""Imposta di successione, ipotecaria e catastale per beneficiario.

Base normativa:
- Art. 2, commi 48-49, D.L. 262/2006 (conv. L. 286/2006), che ha
  reistituito l'imposta ex D.Lgs. 346/1990 (T.U.S.), come razionalizzato
  dal D.Lgs. 139/2024 (in vigore per le successioni aperte dal 1/1/2025):
  * 4% per coniuge e parenti in linea retta, franchigia 1.000.000 euro
    per ciascun beneficiario;
  * 6% per fratelli e sorelle, franchigia 100.000 euro;
  * 6% per altri parenti fino al 4° grado e affini in linea retta e
    collaterale fino al 3° grado, senza franchigia;
  * 8% per gli altri soggetti, senza franchigia.
- Art. 2, comma 49-bis, D.L. 262/2006: franchigia 1.500.000 euro se il
  beneficiario è persona con handicap grave (L. 104/1992, art. 3 c. 3).
- Immobili in successione: imposta ipotecaria 2% e catastale 1% (D.Lgs.
  347/1990; misura fissa 200 euro dal 2014 ex art. 26, c. 2, D.L.
  104/2013); in misura fissa di 200 euro ciascuna se ricorrono i
  requisiti «prima casa» ex art. 69, c. 3-4, L. 342/2000, con i requisiti
  della nota II-bis all'art. 1 Tariffa, parte I, D.P.R. 131/1986.
- La parte dell'unione civile è equiparata al coniuge (art. 1, c. 20,
  L. 76/2016); il convivente di fatto rientra tra gli «altri soggetti».

Il tool calcola per singolo beneficiario sulla quota dichiarata; la base
imponibile (attivo ereditario netto, passività deducibili, valori
catastali degli immobili) va determinata a monte secondo il T.U.S.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float

_FONTE_DL262 = {
    "code": "dl_262_2006_art2",
    "title": "Art. 2, c. 48-49, D.L. 262/2006 — aliquote e franchigie successioni",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2006-10-03;262",
}
_FONTE_DLGS347 = {
    "code": "dlgs_347_1990",
    "title": "D.Lgs. 347/1990 — imposte ipotecaria e catastale",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:1990-10-31;347",
}

_RAPPORTI: Dict[str, Dict[str, Any]] = {
    "coniuge_linea_retta": {"label": "Coniuge, parte di unione civile o parente in linea retta", "aliquota": 4.0, "franchigia": 1_000_000.0},
    "fratello_sorella": {"label": "Fratello o sorella", "aliquota": 6.0, "franchigia": 100_000.0},
    "parente_4_affine_3": {"label": "Parente fino al 4° / affine in linea retta / affine collaterale fino al 3°", "aliquota": 6.0, "franchigia": 0.0},
    "altro": {"label": "Altro soggetto (incluso il convivente di fatto)", "aliquota": 8.0, "franchigia": 0.0},
}

_FRANCHIGIA_HANDICAP = 1_500_000.0
_MINIMO_IPOCATASTALI = 200.0


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    quota = safe_float(payload.get("succ_quota"))
    rapporto = clean_text(payload.get("succ_rapporto")) or "coniuge_linea_retta"
    handicap = clean_text(payload.get("succ_handicap")) == "1"
    valore_immobili = safe_float(payload.get("succ_valore_immobili"))
    prima_casa = clean_text(payload.get("succ_prima_casa")) == "1"

    if quota <= 0:
        raise ValueError("Inserisci il valore della quota devoluta al beneficiario.")
    if rapporto not in _RAPPORTI:
        raise ValueError("Rapporto di parentela non riconosciuto.")
    if valore_immobili < 0:
        raise ValueError("Il valore degli immobili non può essere negativo.")
    if valore_immobili > quota:
        raise ValueError(
            "Il valore degli immobili nella quota non può superare la quota stessa."
        )

    voce = _RAPPORTI[rapporto]
    franchigia = _FRANCHIGIA_HANDICAP if handicap else float(voce["franchigia"])
    aliquota = float(voce["aliquota"])

    imponibile = max(quota - franchigia, 0.0)
    imposta_successione = round(imponibile * aliquota / 100.0, 2)

    ipotecaria = catastale = 0.0
    warnings_immobili: List[str] = []
    if valore_immobili > 0:
        if prima_casa:
            ipotecaria = _MINIMO_IPOCATASTALI
            catastale = _MINIMO_IPOCATASTALI
            warnings_immobili.append(
                "La misura fissa ex art. 69 L. 342/2000 spetta per il solo immobile "
                "prima casa (e pertinenze), una volta per immobile: se la quota "
                "comprende altri immobili, su questi restano dovute le proporzionali "
                "2% + 1%; con più coeredi l'agevolazione sull'immobile si applica "
                "una sola volta anche se un solo coerede ha i requisiti."
            )
        else:
            ipotecaria = max(round(valore_immobili * 0.02, 2), _MINIMO_IPOCATASTALI)
            catastale = max(round(valore_immobili * 0.01, 2), _MINIMO_IPOCATASTALI)
            if valore_immobili * 0.02 < _MINIMO_IPOCATASTALI or valore_immobili * 0.01 < _MINIMO_IPOCATASTALI:
                warnings_immobili.append(
                    "Il minimo di 200 euro per le imposte ipotecaria e catastale opera "
                    "una sola volta per successione sul valore complessivo degli "
                    "immobili, non per ciascun beneficiario: con più eredi il calcolo "
                    "per quota può sovrastimare i minimi."
                )
        warnings_immobili.append(
            "Il calcolo ipocatastale vale per i soli immobili siti in Italia; restano "
            "esclusi tassa ipotecaria e bolli per le formalità."
        )

    totale = round(imposta_successione + ipotecaria + catastale, 2)

    notes: List[str] = [
        f"Rapporto: {voce['label']} — aliquota {aliquota:g}%, franchigia "
        f"{'1.500.000 (handicap grave, c. 49-bis)' if handicap else format(franchigia, ',.0f').replace(',', '.')} euro.",
        "La franchigia opera per ciascun beneficiario sulla propria quota.",
    ]
    if valore_immobili > 0 and prima_casa:
        notes.append(
            "Ipotecaria e catastale in misura fissa (200 euro ciascuna) ex art. 69, "
            "c. 3-4, L. 342/2000, con i requisiti della nota II-bis all'art. 1 "
            "Tariffa, parte I, D.P.R. 131/1986."
        )

    return {
        "quota_devoluta": round(quota, 2),
        "rapporto": voce["label"],
        "franchigia": round(franchigia, 2),
        "imponibile": round(imponibile, 2),
        "aliquota": aliquota,
        "imposta_successione": imposta_successione,
        "imposta_ipotecaria": round(ipotecaria, 2),
        "imposta_catastale": round(catastale, 2),
        "totale_imposte": totale,
        "notes": notes,
        "warnings": [
            "La base imponibile va determinata secondo il T.U.S. (attivo netto, "
            "passività deducibili, valore catastale degli immobili): questo calcolo "
            "applica aliquote e franchigie alla quota già determinata. Per aziende, "
            "partecipazioni e trasferimenti ex art. 3 T.U.S. valgono esenzioni "
            "specifiche non gestite qui.",
            *warnings_immobili,
        ],
        "sources": [_FONTE_DL262, _FONTE_DLGS347],
    }


def opzioni_rapporti() -> list[dict]:
    return [{"value": chiave, "label": voce["label"]} for chiave, voce in _RAPPORTI.items()]
