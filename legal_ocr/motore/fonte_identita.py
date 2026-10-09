"""Pixel nativi di una scansione PDF semplice, dopo controllo del contenuto.

Un'unica immagine effettivamente disegnata può conservare i propri pixel.
Qualunque sovrapposizione, ritaglio, maschera o trasformazione non rappresentata
dall'immagine restituita impedisce questo percorso: il PDF originale resta fonte.
"""
from __future__ import annotations

import io
import math
import zlib


class _FonteNonVerificata(ValueError):
    """Motivo controllato, senza riportare contenuti del PDF negli avvisi."""


def _collegamenti_invisibili(page):
    annotations = page.get('/Annots')
    annotations = annotations.get_object() if annotations else []
    for reference in annotations:
        annotation = reference.get_object()
        if (annotation.get('/Subtype') != '/Link' or annotation.get('/Border') != [0, 0, 0]
                or any(key in annotation for key in ('/AP', '/BS', '/C'))):
            raise _FonteNonVerificata('Annotazione con aspetto grafico non escluso.')
    return len(annotations)


def _matrice_immagine(page, reader):
    from pypdf.generic import ContentStream
    matrix = (1., 1., 0., 0.)  # scala x/y, traslazione x/y; soli assi positivi.
    stack, painted = [], []
    operations = ContentStream(page.get_contents(), reader).operations
    if len(operations) > 64:
        raise _FonteNonVerificata('Contenuto complesso.')
    for args, operator in operations:
        if operator == b'q':
            stack.append(matrix)
        elif operator == b'Q':
            if not stack:
                raise _FonteNonVerificata('Stato grafico non bilanciato.')
            matrix = stack.pop()
        elif operator == b'cm':
            if len(args) != 6:
                raise _FonteNonVerificata('Matrice incompleta.')
            a, b, c, d, e, f = map(float, args)
            if not all(math.isfinite(v) for v in (a, b, c, d, e, f)) or b != 0 or c != 0 or a <= 0 or d <= 0:
                raise _FonteNonVerificata('Rotazione, riflessione o distorsione.')
            sx, sy, tx, ty = matrix
            matrix = sx * a, sy * d, tx + sx * e, ty + sy * f
        elif operator == b'Do' and len(args) == 1:
            painted.append((args[0], matrix))
        elif operator not in (b'w', b'G', b'g', b'RG', b'rg', b'J', b'j', b'M', b'd'):
            # Sono ammessi solo attributi della penna senza alcun disegno.
            # Testi, tracciati, clip, trasparenze, moduli e immagini inline no.
            raise _FonteNonVerificata('Contenuto diverso dalla singola immagine.')
    if stack or len(painted) != 1:
        raise _FonteNonVerificata('Immagine non unica o stato grafico non bilanciato.')
    return painted[0]


def immagine_nativa_copertina(pdf_bytes, page_index):
    """Restituisce (immagine RGB da chiudere, audit), oppure (None, motivo).

    Indice pagina da zero. Non esegue OCR e non usa alcun dato del titolare.
    JPEG e pixel Flate senza predittori sono decodificati senza ricampionamento.
    """
    try:
        from PIL import Image
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError
    except ImportError:
        return None, ['Fonte nativa della carta: controllo del PDF non disponibile.']
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes), strict=True)
        if not isinstance(page_index, int) or not 0 <= page_index < len(reader.pages):
            raise _FonteNonVerificata('Indice della pagina non valido.')
        page = reader.pages[page_index]
        if page.rotation or float(page.get('/UserUnit', 1)) != 1 or '/Group' in page:
            raise _FonteNonVerificata('Rotazione o trasparenza della pagina.')
        invisible_links = _collegamenti_invisibili(page)
        colors = page['/Resources'].get('/ColorSpace', {})
        if '/DefaultRGB' in colors or '/DefaultGray' in colors:
            raise _FonteNonVerificata('Spazio colore predefinito sostituito dal PDF.')
        name, (sx, sy, tx, ty) = _matrice_immagine(page, reader)
        image_object = page['/Resources']['/XObject'][name].get_object()
        if image_object.get('/Subtype') != '/Image':
            raise _FonteNonVerificata('Oggetto disegnato diverso da immagine.')
        forbidden = ('/SMask', '/Mask', '/ImageMask', '/SMaskInData', '/Decode',
                     '/DecodeParms', '/Alternates', '/OC', '/OPI', '/Intent')
        if any(key in image_object for key in forbidden):
            raise _FonteNonVerificata('Maschera, decodifica o rappresentazione alternativa.')
        filters = image_object.get('/Filter')
        if isinstance(filters, list):
            filters = filters[0] if len(filters) == 1 else None
        if (filters not in ('/DCTDecode', '/FlateDecode') or image_object.get('/ColorSpace') not in ('/DeviceRGB', '/DeviceGray')
                or int(image_object.get('/BitsPerComponent', 0)) != 8):
            raise _FonteNonVerificata('Codifica o colore non verificabile senza rendering.')
        width, height = int(image_object['/Width']), int(image_object['/Height'])
        if not 0 < width * height <= 40_000_000 or width <= 0 or height <= 0:
            raise _FonteNonVerificata('Dimensioni non ammesse.')
        if abs((sx / width) / (sy / height) - 1) > .005:
            raise _FonteNonVerificata('Rapporto geometrico dei pixel alterato.')
        # Il box visibile è l'intersezione di CropBox e MediaBox.
        boxes = [tuple(map(float, box)) for box in (page.mediabox, page.cropbox)]
        left, bottom = max(b[0] for b in boxes), max(b[1] for b in boxes)
        right, top = min(b[2] for b in boxes), min(b[3] for b in boxes)
        if tx < left or ty < bottom or tx + sx > right or ty + sy > top:
            raise _FonteNonVerificata('Immagine ritagliata dal bordo della pagina.')
        if filters == '/FlateDecode':
            mode = 'RGB' if image_object.get('/ColorSpace') == '/DeviceRGB' else 'L'
            expected = width * height * (3 if mode == 'RGB' else 1)
            decoder = zlib.decompressobj()
            pixels = decoder.decompress(image_object._data, expected + 1)
            if len(pixels) != expected or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:
                raise _FonteNonVerificata('Pixel compressi discordanti con le dimensioni dichiarate.')
            with Image.frombytes(mode, (width, height), pixels) as source:
                result = source.convert('RGB')
        else:
            with Image.open(io.BytesIO(image_object.get_data())) as source:
                if source.format != 'JPEG' or source.size != (width, height):
                    raise _FonteNonVerificata('Pixel discordanti con la struttura PDF.')
                result = source.convert('RGB')
        audit = (f'Fonte nativa della carta: pagina {page_index + 1}, una sola immagine {filters[1:]} disegnata, '
                 f'{width} × {height} pixel; matrice assiale e limiti visibili verificati, '
                 'nessuna sovrapposizione, maschera o ritaglio; pixel decodificati senza ricampionamento.')
        if invisible_links:
            audit += f' {invisible_links} collegamenti privi di bordo e aspetto grafico non modificano i pixel.'
        return result, [audit]
    except (PdfReadError, OSError, ValueError, KeyError, TypeError, IndexError, zlib.error, Image.DecompressionBombError) as exc:
        reason = str(exc) if isinstance(exc, _FonteNonVerificata) else type(exc).__name__
        return None, [f'Fonte nativa della carta non adottata: {reason} '
                      'struttura, geometria o rappresentazione non verificabili come immagine singola.']
