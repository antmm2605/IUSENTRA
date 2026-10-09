"""Titolare della copertina cartacea, ancorato alla stessa carta e a due lettori.

Il modello guida la ricerca di titolo, numero e «DI», mai valori o coordinate
di una persona. Righe aggiuntive, margini mancanti o letture discordanti fermano
il recupero; i pixel originali non ricevono filtri né correzioni dei caratteri.
"""
from __future__ import annotations

import re

from .consenso import leggi_con_secondo_lettore
from .lettura import leggi_testo, testo_per_righe

_TITOLO = re.compile(r"CARTA\s+D[’']?I?\s*IDENTIT[ÀA]\b", re.I)
_NUMERO = re.compile(r"\b([A-Z]{2})\s*(\d{7})\b", re.I)
_NOME = re.compile(r"[A-ZÀ-ÖØ-Ý]+(?:[’'-][A-ZÀ-ÖØ-Ý]+)*", re.I)


def _numeri(text):
    return {''.join(item).upper() for item in _NUMERO.findall(text)}


def _righe(words):
    rows = {}
    for word in words:
        rows.setdefault(tuple(word.get(k, 0) for k in ('block', 'par', 'line')), []).append(word)
    return sorted((sorted(row, key=lambda w: w['left']) for row in rows.values()),
                  key=lambda row: min(w['top'] for w in row))


def _limiti(words):
    return (min(w['left'] for w in words), min(w['top'] for w in words),
            max(w['left'] + w['width'] for w in words),
            max(w['top'] + w['height'] for w in words))


def _testo(row):
    return ' '.join(w['text'] for w in row)


def _localizza(words, number):
    rows = _righe(words)
    titles = [row for row in rows if _TITOLO.search(_testo(row))]
    if len(titles) != 1 or len(_TITOLO.findall(_testo(titles[0]))) != 1:
        return None
    title = [w for w in titles[0] if re.search(r'CARTA|IDENTIT|^D[I’\']?$', w['text'], re.I)]
    left, top, right, bottom = _limiti(title)
    width = right - left
    def within(row):
        return all(left <= w['left'] + w['width'] / 2 <= right for w in row)
    numbers = [row for row in rows if within(row) and _numeri(_testo(row)) == {number}
               and bottom <= min(w['top'] for w in row) <= bottom + width * .35]
    if len(numbers) != 1:
        return None
    parts = [w for w in numbers[0] if re.fullmatch(r'[A-Z]{2}|\d{7}|[A-Z]{2}\d{7}', w['text'], re.I)]
    if not parts or min(float(w.get('conf', 0)) for w in parts) < .8:
        return None
    number_bottom = _limiti(numbers[0])[3]
    markers = [row for row in rows if within(row) and _testo(row).strip(' .:').upper() == 'DI'
               and number_bottom < row[0]['top'] < number_bottom + width * .3
               and float(row[0].get('conf', 0)) >= .8]
    if len(markers) != 1:
        return None
    marker = markers[0][0]
    return left, top, right, marker['top'] + marker['height'], marker['height']


def _bordo_inferiore(image, location):
    """Misura una linea scura estesa; non tronca alla seconda riga presunta."""
    left, _, right, start, h = location
    end = min(image.height, start + round(h * 10))
    with image.crop((left, start, right, end)).convert('L') as strip:
        consecutive = 0
        for y in range(strip.height):
            with strip.crop((0, y, strip.width, y + 1)) as row:
                dark = sum(row.histogram()[:180]) / max(1, strip.width)
            consecutive = consecutive + 1 if dark >= .6 else 0
            if consecutive == 2 and y > h * 2:
                return start + y - 1 - round(h * .3)
    return None


def _coppia(words, h):
    # Puntini/righe guida riconosciuti come lettere non diventano un nome.
    substantial = [w for w in words if w['height'] >= h * .35]
    rows = _righe(substantial)
    if len(rows) != 2:
        return None
    if any(not _NOME.fullmatch(w['text']) or float(w.get('conf', 0)) < .7 for w in substantial):
        return None
    if not .3 * h <= _limiti(rows[1])[1] - _limiti(rows[0])[3] <= 4 * h:
        return None
    names = tuple(_testo(row).upper() for row in rows)
    if any(re.search(r'\b(?:COMUNE|CARTA|IDENTITÀ|IDENTITA|COGNOME|NOME|FIRMA)\b', name) for name in names):
        return None
    return names


