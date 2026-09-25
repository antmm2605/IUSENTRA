"""Contributo unificato del ricorso amministrativo (art. 13, commi 6-bis e 6-bis.1, d.P.R. 115/2002).

Collega il tipo di ricorso del modulo SIGA alla categoria del calcolatore già
presente in IUSENTRA (``GestioneStrumentiLegali.calcola_contributo_unificato``):
- lett. a) € 300: accesso (art. 116 c.p.a.), silenzio (art. 117), ottemperanza;
- lett. c) rito abbreviato (art. 119) e lett. d) appalti (art. 120) per valore;
- lett. e) € 650 negli altri casi; aumento della metà per le impugnazioni (6-bis.1).
Ricorsi elettorali e riassunzione sono nelle esenzioni del modulo ufficiale.
Il risultato è una proposta da verificare: la tipologia la sceglie l'avvocato.
"""

from __future__ import annotations

from typing import Any, Callable

TAR_CATEGORIA = {
    "85": "amministrativo_accesso_soggiorno_cittadinanza", "86": "amministrativo_accesso_soggiorno_cittadinanza",
    "4": "amministrativo_ottemperanza", "83": "amministrativo_rito_abbreviato", "95": "amministrativo_appalti",
}
CDS_CATEGORIA = {
    "Y4": "amministrativo_accesso_soggiorno_cittadinanza", "Y6": "amministrativo_accesso_soggiorno_cittadinanza",
    "Y2": "amministrativo_ottemperanza", "ZI": "amministrativo_ottemperanza", "YB": "amministrativo_ottemperanza",
    "YC": "amministrativo_ottemperanza", "ZO": "amministrativo_ottemperanza", "Y3": "amministrativo_rito_abbreviato",
    "YE": "amministrativo_rito_abbreviato", "Y5": "amministrativo_appalti",
}
ESENTI_TAR = {"96": "RICORSI ELETTORALI", "97": "RICORSI ELETTORALI", "92": "RIASSUNZIONE"}
ESENTI_CDS = {"ZM": "RICORSI IN MATERIA ELETTORALE", "ZN": "RICORSI IN MATERIA ELETTORALE"}


def proposta(tipo_ricorso: str, appello: bool, valore: float | None,
             calcola: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """{importo, categoria, esenzione, nota} per il tipo di ricorso indicato."""
    esenzione = (ESENTI_CDS if appello else ESENTI_TAR).get(tipo_ricorso, "")
    if esenzione:
        return {"importo": 0.0, "categoria": "", "esenzione": esenzione,
                "nota": f"Esente secondo il modulo ufficiale: «{esenzione}»."}
    if not tipo_ricorso:
        return {"importo": None, "categoria": "", "esenzione": "", "nota": "Indica il tipo di ricorso per il calcolo."}
    categoria = (CDS_CATEGORIA if appello else TAR_CATEGORIA).get(tipo_ricorso, "amministrativo_ordinario")
    dati: dict[str, Any] = {"cu_categoria": categoria, "cu_grado": "appello" if appello else "primo_grado"}
    if categoria == "amministrativo_appalti":
        dati.update({"cu_valore": valore or 0, "cu_valore_tipo": "determinato" if valore else "non_indicato"})
    esito = calcola(dati)
    importo = float(esito.get("totale") or esito.get("base") or 0)
    note = "; ".join(str(n) for n in esito.get("notes") or [])
    return {"importo": importo, "categoria": categoria, "esenzione": "",
            "nota": f"Art. 13 c. 6-bis d.P.R. 115/2002. {note}".strip()}


__all__ = ["proposta"]
