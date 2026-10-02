"""Editor PDF nativo a overlay per il fascicolo.

Il modulo non converte mai il PDF in HTML: apre il PDF originale, applica
interventi grafici espliciti sulle pagine e restituisce un nuovo PDF.

Due regole governano il salvataggio, e sono in tensione fra loro.

La prima: un documento che puo' finire agli atti va modificato *aggiungendo*,
non riscrivendo. Il salvataggio incrementale lascia intatti i byte originali e
accoda le modifiche, cosi' dentro il file modificato l'originale resta
verificabile.

La seconda: un oscuramento deve togliere davvero il testo. Finche' si disegnava
un rettangolo bianco sopra, il testo restava nel contenuto della pagina e si
riprendeva con un copia-incolla: sembrava coperto e non lo era.

Le due cose non convivono. Un salvataggio incrementale conserva la revisione
precedente, quindi conserverebbe anche il testo che l'oscuramento doveva
distruggere. Percio': se fra le modifiche c'e' un oscuramento il file viene
riscritto per intero, e solo in quel caso.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
import re
import math
from typing import Any, Iterable

import fitz


class PdfOverlayError(ValueError):
    """Annotazione PDF non valida o PDF non modificabile."""


@dataclass(frozen=True)
class PdfPageInfo:
    number: int
    width: float
    height: float


def pdf_page_infos(pdf_bytes: bytes) -> list[PdfPageInfo]:
    """Misure delle pagine. Sola lettura: passa dal motore di rendering."""
    from pct.rendering_pdf import RenderingPdfError, dimensioni_pagine

    try:
        return [
            PdfPageInfo(number=misura.numero, width=misura.larghezza, height=misura.altezza)
            for misura in dimensioni_pagine(pdf_bytes)
        ]
    except RenderingPdfError as exc:
        raise PdfOverlayError(str(exc)) from exc


def render_pdf_page_png(pdf_bytes: bytes, *, page_number: int, zoom: float = 1.6) -> bytes:
    """Una pagina come immagine. Sola lettura: passa dal motore di rendering."""
    from pct.rendering_pdf import RenderingPdfError, pagina_png

    try:
        return pagina_png(pdf_bytes, numero_pagina=page_number, scala=zoom, predefinita=1.6)
    except RenderingPdfError as exc:
        raise PdfOverlayError(str(exc)) from exc


def apply_pdf_overlays(pdf_bytes: bytes, annotations: Iterable[dict[str, Any]]) -> tuple[bytes, int]:
    """Applica le modifiche e restituisce il PDF nuovo con quante ne ha applicate.

    Senza oscuramenti il file esce da un salvataggio incrementale: i byte
    dell'originale restano dov'erano. Con almeno un oscuramento il file viene
    riscritto, perche' il testo tolto non deve sopravvivere in una revisione
    precedente.
    """
    normalized = [_normalize_annotation(item) for item in annotations]
    if not normalized:
        raise PdfOverlayError("Nessuna modifica PDF da salvare.")
    keys = [(a["page"], a["span"]) for a in normalized if a["type"] == "replace"]
    if len(keys) != len(set(keys)):
        raise PdfOverlayError("La stessa riga ha più modifiche: mantieni soltanto l’ultima.")
    oscura = any(str(item.get("type")) in {"cover", "replace"} for item in normalized)
    with tempfile.TemporaryDirectory(prefix="iusentra-pdf-") as cartella:
        lavoro = Path(cartella) / "documento.pdf"
        lavoro.write_bytes(pdf_bytes)
        with fitz.open(str(lavoro)) as doc:
            if doc.is_encrypted:
                raise PdfOverlayError("PDF cifrato: importare una versione sbloccata prima della modifica.")
            pagine_da_oscurare: set[int] = set()
            sostituzioni = []
            rotazioni = []
            for annotation in normalized:
                page_number = int(annotation["page"])
                if page_number < 1 or page_number > len(doc):
                    raise PdfOverlayError("Una modifica indica una pagina PDF non disponibile.")
                if annotation["type"] == "rotate":
                    rotazioni.append((page_number - 1, annotation["degrees"]))
                    continue
                if annotation["type"] == "replace":
                    sostituzioni.append(_prepare_replacement(doc[page_number - 1], annotation))
                    continue
                _apply_annotation(doc[page_number - 1], annotation)
                if str(annotation["type"]) == "cover":
                    pagine_da_oscurare.add(page_number - 1)
            for indice in sorted(pagine_da_oscurare):
                _esegui_oscuramenti(doc[indice])
            grouped = {}
            for replacement in sostituzioni:
                grouped.setdefault(replacement[0].number, []).append(replacement)
            for replacements in grouped.values():
                page = replacements[0][0]
                retained = _retain_intersecting_characters(page, replacements)
                for _, area, *_ in replacements:
                    page.add_redact_annot(area, fill=None)
                page.apply_redactions(images=0, graphics=0)
                for origin, text, font, size, color, rotation in _removed_characters(page, retained):
                    _insert_span(page, origin, text, font, size, color, rotation)
                for _, _, origin, text, font, size, color, rotation, _ in replacements:
                    _insert_span(page, origin, text, font, size, color, rotation)
            for indice, degrees in rotazioni:
                doc[indice].set_rotation((doc[indice].rotation + degrees) % 360)
            if oscura:
                # Riscrittura piena: la revisione precedente conteneva il testo
                # oscurato e non deve restare nel file.
                return bytes(doc.tobytes(garbage=4, deflate=True, clean=True)), len(normalized)
            doc.save(str(lavoro), incremental=True, encryption=fitz.PDF_ENCRYPT_KEEP)
        return lavoro.read_bytes(), len(normalized)


def _esegui_oscuramenti(page: fitz.Page) -> None:
    """Toglie davvero il contenuto sotto i rettangoli di oscuramento."""
    try:
        page.apply_redactions()
    except TypeError:
        # Versioni piu' vecchie non accettano argomenti opzionali.
        page.apply_redactions()


def _normalize_annotation(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise PdfOverlayError("Annotazione PDF non valida.")
    kind = str(raw.get("type") or "").strip().lower()
    if kind not in {"text", "highlight", "cover", "replace", "rotate", "image"}:
        raise PdfOverlayError("Tipo modifica PDF non supportato.")
    page = _int(raw.get("page"), "Pagina PDF non valida.")
    if kind == "rotate":
        if raw.get("degrees") not in {-270, -180, -90, 90, 180, 270}:
            raise PdfOverlayError("Rotazione della pagina non valida.")
        return {"type": kind, "page": page, "degrees": int(raw["degrees"])}
    x = _ratio(raw.get("x"), "Coordinata X non valida.")
    y = _ratio(raw.get("y"), "Coordinata Y non valida.")
    annotation: dict[str, Any] = {
        "type": kind,
        "page": page,
        "x": x,
        "y": y,
        "color": _color(raw.get("color"), "#111827"),
        "fillColor": _color(raw.get("fillColor"), "#fef3c7"),
    }
    if kind == "image":
        from web.services.viewer_image_objects import normalize_image
        return {**annotation, **normalize_image(raw)}
    if kind in {"text", "replace"}:
        text = str(raw.get("text") or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if not text:
            raise PdfOverlayError("Il testo da applicare al PDF è vuoto.")
        if len(text) > 1200:
            raise PdfOverlayError("Il testo della modifica PDF è troppo lungo.")
        annotation["text"] = text
        annotation["listStyle"] = raw.get("listStyle", "none")
        if annotation["listStyle"] not in {"none", "bullet", "number"}:
            raise PdfOverlayError("Tipo di elenco non valido.")
        annotation["lineHeightPt"] = min(100.0, max(annotation.get("fontSizePt", 6.0), _float(raw.get("lineHeightPt"), _float(raw.get("fontSizePt"), 12.0) * 1.2)))
        annotation["fontSizePt"] = min(max(_float(raw.get("fontSizePt"), 12.0), 6.0), 48.0)
        family = str(raw.get("fontFamily") or "helvetica")
        fonts = {"helvetica": ("helv", "hebo", "heit", "hebi"), "times": ("tiro", "tibo", "tiit", "tibi"), "courier": ("cour", "cobo", "coit", "cobi")}
        if family not in fonts or raw.get("align", "left") not in {"left", "center", "right"}:
            raise PdfOverlayError("Formattazione del testo non valida.")
        annotation["fontName"] = fonts[family][int(raw.get("bold") is True) + 2 * int(raw.get("italic") is True)]
        annotation["underline"] = raw.get("underline") is True
        annotation["align"] = raw.get("align", "left")
        if raw.get("rotation", 0) not in set(range(0, 360, 45)):
            raise PdfOverlayError("Rotazione del testo non valida.")
        annotation["rotation"] = int(raw.get("rotation", 0))
        if kind == "replace":
            try:
                annotation["span"] = int(raw["span"])
            except (KeyError, TypeError, ValueError, OverflowError):
                raise PdfOverlayError("Seleziona il testo originale da modificare.") from None
            if annotation["span"] < 0 or "\n" in text:
                raise PdfOverlayError("La modifica deve riguardare una singola riga di testo selezionata.")
    else:
        annotation["width"] = min(max(_float(raw.get("width"), 0.2), 0.01), 1.0)
        annotation["height"] = min(max(_float(raw.get("height"), 0.04), 0.01), 1.0)
    return annotation


def _apply_annotation(page: fitz.Page, annotation: dict[str, Any]) -> None:
    width = float(page.rect.width)
    height = float(page.rect.height)
    x = width * float(annotation["x"])
    y = height * float(annotation["y"])
    kind = str(annotation["type"])
    if kind == "image":
        from web.services.viewer_image_objects import insert_image
        insert_image(page, annotation)
        return
    if kind == "text":
        from web.services.viewer_image_objects import text_lines
        text = text_lines(annotation)
        size = float(annotation["fontSizePt"])
        font = annotation["fontName"]
        lines = text.splitlines()
        leading = annotation["lineHeightPt"]
        lengths = [fitz.get_text_length(line, fontname=font, fontsize=size) for line in lines]
        longest = max(lengths, default=0)
        align = annotation["align"]
        left = x - (longest / 2 if align == "center" else longest if align == "right" else 0)
        rotation = annotation["rotation"]
        matrix = fitz.Matrix(1, 1).prerotate(-rotation)
        box = fitz.Rect(left-x,-size,left-x+longest,(len(lines)-1)*leading+size*.3) * matrix
        box += (x,y,x,y)
        if box.x0 < 0 or box.x1 > width or box.y0 < 0 or box.y1 > height:
            raise PdfOverlayError("Il testo supera il bordo della pagina. Spostalo o riduci la dimensione.")
        if any(not fitz.Font(fontname=font).has_glyph(ord(char)) for char in text if char != "\n"):
            raise PdfOverlayError("Il carattere scelto non supporta tutti i simboli del testo.")
        for index, (line, length) in enumerate(zip(lines, lengths)):
            line_x = x - (length / 2 if align == "center" else length if align == "right" else 0)
            relative = fitz.Point(line_x-x,index*leading) * matrix
            point = fitz.Point(x+relative.x,y+relative.y) * page.derotation_matrix
            _insert_span(page, point, line, font, size, _rgb(annotation["color"]), (rotation+page.rotation)%360)
            if annotation["underline"] and length:
                start = fitz.Point(line_x-x,index*leading+size*.12) * matrix
                end = fitz.Point(line_x-x+length,index*leading+size*.12) * matrix
                page.draw_line(fitz.Point(x+start.x,y+start.y)*page.derotation_matrix,fitz.Point(x+end.x,y+end.y)*page.derotation_matrix,color=_rgb(annotation["color"]),width=max(.5,size*.05),overlay=True)
        return

    rect = fitz.Rect(
        x,
        y,
        min(width, x + width * float(annotation["width"])),
        min(height, y + height * float(annotation["height"])),
    )
    rect = rect * page.derotation_matrix
    if kind == "cover":
        # Oscuramento vero: si marca l'area e il contenuto sotto viene tolto
        # dalla pagina quando si applicano le redazioni. Un rettangolo disegnato
        # sopra lascerebbe il testo nel file, recuperabile con un copia-incolla.
        page.add_redact_annot(rect, fill=(1.0, 1.0, 1.0))
        return
    page.draw_rect(rect, color=None, fill=_rgb(annotation["fillColor"]), fill_opacity=0.35, overlay=True)


def _int(value: Any, message: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        raise PdfOverlayError(message) from None
    if parsed < 1:
        raise PdfOverlayError(message)
    return parsed


def _float(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(parsed):
        raise PdfOverlayError("Numero non valido nella modifica PDF.")
    return parsed


def _ratio(value: Any, message: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise PdfOverlayError(message) from None
    if not math.isfinite(parsed) or parsed < 0 or parsed > 1:
        raise PdfOverlayError(message)
    return parsed


def _color(value: Any, default: str) -> str:
    raw = str(value or default).strip()
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", raw):
        return default
    return raw.lower()


def _rgb(value: str) -> tuple[float, float, float]:
    hex_value = _color(value, "#111827").lstrip("#")
    return (
        int(hex_value[0:2], 16) / 255.0,
        int(hex_value[2:4], 16) / 255.0,
        int(hex_value[4:6], 16) / 255.0,
    )


def _editable_spans(page):
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            direction = line.get("dir", (1, 0))
            angle = math.degrees(math.atan2(-direction[1], direction[0])) % 360
            rotation = round(angle / 45) * 45 % 360
            if abs((angle - rotation + 180) % 360 - 180) > .01:
                continue
            for span in line.get("spans", []):
                if str(span.get("text", "")).strip():
                    spans.append({**span, "rotation": rotation})
    return spans


def pdf_text_spans(pdf_bytes: bytes, page_number: int) -> list[dict]:
    """Testo digitale selezionabile nell'editor, senza OCR o ricostruzioni."""
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if doc.is_encrypted or not 1 <= page_number <= len(doc):
            raise PdfOverlayError("Pagina di testo non disponibile.")
        page = doc[page_number - 1]
        result = []
        for i, span in enumerate(_editable_spans(page)):
            area = fitz.Rect(span["bbox"]) * page.rotation_matrix
            result.append({"id": i, "text": span["text"], "x": area.x0 / page.rect.width,
                           "y": area.y0 / page.rect.height, "width": area.width / page.rect.width,
                           "height": area.height / page.rect.height})
        return result


