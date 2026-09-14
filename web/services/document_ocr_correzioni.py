"""Correzioni forensi deterministiche sul testo riconosciuto.

Il motore OCR sbaglia sempre negli stessi punti, e sono punti che in un atto
contano: «art .» invece di «art.», «N .» invece di «N.», l'indirizzo PEC spezzato
dagli spazi, il numero di ruolo letto come «RG0». Sono errori meccanici, non
interpretazioni: correggerli non e' riscrivere il documento.

Le regole non nascono qui: sono quelle gia' usate dalla pipeline probatoria
(`legal_ocr.postprocess`), che le applica ai documenti acquisiti con valore di
evidenza. Riusarle significa che lo stesso atto, letto dalla pipeline o letto
in pagina dall'avvocato, viene normalizzato allo stesso modo.

Ogni correzione applicata viene dichiarata: l'avvocato deve poter sapere che
cosa e' stato cambiato rispetto a quello che il motore ha letto, altrimenti il
testo che rilegge non e' piu' verificabile contro la pagina.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from legal_ocr.postprocess import apply_deterministic_corrections


def correggi_testo(testo: str) -> tuple[str, list[str]]:
    """Testo normalizzato e identificativi delle regole che sono intervenute."""
    grezzo = str(testo or "")
    if not grezzo.strip():
        return grezzo, []
    corretto, storia = apply_deterministic_corrections(grezzo, user="riconoscimento")
    return corretto, [str(voce.get("rule_id") or "") for voce in storia if voce.get("rule_id")]


def correggi_blocchi(blocchi: Sequence[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Blocchi con il testo normalizzato e l'elenco delle correzioni applicate.

    Le tabelle vengono corrette cella per cella: un numero di ruolo o una PEC
    stanno spesso dentro una tabella, non in un capoverso.
    """
    conteggio: dict[str, int] = {}
    corretti: list[dict[str, Any]] = []
    for blocco in blocchi:
        voce = dict(blocco)
        if voce.get("tipo") == "tabella":
            righe: list[list[str]] = []
            for riga in voce.get("righe") or []:
                celle: list[str] = []
                for cella in riga:
                    nuova, regole = correggi_testo(str(cella))
                    for regola in regole:
                        conteggio[regola] = conteggio.get(regola, 0) + 1
                    celle.append(nuova)
                righe.append(celle)
            voce["righe"] = righe
        else:
            nuovo, regole = correggi_testo(str(voce.get("testo") or ""))
            for regola in regole:
                conteggio[regola] = conteggio.get(regola, 0) + 1
            voce["testo"] = nuovo
        corretti.append(voce)
    applicate = [{"regola": regola, "occorrenze": numero} for regola, numero in sorted(conteggio.items())]
    return corretti, applicate


__all__ = ["correggi_blocchi", "correggi_testo"]
