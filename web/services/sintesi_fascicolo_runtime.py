"""Aggiornamento e lettura della riga di sintesi del fascicolo nel registro delle letture.

La riga si riscrive alla fine di ogni giro di lettura del fascicolo e, quando il giro trova il fascicolo fermo,
solo se l'identità (stato, date, cliente, ufficio, prossima udienza) è cambiata. Non legge file né PEC: usa
il fascicolo già caricato e il registro. Un guasto qui non ferma mai la lettura.
"""

from __future__ import annotations

import logging
from typing import Any

from pct.registro_letture import RegistroLetture
from pct.registro_letture.identita import identita_fascicolo
from pct.registro_letture.sintesi import identita_cambiata
from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

logger = logging.getLogger(__name__)


def _oggi():
    from pct.archivio_letture.presidi import oggi_roma

    return oggi_roma()


def aggiorna_sintesi_fascicolo(fascicolo: Any, *, registro: RegistroLetture | None = None, solo_se_cambiata: bool = False) -> dict[str, Any] | None:
    fascicolo_id = str(getattr(fascicolo, "id", "") or "").strip()
    if not fascicolo_id:
        return None
    try:
        registro = registro or registro_corrente()
        tenant = tenant_corrente()
        identita = identita_fascicolo(fascicolo, oggi=_oggi())
        if solo_se_cambiata and not identita_cambiata(registro.sintesi(tenant, fascicolo_id), identita):
            return None
        return registro.aggiorna_sintesi(tenant, fascicolo_id, identita)
    except Exception as exc:
        logger.warning("Riga di sintesi non aggiornata per il fascicolo %s: %s", fascicolo_id, exc)
        return None


def sintesi_fascicolo(fascicolo_id: str) -> dict[str, Any] | None:
    try:
        return registro_corrente().sintesi(tenant_corrente(), fascicolo_id)
    except Exception as exc:
        logger.warning("Riga di sintesi non leggibile per il fascicolo %s: %s", fascicolo_id, exc)
        return None


__all__ = ["aggiorna_sintesi_fascicolo", "sintesi_fascicolo"]
