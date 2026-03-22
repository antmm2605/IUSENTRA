"""
OCR — Estrazione testo da PDF e immagini per indicizzazione full-text.

Supporta:
  - PDF digitali (pdfplumber): estrae testo selezionabile nativamente
  - PDF scansionati: OCR per-pagina con pytesseract se nessun testo trovato
  - Immagini (pytesseract): PNG, JPEG, TIFF, BMP, GIF

Le funzioni che accettano `bytes` lavorano su contenuto già decifrato
(la crittografia AES-256-GCM è gestita a carico del chiamante).
Le dipendenze OCR (pytesseract, Pillow) sono opzionali: se non disponibili
restituisce stringa vuota senza sollevare eccezioni.
"""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ESTENSIONI_PDF = {".pdf"}
ESTENSIONI_IMG = {".png", ".jpg", ".jpeg", ".tiff", ".tif", ".bmp", ".gif"}
ESTENSIONI_SUPPORTATE = ESTENSIONI_PDF | ESTENSIONI_IMG


# ------------------------------------------------------------------ API pubblica

def estrai_testo(data: bytes, nome_file: str, lang: str = "ita") -> str:
    """
    Estrae il testo da bytes di un documento.

    Args:
        data:      bytes del documento (già decifrati)
        nome_file: nome originale del file (determina il tipo)
        lang:      codice lingua Tesseract (default "ita" — italiano)

    Returns:
        Testo estratto; stringa vuota se il tipo non è supportato o se fallisce.
    """
    ext = Path(nome_file).suffix.lower()
    if ext in ESTENSIONI_PDF:
        return _da_pdf(data, lang)
    if ext in ESTENSIONI_IMG:
        return _da_immagine(data, lang)
    return ""


def estrai_testo_da_percorso(percorso: str, lang: str = "ita") -> str:
    """
    Estrae il testo leggendo direttamente dal disco (per file NON cifrati).
    Usato principalmente durante il rebuild dell'indice.
    """
    path = Path(percorso)
    if not path.is_file():
        return ""
    try:
        data = path.read_bytes()
    except Exception as e:
        logger.warning("Impossibile leggere %s: %s", percorso, e)
        return ""
    return estrai_testo(data, path.name, lang)


def estensione_supportata(nome_file: str) -> bool:
    """True se il file può essere processato dal modulo OCR."""
    return Path(nome_file).suffix.lower() in ESTENSIONI_SUPPORTATE


# ------------------------------------------------------------------ PDF

def _da_pdf(data: bytes, lang: str) -> str:
    try:
        import pdfplumber
    except ImportError:
        logger.warning("pdfplumber non disponibile — OCR PDF disabilitato")
        return ""

    parti: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            for pagina in pdf.pages:
                testo = pagina.extract_text()
                if testo and testo.strip():
                    parti.append(testo.strip())
                else:
                    # Pagina senza testo selezionabile → OCR via Tesseract
                    t = _ocr_pagina_pdf(pagina, lang)
                    if t:
                        parti.append(t)
    except Exception as e:
        logger.warning("Errore estrazione PDF: %s", e)

    return "\n".join(parti)


def _ocr_pagina_pdf(pagina, lang: str) -> str:
    """OCR su singola pagina PDF renderizzata come immagine."""
    try:
        import pytesseract
        img = pagina.to_image(resolution=200).original
        return pytesseract.image_to_string(img, lang=lang).strip()
    except Exception as e:
        logger.debug("OCR pagina PDF fallito: %s", e)
        return ""


# ------------------------------------------------------------------ Immagini

def _da_immagine(data: bytes, lang: str) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        return pytesseract.image_to_string(img, lang=lang).strip()
    except Exception as e:
        logger.warning("Errore OCR immagine: %s", e)
        return ""
