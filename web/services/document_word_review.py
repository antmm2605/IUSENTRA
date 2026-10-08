"""Applica la revisione al testo Word senza ricostruire tabelle e impaginazione."""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import unicodedata


def _normal(text):
    value, positions = [], []
    for match in re.finditer(r'\S+|\s+', text):
        chunk = ' ' if match.group().isspace() else match.group()
        value.extend(chunk)
        positions.extend([match.start()] if chunk == ' ' else range(match.start(), match.end()))
    return ''.join(value), positions


def _inline_deltas(before, after):
    keys = {'grassetto', 'corsivo', 'sottolineato', 'barrato', 'corpo', 'famiglia', 'colore'}

    def styles(part):
        text = part['text']
        tratti = part.get('tratti', [])
        if not tratti:
            return [part.get('format', {})] * len(text)
        if not isinstance(tratti, list) or len(tratti) > 10000 or ''.join(item.get('testo', '') for item in tratti) != text:
            raise ValueError('Tratti della revisione non validi')
        return [item for item in tratti for _ in item['testo']]

    original, old_positions = _normal(before['text'])
    revised, new_positions = _normal(after['text'])
    old_styles, new_styles = styles(before), styles(after)
    patches = [{} for _ in revised]
    for tag, a, b, c, d in SequenceMatcher(None, original, revised, autojunk=False).get_opcodes():
        for position in range(c, d):
            previous = a + position - c if tag == 'equal' else min(a, len(original) - 1)
            old, new = old_styles[old_positions[previous]], new_styles[new_positions[position]]
            patches[position] = {key: new[key] for key in keys if key in new and new[key] != old.get(key)}
    return patches


def _paragraph_matches(paragraphs, paragraph_pages, page, text, updated, occurrence):
    """Un blocco letto può comprendere più paragrafi Word contigui."""
    spans, chunks, offset = [], [], 0
    for index, paragraph in enumerate(paragraphs):
        if paragraph_pages[index] != page or not paragraph.text:
            continue
        normal, positions = _normal(paragraph.text)
        chunks.append(normal)
        spans.append((index, offset, offset + len(normal), positions))
        offset += len(normal) + 1
    whole = ' '.join(chunks)
    wanted, _ = _normal(text)
    revised, _ = _normal(updated)
    matches = list(re.finditer(r'(?<!\w)' + re.escape(wanted) + r'(?!\w)', whole))
    if occurrence >= len(matches):
        raise ValueError('Testo della revisione non trovato nel Word')
    match = matches[occurrence]
    opcodes = SequenceMatcher(None, wanted, revised, autojunk=False).get_opcodes()

    def boundary(position):
        if position == len(wanted):
            return len(revised)
        for tag, a, b, c, d in opcodes:
            if a <= position <= b:
                if tag == 'equal':
                    return c + position - a
                return c if position == a else d
        return len(revised)

    parts = []
    for index, left, right, positions in spans:
        a, b = max(left, match.start()), min(right, match.end())
        if a < b:
            updated_part = revised[boundary(a - match.start()):boundary(b - match.start())]
            original_start = positions[a - left]
            original_end = positions[b - left - 1] + 1
            parts.append((index, original_start, original_end, updated_part, boundary(a - match.start()), boundary(b - match.start())))
    return parts


