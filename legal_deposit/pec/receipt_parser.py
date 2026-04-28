from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class PecReceipt:
    receipt_type: str
    message_id: str = ""
    subject: str = ""
    outcome: str = ""
    error_reason: str = ""


class PecReceiptParser:
    def parse(self, raw_text: str) -> PecReceipt:
        text = str(raw_text or "")
        lower = text.lower()
        subject = _match(r"oggetto:\s*(.+)", text)
        message_id = _match(r"message-id:\s*<?([^>\n]+)>?", text)
        if "accettazione" in lower:
            return PecReceipt("accettazione", message_id=message_id, subject=subject, outcome="ok")
        if "avvenuta consegna" in lower or "consegna" in lower:
            return PecReceipt("consegna", message_id=message_id, subject=subject, outcome="ok")
        if "mancata consegna" in lower:
            return PecReceipt("mancata_consegna", message_id=message_id, subject=subject, outcome="ko", error_reason=text[:300])
        return PecReceipt("sconosciuta", message_id=message_id, subject=subject, outcome="unknown")


def _match(pattern: str, value: str) -> str:
    found = re.search(pattern, value, flags=re.IGNORECASE)
    return found.group(1).strip() if found else ""
