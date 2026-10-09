"""Offline PDF reading with page-level quality checks and small-box recovery.

No network fallback, modification of source bytes or inference of missing values.
Tesseract remains a local specialist for short boxed fields, not a second catalog.
"""
from __future__ import annotations

import os
import re
from io import BytesIO
from pathlib import Path

ENGINE_VERSION = 'pdf-inspector:1.17.0:iusentra-v8-identita-fonte-nativa-copertina'


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


def _identity_value_signature(text: str) -> dict[str, set[str]]:
    """Soli valori letterali per rilevare regressioni, non per certificarli.

    Non corregge caratteri e non associa carte o persone. I valori mancanti
    o discordanti impediscono che una variante sostituisca la prima lettura.
    """
    source = plain_markdown(text).upper()
    dates = {f'{int(day):02}/{int(month):02}/{year}' for day, month, year in
             re.findall(r'(?<!\d)(\d{1,2})[./-](\d{1,2})[./-](\d{4})(?!\d)', source)}
    values = {
        'date': dates,
        'numero_documento': set(re.findall(r'\b(?:[A-Z]{2}\d{7}|[A-Z]{2}\d{5}[A-Z]{2})\b', source)),
        'codice_fiscale': set(re.findall(r'\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}'
                                       r'[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b', source)),
    }
    for field, label in (('cognome', 'COGNOME|SURNAME'), ('nome', 'NOME|NAME')):
        found = re.findall(r'(?m)^[ \t]*(?:' + label + r')[ .:]*(?:/[ \t]*(?:' + label + r'))?'
                           r'[ \t]*(?:\n[ \t]*)?([A-ZÀ-Ü][A-ZÀ-Ü \'’.-]{1,60})[ \t]*$', source)
        # Alcuni lettori rendono tutta la carta su una sola riga. La prossima
        # etichetta delimita il valore; non indovinare dove termina un nome.
        found += re.findall(r'\b(?:' + label + r')[ .:]*(?:/[ \t]*(?:' + label + r'))?'
                            r'[ \t]+([A-ZÀ-Ü][A-ZÀ-Ü \'’.-]{1,60}?)'
                            r'(?=[ \t]+(?:COGNOME|SURNAME|NOME|NAME|NASCITA|BIRTH|SESSO|SEX|'
                            r'COMUNE|RESIDENZA|EMISSIONE|SCADENZA|DOCUMENTO|CITTADINANZA)\b|\n|$)', source)
        values[field] = {re.sub(r'\s+', ' ', value).strip(' .:') for value in found
                         if not re.search(r'\b(?:COGNOME|SURNAME|NOME|NAME|NASCITA|BIRTH|SEX|SESSO)\b', value)}
    return values


def _identity_page_read(image, *, inspector, options):
    """Prepara prima dell'OCR, poi confronta soltanto i pixel cambiati.

    Il secondo risultato non viene mai fuso con il primo. Restituisce anche
    una copia dell'originale orientata per i recuperi locali: le coordinate
    della variante rettificata non vengono applicate ai pixel originali.
    """
    from legal_ocr.motore.preparazione_identita import prepara_riquadro_identita
    from pct.document_intelligence.catalog_identita_personale import modello_identita_italiana

    prepared = prepara_riquadro_identita(image)
    original = image.rotate(prepared.orientamento, expand=True) if prepared.orientamento else image.copy()
    audit = list(prepared.passaggi)

    def read(candidate):
        result = inspector.process_pdf_with_ocr_bytes(
            _image_pdf(candidate, dpi=216.0), mode='force', dpi=216.0, **options)
        if [page.page_number for page in result.pages] != [1]:
            raise ValueError('Lettura della pagina preparata incompleta.')
        page_result = result.pages[0]
        confidence = float(getattr(getattr(page_result, 'provenance', None), 'ocr_confidence', 0.0) or 0.0)
        return plain_markdown(page_result.markdown), confidence, bool(result.pages_recommending_hosted)

    try:
        selected, confidence, uncertain = read(prepared.immagine)
        changed = (prepared.immagine.size != original.size
                   or prepared.immagine.tobytes() != original.tobytes())
        if changed:
            baseline, baseline_confidence, baseline_uncertain = read(original)
            before, after = _identity_value_signature(baseline), _identity_value_signature(selected)
            lost = [field for field in before if not before[field].issubset(after[field])]
            original_model, candidate_model = modello_identita_italiana(baseline), modello_identita_italiana(selected)
            improves = (bool(selected.strip()) and confidence > baseline_confidence
                        and len(selected.strip()) >= len(baseline.strip()) * .85
                        and (not original_model or candidate_model == original_model) and not lost)
            if improves:
                audit.append('Confronto puntuale con l’originale orientato: variante mantenuta senza '
                             'perdita dei valori letterali riscontrati; campi ancora soggetti a verifica.')
            else:
                selected, uncertain = baseline, baseline_uncertain
                reason = 'valori discordanti o non più letti' if lost else 'nessun miglioramento concordante'
                audit.append(f'Variante preparata scartata: {reason}; conservata la lettura '
                             'dell’originale orientato, senza fusione dei testi.')
        else:
            audit.append('Pixel invariati dopo la diagnosi: nessuna seconda lettura globale.')
        return selected, original, audit, uncertain
    except Exception:
        original.close()
        raise
    finally:
        prepared.immagine.close()


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

    from legal_ocr.motore.errori import ErroreLettura
    from legal_ocr.motore.lettura import leggi_testo

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
            # Una riga sola (psm 7) letta dal motore unico dello studio.
            parole = leggi_testo(enlarged, pytesseract=pytesseract, opzioni='--oem 1 --psm 7', timeout=15)
        except (RuntimeError, ErroreLettura):
            warnings.append(f'Riquadro alla posizione {x/width:.3f}, {y/height:.3f}: lettura non riuscita, controllare nell’originale.')
            continue
        tokens = [(str(p.get('text') or '').strip(), float(p.get('conf') or 0.0) * 100) for p in parole if str(p.get('text') or '').strip()]
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


