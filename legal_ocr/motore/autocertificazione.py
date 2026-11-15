"""Recupero del dichiarante e dell’anno di reddito dai campi del modulo.

Riusa i lettori locali. Nessun nome atteso viene fornito al riconoscimento.
Le coordinate dipendono dai pixel della fonte, non dal modello del cliente.
"""
from __future__ import annotations

import io
import re


def _leggi_anno_reddito(image, boxes: dict, pagina: int) -> tuple[int | None, list[dict]]:
    from PIL import ImageOps
    from .consenso import leggi_con_secondo_lettore

    def chiave_riga(i):
        return (boxes["block_num"][i], boxes["par_num"][i], boxes["line_num"][i])

    parole = boxes["text"]
    ancore = []
    for i, parola in enumerate(parole):
        testo = str(parola).casefold().replace("’", "'")
        if not testo.startswith("relativament"):
            continue
        riga = chiave_riga(i)
        for j in range(i + 1, min(i + 5, len(parole))):
            if chiave_riga(j) != riga:
                break
            if re.fullmatch(r"all'a[n]{1,2}o[.:…]*", str(parole[j]).casefold().replace("’", "'")):
                ancore.append(j)
                break
    if len(ancore) != 1:
        return None, []
    i = ancore[0]
    x, y, larghezza, altezza = (int(boxes[chiave][i]) for chiave in ("left", "top", "width", "height"))
    inizio = x + larghezza
    prove = []
    # Due ritagli dello stesso rigo, uno con il campo intero e uno centrato
    # sui caratteri. Si accetta il numero completo solo se le letture concordano.
    for sinistra, destra, sopra in ((0, 9, 1.1), (2.5, 8.5, 1.0)):
        area = (min(image.width, round(inizio + altezza * sinistra)), max(0, round(y - altezza * sopra)),
                min(image.width, round(inizio + altezza * destra)), min(image.height, round(y + altezza * 1.15)))
        if area[0] >= area[2] or area[1] >= area[3]:
            continue
        with image.crop(area) as crop:
            with ImageOps.autocontrast(ImageOps.grayscale(crop)) as nitido:
                with ImageOps.expand(nitido, border=18, fill=255) as bordo:
                    with bordo.resize((bordo.width * 2, bordo.height * 2)) as campo:
                        lettura = leggi_con_secondo_lettore(campo, dpi=300, preserva_risoluzione=True)
        numero = re.fullmatch(r"[. …]*?(20[0-9]{2})[. …]*", lettura.testo.strip()) if lettura else None
        if numero and lettura.confidenza >= .75:
            prove.append({"pagina": pagina, "area": list(area), "motore": lettura.motore,
                          "confidenza": round(lettura.confidenza, 3), "anno": int(numero[1])})
    anni = {prova["anno"] for prova in prove}
    return (next(iter(anni)) if len(prove) == 2 and len(anni) == 1 else None), prove


def recupera_campi(data: bytes, *, dichiarante: bool, anno_reddito: bool) -> dict:
    import fitz
    import pytesseract
    from PIL import Image

    from .consenso import leggi_con_secondo_lettore
    from .testo import testo_da_immagine

    risultati = []
    tentativi = []
    anni = set()
    prove_anno = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for numero in range(min(2, len(doc))):
            page = doc[numero]
            scale = min(300 / 72, (16_000_000 / max(1, page.rect.width * page.rect.height)) ** .5)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            with Image.open(io.BytesIO(pix.tobytes("png"))) as image:
                boxes = pytesseract.image_to_data(image, lang="ita", config="--psm 6", output_type=pytesseract.Output.DICT, timeout=40)
                if anno_reddito:
                    anno, riscontri = _leggi_anno_reddito(image, boxes, numero + 1)
                    if anno is not None:
                        anni.add(anno)
                    prove_anno.extend(riscontri)
                if not dichiarante:
                    continue
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
    return {"testi": risultati, "tentativi": tentativi, "origine": "ocr",
            "anno_reddito": next(iter(anni)) if len(anni) == 1 else None, "prove_anno": prove_anno}


def recupera_dichiarante(data: bytes) -> dict:
    return recupera_campi(data, dichiarante=True, anno_reddito=False)
