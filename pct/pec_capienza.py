"""Capienza della casella PEC dello studio (IMAP QUOTA, RFC 2087).

Base normativa: art. 20 D.M. 44/2011 impone al soggetto abilitato esterno
una casella con spazio adeguato e avvisi di saturazione; art. 16 co. 6
D.L. 179/2012: se la PEC al difensore non è consegnata per causa a lui
imputabile (casella piena), la notificazione si perfeziona con il deposito
in cancelleria e il PST pubblica solo un avviso. Una casella piena fa
perdere notifiche valide: qui si misura quanto spazio resta.
"""

from __future__ import annotations

import imaplib
import re
from typing import Any

SOGLIA_ATTENZIONE = 80
SOGLIA_CRITICA = 95
_QUOTA = re.compile(r"STORAGE\s+(\d+)\s+(\d+)", re.I)


def leggi_capienza(host: str, porta: int, utente: str, password: str, *, ssl: bool = True, timeout: float = 15) -> dict[str, Any]:
    """Spazio usato e disponibile della casella; ``supportata`` è False se il server non espone QUOTA."""
    classe = imaplib.IMAP4_SSL if ssl else imaplib.IMAP4
    connessione = classe(host, int(porta or (993 if ssl else 143)), timeout=timeout)
    try:
        connessione.login(utente, password)
        if "QUOTA" not in [str(c).upper() for c in connessione.capabilities]:
            return {"supportata": False}
        esito, dati = connessione.getquotaroot("INBOX")
        if esito != "OK":
            return {"supportata": False}
        testo = " ".join(
            (d.decode("utf-8", "replace") if isinstance(d, bytes) else str(d))
            for gruppo in dati for d in (gruppo if isinstance(gruppo, list) else [gruppo])
        )
        return valuta(testo)
    finally:
        try:
            connessione.logout()
        except Exception:
            pass


def valuta(risposta_quota: str) -> dict[str, Any]:
    """Interpreta la risposta QUOTA (valori in KiB) e classifica il rischio."""
    trovata = _QUOTA.search(str(risposta_quota or ""))
    if not trovata:
        return {"supportata": False}
    usati, limite = int(trovata.group(1)), int(trovata.group(2))
    percentuale = round(100 * usati / limite, 1) if limite else 0.0
    livello = "critico" if percentuale >= SOGLIA_CRITICA else ("attenzione" if percentuale >= SOGLIA_ATTENZIONE else "ok")
    return {"supportata": True, "usatiKb": usati, "limiteKb": limite, "percentuale": percentuale, "livello": livello}


__all__ = ["SOGLIA_ATTENZIONE", "SOGLIA_CRITICA", "leggi_capienza", "valuta"]