def _revised_runs(paragraph, affected, start, end, updated, patches):
    """Mantiene gli stili dei caratteri invariati, anche dentro una frase mista."""
    from docx.text.run import Run

    original = ''.join(run.text[max(0, start - offset):min(stop, end) - offset]
                       for run, offset, stop in affected)
    segments = []
    for run, offset, stop in affected:
        left, right = max(start, offset), min(end, stop)
        segments.append((left - start, right - start, run))
    pieces = []
    for tag, left, right, new_left, new_right in SequenceMatcher(None, original, updated, autojunk=False).get_opcodes():
        if tag == 'equal':
            for segment_left, segment_right, run in segments:
                a, b = max(left, segment_left), min(right, segment_right)
                if a < b:
                    pieces.append((run, new_left + a - left, new_left + b - left))
        elif tag in ('replace', 'insert'):
            style_position = min(left, len(original) - 1)
            template = next(run for a, b, run in segments if a <= style_position < b)
            pieces.append((template, new_left, new_right))
    first, first_start, _ = affected[0]
    last, last_start, _ = affected[-1]
    prefix = first.text[:start - first_start]
    suffix = last.text[end - last_start:]
    anchor = first._r
    if prefix:
        element = deepcopy(first._r)
        anchor.addprevious(element)
        Run(element, paragraph).text = prefix
    replacements = []
    for template, left, right in pieces:
        cursor = left
        while cursor < right:
            stop = cursor + 1
            patch = patches[cursor]
            while stop < right and patches[stop] == patch:
                stop += 1
            element = deepcopy(template._r)
            anchor.addprevious(element)
            replacement = Run(element, paragraph)
            replacement.text = updated[cursor:stop]
            replacements.append((replacement, patch))
            cursor = stop
    if suffix:
        element = deepcopy(last._r)
        anchor.addprevious(element)
        Run(element, paragraph).text = suffix
    for run, _, _ in affected:
        run._r.getparent().remove(run._r)
    return replacements


