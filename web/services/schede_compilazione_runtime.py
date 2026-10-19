"""Collega le schede di compilazione ai dati del fascicolo per la redazione guidata.

Legge solo dati già presenti: i valori della precompilazione, i fatti dell'archivio delle letture
(nessuna lettura di documenti in questa richiesta, vedi CLAUDE.md «Registro delle letture») e i nomi
dei documenti del fascicolo. Base normativa: le norme dichiarate in ciascuna scheda.
"""
from __future__ import annotations

import logging
from typing import Any

from pct.schede_compilazione import risolvi_scheda, scheda_per_modello

logger = logging.getLogger(__name__)


def compilazione_per_modello(model_code: str, valori: dict[str, Any], fascicolo: Any) -> dict[str, Any] | None:
    """Stato dei campi e domande per l'avvocato, oppure None se il modello non ha una scheda."""
    scheda = scheda_per_modello(model_code)
    if scheda is None:
        return None
    try:
        from web.services.archivio_letture_runtime import fatti_fascicolo

        fatti = fatti_fascicolo(fascicolo) if fascicolo is not None else []
    except Exception:
        logger.warning("Fatti letti non disponibili per la scheda %s: si usano solo i dati del gestionale", scheda["id"])
        fatti = []
    documenti = [str(getattr(doc, "nome", "") or "") for doc in (getattr(fascicolo, "documenti", None) or [])]
    return risolvi_scheda(scheda, valori, fatti=fatti, documenti=documenti)
