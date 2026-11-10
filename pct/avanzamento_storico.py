"""Storico dell'avanzamento: la stessa transizione con la stessa fonte è un fatto solo.

Una sentenza indicizzata due volte (due copie dello stesso provvedimento, o la stessa
lettura ripetuta dopo un ripristino) produceva due voci «In corso → Definito» con la
stessa sentenza: all'avvocato sembrano due definizioni del fascicolo. La transizione si
registra una volta; le voci già presenti restano nei dati (traccia, art. 20 CAD) e si
nascondono soltanto in lettura.

Una transizione si ripete davvero solo se nel frattempo lo stato è cambiato con un'altra
voce (es. riapertura «Definito → In corso»): in quel caso la nuova voce si registra.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

# Il documento che porta la fonte (docai-<hash>, nome del file): due copie della stessa sentenza
# hanno documenti diversi ma la stessa fonte giuridica, cioè numero della sentenza e ruolo.
_DOCUMENTO_RE = re.compile(r"\s*;?\s*Documento:\s*[^;]*", re.IGNORECASE)


def _testo(valore: Any) -> str:
    return " ".join(str(getattr(valore, "value", valore) or "").split()).strip()


def nota_confrontabile(note: Any) -> str:
    """La nota senza il documento che la porta, per confrontare la fonte della transizione."""
    return _DOCUMENTO_RE.sub("", _testo(note)).strip(" ;").casefold()


def _chiave(voce: Any) -> tuple[str, str, str, str]:
    return (
        _testo(getattr(voce, "stato_precedente", "")).upper(),
        _testo(getattr(voce, "stato_nuovo", "")).upper(),
        _testo(getattr(voce, "descrizione", "")).casefold(),
        nota_confrontabile(getattr(voce, "note", "")),
    )


def _cambia_stato(voce: Any) -> bool:
    chiave = _chiave(voce)
    return bool(chiave[0] and chiave[1] and chiave[0] != chiave[1])


def transizione_gia_registrata(avanzamento: Iterable[Any], precedente: Any, nuovo: Any, note: Any) -> bool:
    """L'ultima voce che ha cambiato stato è già questa transizione, con la stessa fonte?

    Vale solo per le transizioni documentate da una nota (la fonte): un cambio di stato
    manuale senza nota non ha una fonte da confrontare e si registra sempre.
    """
    nota = nota_confrontabile(note)
    precedente, nuovo = _testo(precedente).upper(), _testo(nuovo).upper()
    if not nota or not precedente or precedente == nuovo:
        return False
    ultima = next((voce for voce in reversed(list(avanzamento or [])) if _cambia_stato(voce)), None)
    if ultima is None:
        return False
    chiave = _chiave(ultima)
    return (chiave[0], chiave[1], chiave[3]) == (precedente, nuovo, nota)


def voci_ripetute(avanzamento: Iterable[Any]) -> set[int]:
    """Indici delle voci che ripetono la transizione precedente con la stessa fonte (da nascondere)."""
    ripetute: set[int] = set()
    ultima: tuple[str, str, str, str] | None = None
    for indice, voce in enumerate(avanzamento or []):
        if not _cambia_stato(voce):
            continue
        chiave = _chiave(voce)
        if ultima == chiave and chiave[3]:
            ripetute.add(indice)
            continue
        ultima = chiave
    return ripetute


__all__ = ["nota_confrontabile", "transizione_gia_registrata", "voci_ripetute"]