def apply_review(document, review_file: Path, source) -> tuple[dict[int, Counter], dict[tuple[int, str], str]]:
    from docx.text.paragraph import Paragraph
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    payload = json.loads(review_file.read_text(encoding='utf-8'))
    originals, revised = payload['originali'], payload['blocchi']
    if not isinstance(originals, list) or not isinstance(revised, list) or len(originals) > 10000:
        raise ValueError('Revisione non valida')
    ids = [part['id'] for part in originals]
    if len(set(ids)) != len(ids) or [part['id'] for part in revised] != ids:
        raise ValueError('Struttura della revisione cambiata')
    paragraphs, paragraph_pages, current_page = [], [], 1
    for element in document._element.body.iter(qn('w:p')):
        paragraphs.append(Paragraph(element, document))
        paragraph_pages.append(current_page)
        properties = element.find(qn('w:pPr'))
        if properties is not None and properties.find(qn('w:sectPr')) is not None:
            current_page += 1
    # Gli indici individuano le occorrenze anche se lo stesso testo ricorre
    # su pagine diverse. Nessuna sostituzione globale o ricerca approssimativa.
    occurrences = Counter()
    replacements = {}
    aliases = {}
    expected = {page.number + 1: Counter(re.findall(r'\S+', unicodedata.normalize('NFKC', page.get_text()))) for page in source}
    for before, after in zip(originals, revised):
        text = before.get('text', '')
        page = before.get('page')
        if not isinstance(text, str) or page not in expected or after.get('page') != page:
            raise ValueError('Pagina della revisione non valida')
        if before == after:
            occurrences[(page, text)] += 1
            continue
        if before.get('kind') != after.get('kind') or before.get('rows') != after.get('rows'):
            raise ValueError('Revisione della struttura non applicabile')
        updated = after.get('text', '')
        if not text or not isinstance(updated, str) or len(updated) > 100000:
            raise ValueError('Testo della revisione non valido')
        if ' '.join(text.split()) not in ' '.join(source[page - 1].get_text().split()):
            raise ValueError('Testo originale non presente nella fonte')
        occurrence = occurrences[(page, text)]
        occurrences[(page, text)] += 1
        inline_patches = _inline_deltas(before, after)
        for index, start, end, updated_part, a, b in _paragraph_matches(paragraphs, paragraph_pages, page, text, updated, occurrence):
            replacements.setdefault(index, []).append((start, end, updated_part, before.get('format', {}), after.get('format', {}), inline_patches[a:b]))
            original_part = paragraphs[index].text[start:end]
            aliases[(page - 1, ' '.join(original_part.split()))] = ' '.join(updated_part.split())
        expected[page].subtract(re.findall(r'\S+', unicodedata.normalize('NFKC', text)))
        expected[page].update(re.findall(r'\S+', unicodedata.normalize('NFKC', updated)))
    for index, changes in replacements.items():
        paragraph = paragraphs[index]
        for start, end, updated, before_format, after_format, inline_patches in sorted(changes, key=lambda item: item[0], reverse=True):
            offset, affected = 0, []
            for run in paragraph.runs:
                stop = offset + len(run.text)
                if offset < end and stop > start:
                    affected.append((run, offset, stop))
                offset = stop
            if not affected:
                raise ValueError('Formato della revisione non trovato')
            revised_runs = _revised_runs(paragraph, affected, start, end, updated, inline_patches)
            replacement_runs = [run for run, _ in revised_runs]
            # Prima gli interventi sul pezzo selezionato; i comandi del
            # capoverso vengono applicati di seguito a tutto il blocco.
            for run, patch in revised_runs:
                for key, attribute in [('grassetto', 'bold'), ('corsivo', 'italic'), ('sottolineato', 'underline'), ('barrato', 'strike')]:
                    if key in patch:
                        setattr(run.font, attribute, bool(patch[key]))
                if patch.get('corpo'):
                    size = float(patch['corpo'])
                    if not 2 <= size <= 96:
                        raise ValueError('Corpo non valido')
                    run.font.size = Pt(size)
                if patch.get('famiglia'):
                    family = patch['famiglia']
                    if not isinstance(family, str) or not re.fullmatch(r'[A-Za-z0-9 ,\-]{1,100}', family):
                        raise ValueError('Carattere non valido')
                    run.font.name = family.split(',')[0].strip()
                if patch.get('colore'):
                    color = patch['colore']
                    if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
                        raise ValueError('Colore non valido')
                    run.font.color.rgb = RGBColor.from_string(color[1:])
            delta = {key: value for key, value in after_format.items() if value != before_format.get(key)}
            for key, attribute in [('grassetto', 'bold'), ('corsivo', 'italic'), ('sottolineato', 'underline'), ('barrato', 'strike')]:
                if key in delta:
                    value = bool(delta.pop(key))
                    for replacement in replacement_runs:
                        setattr(replacement.font, attribute, value)
            if 'corpo' in delta:
                size = float(delta.pop('corpo'))
                if size != 0 and not 2 <= size <= 96:
                    raise ValueError('Corpo non valido')
                if size:
                    for replacement in replacement_runs:
                        replacement.font.size = Pt(size)
            if 'famiglia' in delta:
                family = delta.pop('famiglia')
                if not isinstance(family, str) or (family and not re.fullmatch(r'[A-Za-z0-9 ,\-]{1,100}', family)):
                    raise ValueError('Carattere non valido')
                if family:
                    for replacement in replacement_runs:
                        replacement.font.name = family.split(',')[0].strip()
            if 'colore' in delta:
                color = delta.pop('colore')
                if not isinstance(color, str) or (color and not re.fullmatch(r'#[0-9a-fA-F]{6}', color)):
                    raise ValueError('Colore non valido')
                if color:
                    for replacement in replacement_runs:
                        replacement.font.color.rgb = RGBColor.from_string(color[1:])
            if 'allineamento' in delta:
                value = delta.pop('allineamento')
                alignment = {'sinistra': WD_ALIGN_PARAGRAPH.LEFT, 'centro': WD_ALIGN_PARAGRAPH.CENTER,
                             'destra': WD_ALIGN_PARAGRAPH.RIGHT, 'giustificato': WD_ALIGN_PARAGRAPH.JUSTIFY}
                if value not in alignment:
                    raise ValueError('Allineamento non valido')
                paragraph.alignment = alignment[value]
            if 'interlinea' in delta:
                value = float(delta.pop('interlinea'))
                if value != 0 and not 0.8 <= value <= 4:
                    raise ValueError('Interlinea non valida')
                paragraph.paragraph_format.line_spacing = value or None
            if 'rientro' in delta:
                value = float(delta.pop('rientro'))
                if not 0 <= value <= 100:
                    raise ValueError('Rientro non valido')
                paragraph.paragraph_format.left_indent = Pt(value * 72 / 25.4)
            if delta:
                raise ValueError('Formato di paragrafo non applicato')
    return expected, aliases