def _prepare_replacement(page, annotation):
    spans = _editable_spans(page)
    if annotation["span"] >= len(spans):
        raise PdfOverlayError("Il testo selezionato non è più disponibile: riapri la pagina.")
    span = spans[annotation["span"]]
    area = fitz.Rect(span["bbox"])
    font, font_metrics = _original_font(page, span)
    size = float(span["size"])
    replacement = annotation["text"]
    if any(not font_metrics.has_glyph(ord(char), fallback=False) for char in replacement):
        raise PdfOverlayError("Il testo contiene caratteri non supportati dal carattere della riga.")
    rotation = span["rotation"]
    available_length = font_metrics.text_length(span["text"], fontsize=size)
    if rotation == 0:
        available_length = _available_line_width(page, span, spans)

    if font_metrics.text_length(replacement, fontsize=size) > available_length + 0.5:
        raise PdfOverlayError("Il nuovo testo richiede un ritorno a capo oltre il margine del documento. La riga non viene troncata; modifica il documento sorgente nell’editor finché l’impaginazione automatica non è disponibile.")
    # Il rettangolo centrale intercetta le lettere della riga senza invadere
    # le righe adiacenti quando i bounding box tipografici si sovrappongono.
    if rotation in {0, 180}:
        area.y0 += area.height * .2
        area.y1 -= area.height * .2
    elif rotation in {90, 270}:
        area.x0 += area.width * .2
        area.x1 -= area.width * .2
    color = int(span.get("color", 0))
    rgb = ((color >> 16 & 255) / 255, (color >> 8 & 255) / 255, (color & 255) / 255)
    return page, area, fitz.Point(span["origin"]), replacement, font, size, rgb, rotation, span


