"""Forma di una regola del formulario: che cosa cambia, perche', quante volte.

Ogni correzione al testo letto dalla macchina deve essere dichiarabile: il
riconoscimento in pagina mostra all'avvocato quali regole sono intervenute e
quante volte, e l'evidenza probatoria conserva il testo prima e dopo. Una
regola che non sa dire che cosa ha fatto non e' ammessa.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

Sostituzione = Callable[[str], tuple[str, int]]


@dataclass(frozen=True)
class Regola:
    """Una trasformazione deterministica del testo, con identita' stabile."""

    id: str
    etichetta: str
    motivo: str
    applica: Sostituzione


@dataclass(frozen=True)
class Esito:
    """Testo corretto e regole intervenute, con il numero di occorrenze."""

    testo: str
    occorrenze: tuple[tuple[str, int], ...]

    @property
    def regole(self) -> list[str]:
        return [identificativo for identificativo, _ in self.occorrenze]


def regola_regex(
    identificativo: str,
    etichetta: str,
    motivo: str,
    schema: str | re.Pattern[str],
    sostituto: str | Callable[[re.Match[str]], str],
    *,
    flags: int = 0,
) -> Regola:
    """Regola costruita da un'espressione regolare e dal suo sostituto."""
    espressione = re.compile(schema, flags) if isinstance(schema, str) else schema

    def applica(testo: str) -> tuple[str, int]:
        return espressione.subn(sostituto, testo)

    return Regola(identificativo, etichetta, motivo, applica)


def applica_regole(testo: str, regole: list[Regola] | tuple[Regola, ...]) -> Esito:
    """Applica le regole in ordine e riporta quelle che hanno cambiato il testo."""
    corrente = str(testo or "")
    intervenute: list[tuple[str, int]] = []
    for regola in regole:
        nuovo, quante = regola.applica(corrente)
        if quante and nuovo != corrente:
            intervenute.append((regola.id, quante))
            corrente = nuovo
    return Esito(corrente, tuple(intervenute))


def conserva_maiuscole(originale: str, canonico: str) -> str:
    """Il canonico con la forma di maiuscole dell'originale (tutto maiuscolo o iniziale)."""
    lettere = [carattere for carattere in originale if carattere.isalpha()]
    if lettere and all(carattere.isupper() for carattere in lettere):
        return canonico.upper()
    if lettere and lettere[0].isupper():
        return canonico[:1].upper() + canonico[1:]
    return canonico


__all__ = ["Esito", "Regola", "Sostituzione", "applica_regole", "conserva_maiuscole", "regola_regex"]
