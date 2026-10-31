"""Stato operativo di una scadenza: una sola regola per scadenziario, viste e barra in alto.

Verifica del 31/10/2026 (V28): le «scadute da chiudere» erano quasi tutte udienze già
passate, e tre conteggi diversi (scadenziario, viste, barra in alto) davano numeri
diversi. Un'udienza non è un adempimento che scade: è un evento che si è tenuto (o è
stato rinviato) e di cui va registrato l'esito dal verbale o dal provvedimento
successivo (artt. 126 e 127-ter c.p.c.). Per questo un'udienza passata e ancora
aperta è «esito da registrare», non «scaduta»; gli adempimenti passati restano
«scaduti da chiudere». Nessuna voce si chiude da sola: decide l'avvocato.

Il giorno di riferimento è quello di Roma (``pct.ora_italiana.oggi_roma``).
"""
from __future__ import annotations

from datetime import date
from typing import Any

BOZZA = "bozza"
ANNULLATA = "annullata"
COMPLETATA = "completata"
APERTA = "aperta"
SCADUTA = "scaduta"
ESITO_UDIENZA = "esito_udienza"


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def _giorno(scadenza: Any) -> date | None:
    calendario = getattr(scadenza, "data_calendario_obj", None)
    if isinstance(calendario, date):
        return calendario
    try:
        return date.fromisoformat(_valore(scadenza, "data_scadenza")[:10])
    except ValueError:
        return None


def stato_operativo(scadenza: Any, oggi: date | None = None) -> str:
    stato = _valore(scadenza, "stato").upper()
    if stato == "BOZZA":
        return BOZZA
    if stato == "ANNULLATO":
        return ANNULLATA
    if stato == "COMPLETATO":
        return COMPLETATA
    if oggi is None:
        from pct.ora_italiana import oggi_roma

        oggi = oggi_roma()
    giorno = _giorno(scadenza)
    passata = stato == "SCADUTO" or bool(giorno and giorno < oggi)
    if not passata:
        return APERTA
    return ESITO_UDIENZA if _valore(scadenza, "tipo").upper() == "UDIENZA" else SCADUTA


def scaduta_da_chiudere(scadenza: Any, oggi: date | None = None) -> bool:
    return stato_operativo(scadenza, oggi) == SCADUTA


def esito_udienza_da_registrare(scadenza: Any, oggi: date | None = None) -> bool:
    return stato_operativo(scadenza, oggi) == ESITO_UDIENZA


def aperta(scadenza: Any, oggi: date | None = None) -> bool:
    return stato_operativo(scadenza, oggi) == APERTA


__all__ = [
    "ANNULLATA", "APERTA", "BOZZA", "COMPLETATA", "ESITO_UDIENZA", "SCADUTA",
    "aperta", "esito_udienza_da_registrare", "scaduta_da_chiudere", "stato_operativo",
]