def _original_font(page, span):
    name = str(span.get("font", "")).casefold()
    bold, italic = "bold" in name, any(word in name for word in ("italic", "oblique"))
    family = "times" if any(word in name for word in ("times", "serif")) else "courier" if "courier" in name else "helvetica"
    fonts = {"times": ("tiro", "tibo", "tiit", "tibi"), "courier": ("cour", "cobo", "coit", "cobi"), "helvetica": ("helv", "hebo", "heit", "hebi")}
    font = fonts[family][int(bold) + 2 * int(italic)]
    font_metrics = fitz.Font(fontname=font)
    original_font_available = name in {"helvetica", "helvetica-bold", "helvetica-oblique", "helvetica-boldoblique", "times-roman", "times-bold", "times-italic", "times-bolditalic", "courier", "courier-bold", "courier-oblique", "courier-boldoblique"}
    normalize = lambda value: str(value).split("+")[-1].casefold().replace("-", "").replace(" ", "")
    for record in page.get_fonts(full=True):
        if normalize(record[3]) != normalize(span.get("font", "")):
            continue
        _, _, _, buffer = page.parent.extract_font(record[0])
        if buffer:
            font_metrics = fitz.Font(fontbuffer=buffer)
            font = f"iusentraedit{record[0]}"
            page.insert_font(fontname=font, fontbuffer=buffer)
            original_font_available = True
        break
    if not original_font_available:
        raise PdfOverlayError("Il carattere originale non è incorporato nel PDF. Per conservarne l’aspetto modifica il documento sorgente nell’editor.")
    return font, font_metrics


