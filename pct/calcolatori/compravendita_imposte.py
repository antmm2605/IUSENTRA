"""Imposte sulla compravendita immobiliare (abitazioni).

Base normativa:
- Cessioni da privato (o da impresa esente IVA): imposta di registro 9%,
  ridotta al 2% con i requisiti «prima casa» (art. 1 Tariffa, parte I,
  D.P.R. 131/1986, come sostituito dall'art. 10 D.Lgs. 23/2011 dal
  1/1/2014), con minimo di 1.000 euro; imposte ipotecaria e catastale
  fisse di 50 euro ciascuna (art. 10, c. 3, D.Lgs. 23/2011).
- Base imponibile «prezzo-valore» (art. 1, c. 497, L. 266/2005): per le
  abitazioni cedute a persone fisiche si può chiedere in atto la
  tassazione sul valore catastale anziché sul prezzo.
- Cessioni da impresa costruttrice soggette a IVA (art. 10, n. 8-bis,
  D.P.R. 633/1972 e Tabella A): IVA 4% prima casa, 10% altre abitazioni,
  22% categorie A/1, A/8, A/9; registro, ipotecaria e catastale fisse di
  200 euro ciascuna (base imponibile IVA = prezzo).
- Requisiti prima casa: nota II-bis all'art. 1 Tariffa D.P.R. 131/1986
  (no categorie A/1, A/8, A/9).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping

from pct.calcolatori._base import clean_text, safe_float

_FONTE_DLGS23 = {
    "code": "dlgs_23_2011_art10",
    "title": "Art. 10 D.Lgs. 23/2011 — registro 9%/2% e ipocatastali 50 euro",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:2011-03-14;23",
}
_FONTE_IVA = {
    "code": "dpr_633_1972_tab_a",
    "title": "D.P.R. 633/1972, art. 10 n. 8-bis e Tabella A — IVA sulle abitazioni",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.del.presidente.della.repubblica:1972-10-26;633",
}
_FONTE_PREZZO_VALORE = {
    "code": "l_266_2005_c497",
    "title": "Art. 1, c. 497, L. 266/2005 — regime del prezzo-valore",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:legge:2005-12-23;266",
}

_MINIMO_REGISTRO = 1000.0
_FISSA_IPOCATASTALE_PRIVATO = 50.0
_FISSA_ATTO_IVA = 200.0


def calcola(payload: Mapping[str, Any]) -> Dict[str, Any]:
    regime = clean_text(payload.get("comp_regime")) or "privato"
    prezzo = safe_float(payload.get("comp_prezzo"))
    valore_catastale = safe_float(payload.get("comp_valore_catastale"))
    prima_casa = clean_text(payload.get("comp_prima_casa")) == "1"
    lusso = clean_text(payload.get("comp_lusso")) == "1"

    if regime not in ("privato", "iva"):
        raise ValueError("Regime ammesso: cessione da privato oppure soggetta a IVA.")
    if prezzo <= 0:
        raise ValueError("Inserisci il prezzo di compravendita.")
    if valore_catastale < 0:
        raise ValueError("Il valore catastale non può essere negativo.")
    if prima_casa and lusso:
        raise ValueError(
            "Le categorie di lusso (A/1, A/8, A/9) non ammettono l'agevolazione "
            "prima casa (nota II-bis art. 1 Tariffa D.P.R. 131/1986)."
        )

    dettaglio: List[Dict[str, Any]] = []
    notes: List[str] = []
    warnings: List[str] = []

    if regime == "privato":
        if valore_catastale > 0:
            base = valore_catastale
            notes.append(
                "Base imponibile: valore catastale col regime del prezzo-valore "
                "(art. 1, c. 497, L. 266/2005) — spetta solo se l'acquirente è persona "
                "fisica che non agisce nell'esercizio di impresa, arte o professione, "
                "va richiesto espressamente in atto e il prezzo effettivo va comunque "
                "indicato."
            )
            if valore_catastale > prezzo:
                warnings.append(
                    "Il valore catastale supera il prezzo: il prezzo-valore è "
                    "un'opzione e in questo caso sarebbe antieconomica — verificare "
                    "i dati inseriti."
                )
        else:
            base = prezzo
            notes.append(
                "Base imponibile: prezzo dichiarato. Per le abitazioni acquistate da "
                "persona fisica (fuori da impresa, arte o professione) conviene "
                "valutare il prezzo-valore sul valore catastale."
            )
        aliquota = 2.0 if prima_casa else 9.0
        registro = max(round(base * aliquota / 100.0, 2), _MINIMO_REGISTRO)
        if base * aliquota / 100.0 < _MINIMO_REGISTRO:
            notes.append("Imposta di registro applicata al minimo di legge (1.000 euro).")
        ipotecaria = _FISSA_IPOCATASTALE_PRIVATO
        catastale = _FISSA_IPOCATASTALE_PRIVATO
        iva = 0.0
        dettaglio = [
            {"voce": "Imposta di registro", "importo": registro, "riferimento": f"{aliquota:g}% (art. 1 Tariffa D.P.R. 131/1986)"},
            {"voce": "Imposta ipotecaria", "importo": ipotecaria, "riferimento": "fissa 50 euro (art. 10, c. 3, D.Lgs. 23/2011)"},
            {"voce": "Imposta catastale", "importo": catastale, "riferimento": "fissa 50 euro (art. 10, c. 3, D.Lgs. 23/2011)"},
        ]
    else:
        base = prezzo
        if lusso:
            aliquota_iva = 22.0
        elif prima_casa:
            aliquota_iva = 4.0
        else:
            aliquota_iva = 10.0
        iva = round(base * aliquota_iva / 100.0, 2)
        registro = _FISSA_ATTO_IVA
        ipotecaria = _FISSA_ATTO_IVA
        catastale = _FISSA_ATTO_IVA
        notes.append(
            "Cessione soggetta a IVA (impresa costruttrice entro 5 anni o con opzione): "
            "base imponibile il prezzo; il prezzo-valore non si applica."
        )
        dettaglio = [
            {"voce": "IVA", "importo": iva, "riferimento": f"{aliquota_iva:g}% (Tabella A D.P.R. 633/1972)"},
            {"voce": "Imposta di registro", "importo": registro, "riferimento": "fissa 200 euro"},
            {"voce": "Imposta ipotecaria", "importo": ipotecaria, "riferimento": "fissa 200 euro"},
            {"voce": "Imposta catastale", "importo": catastale, "riferimento": "fissa 200 euro"},
        ]

    totale = round(sum(riga["importo"] for riga in dettaglio), 2)

    if prima_casa:
        notes.append(
            "Requisiti prima casa (nota II-bis all'art. 1 Tariffa D.P.R. 131/1986): "
            "residenza nel Comune entro 18 mesi; nessuna altra casa di abitazione "
            "nello stesso Comune (lett. b) né altro immobile agevolato sul territorio "
            "nazionale, salvo rivendita entro due anni (lett. c; termine elevato da "
            "uno a due anni dall'art. 1, c. 116, L. 207/2024); categoria non di lusso."
        )
    if regime == "privato":
        warnings.append(
            "Gli atti soggetti a registro proporzionale sono esenti da bollo, tasse "
            "ipotecarie e tributi speciali catastali (art. 10, c. 3, D.Lgs. 23/2011): "
            "restano esclusi dal calcolo solo onorario notarile, oneri condominiali e "
            "di mediazione. Il leasing abitativo prima casa (registro 1,5%, art. 1, "
            "c. 83, L. 208/2015) e i terreni non sono coperti."
        )
    else:
        warnings.append(
            "Restano esclusi: onorario notarile, imposta di bollo (230 euro), tassa "
            "ipotecaria e tributi speciali catastali (90 euro complessivi), oneri "
            "condominiali e di mediazione. Per terreni e immobili strumentali valgono "
            "aliquote diverse."
        )

    return {
        "regime": "Cessione da privato" if regime == "privato" else "Cessione soggetta a IVA",
        "base_imponibile": round(base, 2),
        "prima_casa": "Sì" if prima_casa else "No",
        "dettaglio": dettaglio,
        "totale_imposte": totale,
        "notes": notes,
        "warnings": warnings,
        "sources": [_FONTE_DLGS23, _FONTE_IVA, _FONTE_PREZZO_VALORE],
    }
