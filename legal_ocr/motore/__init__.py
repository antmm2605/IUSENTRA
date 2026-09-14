"""Il motore di lettura dello studio: uno solo, per il fascicolo, l'editor e l'indice.

- `runtime`: dove sta Tesseract e come si configura (un thread per processo).
- `immagine`: preparazione della pagina (raddrizzamento, luce, bordo, densita').
- `lettura`: la strategia di lettura con Tesseract (prima passata sicura,
  altre configurazioni in parallelo solo se serve, binarizzazione per le copie
  sbiadite) e il PDF ricercabile.
- `consenso`: il secondo lettore (PDF Inspector, rete PP-OCR) che conferma o
  corregge le parole incerte.
- `pagina`: il percorso completo da immagine a blocchi con formato, correzioni
  del formulario e riferimenti giuridici.
- `testo`: solo il testo, per indice, Lex, editor e lettori automatici.
"""

from __future__ import annotations

from .errori import ErroreLettura, MotoreNonDisponibile
from .lettura import CONFIGURAZIONI, Lettura, leggi_immagine, parole_da_dati
from .pagina import PaginaLetta, riconosci_immagine
from .testo import PaginaTesto, TestoLetto, testo_da_immagine, testo_da_immagine_bytes, testo_da_pdf

VERSIONE_MOTORE = "2026.09.14.motore-unico.v1"

__all__ = [
    "CONFIGURAZIONI",
    "ErroreLettura",
    "Lettura",
    "MotoreNonDisponibile",
    "PaginaLetta",
    "PaginaTesto",
    "TestoLetto",
    "VERSIONE_MOTORE",
    "leggi_immagine",
    "parole_da_dati",
    "riconosci_immagine",
    "testo_da_immagine",
    "testo_da_immagine_bytes",
    "testo_da_pdf",
]
