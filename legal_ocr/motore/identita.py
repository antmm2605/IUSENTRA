"""Recupero puntuale della MRZ di una carta fotografata su un foglio.

Riusa PP-OCR locale, preserva l'immagine e accetta soltanto cifre di controllo
concordanti. Il nome del file non prova mai il titolare della carta.
"""
from __future__ import annotations

from .consenso import leggi_con_secondo_lettore
from .mrz import righe_td1_complete


def recupera_mrz_carta(image) -> tuple[str, list[str]]:
    """Una sola regione e quattro rotazioni al massimo, nessuna correzione OCR."""
    try:
        import cv2
        import numpy as np
        from PIL import Image, ImageFilter

        mask = np.asarray(image.convert('L').point(lambda value: 255 if value < 245 else 0)
                          .filter(ImageFilter.MedianFilter(9)))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        area = image.width * image.height
        regions = []
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if (.02 <= cv2.contourArea(contour) / area <= .65
                    and .5 <= width / max(height, 1) <= 2):
                regions.append((x, y, width, height))
        if len(regions) != 1:
            return '', ['Recupero MRZ: nessuna regione singola della carta riscontrata.']
        x, y, width, height = regions[0]
        region = image.crop((max(0, x - 15), max(0, y - 15),
                             min(image.width, x + width + 15), min(image.height, y + height + 15)))
        scale = min(2.0, 2400 / max(region.width, region.height))
        if scale > 1:
            resized = region.resize((round(region.width * scale), round(region.height * scale)), Image.Resampling.LANCZOS)
            region.close()
            region = resized
        try:
            for angle in (0, 90, 180, 270):
                candidate = region.rotate(angle, expand=True) if angle else region
                try:
                    reading = leggi_con_secondo_lettore(candidate, dpi=216)
                    if reading is None or reading.confidenza < .94:
                        continue
                    lines = righe_td1_complete(reading.testo)
                    if lines:
                        location = ', '.join(f'{value:.3f}' for value in
                                             (x / image.width, y / image.height, width / image.width, height / image.height))
                        return reading.testo, [f'Recupero MRZ regione-v1: riquadro ({location}), '
                            f'rotazione di lettura {angle}°, cifre di controllo riscontrate; originale invariato.']
                finally:
                    if candidate is not region:
                        candidate.close()
        finally:
            region.close()
        return '', ['Recupero MRZ: nessuna lettura della regione supera i controlli del documento.']
    except (ImportError, ValueError, RuntimeError) as exc:
        return '', [f'Recupero MRZ non completato: {type(exc).__name__}.']
