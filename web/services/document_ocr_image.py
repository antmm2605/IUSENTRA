"""Compatibilita': la preparazione dell'immagine vive in `legal_ocr.motore.immagine`."""

from __future__ import annotations

from legal_ocr.motore.immagine import (
    A4_ALTEZZA_POLLICI,
    A4_LARGHEZZA_POLLICI,
    ANGOLO_MASSIMO_RADDRIZZAMENTO,
    DPI_MASSIMO,
    DPI_MINIMO,
    LATO_MASSIMO,
    PaginaPreparata,
    densita_pagina,
    inclinazione_stimata,
    prepara_pagina,
    regioni_grafiche,
)

__all__ = [
    "A4_ALTEZZA_POLLICI",
    "A4_LARGHEZZA_POLLICI",
    "ANGOLO_MASSIMO_RADDRIZZAMENTO",
    "DPI_MASSIMO",
    "DPI_MINIMO",
    "LATO_MASSIMO",
    "PaginaPreparata",
    "densita_pagina",
    "inclinazione_stimata",
    "prepara_pagina",
    "regioni_grafiche",
]
