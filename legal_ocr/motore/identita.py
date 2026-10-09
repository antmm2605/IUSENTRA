"""Recupero puntuale della MRZ di una carta fotografata su un foglio.

Riusa PP-OCR locale e preserva l'immagine. La MRZ richiede cifre di controllo
concordanti; il fronte CIE resta soggetto ai controlli del titolare del chiamante.
Il nome del file non prova mai il titolare della carta.
"""
from __future__ import annotations

import re

from .consenso import leggi_con_secondo_lettore
from .mrz import righe_td1_complete
from .copertina_cartacea import recupera_titolare_cartacea as recupera_titolare_cartacea

RECUPERO_IDENTITA_VERSIONE = 'regione-v13-copertina-provenienza'


def recupera_residenza_cartacea(image, known_text):
    """Recupero governato del campo mancante, non trattamento dell'intera pagina.

    La pagina deve essere già orientata dal motore condiviso. I token deboli
    localizzano soltanto; i valori sono adottati da due letture concordanti.
    """
    from PIL import Image
    import pytesseract
    from .lettura import _leggi
    from .immagine import diagnostica_zona_testo, prepara_zona_testo, passaggi_diagnosi_zona
    from pct.document_intelligence.catalog_identita_personale import (
        residenza_riga_cartacea, concorda_residenza_cartacea, segmenti_identita_italiana)
    segments = [s['text'] for s in segmenti_identita_italiana(known_text)
                if s['model'] == 'carta_cartacea']
    if len(segments) != 1 or residenza_riga_cartacea(segments[0]):
        return '', []
    source = segments[0]
    title = re.search(r"CARTA\s+D[’']?I?\s*IDENTIT[ÀA]", source, re.I)
    surname = re.search(r'\bCOGNOME[ .:]*([A-ZÀ-Ü]+)', source, re.I)
    name = re.search(r'\bNOME[ .:]*([A-ZÀ-Ü]+)', source, re.I)
    if not title or not surname or not name:
        return '', ['Residenza cartacea: modello o titolare non riscontrati; nessun ritaglio attribuito.']
    words, _ = _leggi(pytesseract, image, lingua='ita+eng',
                     opzioni='--oem 1 --psm 11', dpi=216, timeout=20)
    labels = [w for w in words if w['text'].strip(' .:').upper() in ('VIA', 'VIE')]
    regions, audit = [], []
    for label in labels:
        h, x, y = label['height'], label['left'], label['top']
        numbers = [w for w in words if re.fullmatch(r'\d{1,5}', w['text'])
                   and x < w['left'] < x + image.width * .5 and abs(w['top'] - y) <= h]
        markers = [w for w in words if w['text'].strip(' .:').upper() == 'NUM'
                   and x < w['left'] and abs(w['top'] - y) <= h]
        names = [w for w in words if w['text'].strip(' .:').upper() == 'NOME'
                 and 0 < y - w['top'] < h * 18 and abs(w['left'] - x) < h * 2]
        civic = [w for w in numbers if any(0 < w['left'] - m['left'] - m['width'] < h * 3 for m in markers)]
        if len(civic) != 1 or len(names) != 1:
            continue
        right = min(image.width, civic[0]['left'] + civic[0]['width'] + round(h * 3.67))
        row_box = (max(0, x - round(h * 1.4)), max(0, y - round(h * .65)), right, min(image.height, y + round(h * 1.4)))
        # Il campo mancante riceve per primo il ritaglio e lo zoom. Il contesto
        # dei nomi viene letto dopo, solo se la riga isolata è insufficiente.
        name_word = names[0]
        name_line = [w for w in words if abs(w['top'] - name_word['top']) < h and name_word['left'] <= w['left'] < right]
        name_height = max(w['height'] for w in name_line)
        context_box = (max(0, name_word['left'] - name_height),
                       max(0, name_word['top'] - round(name_height * 3.75)),
                       right, min(image.height, y + round(h * 3.33)))
        regions.append((row_box, context_box, h))
    if len(regions) != 1:
        return '', ['Residenza cartacea: area Via non univoca; nessun dato applicato.']
    for phase, box in zip(('riga Via', 'contesto della stessa area'), regions[0][:2]):
        crop = image.crop(box)
        try:
            # Misura i glifi della riga individuata, non i puntini del fondo.
            scale = max(2.0, min(3.0, 48 / max(regions[0][2], 1)))
            enlarged = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.Resampling.LANCZOS)
            try:
                first = leggi_con_secondo_lettore(enlarged, dpi=216)
                audit.append(f'Residenza cartacea: {phase}, ritaglio {box}, zoom ×{scale:.2f} prima dei trattamenti; originale invariato.')
                address = residenza_riga_cartacea(first.testo) if first and first.confidenza >= .9 else None
                if not address:
                    audit.append(f'Residenza cartacea: {phase} insufficiente; nessun valore applicato.')
                    continue
                second = leggi_con_secondo_lettore(crop, dpi=216)
                other = residenza_riga_cartacea(second.testo) if second and second.confidenza >= .9 else None
                def normalize(value):
                    return re.sub(r'[ .]+', '', value.upper())
                # Dopo il ritaglio e lo zoom, riusa soltanto il trattamento
                # giustificato dalla diagnosi misurata della stessa zona.
                # La preparazione non sostituisce una lettura discordante.
                if not other or tuple(map(normalize, address)) != tuple(map(normalize, other)):
                    diagnosis = diagnostica_zona_testo(enlarged)
                    for step_diagnosis in passaggi_diagnosi_zona(diagnosis):
                        prepared = prepara_zona_testo(enlarged, step_diagnosis)
                        try:
                            candidate = leggi_con_secondo_lettore(prepared.immagine, dpi=216)
                            checked = residenza_riga_cartacea(candidate.testo) if candidate and candidate.confidenza >= .9 else None
                            audit.extend(f'Residenza cartacea: {step} dopo zoom insufficiente/confronto negativo.' for step in prepared.passaggi)
                            if checked and concorda_residenza_cartacea(address, checked, source):
                                second, other = candidate, checked
                                audit.append('Residenza cartacea: passaggio riscontrato; arresto dei trattamenti della zona.')
                                break
                            audit.append('Residenza cartacea: passaggio senza miglioramento riscontrato, scartato; prossimo tentativo sulla zona preservata.')
                        finally:
                            prepared.immagine.close()
                if not concorda_residenza_cartacea(address, other, source):
                    audit.append('Residenza cartacea: letture della zona non concordanti; nessun valore applicato.')
                    continue
                # Il contesto deve riscontrare entrambi i nomi della fonte.
                context = first.testo + '\n' + second.testo
                if not all(re.search(r'\b' + re.escape(w.group(1)) + r'\b', context, re.I) for w in (surname, name)):
                    audit.append('Residenza cartacea: titolare della zona non riscontrato; nessun valore applicato.')
                    continue
                chosen = second if re.match(r'^VIA I(?=[A-Z])', address[0]) else first
                return title.group() + '\n' + chosen.testo, [*audit, 'Residenza cartacea: via e civico concordanti in due letture della stessa zona e nella fonte iniziale; titolare riscontrato.']
            finally:
                enlarged.close()
        finally:
            crop.close()
    return '', audit


