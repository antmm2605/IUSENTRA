"""Quale regola del contributo unificato vale per ogni tipologia del preventivo.

Il preventivo non usa importi fissi per il contributo: lo calcola con il calcolatore
dell'art. 13 D.P.R. 115/2002 (`pct.strumenti_legali.GestioneStrumentiLegali`) dal valore
della causa e dal grado. Qui si dichiara, per ogni tipologia del catalogo preventivi, la
categoria e il grado del calcolatore:

- art. 13, comma 1: scaglioni per valore (civile ordinario); comma 3: metà per decreto
  ingiuntivo e controversie di lavoro; comma 1-bis: +50% per l'impugnazione, doppio in
  Cassazione; comma 1-bis, ultimo periodo: doppio per la sezione specializzata in materia
  di impresa (D.Lgs. 168/2003, art. 3); comma 2: opposizione agli atti esecutivi;
- art. 13, comma 6-bis: processo amministrativo (lettera a: accesso, silenzio, soggiorno e
  cittadinanza; lettera d: contratti pubblici per valore; ordinario negli altri casi);
- art. 13, comma 6-quater: processo tributario per valore; in Cassazione la misura civile.

Le tipologie con esenzioni o importi che dipendono da dati non presenti nel preventivo
(famiglia, minori, concorsuale, ottemperanza con risarcitoria, appello tributario) non sono
mappate: resta la voce indicativa del catalogo, da verificare.
"""

from __future__ import annotations

from typing import Any

# tipologia → (categoria del calcolatore, grado fisso o "" per usare il grado scelto, sezione impresa)
_REGOLE: dict[str, tuple[str, str, bool]] = {
    "atto_citazione": ("civile_ordinario", "", False),
    "comparsa_risposta": ("civile_ordinario", "", False),
    "risarcimento_danni": ("civile_ordinario", "", False),
    "opposizione_di": ("civile_ordinario", "", False),
    "decreto_ingiuntivo": ("decreto_ingiuntivo", "primo_grado", False),
    "appello_civile": ("civile_ordinario", "appello", False),
    "cassazione_civile": ("civile_ordinario", "cassazione", False),
    "contenzioso_societario": ("civile_ordinario", "", True),
    "responsabilita_organi_sociali": ("civile_ordinario", "", True),
    "controversia_lavoro": ("lavoro", "primo_grado", False),
    "licenziamento": ("lavoro", "primo_grado", False),
    "differenze_retributive": ("lavoro", "primo_grado", False),
    "appello_lavoro": ("lavoro", "appello", False),
    "opposizione_atti_esecutivi": ("opposizione_atti_esecutivi", "primo_grado", False),
    "ricorso_tributario": ("tributario", "primo_grado", False),
    "contenzioso_doganale": ("tributario", "primo_grado", False),
    "cassazione_tributaria": ("tributario", "cassazione", False),
    "ricorso_tar": ("amministrativo_ordinario", "primo_grado", False),
    "motivi_aggiunti": ("amministrativo_ordinario", "primo_grado", False),
    "cautelare_sospensiva": ("amministrativo_ordinario", "primo_grado", False),
    "espropriazione_pu": ("amministrativo_ordinario", "primo_grado", False),
    "appello_cds": ("amministrativo_ordinario", "appello", False),
    "accesso_atti": ("amministrativo_accesso_soggiorno_cittadinanza", "primo_grado", False),
    "silenzio_inadempimento": ("amministrativo_accesso_soggiorno_cittadinanza", "primo_grado", False),
    "appalti_contratti_pubblici": ("amministrativo_appalti", "primo_grado", False),
}


def grado_dal_testo(etichetta: str) -> str:
    testo = str(etichetta or "").casefold()
    if "cassazione" in testo:
        return "cassazione"
    if "appello" in testo or "consiglio di stato" in testo or "secondo grado" in testo:
        return "appello"
    return "primo_grado"


def parametri_contributo(tipologia: str, *, valore: float, grado_scelto: str = "") -> dict[str, Any] | None:
    """I parametri del calcolatore per la tipologia; None se il contributo non si calcola in automatico."""
    regola = _REGOLE.get(str(tipologia or ""))
    if regola is None:
        return None
    categoria, grado, impresa = regola
    return {
        "cu_categoria": categoria,
        "cu_grado": grado or grado_dal_testo(grado_scelto),
        "cu_valore": valore,
        "cu_valore_tipo": "determinato" if valore > 0 else "indeterminabile",
        "cu_sezione_specializzata_impresa": impresa,
    }


def contributo_per_preventivo(calcolatore: Any, tipologia: str, *, valore: float, grado_scelto: str = "") -> float | None:
    parametri = parametri_contributo(tipologia, valore=valore, grado_scelto=grado_scelto)
    if parametri is None:
        return None
    return round(float(calcolatore.calcola_contributo_unificato(parametri).get("base") or 0.0), 2)


__all__ = ["contributo_per_preventivo", "grado_dal_testo", "parametri_contributo"]
