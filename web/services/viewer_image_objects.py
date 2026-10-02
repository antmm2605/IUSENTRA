"""Immagini raster verificate ed elenchi del lettore PDF."""
import base64
import binascii
import io
import math
import fitz
from PIL import Image, ImageOps, ImageEnhance


def normalize_image(raw):
    from web.services.pdf_overlay_editor import PdfOverlayError
    value = raw.get("imageData")
    if not isinstance(value, str) or len(value) > 7_000_000:
        raise PdfOverlayError("Scegli un’immagine PNG o JPEG di massimo 5 MB.")
    try:
        data = base64.b64decode(value, validate=True)
        if len(data) > 5_000_000:
            raise ValueError()
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG"} or image.width * image.height > 20_000_000:
                raise ValueError()
            image.load()
            image = ImageOps.exif_transpose(image).convert("RGBA" if image.mode in {"RGBA", "LA", "P"} else "RGB")
            for setting, enhancer, low, high in (("imageBrightness",ImageEnhance.Brightness,.2,2),("imageContrast",ImageEnhance.Contrast,.2,2),("imageSharpness",ImageEnhance.Sharpness,0,3)):
                factor=float(raw.get(setting,1))
                if not math.isfinite(factor) or not low<=factor<=high:raise ValueError()
                if factor!=1:image=enhancer(image).enhance(factor)
            if raw.get("imageGrayscale") is True:image=ImageOps.grayscale(image).convert("RGB")
            if raw.get("imageAutocontrast") is True:
                if image.mode=="RGBA":
                    alpha=image.getchannel("A");image=ImageOps.autocontrast(image.convert("RGB"),cutoff=1);image.putalpha(alpha)
                else:image=ImageOps.autocontrast(image,cutoff=1)
            output = io.BytesIO()
            image.save(output, format="PNG")
            if output.tell() > 20_000_000:
                raise ValueError()
        width, height = float(raw["width"]), float(raw["height"])
        if not all(math.isfinite(n) and 0 < n <= 1 for n in (width, height)):
            raise ValueError()
        rotation = raw.get("rotation", 0)
        if rotation not in {0, 90, 180, 270}:
            raise ValueError()
        return {"imageBytes": output.getvalue(), "width": width, "height": height, "rotation": rotation, "keepRatio": raw.get("keepRatio") is not False}
    except (ValueError, KeyError, TypeError, binascii.Error, OSError, Image.DecompressionBombError) as exc:
        raise PdfOverlayError("Immagine non valida. Usa PNG o JPEG, fino a 5 MB e 20 milioni di pixel.") from exc


def insert_image(page, annotation):
    from web.services.pdf_overlay_editor import PdfOverlayError
    w, h = page.rect.width, page.rect.height
    rect = fitz.Rect(annotation["x"] * w, annotation["y"] * h, (annotation["x"] + annotation["width"]) * w, (annotation["y"] + annotation["height"]) * h)
    if not page.rect.contains(rect):
        raise PdfOverlayError("Il riquadro dell’immagine supera il bordo della pagina. Spostalo o ridimensionalo.")
    page.insert_image(rect * page.derotation_matrix, stream=annotation["imageBytes"], keep_proportion=annotation["keepRatio"], rotate=(annotation["rotation"] + page.rotation) % 360, overlay=True)


def text_lines(annotation):
    lines = annotation["text"].splitlines()
    style = annotation.get("listStyle", "none")
    if style == "bullet":
        return "\n".join("• " + line for line in lines)
    if style == "number":
        return "\n".join(f"{index}. {line}" for index, line in enumerate(lines, 1))
    return annotation["text"]


def writing_layout(pdf_bytes, page_number):
    """Margine e interlinea del corpo osservati nel documento, senza OCR."""
    from collections import Counter
    from statistics import median
    from web.services.pdf_overlay_editor import _editable_spans, PdfOverlayError
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if not 1 <= page_number <= len(doc):
            raise PdfOverlayError("Pagina non disponibile.")
        page = doc[page_number - 1]
        spans = [s for s in _editable_spans(page) if s["rotation"] == 0]
        if not spans:
            return None
        sizes = Counter()
        for span in spans:
            sizes[round(span["size"], 1)] += len(span["text"])
        size = sizes.most_common(1)[0][0]
        body = [s for s in spans if abs(s["size"] - size) < .2]
        exemplar = max(body, key=lambda s: len(s["text"]))
        left = min(s["bbox"][0] for s in body)
        ys = sorted(set(round(s["origin"][1], 2) for s in body))
        gaps = [b-a for a,b in zip(ys, ys[1:]) if size <= b-a <= size*3]
        leading = min(gaps) if gaps else size*1.2
        name = exemplar["font"].casefold()
        return {"x": left/page.rect.width, "lineHeightPt": round(leading, 1), "fontSizePt": size, "fontFamily": "times" if "times" in name else "courier" if "courier" in name else "helvetica", "bold": "bold" in name, "italic": "italic" in name or "oblique" in name, "color": f"#{exemplar.get('color',0):06x}"}
