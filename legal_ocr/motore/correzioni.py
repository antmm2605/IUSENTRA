"""Le correzioni del formulario applicate ai blocchi della pagina, dichiarate.

Le tabelle vengono corrette cella per cella: un numero di ruolo o una PEC
stanno spesso dentro una tabella, non in un capoverso. Ogni regola intervenuta
viene riportata con etichetta e numero di occorrenze, cosi' l'avvocato sa che
cosa e' stato cambiato rispetto a quello che il motore ha letto.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from ..formulario import applica_formulario, etichetta


def correggi_testo(testo: str) -> tuple[str, list[str]]:
    """Testo normalizzato e identificativi delle regole che sono intervenute."""
    grezzo = str(testo or "")
    if not grezzo.strip():
        return grezzo, []
    esito = applica_formulario(grezzo)
    return esito.testo, esito.regole


def correggi_blocchi(blocchi: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Blocchi con il testo normalizzato e l'elenco delle correzioni applicate."""
    conteggio: dict[str, int] = {}

    def registra(regole: Sequence[str]) -> None:
        for regola in regole:
            conteggio[regola] = conteggio.get(regola, 0) + 1

    corretti: list[dict[str, Any]] = []
    for blocco in blocchi:
        voce = dict(blocco)
        if voce.get("tipo") == "tabella":
            righe: list[list[str]] = []
            for riga in voce.get("righe") or []:
                celle: list[str] = []
                for cella in riga:
                    nuova, regole = correggi_testo(str(cella))
                    registra(regole)
                    celle.append(nuova)
                righe.append(celle)
            voce["righe"] = righe
        else:
            nuovo, regole = correggi_testo(str(voce.get("testo") or ""))
            registra(regole)
            voce["testo"] = nuovo
            if "voce" in voce:
                voce["voce"], _ = correggi_testo(str(voce.get("voce") or ""))
        corretti.append(voce)
    applicate = [
        {"regola": regola, "occorrenze": numero, "etichetta": etichetta(regola)}
        for regola, numero in sorted(conteggio.items())
    ]
    return corretti, applicate


__all__ = ["correggi_blocchi", "correggi_testo"]
