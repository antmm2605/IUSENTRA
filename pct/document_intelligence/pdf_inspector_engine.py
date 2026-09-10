"""Offline PDF reading with page-level quality checks and small-box recovery.

No network fallback, modification of source bytes or inference of missing values.
Tesseract remains a local specialist for short boxed fields, not a second catalog.
"""
from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path

ENGINE_VERSION = 'pdf-inspector:1.17.0:iusentra-v2'


def _unwrap_markdown_link(match: 're.Match[str]') -> str:
    """Un collegamento Markdown torna testo leggibile senza perdere l'indirizzo.

    L'estrattore rende gli indirizzi come `[url](url)`. Lasciarli intatti
    significa che chi cerca l'indirizzo nel testo ne raccoglie anche la
    seconda copia e le parentesi, e il collegamento all'udienza finisce
    inutilizzabile in agenda e scadenziario.
    """

    etichetta = (match.group(1) or '').strip()
    indirizzo = (match.group(2) or '').strip()
    if not indirizzo:
        return etichetta
    if not etichetta or etichetta == indirizzo:
        return indirizzo
    return f'{etichetta} ({indirizzo})'


def plain_markdown(text: str) -> str:
    """Keep headings as text for existing catalogue contracts, not Markdown syntax."""
    text = re.sub(r'(?m)^#{1,6}\s+', '', text)
    text = re.sub(r'\*\*([^*\n]+)\*\*', r'\1', text)
    text = re.sub(r'</?u>', '', text)
    #  `[etichetta](indirizzo)`, comprese le forme annidate prodotte
    #  dall'estrattore per gli indirizzi gia' scritti per esteso.
    text = re.sub(r'\[([^\]\n]*)\]\(\s*([^)\s]*)\s*\)', _unwrap_markdown_link, text)
    return text.strip()


def duplicated_glyphs(text: str) -> bool:
    """Repeated overprinted glyph pairs, not ordinary doubled Italian letters."""
    return len(re.findall(r'(?:([A-Za-z])\1){4,}', text)) >= 2


def _image_pdf(image, dpi: float = 216.0) -> bytes:
    stream = BytesIO()
    image.convert('RGB').save(stream, format='PDF', resolution=dpi)
    return stream.getvalue()


def _boxed_regions_with_pillow(image) -> list[tuple[int, int, int, int]]:
    """Detect simple printed rectangles when OpenCV is not available locally."""
    gray = image.convert('L')
    width, height = gray.size
    dark_threshold = 80
    minimum_horizontal_ink = max(24, int(width * .065))
    rows: list[tuple[int, int, int]] = []
    pixels = gray.load()
    for y in range(height):
        xs = [x for x in range(width) if pixels[x, y] < dark_threshold]
        if len(xs) >= minimum_horizontal_ink:
            rows.append((y, min(xs), max(xs)))
    if not rows:
        return []

    groups: list[tuple[int, int, int, int]] = []
    start_y, end_y, min_x, max_x = rows[0][0], rows[0][0], rows[0][1], rows[0][2]
    for y, left, right in rows[1:]:
        if y <= end_y + 2:
            end_y = y
            min_x = min(min_x, left)
            max_x = max(max_x, right)
            continue
        groups.append((start_y, end_y, min_x, max_x))
        start_y, end_y, min_x, max_x = y, y, left, right
    groups.append((start_y, end_y, min_x, max_x))

    boxes: list[tuple[int, int, int, int]] = []
    for index, top in enumerate(groups):
        for bottom in groups[index + 1:index + 8]:
            y1, _top_end, x1, x2 = top
            _bottom_start, y2, bx1, bx2 = bottom
            box_width = max(x2, bx2) - min(x1, bx1) + 1
            box_height = y2 - y1 + 1
            if not (width * .04 < box_width < width * .38 and 15 < box_height < height * .055 and 1.4 < box_width / box_height < 15):
                continue
            candidate = (min(x1, bx1), y1, box_width, box_height)
            if any(abs(candidate[0] - x) < 12 and abs(candidate[1] - y) < 12 for x, y, _, _ in boxes):
                continue
            boxes.append(candidate)
            break
    return boxes


