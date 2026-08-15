"""Rendimento BOT e pronti contro termine dai dati del contratto.

Base normativa:
- BOT: titoli senza cedola emessi sotto la pari; il rendimento nasce dallo
  scarto di emissione, assoggettato a IMPOSTA SOSTITUTIVA del 12,50%
  applicata in via anticipata alla sottoscrizione (D.Lgs. 239/1996, artt.
  1-3, per l'investitore «nettista»; aliquota agevolata dei titoli
  pubblici ex art. 31 D.P.R. 601/1973, confermata dall'art. 3, c. 2,
  lett. a, D.L. 66/2014). Il calcolo assume prezzo di acquisto pari al
  prezzo di emissione (sottoscrizione in asta): per acquisti sul mercato
  secondario la componente plus/minusvalenza segue il regime dei redditi
  diversi (art. 67, c. 1, lett. c-ter TUIR, base imponibile 48,08% ex
  art. 3, c. 2, lett. b, D.L. 66/2014) qui non gestito.
- Pronti contro termine: il provento (differenza tra prezzo a termine e
  prezzo a pronti) è reddito di capitale ex art. 44, comma 1, lett. g-bis
  TUIR, con ritenuta 26% (art. 3 D.L. 66/2014). I corrispettivi inseriti
  devono essere già depurati degli interessi maturati sul titolo
  sottostante nel periodo (art. 45, c. 1, TUIR), che seguono il regime
  proprio del titolo.

Tutti i dati (prezzi, giorni, commissioni) sono forniti dall'utente dal
contratto o dalla nota di eseguito: il tool non scarica serie di mercato e
non stima prezzi. Convenzione di annualizzazione: anno civile di 365
giorni (i rendimenti lordi d'asta pubblicati dal MEF usano ACT/360 e non
coincidono con questi).
"""
from __future__ import annotations

from typing import Any, Dict, Mapping

from pct.calcolatori._base import safe_float, safe_int

_ALIQUOTA_BOT = 12.5
_ALIQUOTA_PCT = 26.0

_FONTE_DL66 = {
    "code": "dl_66_2014_art3",
    "title": "Art. 3 D.L. 66/2014 — ritenute sui redditi di natura finanziaria",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legge:2014-04-24;66",
}
_FONTE_239 = {
    "code": "dlgs_239_1996",
    "title": "D.Lgs. 239/1996 — regime fiscale dei titoli di Stato",
    "url": "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:1996-04-01;239",
}


