"""Quale parte della lettura del fascicolo risponde alla domanda dell'avvocato.

«Riassumi il fascicolo» vuole tutto; «a che punto siamo con le notifiche» vuole
le notifiche e i prossimi passi; «quando è la prossima udienza» vuole la fase.
La lettura è una sola, sempre completa: qui si sceglie soltanto quali sezioni
mostrare, senza mai riscrivere il loro contenuto.
"""

from __future__ import annotations

import re
from typing import Any

from pct.fascicolo_lettura.narrativa import ORDINE_SEZIONI, componi

_FUOCHI: tuple[tuple[str, tuple[str, ...]], ...] = (
    (r"\bnotific|\brelat[ae]\b|\bpec\b|\bconsegn", ("quadro", "depositi_notifiche", "prossimi_passi", "lacune")),
    (r"\bdeposit|\bbusta\b|\bcanceller|\bricevut", ("quadro", "depositi_notifiche", "prossimi_passi", "lacune")),
    (r"\bdocument|\batti\b|\ballegat|\bcatalog|\bprovvediment|\bsentenz|\bordinanz", ("quadro", "documenti", "oggetto", "prossimi_passi")),
    (r"\budienz|\bfase\b|\bpunto\b|\bstato\b|\bsituazion", ("quadro", "fase", "cronologia", "prossimi_passi")),
    (r"\bscadenz|\btermin|\bprossim|\bcosa\s+(?:devo|dobbiamo|bisogna)\s+fare|\bda\s+fare|\badempiment", ("quadro", "fase", "prossimi_passi", "lacune")),
    (r"\beconom|\bparcell|\bfattur|\bincass|\bpreventiv|\bcompens|\bconformit", ("quadro", "conformita_economico", "prossimi_passi")),
    (r"\bcosa\s+tratta|\boggetto\b|\bdi\s+che\s+cosa|\bmateria\b|\bdomanda\b", ("quadro", "oggetto", "documenti", "fase")),
    (r"\bfatto\b|\bstoria\b|\bcronolog|\bfinora|\bfin\s+qui|\bsvolt", ("quadro", "cronologia", "fase", "prossimi_passi")),
)


def sezioni_per_domanda(domanda: str) -> tuple[str, ...]:
    """Le sezioni da mostrare: tutte per una lettura, le pertinenti per una domanda puntuale."""
    testo = " ".join(str(domanda or "").split()).lower()
    if not testo or re.search(r"\briassum|\bsintesi|\bleggi\b|\blettura|\bquadro\s+complet|\btutto\b|\bpanoramic|\bspiega", testo):
        return ORDINE_SEZIONI
    scelte: list[str] = []
    for modello, sezioni in _FUOCHI:
        if re.search(modello, testo):
            for sezione in sezioni:
                if sezione not in scelte:
                    scelte.append(sezione)
    return tuple(scelte) if scelte else ORDINE_SEZIONI


def testo_lettura_per_domanda(domanda: str, lettura: dict[str, Any]) -> str:
    """Il testo della lettura, limitato alle sezioni che rispondono alla domanda."""
    if not lettura or not lettura.get("intestazione"):
        return ""
    return componi(lettura, sezioni_per_domanda(domanda))


__all__ = ["sezioni_per_domanda", "testo_lettura_per_domanda"]
