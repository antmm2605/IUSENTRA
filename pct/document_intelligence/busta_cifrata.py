"""Busta telematica cifrata per l'ufficio: lettura «non applicabile», mai errore.

La busta del deposito telematico (``Atto.enc``) è crittografata con la chiave
pubblica dell'ufficio giudiziario destinatario: nessuno studio può decifrarla e
gli atti in chiaro sono già nel fascicolo come documenti separati. Un allegato
``.enc`` dentro un messaggio o una PEC non rende quindi incompleta la lettura
del messaggio, e un documento che sia soltanto la busta non è un errore
dell'indice: è un oggetto che la legge rende illeggibile a chi non è l'ufficio.

Qui vive la sola regola che lo riconosce, usata dall'estrazione (allegato e
documento), dal riepilogo dell'indice Lex e dalla riconvalida degli esiti già
salvati con quella causa da versioni precedenti.

Base normativa: D.M. 44/2011 art. 14 (struttura e trasmissione della busta
telematica); Specifiche tecniche DGSIA (provv. 16/04/2014 e successive
modifiche, art. 14: busta crittografata con la chiave pubblica dell'ufficio
destinatario).
"""
from __future__ import annotations

import re
from typing import Any, Iterable

CODICE_BUSTA_CIFRATA = "busta_cifrata_ufficio"
NOTA_BUSTA_CIFRATA = "Busta cifrata per l'ufficio: non leggibile per legge, atti in chiaro nel fascicolo."

# Le cause storiche salvate da versioni precedenti nominano la busta o Atto.enc
# («Lettura del messaggio incompleta: Atto.enc: Busta cifrata destinata
# all'ufficio giudiziario…»). Un documento cifrato a riposo senza chiave
# («Documento cifrato non decifrabile») è un vero errore e non corrisponde.
_CAUSA_BUSTA = re.compile(r"\batto\.enc\b|\bbusta\s+(?:telematica\s+|cms\s+)?cifrata\b", re.IGNORECASE)
_CODICI_MAI_BUSTA = frozenset({"encrypted_document", "source_unavailable", "source_access_denied"})


def e_busta_cifrata(nome: str) -> bool:
    """Il nome è quello di una busta telematica cifrata (anche con il suffisso .bin dell'archivio)."""
    pulito = str(nome or "").strip().lower()
    if pulito.endswith(".bin"):
        pulito = pulito[:-4]
    return pulito.endswith(".enc")


def causa_busta_cifrata(error_code: Any, message: Any) -> bool:
    """L'esito salvato fallisce solo per la busta cifrata: va trattato come non applicabile."""
    codice = str(error_code or "").strip()
    if codice == CODICE_BUSTA_CIFRATA:
        return True
    if codice in _CODICI_MAI_BUSTA:
        return False
    return bool(_CAUSA_BUSTA.search(str(message or "")))


def nota_non_applicabile(esito: dict[str, Any]) -> dict[str, Any]:
    """La nota che sostituisce l'errore: stessa identità della fonte, causa dichiarata."""
    return {**esito, "error_code": CODICE_BUSTA_CIFRATA, "message": NOTA_BUSTA_CIFRATA, "state": "not_applicable"}


def separa_non_applicabili(esiti: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Divide gli esiti negativi in errori veri e note «non applicabile» (busta cifrata)."""
    errori: list[dict[str, Any]] = []
    note: list[dict[str, Any]] = []
    for esito in esiti:
        if causa_busta_cifrata(esito.get("error_code"), esito.get("message")):
            note.append(nota_non_applicabile(dict(esito)))
        else:
            errori.append(dict(esito))
    return errori, note


__all__ = [
    "CODICE_BUSTA_CIFRATA",
    "NOTA_BUSTA_CIFRATA",
    "causa_busta_cifrata",
    "e_busta_cifrata",
    "nota_non_applicabile",
    "separa_non_applicabili",
]
