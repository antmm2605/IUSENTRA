"""Tre stati della consegna. Nessuno significa «atto giuridicamente corretto»: il migliore e' «pronta per la revisione
dell'avvocato», e un filtro automatico superato non cambia questo.

- bozza_incompleta: vuota, requisiti obbligatori del modello d'atto non rilevati, dati mancanti da inserire;
- bozza_con_verifiche_pendenti: errori o dubbi della revisione indipendente, norme o dati mancanti dichiarati,
  pagamenti da imputare, note aperte per l'avvocato;
- pronta_per_revisione_avvocato: nessuno dei motivi sopra.
"""
from __future__ import annotations

import re


def stato(bozza: str, requisiti_mancanti: list[dict], revisione: dict, scheda: dict | None, prospetto_credito: dict | None) -> dict:
    motivi_inc, motivi_pend = [], []
    if len((bozza or "").strip()) < 300:
        motivi_inc.append("bozza vuota o troppo breve")
    motivi_inc += [f"requisito non rilevato: {r['descrizione']} ({r['norma']})" for r in requisiti_mancanti]
    n_mancanti = len(re.findall(r"\[DATO MANCANTE", bozza or "", re.I))
    if n_mancanti:
        motivi_inc.append(f"{n_mancanti} dati da inserire ([DATO MANCANTE])")
    motivi_pend += [f"{t}: {d}" for t, d in revisione.get("gravi", [])]
    motivi_pend += [f"{t}: {d}" for t, d in revisione.get("pendenti", [])]
    if scheda:
        motivi_pend += [f"norma mancante da verificare: {x}" for x in scheda.get("norme_mancanti", [])]
        motivi_pend += [f"dato mancante da acquisire: {x}" for x in scheda.get("dati_mancanti", [])]
    if prospetto_credito:
        motivi_pend += [f"pagamento da imputare: {p}" for p in prospetto_credito.get("pagamenti_da_imputare", [])]
        motivi_pend += [f"voce con residuo negativo: {v}" for v in prospetto_credito.get("voci_negative", [])]
    if motivi_inc:
        s = "bozza_incompleta"
    elif motivi_pend:
        s = "bozza_con_verifiche_pendenti"
    else:
        s = "pronta_per_revisione_avvocato"
    return {"stato": s, "motivi": motivi_inc + motivi_pend, "errori_gravi_revisione": len(revisione.get("gravi", []))}
