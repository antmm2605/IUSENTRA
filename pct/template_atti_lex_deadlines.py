"""Scadenze delle schede nella risposta Lex, senza modificare bozze o fonti."""
from __future__ import annotations

import logging
from contextlib import nullcontext
from typing import Any

from pct.schede_compilazione import risolvi_scheda, scheda_per_modello
from pct.schede_lex import blocco_scadenze, ripara_risposta, scadenze_calcolate

logger = logging.getLogger(__name__)


def completa_scadenze(
    risposta: str, model_code: str, valori: dict[str, Any], fascicolo: Any, *, messaggio: str = "",
) -> tuple[str, dict[str, Any]]:
    """Legge soltanto i fatti SQL del fascicolo già autorizzato dal chiamante.

    Il modello e i valori provengono dal compilatore; la richiesta della chat
    non può fornire una scheda risolta o sostituire una data nell'archivio.
    """
    scheda = scheda_per_modello(model_code)
    if not scheda or not any(c.get("fonte", {}).get("termine") for c in scheda["campi"]):
        return risposta, {}
    try:
        from flask import has_request_context

        from web.services.archivio_letture_runtime import fatti_fascicolo
        from web.services.registro_letture_runtime import registro_consultivo

        with registro_consultivo() if has_request_context() else nullcontext():
            fatti = fatti_fascicolo(fascicolo)
        risolta = risolvi_scheda(scheda, valori, fatti=fatti)
    except Exception:
        logger.exception("Scadenze Lex non disponibili per il modello %s", model_code)
        return (risposta + "\n\nNon è stato possibile verificare le scadenze nell'archivio delle letture.",
                {"stato": "non_disponibile", "scheda": scheda["id"], "scadenze": []})
    scadenze = scadenze_calcolate(risolta)
    if not scadenze:
        return (risposta + "\n\nScadenza non calcolata: manca una data di partenza univoca nei fatti già letti.",
                {"stato": "dati_insufficienti", "scheda": scheda["id"], "scadenze": []})
    # Anche le date di partenza dimostrate dal calcolatore sono dati noti.
    dati_noti = [str(getattr(fascicolo, "titolo", "") or "")]
    dati_noti.extend(str(v) for v in valori.values() if isinstance(v, (str, int, float)))
    note = "\n".join([messaggio, *dati_noti, *(s["spiegazione"] for s in scadenze)])
    risposta = ripara_risposta(risposta, risolta, note)
    # Se le date erano già presenti, resta comunque visibile l'incertezza della fonte.
    if any(s["verifica_avvocato"] for s in scadenze) and "non presentarlo come confermato" not in risposta:
        risposta += "\n\n" + blocco_scadenze(risolta)
    from pct.schede_termini import fatti_base

    fonti = {}
    for campo in scheda["campi"]:
        termine = campo.get("fonte", {}).get("termine")
        if termine:
            for fatto in fatti_base(termine, fatti):
                key = (fatto.id, fatto.oggetto_id, fatto.sha256)
                fonti[key] = {k: getattr(fatto, k) for k in ("id", "tipo", "oggetto_id", "sha256", "verifica")}
    return risposta, {"stato": "calcolato", "scheda": scheda["id"], "scadenze": scadenze,
                      "fonti": list(fonti.values())}
