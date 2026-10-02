"""Ricerca giuridica di Lex: indice lessicale FTS5, indice vettoriale e fusione ibrida.

Moduli:
- ``testo``: normalizzazione, stopword italiane, stemming leggero, analisi della domanda;
- ``indice_fts``: indice SQLite FTS5 sui chunk Normattiva (bm25, articolo/codice esatto, vigenza);
- ``embedding``: client Ollama per gli embedding e embedding finti deterministici per i test;
- ``indice_vettoriale``: vettori int8 con scala su file memmappati, ricerca esatta a blocchi;
- ``ibrida``: fusione RRF e ordinamento finale in cui domina la pertinenza;
- ``classificatore``: domanda giuridica o domanda sui dati dello studio.
"""

from __future__ import annotations

__all__ = [
    "classificatore",
    "embedding",
    "ibrida",
    "indice_fts",
    "indice_vettoriale",
    "testo",
]
