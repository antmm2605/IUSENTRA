"""Importazione fedele di un documento nell'editor atti.

Converte un PDF (o un DOCX) in HTML conservando quello che l'importazione «a
testo» perde: carattere e corpo esatti, grassetto, corsivo, sottolineato,
barrato, colori del testo e degli sfondi, allineamenti, rientri, interlinea,
elenchi, **tabelle** (anche senza filetti, con celle unite e sfondi),
**immagini** e loghi, grafica vettoriale, collegamenti, intestazioni e piedi,
formato e margini della pagina.

Due modalita':

* ``fedele`` (predefinita) — ricostruisce un documento che scorre: paragrafi,
  tabelle e immagini restano modificabili nell'editor e l'aspetto e' quello
  dell'originale. E' la modalita' giusta per l'editor atti.
* ``esatto`` — ogni riga e' posizionata alle coordinate del PDF. Sovrapponibile
  all'originale, ma il testo non scorre piu': serve per gli allegati da
  riprodurre tali e quali.

Il resto dell'applicazione chiama solo `converti_file`. Perche' un atto
importato male costringe l'avvocato a riscriverlo: la fedelta' qui non e'
estetica, e' tempo di lavoro.
"""

from __future__ import annotations

from .conversione import converti
from .formati import ESTENSIONI, converti_bytes, converti_docx, converti_file
from .modello import DocumentoConvertito, Elemento, PaginaConvertita, Riga, Tratto
from .taratura import FAMIGLIE_EDITOR, Taratura, famiglia_editor, pila_font

VERSIONE_IMPORTAZIONE_FEDELE = "2026.09.18.docfedele.v1"

__all__ = [
    "ESTENSIONI",
    "FAMIGLIE_EDITOR",
    "VERSIONE_IMPORTAZIONE_FEDELE",
    "DocumentoConvertito",
    "Elemento",
    "PaginaConvertita",
    "Riga",
    "Taratura",
    "Tratto",
    "converti",
    "converti_bytes",
    "converti_docx",
    "converti_file",
    "famiglia_editor",
    "pila_font",
]