def _retain_intersecting_characters(page, replacements):
    """Conserva i glifi di altri testi incrociati dall'area sostituita.

    Le origini dei singoli glifi conservano posizione e spaziatura originali.
    La redazione privacy resta separata e non viene mai ricostruita.
    """
    retained = []
    targets = [item[-1] for item in replacements]
    for block in page.get_text("rawdict")["blocks"]:
        for line in block.get("lines", []):
            direction = line.get("dir", (1, 0))
            angle = math.degrees(math.atan2(-direction[1], direction[0])) % 360
            rotation = round(angle / 45) * 45 % 360
            for span in line.get("spans", []):
                chars = span.get("chars", [])
                text = "".join(char["c"] for char in chars)
                if any(span["origin"] == target["origin"] and text == target["text"]
                       for target in targets):
                    continue
                touched = [char for char in chars if any(
                    fitz.Rect(char["bbox"]).intersects(item[1]) for item in replacements)]
                if not touched:
                    continue
                if abs((angle - rotation + 180) % 360 - 180) > .01:
                    raise PdfOverlayError("La selezione incrocia un altro testo inclinato: modifica il documento sorgente per conservarlo.")
                font, _ = _original_font(page, span)
                color = int(span.get("color", 0))
                rgb = ((color >> 16 & 255) / 255, (color >> 8 & 255) / 255, (color & 255) / 255)
                for char in touched:
                    retained.append((fitz.Point(char["origin"]), char["c"], font,
                                     float(span["size"]), rgb, rotation))
    return retained


