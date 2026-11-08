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
- imposta di bollo di € 2 sulle fatture per somme non soggette a IVA superiori a € 77,47
  (art. 13, comma 1, Tariffa parte I, all. A, D.P.R. 642/1972; art. 6 D.M. 17/06/2014 per le
  fatture elettroniche; elenco B delle fatture da integrare dell'Agenzia delle Entrate: nature
  N2.1, N2.2, N3.5, N3.6, N4; le anticipazioni N1, art. 15 D.P.R. 633/1972, non contano).
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


def bollo_dovuto(*, iva_applicabile: bool, importo_non_soggetto: float) -> bool:
    """Bollo di € 2 dovuto sulle somme non soggette a IVA oltre € 77,47."""
    return (not iva_applicabile) and round(float(importo_non_soggetto or 0.0), 2) > SOGLIA_BOLLO


__all__ = ["IMPORTO_BOLLO", "REGIMI", "SOGLIA_BOLLO", "bollo_dovuto", "e_sostituto_imposta",
           "parametri_fiscali", "regime_normalizzato"]
