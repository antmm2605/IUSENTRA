"""Compatibilita': il formato del testo riconosciuto vive in `legal_ocr.formato`.

Il motore di lettura e' uno solo e sta in `legal_ocr`; questo modulo resta per
chi importava i nomi da qui.
"""

from __future__ import annotations

from legal_ocr.formato import (
    ALLINEAMENTI,
    ALLINEAMENTO_CENTRO,
    ALLINEAMENTO_DESTRA,
    ALLINEAMENTO_GIUSTIFICATO,
    ALLINEAMENTO_SINISTRA,
    LUNGHEZZA_MASSIMA_RUBRICA,
    SCARTO_CENTRATURA,
    SOGLIA_GRASSETTO,
    SOGLIE_TITOLO,
    TOLLERANZA_MARGINE,
    Formato,
    Misure,
    blocchi_con_formato,
    densita_parole,
    formato_blocco,
    misure_pagina,
)

__all__ = [
    "ALLINEAMENTI",
    "ALLINEAMENTO_CENTRO",
    "ALLINEAMENTO_DESTRA",
    "ALLINEAMENTO_GIUSTIFICATO",
    "ALLINEAMENTO_SINISTRA",
    "LUNGHEZZA_MASSIMA_RUBRICA",
    "SCARTO_CENTRATURA",
    "SOGLIA_GRASSETTO",
    "SOGLIE_TITOLO",
    "TOLLERANZA_MARGINE",
    "Formato",
    "Misure",
    "blocchi_con_formato",
    "densita_parole",
    "formato_blocco",
    "misure_pagina",
]
