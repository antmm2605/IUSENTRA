"""Casella PEC e posta ordinaria nella Panoramica, senza caricare l'intero catalogo.

La Panoramica mostra i 5 messaggi più recenti della posta in arrivo e conta le PEC
da esaminare (non aperte e non prese in carico dal presidio). Caricare e
convertire tutti i messaggi (oltre 2.000 nello studio di produzione) costava
circa 2 secondi a ogni costruzione: con l'archivio SQL bastano gli identificativi
dei non letti (colonna indicizzata) e le righe più recenti.

Con un archivio JSON esplicitamente configurato resta la lettura completa del gestore.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from pct.email_client import CartellaEmail, EmailRicevuta, StatoEmail


def _ordina(emails: list[Any], parse: Callable[[Any], datetime | None]) -> list[Any]:
    return sorted(emails, key=lambda email: parse(getattr(email, "timestamp", "")) or datetime.min, reverse=True)


def quadro_cartella_arrivo(
    db_path: str,
    *,
    crea_casella: Callable[..., Any],
    gestore_completo: Callable[[], Any],
    parse: Callable[[Any], datetime | None],
    limite: int,
) -> tuple[list[EmailRicevuta], set[str]]:
    """(messaggi più recenti in ordine di data, identificativi dei non letti) della posta in arrivo."""
    from pct.email_sql_client import GestioneEmailSQL

    casella = crea_casella(db_path, load_catalog=False, allow_initialize=False)
    if isinstance(casella, GestioneEmailSQL):
        quadro = casella.repository.riepilogo_cartella(CartellaEmail.INBOX, recenti=max(60, limite * 12))
        recenti = [EmailRicevuta.from_dict(record) for record in quadro["recenti"]]
        return _ordina(recenti, parse)[:limite], set(quadro["non_lette"])
    emails = gestore_completo().tutte(cartella=CartellaEmail.INBOX)
    non_lette = {str(getattr(email, "id", "") or "") for email in emails if getattr(email, "stato", "") == StatoEmail.NON_LETTA}
    return _ordina(emails, parse)[:limite], non_lette


__all__ = ["quadro_cartella_arrivo"]
