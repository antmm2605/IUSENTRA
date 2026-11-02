"""«Da PEC del gg/mm/aaaa»: la provenienza di un documento entrato nel fascicolo da una PEC collegata.

Legge solo i metadati del documento (etichette ``iusentra:pec:`` / ``iusentra:pec-data:`` scritte dal flusso
PEC → documenti, oppure la fonte PEC con il riferimento interno del messaggio per i documenti salvati prima):
nessuna lettura del presidio nella richiesta. Il link apre la PEC nella casella (``/email/?audit_id=``).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from pct.pec_fascicolo_documenti.salvataggio import ETICHETTA_DATA, ETICHETTA_PEC

FONTI_PEC = frozenset({"PEC_FASCICOLO", "PEC_CANCELLERIA", "PEC_NOTIFICA", "PEC_AUDIT_NOTIFICATION_RECEIPT", "PEC_AUDIT_PIPELINE"})


def _etichetta(tags: list[Any], prefisso: str) -> str:
    return next((str(tag)[len(prefisso):].strip() for tag in tags if str(tag).startswith(prefisso)), "")


def origine_pec(doc: Any) -> dict[str, str] | None:
    tags = list(getattr(doc, "tags", []) or [])
    message_id = _etichetta(tags, ETICHETTA_PEC)
    giorno = _etichetta(tags, ETICHETTA_DATA)
    fonte = str(getattr(doc, "fonte_documento", "") or "").strip().upper()
    if not message_id and fonte in FONTI_PEC:
        message_id = str(getattr(doc, "msg_id_portale", "") or "").split("#", 1)[0].strip()
        giorno = giorno or str(getattr(doc, "data_documento", "") or "")[:10]
    if not message_id:
        return None
    parti = giorno.split("-")
    data = f"{parti[2]}/{parti[1]}/{parti[0]}" if len(parti) == 3 and all(p.isdigit() for p in parti) else ""
    return {"label": f"da PEC del {data}" if data else "da PEC", "href": f"/email/?audit_id={quote(message_id, safe='')}"}


__all__ = ["FONTI_PEC", "origine_pec"]
