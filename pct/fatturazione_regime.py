"""Parametri fiscali di proforma e fatture secondo il regime fiscale dello studio.

Basi normative:
- regime ordinario (RF01): la prestazione professionale è soggetta a IVA (artt. 3 e 16
  D.P.R. 633/1972); quando paga un sostituto d'imposta (art. 23, primo comma, D.P.R. 600/1973:
  amministrazioni dello Stato, enti pubblici, società, enti, condomìni) si opera la ritenuta
  d'acconto del 20% (art. 25, comma 1, D.P.R. 600/1973). Il compenso liquidato in sentenza con
  distrazione (art. 93 c.p.c.) e pagato dalla PA soccombente sconta la ritenuta del sostituto
  (Ris. AdE 35/E del 15/03/2019);
- regime forfetario (RF19): niente IVA (art. 1, comma 58, L. 190/2014) e niente ritenuta
  (art. 1, comma 67, L. 190/2014);
- regime dei minimi (RF02): niente IVA né ritenuta (art. 27, commi 1 e 5, D.L. 98/2011);
- imposta di bollo di € 2 sulle fatture (anche note di variazione e proforma, da applicare in
  fattura) quando la parte non soggetta a IVA supera € 77,47 (art. 13, comma 1, Tariffa parte I,
  all. A, D.P.R. 642/1972; art. 6 D.M. 17/06/2014 per le fatture elettroniche). Non è dovuta sulla
  parte assoggettata a IVA (art. 6 Tabella all. B D.P.R. 642/1972): nelle fatture miste conta solo
  la parte senza IVA. Rientrano nella parte senza IVA le operazioni con natura N2.x, N3.x, N4
  (forfetario RF19, minimi RF02, non soggette, non imponibili, esenti) e le anticipazioni in nome e
  per conto del cliente escluse ex art. 15 D.P.R. 633/1972 (Risposta AdE n. 491 del 20/07/2021:
  l'esenzione delle operazioni IVA non copre le somme anticipate). Esclusioni registrate solo con
  fonte (Guida AdE «L'imposta di bollo sulle fatture elettroniche», ed. 2024, elenco B): codici NB1
  (documento assicurativo), NB2 (ente del terzo settore), NB3 (banca e cliente correntista) e i tipi
  documento TD16, TD17, TD18, TD19, TD28.
"""
from __future__ import annotations

import re
from typing import Any

REGIMI = frozenset({"RF01", "RF02", "RF19"})
REGIMI_SENZA_IVA_NE_RITENUTA = frozenset({"RF02", "RF19"})
SOGLIA_BOLLO = 77.47
IMPORTO_BOLLO = 2.00

# Denominazioni tipiche dei sostituti d'imposta pubblici (art. 23, primo comma, D.P.R. 600/1973).
_PA_RE = re.compile(
    r"\b(?:ministero|ministro|mim|miur|mef|presidenza\s+del\s+consiglio|agenzia\s+delle\s+entrate|"
    r"inps|inail|regione|provincia|citt[aà]\s+metropolitana|comune\s+di|azienda\s+sanitaria|"
    r"asl|asp|ausl|azienda\s+ospedaliera|universit[aà]|istituto\s+comprensivo|liceo|"
    r"ufficio\s+scolastico|amministrazione|prefettura|questura|avvocatura\s+dello\s+stato)\b",
    re.IGNORECASE,
)


def regime_normalizzato(regime: Any) -> str:
    valore = str(regime or "").strip().upper()
    return valore if valore in REGIMI else ""


def e_sostituto_imposta(nome: Any = "", codice_fiscale: Any = "") -> bool:
    """Vero per PA riconoscibili dal nome o per soggetti non persone fisiche (CF numerico di 11 cifre)."""
    cf = re.sub(r"\s+", "", str(codice_fiscale or ""))
    if re.fullmatch(r"\d{11}", cf):
        return True
    return bool(_PA_RE.search(str(nome or "")))


def parametri_fiscali(regime: Any, *, pagatore_sostituto: bool) -> dict[str, Any]:
    """IVA e ritenuta per il regime dello studio; regime ignoto = ordinario (default della configurazione)."""
    codice = regime_normalizzato(regime) or "RF01"
    senza = codice in REGIMI_SENZA_IVA_NE_RITENUTA
    return {
        "regime_fiscale": codice,
        "applica_iva": not senza,
        "applica_ritenuta": (not senza) and bool(pagatore_sostituto),
    }


# Esclusioni con fonte: Guida AdE «L'imposta di bollo sulle fatture elettroniche» (2024), elenco B.
ESCLUSIONI_BOLLO = {
    "NB1": "Documento assicurativo: bollo assorbito nell'imposta sulle assicurazioni (Guida AdE 2024, elenco B)",
    "NB2": "Documento emesso da ente del terzo settore (Guida AdE 2024, elenco B)",
    "NB3": "Documento tra banca e cliente correntista: bollo assorbito nell'estratto conto (Guida AdE 2024, elenco B)",
}
TIPI_DOCUMENTO_ESCLUSI = frozenset({"TD16", "TD17", "TD18", "TD19", "TD28"})


def importo_non_soggetto_iva(*, iva_applicabile: bool, base_iva: float, anticipazioni: float) -> float:
    """Parte del documento senza IVA: base (se l'IVA non si applica) più anticipazioni art. 15."""
    parte = (0.0 if iva_applicabile else float(base_iva or 0.0)) + float(anticipazioni or 0.0)
    return round(parte, 2)


def esclusione_bollo(document: Any) -> str:
    """Motivo dell'esclusione registrata sul documento (solo esclusioni con fonte), altrimenti ""."""
    if not isinstance(document, dict):
        return ""
    codice = str(document.get("esclusione_bollo") or "").strip().upper()
    if codice in ESCLUSIONI_BOLLO:
        return ESCLUSIONI_BOLLO[codice]
    tipo = str(document.get("tipo_documento") or "").strip().upper()
    if tipo in TIPI_DOCUMENTO_ESCLUSI:
        return f"Tipo documento {tipo} escluso dal bollo (Guida AdE 2024, elenco B)"
    return ""


def bollo_dovuto(*, iva_applicabile: bool, importo_non_soggetto: float, esclusione: str = "") -> bool:
    """Bollo di € 2 dovuto quando la parte non soggetta a IVA supera € 77,47, salvo esclusione con fonte.

    ``importo_non_soggetto`` è già la sola parte senza IVA: ``iva_applicabile`` resta per compatibilità.
    """
    del iva_applicabile
    if esclusione:
        return False
    return round(float(importo_non_soggetto or 0.0), 2) > SOGLIA_BOLLO


def scelta_bollo(inviato: Any, attuale: Any = None) -> bool | None:
    """Valore da salvare dal modulo: spunta = bollo esplicito; senza spunta vale la legge (None).

    Il bollo dovuto non è facoltativo (art. 13 Tariffa all. A D.P.R. 642/1972): togliere la spunta
    non lo elimina. Resta prevalente solo un «no» già salvato in modo esplicito sul documento;
    chi non vuole addebitarlo al cliente usa «bollo a carico dello studio».
    """
    if inviato is True:
        return True
    return False if attuale is False else None


__all__ = ["ESCLUSIONI_BOLLO", "IMPORTO_BOLLO", "REGIMI", "SOGLIA_BOLLO", "TIPI_DOCUMENTO_ESCLUSI",
           "bollo_dovuto", "e_sostituto_imposta", "esclusione_bollo", "importo_non_soggetto_iva",
           "scelta_bollo",
           "parametri_fiscali", "regime_normalizzato"]