def calcola_bot(payload: Mapping[str, Any]) -> Dict[str, Any]:
    prezzo = safe_float(payload.get("bot_prezzo"))
    giorni = safe_int(payload.get("bot_giorni"))
    nominale = safe_float(payload.get("bot_nominale"), 100.0) or 100.0
    commissioni = safe_float(payload.get("bot_commissioni"))

    if prezzo <= 0:
        raise ValueError("Inserisci il prezzo di acquisto (per 100 di nominale).")
    if prezzo >= 110:
        raise ValueError("Prezzo non plausibile per un BOT: verifica la nota di eseguito.")
    if giorni <= 0 or giorni > 400:
        raise ValueError(
            "I giorni alla scadenza devono essere compresi tra 1 e 400 "
            "(i BOT hanno durata massima di dodici mesi)."
        )
    if commissioni < 0:
        raise ValueError("Le commissioni non possono essere negative.")

    scarto = 100.0 - prezzo
    imposta = max(scarto, 0.0) * _ALIQUOTA_BOT / 100.0
    # L'imposta sostitutiva e' applicata in via anticipata alla sottoscrizione
    # (meccanismo del conto unico, art. 3 D.Lgs. 239/1996): entra nell'esborso.
    esborso = prezzo + commissioni + imposta
    guadagno_netto = 100.0 - esborso

    rendimento_periodo = guadagno_netto / esborso * 100.0
    rendimento_annuo = rendimento_periodo * 365.0 / giorni
    rendimento_lordo_annuo = (scarto / prezzo) * 100.0 * 365.0 / giorni

    quota = nominale / 100.0
    return {
        "prezzo_acquisto": round(prezzo, 4),
        "giorni": giorni,
        "scarto_emissione": round(scarto * quota, 2),
        "imposta_sostitutiva": round(imposta * quota, 2),
        "aliquota_imposta": _ALIQUOTA_BOT,
        "esborso_totale": round(esborso * quota, 2),
        "rimborso_a_scadenza": round(100.0 * quota, 2),
        "guadagno_netto": round(guadagno_netto * quota, 2),
        "rendimento_netto_periodo": round(rendimento_periodo, 4),
        "rendimento_netto_annuo": round(rendimento_annuo, 4),
        "rendimento_lordo_annuo": round(rendimento_lordo_annuo, 4),
        "notes": [
            "Imposta sostitutiva 12,50% sullo scarto di emissione, anticipata alla "
            "sottoscrizione ed inclusa nell'esborso (D.Lgs. 239/1996; art. 31 D.P.R. "
            "601/1973; art. 3 D.L. 66/2014). Calcolo per investitore nettista con "
            "prezzo di sottoscrizione in asta; annualizzazione su 365 giorni.",
            "Il rendimento lordo d'asta pubblicato dal MEF usa la convenzione ACT/360 "
            "e non coincide con quello su base 365 qui esposto.",
        ],
        "warnings": [
            "Se il rendimento netto è negativo, l'esborso (prezzo + commissioni + "
            "imposta) supera il rimborso a scadenza: valutare l'incidenza delle "
            "commissioni.",
        ]
        if guadagno_netto < 0
        else [],
        "sources": [_FONTE_239, _FONTE_DL66],
    }


def calcola_pct(payload: Mapping[str, Any]) -> Dict[str, Any]:
    prezzo_pronti = safe_float(payload.get("pct_prezzo_pronti"))
    prezzo_termine = safe_float(payload.get("pct_prezzo_termine"))
    giorni = safe_int(payload.get("pct_giorni"))

    if prezzo_pronti <= 0 or prezzo_termine <= 0:
        raise ValueError("Inserisci prezzo a pronti e prezzo a termine dal contratto.")
    if giorni <= 0 or giorni > 730:
        raise ValueError("La durata deve essere compresa tra 1 e 730 giorni.")

    provento = prezzo_termine - prezzo_pronti
    ritenuta = max(provento, 0.0) * _ALIQUOTA_PCT / 100.0
    provento_netto = provento - ritenuta

    rendimento_lordo_annuo = provento / prezzo_pronti * 100.0 * 365.0 / giorni
    rendimento_netto_annuo = provento_netto / prezzo_pronti * 100.0 * 365.0 / giorni

    return {
        "prezzo_pronti": round(prezzo_pronti, 2),
        "prezzo_termine": round(prezzo_termine, 2),
        "giorni": giorni,
        "provento_lordo": round(provento, 2),
        "ritenuta_fiscale": round(ritenuta, 2),
        "aliquota_ritenuta": _ALIQUOTA_PCT,
        "provento_netto": round(provento_netto, 2),
        "rendimento_lordo_annuo": round(rendimento_lordo_annuo, 4),
        "rendimento_netto_annuo": round(rendimento_netto_annuo, 4),
        "notes": [
            "Provento del pronti contro termine tassato come reddito di capitale al 26% "
            "(art. 44, c. 1, lett. g-bis TUIR; art. 3 D.L. 66/2014).",
            "I prezzi inseriti devono essere già depurati degli interessi maturati sul "
            "titolo sottostante nel periodo (art. 45, c. 1, TUIR): il rateo segue il "
            "regime proprio del titolo (12,5% se titolo di Stato) e non entra in "
            "questa base imponibile.",
        ],
        "warnings": [
            "Provento negativo: il prezzo a termine è inferiore al prezzo a pronti."
        ]
        if provento < 0
        else [],
        "sources": [_FONTE_DL66],
    }
