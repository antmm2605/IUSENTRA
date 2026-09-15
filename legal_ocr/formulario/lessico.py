"""La regola del lessico: una parola che non esiste torna alla parola che esiste.

Le altre regole del formulario lavorano su forme (date, importi, codici, numeri
di ruolo): sanno che cosa deve esserci in quel punto. Questa lavora sulle
parole, dove la forma non basta, e per questo si appoggia al lessico dichiarato
(`legal_ocr/lessico/`): corregge solo se la parola letta non esiste e una sola
parola del lessico si ottiene con le confusioni dichiarate. È l'ultima regola
ad applicarsi, quando caratteri, abbreviazioni, numeri e accenti hanno già
sistemato tutto il resto.
"""

from __future__ import annotations

from .regola import Regola


def _applica(testo: str) -> tuple[str, int]:
    from legal_ocr.lessico.correttore import correggi_testo

    return correggi_testo(testo)


REGOLE: tuple[Regola, ...] = (
    Regola(
        "lessico.parola.v1",
        "parole riportate al lessico",
        "Parola inesistente riportata all'unica parola del lessico forense o italiano ottenibile con le confusioni dichiarate.",
        _applica,
    ),
)

__all__ = ["REGOLE"]
