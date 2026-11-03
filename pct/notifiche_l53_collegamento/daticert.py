"""Il destinatario di una ricevuta PEC dai dati di certificazione (daticert.xml, art. 6 D.P.R. 68/2005).

Nessun ``from __future__``: il file si concatena allo script di sola lettura del server (deploy/hetzner).
"""

import re
from email import message_from_bytes, policy

_CONSEGNA = re.compile(r"<consegna>\s*([^<\s]+@[^<\s]+)\s*</consegna>", re.IGNORECASE)
_CERTIFICATI = re.compile(r"<destinatari\s+tipo=\"certificato\"\s*>\s*([^<\s]+@[^<\s]+)\s*</destinatari>", re.IGNORECASE)


def daticert_dal_messaggio(mime: bytes) -> str:
    """Il testo del daticert.xml contenuto nella ricevuta, o stringa vuota."""
    try:
        messaggio = message_from_bytes(bytes(mime or b""), policy=policy.compat32)
    except Exception:  # noqa: BLE001 - MIME illeggibile: nessun destinatario
        return ""
    for parte in messaggio.walk():
        nome = str(parte.get_filename() or "").casefold()
        if nome.endswith("daticert.xml"):
            corpo = parte.get_payload(decode=True) or b""
            return corpo.decode("utf-8", errors="replace")
    return ""


def destinatario_da_daticert(xml: str) -> str:
    """L'indirizzo di consegna; in mancanza l'unico destinatario certificato. Mai una scelta fra più indirizzi."""
    consegna = {m.strip().casefold() for m in _CONSEGNA.findall(xml or "")}
    if len(consegna) == 1:
        return next(iter(consegna))
    certificati = {m.strip().casefold() for m in _CERTIFICATI.findall(xml or "")}
    return next(iter(certificati)) if len(certificati) == 1 and not consegna else ""