def _removed_characters(page, retained):
    """Ripristina solo i glifi effettivamente rimossi dal motore PDF.

    Il riquadro geometrico può toccare un glifo senza che il motore lo rimuova.
    Il confronto impedisce di disegnarlo due volte nella stessa posizione.
    """
    from collections import Counter
    def key(text, origin, size, color):
        return text, tuple(round(n, 3) for n in origin), round(size, 3), color
    remaining = Counter(key(char["c"], char["origin"], span["size"], span.get("color", 0))
        for block in page.get_text("rawdict")["blocks"] for line in block.get("lines", [])
        for span in line["spans"] for char in span.get("chars", []))
    for record in retained:
        origin, text, _, size, rgb, _ = record
        color = sum(round(channel * 255) << shift for channel, shift in zip(rgb, (16, 8, 0)))
        identity = key(text, origin, size, color)
        if remaining[identity]:
            remaining[identity] -= 1
        else:
            yield record


def _available_line_width(page, selected, spans):
    """Spazio effettivo fino al margine e prima di altri testi sulla riga.

    I margini osservati nella pagina prevalgono sulla larghezza del vecchio testo.
    Nessuna espansione può invadere un altro campo o oltrepassare il foglio.
    """
    horizontal = [fitz.Rect(span["bbox"]) for span in spans if span["rotation"] == 0]
    area = fitz.Rect(selected["bbox"])
    left = min((rect.x0 for rect in horizontal), default=area.x0)
    right = min(page.cropbox.width, max(page.cropbox.width - max(0, left),
                                       max((rect.x1 for rect in horizontal), default=area.x1)))
    for other in spans:
        if other is selected:
            continue
        rect = fitz.Rect(other["bbox"])
        if rect.x0 >= area.x1 and min(rect.y1, area.y1) > max(rect.y0, area.y0):
            right = min(right, rect.x0)
    return max(area.width, right - float(selected["origin"][0]))


def _insert_span(page, origin, text, font, size, color, rotation):
    if rotation % 90 == 0:
        page.insert_text(origin, text, fontname=font, fontsize=size, color=color, rotate=rotation)
    else:
        page.insert_text(origin, text, fontname=font, fontsize=size, color=color,
                         morph=(origin, fitz.Matrix(rotation)))
