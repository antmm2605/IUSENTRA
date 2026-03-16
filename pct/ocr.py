"""
pct/ocr.py — Estrazione testo da documenti PDF e immagini.

Usa pdfplumber per PDF (testo nativo e layer OCR) e Pillow+pytesseract per
immagini scansionate (opzionale — se pytesseract non installato, restituisce '').

Uso principale:
  - Indicizzare automaticamente i documenti caricati nel portale cliente
  - Permettere la ricerca full-text nel contenuto dei documenti
"""
from __future__ import annotations

import os
from typing import Optional


def estrai_testo_pdf(percorso: str, max_pagine: int = 20) -> str:
    """
    Estrae testo da un file PDF usando pdfplumber.
    Ritorna stringa vuota se il modulo non è disponibile o il file non è leggibile.
    """
    try:
        import pdfplumber
    except ImportError:
        return ""

    testo_pagine = []
    try:
        with pdfplumber.open(percorso) as pdf:
            for i, pagina in enumerate(pdf.pages[:max_pagine]):
                t = pagina.extract_text()
                if t:
                    testo_pagine.append(t.strip())
    except Exception:
        return ""
    return "\n\n".join(testo_pagine)


def estrai_testo_immagine(percorso: str, lingua: str = "ita") -> str:
    """
    OCR su immagine (JPEG, PNG, TIFF) via pytesseract.
    Richiede: pip install pytesseract Pillow  +  apt install tesseract-ocr tesseract-ocr-ita
    Ritorna stringa vuota se non disponibile.
    """
    try:
        from PIL import Image
        import pytesseract
    except ImportError:
        return ""

    try:
        img = Image.open(percorso)
        return pytesseract.image_to_string(img, lang=lingua).strip()
    except Exception:
        return ""


def estrai_testo(percorso: str) -> str:
    """
    Rileva automaticamente il tipo di file ed estrae il testo.
    Supporta: .pdf, .jpg, .jpeg, .png, .tiff, .tif
    """
    if not os.path.isfile(percorso):
        return ""
    ext = os.path.splitext(percorso)[1].lower()
    if ext == ".pdf":
        return estrai_testo_pdf(percorso)
    if ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"):
        return estrai_testo_immagine(percorso)
    return ""


def indicizza_documento(percorso: str, indice, id_fascicolo: str,
                        nome_file: str, id_documento: Optional[str] = None):
    """
    Estrae il testo da un documento e lo aggiunge all'indice di ricerca.
    indice: istanza di IndiceRicerca (pct.search_index)
    """
    testo = estrai_testo(percorso)
    if not testo:
        return False
    try:
        indice.indicizza(
            tipo="documento",
            id=id_documento or nome_file,
            titolo=nome_file,
            testo=testo,
            meta={"id_fascicolo": id_fascicolo, "file": nome_file},
        )
        return True
    except Exception:
        return False