def _semplice(text):
    return re.sub(r'\s+', ' ', re.sub(r'[#*_`]', '', text)).strip().upper().replace('’', "'")


def _modello_copertina(known_text):
    from pct.document_intelligence.catalog_identita_personale import modello_identita_italiana
    return (modello_identita_italiana(known_text) == 'carta_cartacea'
            and bool(_TITOLO.search(known_text))
            and not all(re.search(r'\b' + label + r'\b', known_text, re.I) for label in ('COGNOME', 'NOME')))


def copertina_cartacea_applicabile(known_text):
    """Gate senza OCR, condiviso con chi propone la fonte nativa del PDF."""
    return _modello_copertina(known_text) and len(_numeri(known_text)) == 1


def recupera_titolare_cartacea(image, known_text):
    """Restituisce solo i campi della copertina concordanti e il loro audit."""
    if not _modello_copertina(known_text):
        return '', []
    if len(_numeri(known_text)) != 1:
        return '', ['Copertina cartacea: numero mancante o numeri discordanti nella fonte; nessun dato applicato.']
    import pytesseract
    from PIL import ImageOps
    number = next(iter(_numeri(known_text)))
    audit = []
    words = leggi_testo(image, pytesseract=pytesseract, opzioni='--oem 1 --psm 11', timeout=20)
    location = _localizza(words, number)
    if not location:
        return '', ['Copertina cartacea: titolo, numero e dicitura DI non localizzati in modo univoco; nessun dato applicato.']
    bottom = _bordo_inferiore(image, location)
    if bottom is None:
        return '', ['Copertina cartacea: bordo inferiore non misurabile; righe del titolare non delimitate.']
    left, top, right, start, h = location
    context_box = (left, max(0, top - round(h / 2)), right, bottom)
    names_box = (left, start, right, bottom)
    audit.append(f'Copertina cartacea: titolo, numero e DI nella stessa area; contesto {context_box}, '
                 f'titolare {names_box}, bordo inferiore misurato; pixel originali invariati.')
    with image.crop(context_box) as raw_context, image.crop(names_box) as raw_names:
        with ImageOps.expand(raw_context, border=max(8, round(h * .8)), fill='white') as context:
            first = leggi_testo(context, pytesseract=pytesseract, opzioni='--oem 1 --psm 6', timeout=20)
            text = testo_per_righe(first)
            second = leggi_con_secondo_lettore(context, preserva_risoluzione=True)
            if (not second or second.confidenza < .9 or not _TITOLO.search(text)
                    or not _TITOLO.search(second.testo) or _numeri(text) != {number}
                    or _numeri(second.testo) != {number}):
                return '', audit + ['Copertina cartacea: titolo e numero non concordanti nei due lettori; recupero terminato.']
            marker_rows = [row for row in _righe(first) if _testo(row).strip(' .:').upper() == 'DI']
            if len(marker_rows) != 1:
                return '', audit + ['Copertina cartacea: separazione del titolare non riscontrata nel contesto.']
            marker_bottom = _limiti(marker_rows[0])[3]
            contextual = _coppia([w for w in first if w['top'] > marker_bottom], h)
            if not contextual or not _semplice(second.testo).endswith('DI ' + _semplice(' '.join(contextual))):
                return '', audit + ['Copertina cartacea: due righe del titolare non concordanti nel contesto; recupero terminato.']
        with ImageOps.expand(raw_names, border=max(8, round(h * .8)), fill='white') as names:
            primary = leggi_testo(names, pytesseract=pytesseract, opzioni='--oem 1 --psm 6', timeout=20)
            pair = _coppia(primary, h)
            secondary = leggi_con_secondo_lettore(names, preserva_risoluzione=True)
            if (not pair or pair != contextual or not secondary or secondary.confidenza < .94
                    or _semplice(secondary.testo) != _semplice(' '.join(pair))):
                return '', audit + ['Copertina cartacea: titolare discordante o insufficiente; nessun campo applicato, recupero terminato.']
    audit.append('Copertina cartacea: cognome e nome concordanti in Tesseract e PP-OCR, nel contesto e nella zona '
                 'del titolare; etichette determinate dalle due righe del modello dopo DI, senza correzioni dei valori.')
    return f"CARTA D'IDENTITÀ\nN. {number}\nCognome: {pair[0]}\nNome: {pair[1]}", audit