def _boxed_regions(image) -> list[tuple[int, int, int, int]]:
    try:
        import cv2
        import numpy as np
    except ModuleNotFoundError:
        return _boxed_regions_with_pillow(image)

    gray = cv2.cvtColor(np.asarray(image.convert('RGB')), cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    height, width = gray.shape
    boxes: list[tuple[int, int, int, int]] = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if not (width * .04 < w < width * .38 and 15 < h < height * .055 and 1.4 < w / h < 15):
            continue
        polygon = cv2.approxPolyDP(contour, .025 * cv2.arcLength(contour, True), True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon) or cv2.contourArea(contour) < w * h * .70:
            continue
        if any(abs(x-a) < 12 and abs(y-b) < 12 for a, b, _, _ in boxes):
            continue
        boxes.append((x, y, w, h))
    return boxes


def _visible_ink_ratio(image) -> float:
    gray = image.convert('L')
    total = gray.width * gray.height
    if not total:
        return 0.0
    return sum(1 for value in gray.tobytes() if value < 110) / total


def _small_box_values(image, existing: str) -> tuple[list[str], list[str]]:
    """Recover short printed values in detected quadrilateral boxes.

    Coordinates accompany additions so consumers cannot silently attach a value
    to the wrong field. No filename, client or expected value is used.
    """
    import pytesseract
    from PIL import ImageOps

    width, height = image.size
    boxes = _boxed_regions(image)
    additions, warnings = [], []
    for x, y, w, h in sorted(boxes, key=lambda box: (box[1], box[0])):
        inner = image.crop((x+6, y+6, x+w-6, y+h-6)).convert('RGB')
        # Empty table cells must not generate invented characters or OCR work.
        if _visible_ink_ratio(inner) < .025:
            continue
        enlarged = ImageOps.expand(inner.resize((inner.width*3, inner.height*3)), border=35, fill='white')
        try:
            data = pytesseract.image_to_data(enlarged, lang='ita', config='--psm 7', output_type=pytesseract.Output.DICT, timeout=15)
        except RuntimeError:
            warnings.append(f'Riquadro alla posizione {x/width:.3f}, {y/height:.3f}: lettura non riuscita, controllare nell’originale.')
            continue
        tokens = [(str(t).strip(), float(c)) for t, c in zip(data['text'], data['conf']) if str(t).strip()]
        if not tokens:
            continue
        value = ' '.join(t for t, _ in tokens)
        # Restrict to short numerical fields. Longer content is read by the main engine.
        if not re.fullmatch(r'\d[\d.,/\- ]{0,23}', value) or min(c for _, c in tokens) < 75:
            continue
        if re.search(r'(?<!\w)' + re.escape(value) + r'(?!\w)', existing):
            continue
        position = f'{x/width:.3f},{y/height:.3f},{w/width:.3f},{h/height:.3f}'
        additions.append(f'Valore letto nel riquadro ({position}): {value}')
    return additions, warnings


def extract_pdf_inspected(content: bytes):
    from .extraction import ExtractionResult
    from .models import DocumentAIPageText
    from .pdf_quality import has_only_signature_text

    pages, warnings = [], []
    try:
        import pdf_inspector
        import pdfplumber
        import pypdfium2

        bundled = Path('/opt/iusentra/ocr')
        if bundled.is_dir():
            os.environ.setdefault('PDFIUM_LIB_PATH', str(bundled / 'pdfium/lib/libpdfium.so'))
            os.environ.setdefault('ORT_DYLIB_PATH', str(bundled / 'onnx/onnxruntime-linux-x64-1.27.0/lib/libonnxruntime.so.1.27.0'))
        options = {'offline': True}
        model_dir = os.environ.get('IUSENTRA_PDF_OCR_MODEL_DIR') or (str(bundled / 'models') if bundled.is_dir() else '')
        if model_dir:
            options['model_directory'] = model_dir
        # The native quality probe is separate from OCR confidence and legal classification.
        with pdfplumber.open(BytesIO(content)) as native, pypdfium2.PdfDocument(content) as rendered:
            if len(native.pages) != len(rendered):
                raise ValueError('Numero di pagine non coerente tra i lettori PDF.')
            if any(p.width * p.height * 9 > 35_000_000 for p in native.pages):
                raise ValueError('Pagina troppo grande per il controllo OCR sicuro.')
            result = pdf_inspector.process_pdf_with_ocr_bytes(content, **options)
            if [p.page_number for p in result.pages] != list(range(1, len(native.pages)+1)):
                raise ValueError('La lettura non ha restituito tutte le pagine in ordine.')
            for page_number, (source, page_result) in enumerate(zip(native.pages, result.pages), 1):
                raw = source.extract_text() or ''
                corrupt = duplicated_glyphs(raw) or len(re.findall(r'\(cid:\d+\)', raw)) >= 2
                text = page_result.markdown
                needs_image = corrupt or page_number in result.pages_routed_to_ocr or has_only_signature_text(raw)
                page = bitmap = None
                try:
                    if needs_image:
                        page = rendered[page_number-1]
                        if page.get_width() * page.get_height() * 9 > 35_000_000:
                            raise ValueError('Pagina troppo grande per il controllo OCR sicuro.')
                        bitmap = page.render(scale=3)
                        image = bitmap.to_pil().convert('RGB')
                        if corrupt or (has_only_signature_text(raw) and page_number not in result.pages_routed_to_ocr):
                            reread = pdf_inspector.process_pdf_with_ocr_bytes(_image_pdf(image), mode='force', dpi=216.0, **options)
                            if len(reread.pages) != 1:
                                raise ValueError('Rilettura della pagina incompleta.')
                            text = reread.markdown
                            warnings.append(f'Pagina {page_number}: livello testuale non affidabile escluso dalla lettura; originale invariato.')
                        additions, box_warnings = _small_box_values(image, text)
                        if additions:
                            text += '\n\n' + '\n'.join(additions)
                            warnings.append(f'Pagina {page_number}: recuperati valori da riquadri; posizione riportata nel testo per verifica.')
                        warnings.extend(f'Pagina {page_number}: {w}' for w in box_warnings)
                    if page_number in result.pages_recommending_hosted:
                        warnings.append(f'Pagina {page_number}: lettura incerta, verificare l’originale; nessun invio a servizi esterni.')
                    pages.append(DocumentAIPageText(page_number=page_number, text=plain_markdown(text)))
                finally:
                    if bitmap is not None:
                        bitmap.close()
                    if page is not None:
                        page.close()
        full_text = '\n\n'.join(p.text for p in pages)
        return ExtractionResult(ok=bool(full_text.strip()), text=full_text, pages=pages,
                                extraction_engine=ENGINE_VERSION, warnings=warnings,
                                error_code='' if full_text.strip() else 'pdf_ocr_empty')
    except Exception as exc:
        # No silent success or remote fallback on an unavailable OCR runtime.
        return ExtractionResult(ok=False, text='', pages=[], extraction_engine=ENGINE_VERSION,
                                warnings=warnings, error_code='pdf_inspector_failed',
                                error_message=f'Lettura PDF non completata: {exc}')
