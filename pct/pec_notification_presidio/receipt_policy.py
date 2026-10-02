"""Le ricevute di trasporto sono prove, non nuovi obblighi di notifica.

RAC, RdAC e mancata consegna vengono correlate all'invio dal repository
ricevute. Creare un candidato autonomo moltiplicherebbe lo stesso invio e
scambierebbe anche depositi e PEC ordinarie per notifiche ex legge 53/1994.
"""

from typing import Any, Mapping

RECEIPT_CASES = frozenset({"acceptance_receipt", "delivery_receipt", "delivery_failure"})
RECEIPT_TRIGGERS = frozenset({"RAC", "RDAC", "DELIVERY_FAILURE"})


def is_transport_receipt(payload: Mapping[str, Any]) -> bool:
    return (str(payload.get("notification_case") or "").casefold() in RECEIPT_CASES
            or str(payload.get("trigger_type") or "").upper() in RECEIPT_TRIGGERS)
