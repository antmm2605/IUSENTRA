"""La sintesi degli obblighi di notifica già calcolati, conservata per il quadro del fascicolo.

Calcolare gli obblighi di notifica costa secondi (fatti dell'archivio, catalogo, verifiche per atto): il quadro
del fascicolo deve rispondere in meno di un secondo e non può ricalcolarli nella richiesta. La sintesi si salva
quando il calcolo avviene comunque (giro in sfondo della lettura del fascicolo, apertura degli obblighi di notifica)
nella cache dei payload del registro delle letture, la stessa della Lettura: ``invalida_lettura`` la cancella
quando cambiano documenti o PEC, e il giro successivo la ricrea. Senza sintesi il quadro lo dice, senza inventare.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

logger = logging.getLogger(__name__)

CHIAVE = "obblighi-notifica-sintesi:v1"
DURATA = timedelta(days=30)


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split())


def compatta(obblighi: Iterable[Mapping[str, Any]]) -> list[dict[str, str]]:
    """Per ogni atto: etichetta, stato dell'obbligo e scadenza (ISO); nient'altro esce dal calcolo."""
    return [{"atto": _testo(o.get("etichetta") or o.get("atti") or o.get("documento")), "stato": _testo(o.get("stato")),
             "scadenza": _testo(o.get("scadenza"))[:10]} for o in obblighi if _testo(o.get("etichetta") or o.get("atti"))]


def salva(fascicolo_id: str, obblighi: Iterable[Mapping[str, Any]]) -> None:
    try:
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        scade = (datetime.now(timezone.utc) + DURATA).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        payload = json.dumps({"obblighi": compatta(obblighi),
                              "calcolata_il": datetime.now(timezone.utc).replace(microsecond=0).isoformat()}, ensure_ascii=False)
        registro_corrente().payload_cache_set(tenant_corrente(), _testo(fascicolo_id), CHIAVE, payload, expires_at=scade)
    except Exception as exc:  # la sintesi è un'accelerazione: il calcolo resta valido anche senza
        logger.debug("Sintesi degli obblighi di notifica non salvata per %s: %s", fascicolo_id, exc)


def leggi(fascicolo_id: str) -> dict[str, Any] | None:
    try:
        from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

        grezzo = registro_corrente().payload_cache_get(tenant_corrente(), _testo(fascicolo_id), CHIAVE)
        return json.loads(grezzo) if grezzo else None
    except Exception as exc:
        logger.debug("Sintesi degli obblighi di notifica non leggibile per %s: %s", fascicolo_id, exc)
        return None


__all__ = ["CHIAVE", "compatta", "leggi", "salva"]
