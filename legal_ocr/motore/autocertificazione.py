"""Recupero finito del rigo dichiarante, ancorato all'etichetta del modulo.

Riusa i lettori locali. Nessun nome atteso viene fornito al riconoscimento.
Le coordinate dipendono dai pixel della fonte, non dal modello del cliente.
"""
from __future__ import annotations

import io
import re


def recupera_dichiarante(data: bytes) -> dict:
    import fitz
    import pytesseract
    from PIL import Image

    from .consenso import leggi_con_secondo_lettore
    from .testo import testo_da_immagine

    risultati = []
    tentativi = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for numero in range(min(2, len(doc))):
            page = doc[numero]
            scale = min(300 / 72, (16_000_000 / max(1, page.rect.width * page.rect.height)) ** .5)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            with Image.open(io.BytesIO(pix.tobytes("png"))) as image:
                boxes = pytesseract.image_to_data(image, lang="ita", config="--psm 6", output_type=pytesseract.Output.DICT, timeout=40)
                anchors = [i for i, word in enumerate(boxes.get("text", []))
                           if re.search(r"sottoscr[iı].*(?:/|\.{2})", str(word), re.IGNORECASE)]
                if len(anchors) != 1:
                    tentativi.append({"pagina": numero + 1, "motivo": "Etichetta del dichiarante non individuata univocamente."})
                    continue
                i = anchors[0]
                x, y, width, height = (int(boxes[k][i]) for k in ("left", "top", "width", "height"))
                region = (min(image.width - 1, x + width), max(0, y - height // 3), image.width, min(image.height, y + height))
                with image.crop(region) as crop:
                    zoom = max(1., min(3., 48 / max(1, height)))
                    with crop.resize((max(1, round(crop.width * zoom)), max(1, round(crop.height * zoom))), Image.Resampling.LANCZOS) as enlarged:
                        first = testo_da_immagine(enlarged, raddrizza=False, dpi=300)
                        second = leggi_con_secondo_lettore(enlarged, dpi=300, preserva_risoluzione=True)
                        for reading in (first, second):
                            if reading and reading.testo.strip():
                                risultati.append(reading.testo.strip())
                        tentativi.append({"pagina": numero + 1, "area": list(region), "zoom": round(zoom, 3),
                                          "motori": [r.motore for r in (first, second) if r]})
    return {"testi": risultati, "tentativi": tentativi, "origine": "ocr"}