def extract_pdf_inspected(content: bytes, *, identity_scan: bool = False):
    from .extraction import ExtractionResult
    from .models import DocumentAIPageText
    from .pdf_quality import has_only_signature_text

    pages, warnings, identity_recoveries, identity_sources = [], [], [], []
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
            # Nel comando identità la prima sonda legge soltanto il livello
            # nativo. Nessun OCR dei dati precede la preparazione dei pixel.
            result = (pdf_inspector.extract_pages_markdown_bytes(content) if identity_scan
                      else pdf_inspector.process_pdf_with_ocr_bytes(content, **options))
            returned = ([p.page + 1 for p in result.pages] if identity_scan
                        else [p.page_number for p in result.pages])
            if returned != list(range(1, len(native.pages)+1)):
                raise ValueError('La lettura non ha restituito tutte le pagine in ordine.')
            for page_number, (source, page_result) in enumerate(zip(native.pages, result.pages), 1):
                raw = source.extract_text() or ''
                corrupt = duplicated_glyphs(raw) or len(re.findall(r'\(cid:\d+\)', raw)) >= 2
                text = page_result.markdown
                primary_text = text
                routed = (page_result.needs_ocr if identity_scan else page_number in result.pages_routed_to_ocr)
                needs_image = corrupt or routed or has_only_signature_text(raw)
                uncertain = False if identity_scan else page_number in result.pages_recommending_hosted
                page = bitmap = image = None
                try:
                    if needs_image:
                        page = rendered[page_number-1]
                        if page.get_width() * page.get_height() * 9 > 35_000_000:
                            raise ValueError('Pagina troppo grande per il controllo OCR sicuro.')
                        bitmap = page.render(scale=3)
                        image = bitmap.to_pil().convert('RGB')
                        if identity_scan:
                            text, original_oriented, preparation_audit, uncertain = _identity_page_read(
                                image, inspector=pdf_inspector, options=options)
                            image.close()
                            image = original_oriented
                            warnings.extend(f'Pagina {page_number}: {step}' for step in preparation_audit)
                        else:
                            import pytesseract
                            from legal_ocr.motore.immagine import orienta_testo
                            source_image = image
                            image, orientation = orienta_testo(source_image, pytesseract=pytesseract)
                            if image is not source_image:
                                source_image.close()
                            warnings.append(f'Pagina {page_number}: orientamento-v1, rotazione di lettura {orientation}°; originale invariato.')
                            if orientation or corrupt or (has_only_signature_text(raw) and not routed):
                                reread = pdf_inspector.process_pdf_with_ocr_bytes(_image_pdf(image), mode='force', dpi=216.0, **options)
                                if len(reread.pages) != 1:
                                    raise ValueError('Rilettura della pagina incompleta.')
                                text = reread.markdown
                                warnings.append(f'Pagina {page_number}: livello testuale non affidabile escluso dalla lettura; originale invariato.')
                        primary_text = text
                        additions, box_warnings = _small_box_values(image, text)
                        if additions:
                            text += '\n\n' + '\n'.join(additions)
                            warnings.append(f'Pagina {page_number}: recuperati valori da riquadri; posizione riportata nel testo per verifica.')
                        warnings.extend(f'Pagina {page_number}: {w}' for w in box_warnings)
                    if identity_scan:
                        # Il testo OCR esplorativo non acquisisce la qualifica
                        # dei recuperi che vengono aggiunti alla pagina dopo.
                        identity_sources.append({'page_number': page_number,
                                                 'mode': 'ocr' if needs_image else 'native',
                                                 'text': plain_markdown(primary_text)})
                    if identity_scan and len(native.pages) <= 4:
                        from legal_ocr.motore.identita import recupera_residenza_cartacea, recupera_titolare_cartacea
                        from pct.document_intelligence.catalog_identita_personale import segmenti_identita_italiana
                        if any(s['model'] == 'carta_cartacea' for s in segmenti_identita_italiana(plain_markdown(text))) and page is not None:
                            paper_source = plain_markdown(text)
                            holder_text, holder_audit = recupera_titolare_cartacea(image, paper_source)
                            holder_pixel_source = 'rendered_page'
                            if not holder_text:
                                from legal_ocr.motore.copertina_cartacea import copertina_cartacea_applicabile
                                if copertina_cartacea_applicabile(paper_source):
                                    from legal_ocr.motore.fonte_identita import immagine_nativa_copertina
                                    native_image, native_audit = immagine_nativa_copertina(content, page_number - 1)
                                    holder_audit.extend(native_audit)
                                    if native_image is not None:
                                        try:
                                            native_holder, native_holder_audit = recupera_titolare_cartacea(native_image, paper_source)
                                            holder_audit.extend(native_holder_audit)
                                            if native_holder:
                                                holder_text = native_holder
                                                holder_pixel_source = 'pdf_native_image'
                                                holder_audit.append('Copertina cartacea: titolare riscontrato sui pixel nativi; '
                                                                    'prima lettura e altri campi preservati.')
                                        finally:
                                            native_image.close()
                            if holder_text:
                                text += '\n\n' + holder_text
                                identity_recoveries.append(DocumentAIPageText(page_number=page_number, text=holder_text))
                                holder_source = {'page_number': page_number, 'mode': 'recovery',
                                                 'text': plain_markdown(holder_text)}
                                if holder_pixel_source == 'pdf_native_image':
                                    holder_source['pixel_source'] = holder_pixel_source
                                identity_sources.append(holder_source)
                            warnings.extend(f'Pagina {page_number}: {w}' for w in holder_audit)
                            # I recuperi indipendenti ricevono la medesima
                            # fonte: aggiungere un'intestazione qualificata
                            # non deve simulare una seconda carta nel parser.
                            address_text, address_audit = recupera_residenza_cartacea(image, paper_source)
                            if address_text:
                                text += '\n\n' + address_text
                                identity_sources.append({'page_number': page_number, 'mode': 'recovery',
                                                         'text': plain_markdown(address_text)})
                            warnings.extend(f'Pagina {page_number}: {w}' for w in address_audit)
                        from legal_ocr.motore.mrz import righe_td1_complete
                        # La MRZ non contiene CF e residenza. Una MRZ leggibile
                        # non esonera dal recupero puntuale delle zone stampate.
                        visible = plain_markdown(text)
                        if (not righe_td1_complete(visible)
                                or not re.search(r'\b(?:CODICE\s+FISCALE|FISCAL\s+CODE)\b', visible, re.I)
                                or not re.search(r'\b(?:RESIDENZA|RESIDENCE|ADDRESS)\b', visible, re.I)):
                            from legal_ocr.motore.identita import recupera_mrz_carta
                            if page is None:
                                page = rendered[page_number - 1]
                                bitmap = page.render(scale=3)
                                image = bitmap.to_pil().convert('RGB')
                            recovered, recovery_warnings = recupera_mrz_carta(image)
                            if recovered:
                                text += '\n\n' + recovered
                                identity_recoveries.append(DocumentAIPageText(page_number=page_number, text=recovered))
                                identity_sources.append({'page_number': page_number, 'mode': 'recovery',
                                                         'text': plain_markdown(recovered)})
                            warnings.extend(f'Pagina {page_number}: {warning}' for warning in recovery_warnings)
                    if uncertain:
                        warnings.append(f'Pagina {page_number}: lettura incerta, verificare l’originale; nessun invio a servizi esterni.')
                    pages.append(DocumentAIPageText(page_number=page_number, text=plain_markdown(text),
                        identity_sources=[dict(item) for item in identity_sources if item['page_number'] == page_number]))
                finally:
                    if image is not None:
                        image.close()
                    if bitmap is not None:
                        bitmap.close()
                    if page is not None:
                        page.close()
        full_text = '\n\n'.join(p.text for p in pages)
        return ExtractionResult(ok=bool(full_text.strip()), text=full_text, pages=pages,
                                extraction_engine=ENGINE_VERSION, warnings=warnings, identity_recoveries=identity_recoveries,
                                identity_sources=identity_sources,
                                error_code='' if full_text.strip() else 'pdf_ocr_empty')
    except Exception as exc:
        # No silent success or remote fallback on an unavailable OCR runtime.
        return ExtractionResult(ok=False, text='', pages=[], extraction_engine=ENGINE_VERSION,
                                warnings=warnings, error_code='pdf_inspector_failed',
                                error_message=f'Lettura PDF non completata: {exc}')