def _orientamento_riscontrato(image):
    """Riusa il rilevatore condiviso; un OCR debole non impone una rotazione."""
    import pytesseract
    from .immagine import orienta_testo
    from .lettura import motore_pronto
    oriented, angle = orienta_testo(image, pytesseract=pytesseract,
                                  lingua=motore_pronto(pytesseract))
    if oriented is not image:
        oriented.close()
    return angle


def _angoli_lettura(image, *, modello=''):
    yield 0
    # Il rilevatore si attiva soltanto se la prima lettura non riconosce
    # il documento. Le miniature diagnostiche non vengono adottate come dati.
    angle = _orientamento_riscontrato(image)
    if angle:
        yield angle
    # Una carta elettronica o sanitaria fotografata in verticale richiede
    # una verifica del verso. Le sonde non diventano dati: il chiamante adotta
    # soltanto una lettura che riconosce il modello e supera i suoi controlli.
    if modello not in ('carta_cartacea', 'tessera_sanitaria') and image.height > image.width * 1.2:
        for candidate in (90, 270):
            if candidate != angle:
                yield candidate


def recupera_mrz_carta(image) -> tuple[str, list[str]]:
    """Riquadri limitati e MRZ riscontrata; nessuna correzione dei caratteri."""
    try:
        import cv2
        import numpy as np
        from PIL import Image

        gray = image.convert('L')
        try:
            mask = np.where(np.asarray(gray) < 245, 255, 0).astype('uint8')
        finally:
            gray.close()
        # Il bordo nero dello scanner non è un documento. La maschera serve
        # solo a localizzare: la lettura usa sempre i pixel originali.
        margin = max(2, round(min(mask.shape) * .01))
        mask[:margin, :] = mask[-margin:, :] = 0
        mask[:, :margin] = mask[:, -margin:] = 0
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((21, 21), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        area = image.width * image.height
        regions = []
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if (.02 <= cv2.contourArea(contour) / area <= .65
                    and .5 <= width / max(height, 1) <= 2):
                regions.append((x, y, width, height))
        if not regions or len(regions) > 4:
            return '', ['Recupero MRZ: nessuna regione singola della carta riscontrata.']
        recovered, attempts = [], []
        for x, y, width, height in sorted(regions):
            text, warnings = _leggi_regione(image, x, y, width, height, Image)
            attempts.extend(warnings)
            if text:
                recovered.append((text, warnings, _riscontro_carta(text)))
        # Fronte e MRZ possono dimostrare lo stesso numero documento.
        # La sola vicinanza dei riquadri non collega un retro privo di riscontro.
        identities = {('cie', item[2][1][0][5:14]) if item[2][0] == 'mrz' else item[2]
                      for item in recovered}
        if len(identities) == 1:
            return '\n\n'.join(dict.fromkeys(item[0] for item in recovered)), list(dict.fromkeys(attempts))
        if len(identities) > 1:
            return '', ['Recupero MRZ: più carte distinte riscontrate; nessun dato applicato.']
        return '', ['Recupero MRZ: nessuna lettura dei riquadri supera i controlli del documento.', *attempts]
    except (ImportError, ValueError, RuntimeError) as exc:
        return '', [f'Recupero MRZ non completato: {type(exc).__name__}.']


def _leggi_regione(image, x, y, width, height, Image):
    from pct.document_intelligence.catalog_identita_personale import modello_identita_italiana
    padding = max(15, round(max(width, height) * .06))
    # Prima il riquadro originale: un ingrandimento indiscriminato può
    # peggiorare una carta già leggibile. Il bordo extra è riservato alla MRZ.
    region = image.crop((x, y, x + width, y + height))
    tested_angles, trials, originals = [], [], {}
    models = set()
    # La diagnosi governa il primo tentativo, prima di leggere i valori.
    # Il contesto geometrico deve provenire dalla foto, non da un bordo
    # inventato intorno al bounding box del documento.
    from .preparazione_identita import prepara_riquadro_identita
    context_margin = max(4, round(min(width, height) * .025))
    context = image.crop((max(0, x - context_margin), max(0, y - context_margin),
                          min(image.width, x + width + context_margin),
                          min(image.height, y + height + context_margin)))
    try:
        primary = prepara_riquadro_identita(context)
        try:
            first = leggi_con_secondo_lettore(primary.immagine, dpi=216, preserva_risoluzione=True)
            trials.extend(primary.passaggi)
            first_profile = _riscontro_carta(first.testo) if first else None
            first_model = modello_identita_italiana(first.testo) if first else ''
            if first_model:
                models.add(first_model)
            minimum = .90 if first_profile and first_profile[0] == 'cie' else .94
            if first_profile and first.confidenza >= minimum:
                additions, details = _leggi_zone_cie(
                    image, x, y, width, height, primary.orientamento, Image,
                    rear=first_profile[0] in ('cie_rear', 'mrz'), known_text=first.testo,
                ) if (first_profile[0] in ('cie', 'cie_rear') or
                      (first_profile[0] == 'mrz' and first_profile[1][0][2:5] == 'ITA')) else ('', [])
                region.close()
                return first.testo + additions, [
                    f'Recupero carta {RECUPERO_IDENTITA_VERSIONE}: preparazione guidata dalla diagnosi; '
                    f'riquadro ({x}, {y}, {width}, {height}), rotazione di lettura {primary.orientamento}°, originale invariato.', *trials, *details]
            trials.append('OCR dopo preparazione insufficiente: controlli puntuali sul riquadro, nessun dato ancora applicato.')
        finally:
            primary.immagine.close()
    finally:
        context.close()
    def attempts():
        # Prima confronta gli originali nei versi pertinenti. Preparare
        # ripetutamente una carta ancora ruotata spreca lavoro e peggiora
        # la leggibilità: una lettura già riscontrata interrompe il ciclo.
        # Un modello già riscontrato evita sonde cieche della striscia MRZ;
        # l'orientamento misurato rimane disponibile anche sulla cartacea.
        for angle in _angoli_lettura(region, modello=first_model):
            tested_angles.append(angle)
            yield angle, False
        for angle in sorted(tested_angles, key=lambda item: float(getattr(originals.get(item), 'confidenza', 0)), reverse=True):
            yield angle, True
    try:
        for angle, prepared in attempts():
            candidate = region.rotate(angle, expand=True) if angle else region
            try:
                if prepared:
                    reading, interventions = _leggi_con_diagnosi(candidate, Image, original=originals[angle])
                else:
                    reading = leggi_con_secondo_lettore(candidate, dpi=216)
                    originals[angle] = reading
                    interventions = ['Lettura originale di orientamento; nessun trattamento dei pixel.']
                trials.extend(f'Riquadro ({x}, {y}, {width}, {height}), orientamento provato {angle}°: {step}'
                              for step in interventions)
                if reading is None:
                    continue
                model = modello_identita_italiana(reading.testo)
                if model:
                    models.add(model)
                lines = _riscontro_carta(reading.testo)
                minimum = .90 if lines and lines[0] == 'cie' else .94
                if lines and reading.confidenza >= minimum:
                    location = ', '.join(f'{value:.3f}' for value in
                                         (x / image.width, y / image.height, width / image.width, height / image.height))
                    descriptions = {'cie': 'fronte CIE riconosciuto', 'cie_rear': 'retro CIE: codice fiscale e residenza riconosciuti',
                                    'paper': 'carta cartacea riconosciuta',
                                    'health': 'tessera sanitaria con codice fiscale riscontrato'}
                    proof = ('cifre di controllo MRZ riscontrate' if lines[0] == 'mrz'
                             else descriptions[lines[0]] + '; dati soggetti ai controlli del titolare')
                    additions, details = _leggi_zone_cie(image, x, y, width, height, angle, Image,
                        rear=lines[0] in ('cie_rear', 'mrz'), known_text=reading.testo
                        ) if (lines[0] in ('cie', 'cie_rear') or
                              (lines[0] == 'mrz' and lines[1][0][2:5] == 'ITA')) else ('', [])
                    return reading.testo + additions, [f'Recupero carta {RECUPERO_IDENTITA_VERSIONE}: riquadro ({location}), '
                        f'rotazione di lettura {angle}°, {proof}; originale invariato.', *interventions, *details]
            finally:
                if candidate is not region:
                    candidate.close()
    finally:
        region.close()
    if models == {'carta_cartacea'} or models == {'tessera_sanitaria'}:
        # Questi modelli non hanno una TD1: una lettura debole non deve
        # attivare il recupero delle zone proprie della CIE.
        return '', trials + ['Modello senza MRZ: recupero TD1 non applicato.']
    # Il fondo del riquadro orientato contiene la MRZ: la lettura locale
    # ingrandita evita che le etichette del resto della pagina la mescolino.
    for angle in tested_angles:
        source = image.crop((max(0, x - padding), max(0, y - padding),
                            min(image.width, x + width + padding), min(image.height, y + height + padding)))
        oriented = source.rotate(angle, expand=True)
        source.close()
        try:
            strip = oriented.crop((0, round(oriented.height * .66), oriented.width, oriented.height))
            scale = min(4.0, 2400 / max(strip.width, strip.height))
            enlarged = strip.resize((max(1, round(strip.width * scale)),
                                     max(1, round(strip.height * scale))), Image.Resampling.LANCZOS)
            strip.close()
            try:
                reading = leggi_con_secondo_lettore(enlarged, dpi=216)
                if reading and reading.confidenza >= .94 and righe_td1_complete(reading.testo):
                    checked = righe_td1_complete(reading.testo)
                    additions, details = _leggi_zone_cie(image, x, y, width, height, angle, Image,
                        rear=True, known_text=reading.testo) if checked[0][2:5] == 'ITA' else ('', [])
                    return reading.testo + additions, [f'Recupero MRZ {RECUPERO_IDENTITA_VERSIONE}: riquadro '
                        f'({x / image.width:.3f}, {y / image.height:.3f}, {width / image.width:.3f}, {height / image.height:.3f}), '
                        f'rotazione di lettura {angle}°, controlli individuali riscontrati; originale invariato.', *details]
            finally:
                enlarged.close()
        finally:
            oriented.close()
    return '', trials


_LETTURA_NON_ESEGUITA = object()


def _leggi_con_diagnosi(image, Image, *, original=_LETTURA_NON_ESEGUITA):
    """Originale prima, ingrandimento misurato e trattamento solo se necessario."""
    from .immagine import diagnostica_zona_testo, inclinazione_stimata, prepara_zona_testo, scala_caratteri_zona, separa_sfondo_zona_testo, passaggi_diagnosi_zona

    def accepted(reading):
        profile = _riscontro_carta(reading.testo) if reading else None
        if not profile or reading.confidenza < (.90 if profile[0] == 'cie' else .94):
            return False
        previous = _riscontro_carta(original.testo) if original else None
        def identity(item):
            return ('cie', item[1][0][5:14]) if item[0] == 'mrz' else item
        # Un trattamento non può cambiare la carta già individuata nella
        # fonte. Se i riscontri discordano, nessuna variante viene adottata.
        return not previous or identity(profile) == identity(previous)

    if original is _LETTURA_NON_ESEGUITA:
        original = leggi_con_secondo_lettore(image, dpi=216)
    if accepted(original):
        return original, []
    diagnosis = diagnostica_zona_testo(image)
    if diagnosis.escursione == 0:
        return original, []
    # Un margine conservativo a quarti evita interpolazioni inutilmente
    # aggressive; la misura dei glifi resta il limite del tentativo.
    scale = max(1.0, int(scala_caratteri_zona(image) * 4) / 4)
    attempts = [f'Diagnosi: fondo {diagnosis.livello_sfondo}, escursione {diagnosis.escursione}, '
        f'bordi {diagnosis.rapporto_bordi:.5f}; prima lettura insufficiente.']
    enlarged = image.resize((round(image.width * scale), round(image.height * scale)),
                           Image.Resampling.LANCZOS) if scale > 1.1 else image
    try:
        steps = [f'Ingrandimento misurato ×{scale:.2f}; prima lettura insufficiente.'] if enlarged is not image else []
        if enlarged is not image:
            attempts.extend(steps)
            reading = leggi_con_secondo_lettore(enlarged, dpi=216)
            if accepted(reading):
                return reading, steps
        for step_diagnosis in passaggi_diagnosi_zona(diagnosis):
            prepared = prepara_zona_testo(enlarged, step_diagnosis)
            attempts.extend(prepared.passaggi)
            try:
                reading = leggi_con_secondo_lettore(prepared.immagine, dpi=216)
                if accepted(reading):
                    return reading, steps + list(prepared.passaggi)
                attempts.append('Passaggio non riscontrato, scartato; tentativo successivo sulla zona preservata.')
            finally:
                prepared.immagine.close()
        for mode in ('rimuovi', 'schiarisci', 'scurisci'):
            separated = separa_sfondo_zona_testo(enlarged, modalita=mode)
            if separated:
                attempts.extend(separated.passaggi)
                try:
                    reading = leggi_con_secondo_lettore(separated.immagine, dpi=216)
                    if accepted(reading):
                        return reading, steps + list(separated.passaggi)
                finally:
                    separated.immagine.close()
        angle = inclinazione_stimata(image)
        if .5 <= abs(angle) <= 12:
            attempts.append(f'Raddrizzamento misurato {angle:+.1f}° provato.')
            corrected = enlarged.rotate(angle, resample=Image.Resampling.BICUBIC,
                expand=True, fillcolor='white' if enlarged.mode == 'RGB' else 255)
            try:
                reading = leggi_con_secondo_lettore(corrected, dpi=216)
                if accepted(reading):
                    return reading, steps + [f'Raddrizzamento misurato {angle:+.1f}°; prima lettura insufficiente.']
            finally:
                corrected.close()
        return original, attempts + ['Nessun miglioramento accettato: lettura originale conservata.']
    finally:
        if enlarged is not image:
            enlarged.close()


def _leggi_zone_cie(image, x, y, width, height, angle, Image, *, rear=False, known_text=''):
    """Zone del fronte CIE già riconosciuto, relative alla carta e non al foglio.

    Il modello guida soltanto il ritaglio. Si conservano esclusivamente testi
    letti con etichetta e valore; non si generano campi dalla posizione.
    """
    from .immagine import diagnostica_zona_testo, prepara_zona_testo, scala_caratteri_zona, separa_sfondo_zona_testo, passaggi_diagnosi_zona
    source = image.crop((x, y, x + width, y + height))
    card = source.rotate(angle, expand=True)
    source.close()
    additions, warnings = [], []
    if rear and righe_td1_complete(known_text):
        from .codici_identita import codice_fiscale_da_barre
        code, proof = codice_fiscale_da_barre(card, known_text)
        warnings.append(proof)
        if code:
            additions.append(f'CODICE FISCALE: {code}')
    zones = (
        ('codice fiscale', (.03, .14, .65, .26), r'\b(?:FISCAL\s+CODE|CODICE\s+FISCALE)\s+[A-Z0-9]{16}\b'),
        ('residenza', (.03, .24, .92, .36), r'\b(?:ADDRESS|RESIDENCE)\s+(?:VIA|VIALE|PIAZZA|CORSO)\b'),
    ) if rear else (
        ('comune di rilascio', (.02, .12, .85, .28), r'\bCOMUNE\b.{0,50}\b[A-ZÀ-Ü]{3,}\b'),
        ('nomi', (.30, .26, .72, .45), r'COGNOME\s*/\s*SURNAME\s+[A-ZÀ-Ü\'’ -]+\s+NOME\s*/\s*NAME\s+[A-ZÀ-Ü\'’ -]+'),
        ('luogo e data di nascita', (.27, .39, .96, .56), r'\b(?:NASCITA|BIRTH)\b.{0,80}\d{2}[./]\d{2}[./]\d{4}'),
        ('sesso', (.30, .53, .44, .64), r'\bSEX\s+[MF]\b'),
        ('cittadinanza', (.63, .53, .84, .64), r'\bNATIONALITY\s+[A-Z]{3}\b'),
        ('emissione', (.28, .60, .59, .71), r'EMISSIONE\s*(?:[/ ]*(?:ISSUING|ASSUING))?\s+\d{2}[./]\d{2}[./]\d{4}'),
        ('scadenza', (.58, .62, .95, .80), r'\bSCADENZA\s*(?:[/ ]+EXPIRY)?\s+\d{2}[./]\d{2}[./]\d{4}'),
    )
    try:
        for label, bounds, pattern in zones:
            if rear and label == 'codice fiscale' and additions:
                continue
            if re.search(pattern, known_text, re.I | re.S):
                continue
            box = tuple(round(value * (card.width if index % 2 == 0 else card.height))
                        for index, value in enumerate(bounds))
            cropped = card.crop(box)
            diagnosis = diagnostica_zona_testo(cropped)
            if diagnosis.escursione == 0:
                cropped.close()
                continue
            scale = scala_caratteri_zona(cropped)
            enlarged = None
            try:
                stages = ['originale']
                if scale > 1.1:
                    stages.append('ingrandimento')
                diagnosed_stages = {f'trattamento singolo {index + 1}': step
                                    for index, step in enumerate(passaggi_diagnosi_zona(diagnosis))}
                stages.extend(diagnosed_stages)
                backgrounds = {'separazione sfondo': 'rimuovi', 'schiarimento sfondo': 'schiarisci', 'scurimento sfondo': 'scurisci'}
                stages.extend(backgrounds)
                for stage in stages:
                    if stage != 'originale' and enlarged is None:
                        enlarged = cropped.resize((max(1, round(cropped.width * scale)),
                            max(1, round(cropped.height * scale))), Image.Resampling.LANCZOS) if scale > 1.1 else cropped
                    prepared = (prepara_zona_testo(enlarged, diagnosed_stages[stage]) if stage in diagnosed_stages else
                                separa_sfondo_zona_testo(enlarged, modalita=backgrounds[stage]) if stage in backgrounds else None)
                    if stage in backgrounds and prepared is None:
                        warnings.append(f'CIE {"retro" if rear else "fronte"}: zona {label}, sfondo non separabile; nessuna modifica dei pixel.')
                        continue
                    working = prepared.immagine if prepared else (cropped if stage == 'originale' else enlarged)
                    try:
                        reading = leggi_con_secondo_lettore(working, dpi=216)
                        accepted = reading and reading.confidenza >= .94 and re.search(pattern, reading.testo, re.I | re.S)
                        warnings.append(f'CIE {"retro" if rear else "fronte"}: zona {label}, tentativo {stage}, '
                            f'esito {"accettato" if accepted else "insufficiente"}; originale invariato.')
                        if accepted:
                            additions.append(reading.testo)
                            steps = ', '.join(prepared.passaggi) if prepared else stage
                            warnings.append(f'CIE {"retro" if rear else "fronte"}: zona {label}, limiti relativi {bounds}, '
                                            f'rotazione {angle}°, {steps}; etichetta e valore letti, originale invariato.')
                            break
                    finally:
                        if prepared:
                            working.close()
            finally:
                if enlarged is not None and enlarged is not cropped:
                    enlarged.close()
                cropped.close()
    finally:
        card.close()
    return ('\n\n' + '\n'.join(additions)) if additions else '', warnings


def _riscontro_carta(text):
    """Separa un fronte CIE dalla tessera sanitaria e da una MRZ verificata."""
    from pct.document_intelligence.catalog_identita_personale import modello_identita_italiana
    model = modello_identita_italiana(text)
    mrz = righe_td1_complete(text) if model not in ('carta_cartacea', 'tessera_sanitaria') else None
    if mrz:
        return ('mrz', mrz)
    if model == 'tessera_sanitaria':
        from legal_ocr.formulario.confusioni import _cf_controllo
        labelled = re.sub(r'\bCODICE(?=[A-Z]{6}[0-9LMNPQRSTUV]{2})', 'CODICE ', text.upper())
        codes = {code for code in re.findall(r'\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b', labelled)
                 if _cf_controllo(code[:15]) == code[15]}
        if len(codes) == 1 and re.search(r'\bCOGNOME\b', text, re.I) and re.search(r'\bNOME\b', text, re.I):
            return ('health', next(iter(codes)))
    number = re.search(r'\b[A-Z]{2}\d{5}[A-Z]{2}\b', text)
    if (model == 'cie' and number and re.search(r'IDENTITY\s+CARD', text, re.I)
            and sum(bool(re.search(r'\b' + label + r'\b', text, re.I))
                    for label in ('COGNOME', 'NOME', 'EMISSIONE', 'COMUNE')) >= 3):
        # Le etichette italiane individuano il modello anche quando le
        # traduzioni sono degradate. Questo non certifica alcun valore.
        return ('cie', number.group())
    if model == 'cie' and number and re.search(r'IDENTITY\s+CARD', text, re.I):
        from pct.document_intelligence.catalog_identita_personale import documento_identita_personale
        profile = documento_identita_personale(text)
        if profile and profile.get('tipo_identita') == 'carta_identita':
            # Il catalogo riconosce il modello dai campi effettivi anche se
            # una traduzione inglese è degradata. Non completa i valori:
            # le zone restano soggette a etichetta, lettura e controlli.
            return ('cie', number.group())
    if (model == 'cie' and number and re.search(r'IDENTITY\s+CARD', text, re.I)
            and re.search(r'COGNOME\s*/\s*SURNAME', text, re.I)
            and re.search(r'NOME\s*/\s*NAME', text, re.I)
            and re.search(r'EMISSIONE\s*/\s*ISSUING', text, re.I)):
        return ('cie', number.group())
    # Il retro CIE si legge dalle due etichette bilingui. Non richiede
    # una MRZ valida per recuperare CF e residenza dalla zona stampata.
    if model == 'cie' and all(re.search(pattern, text, re.I) for pattern in (
            r'\bINDIRIZZO\s+DI\s+RESIDENZA\b', r'\bRESIDENCE\b',
            r'\bCODICE\s+FISCALE\b', r'\bFISCAL\s+CODE(?=\b|\d)')):
        from legal_ocr.formulario.confusioni import _cf_controllo
        codes = {code for code in re.findall(r'\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b', text.upper())
                 if _cf_controllo(code[:15]) == code[15]}
        if len(codes) == 1:
            return ('cie_rear', next(iter(codes)))
    paper = re.search(r'\bN\s*[°º.]\s*([A-Z]{2}\s*\d{7})\b', text, re.I)
    if (model == 'carta_cartacea' and paper and re.search(r"CARTA\s+D[’']?I?\s*IDENTIT[ÀA]", text, re.I)
            and not re.search(r'IDENTITY\s+CARD', text, re.I)
            and all(re.search(pattern, text, re.I) for pattern in
                    (r'\bCOMUNE\s+DI\b', r'\bCOGNOME\b', r'\bNOME\b', r'\b(?:NAT[OA]\s+(?:IL|A)|NASCITA)\b'))):
        return ('paper', re.sub(r'\s+', '', paper.group(1)).upper())
    return None
