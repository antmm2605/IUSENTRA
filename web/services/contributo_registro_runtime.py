"""Registro del contributo unificato per la vista economica del fascicolo (regola in `pct.registro_contributo`)."""

from __future__ import annotations

import logging
from threading import Lock
from typing import Any

from pct.registro_contributo import dovuto_del_fascicolo, registro_contributo

logger = logging.getLogger(__name__)
_CALCOLATORE: Any = None
_LOCK = Lock()


def _calcolatore() -> Any:
    """Le tabelle normative si caricano alla prima richiesta, non all'import."""
    global _CALCOLATORE
    if _CALCOLATORE is None:
        with _LOCK:
            if _CALCOLATORE is None:  # pragma: no branch - seconda verifica contro la corsa fra thread
                from pct.strumenti_legali import GestioneStrumentiLegali

                _CALCOLATORE = GestioneStrumentiLegali()
    return _CALCOLATORE


def registro_del_fascicolo(fascicolo: Any) -> dict[str, Any]:
    """Il registro come dizionario; vuoto se non calcolabile (la vista economica non si blocca)."""
    try:
        voce = dict(getattr(fascicolo, "pagamenti", {}) or {}).get("contributo_unificato")
        dovuto, base = dovuto_del_fascicolo(fascicolo, _calcolatore())
        return registro_contributo(voce, dovuto=dovuto, base_dovuto=base).to_dict()
    except Exception as exc:
        logger.warning("Registro del contributo non calcolabile per %s: %s", getattr(fascicolo, "id", ""), exc)
        return {}


__all__ = ["registro_del_fascicolo"]
