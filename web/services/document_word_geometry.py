"""Allineamento delle linee Word misurato sulla resa, senza alterare il testo."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path

import pymupdf
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.text.run import Run
from docx.text.paragraph import Paragraph
from docx.shared import Pt

from document_word_render import render_word


def _lines(path: Path, aliases=None):
    output = defaultdict(list)
    with pymupdf.open(path) as pdf:
        for page in pdf:
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines', []):
                    for span in line['spans']:
                        key = ' '.join(span['text'].split())
                        if aliases:
                            key = aliases.get((page.number, key), key)
                        if key:
                            output[key].append((page.number, span['origin'][1], span['size']))
    return output


def _set_position(run: Run, position: int):
    properties = run._r.get_or_add_rPr()
    for element in list(properties.findall(qn('w:position'))):
        properties.remove(element)
    element = OxmlElement('w:position')
    element.set(qn('w:val'), str(position))
    properties.append(element)


def _split_line_runs(document):
    """Mantiene gli a capo, rendendo misurabile ciascuna riga già presente.

    Un run può contenere più righe: il PDF renderizzato le espone invece come
    span distinti. Separare soltanto i break esistenti conserva testo e stile
    e permette il confronto delle baseline senza inventare corrispondenze.
    """
    changed = False
    for element in list(document._element.body.iter(qn('w:r'))):
        if not any(child.tag == qn('w:br') for child in element):
            continue
        properties = element.find(qn('w:rPr'))
        groups, current = [], []
        for child in element:
            if child.tag == qn('w:rPr'):
                continue
            current.append(child)
            if child.tag == qn('w:br'):
                groups.append(current)
                current = []
        if current:
            groups.append(current)
        if len(groups) < 2:
            continue
        for group in groups:
            replacement = OxmlElement('w:r')
            if properties is not None:
                replacement.append(deepcopy(properties))
            for child in group:
                replacement.append(deepcopy(child))
            element.addprevious(replacement)
        element.getparent().remove(element)
        changed = True
    return changed


def _freeze_line_heights(document, font_config=None):
    """Un aggiustamento del glifo non deve ridimensionare il capoverso.

    Word espande l'interlinea automatica anche per w:position; gli spostamenti
    di una riga alteravano tutte quelle successive. Conserviamo il passo
    dichiarato, in punti, prima di misurare il documento.
    """
    if font_config is None:
        return False
    from fontTools.ttLib import TTFont
    metrics = {}
    for path in list(font_config.parent.glob('*.ttf')) + list(font_config.parent.glob('*.otf')):
        with TTFont(path) as font:
            family = font['name'].getDebugName(16) or font['name'].getDebugName(1)
            if not family or 'hhea' not in font:
                continue
            face = (family.casefold(), int(font['OS/2'].usWeightClass) >= 600,
                    bool(int(font['OS/2'].fsSelection) & 1))
            hhea = font['hhea']
            factor = (hhea.ascent - hhea.descent + hhea.lineGap) / font['head'].unitsPerEm
            if .6 <= factor <= 3:
                metrics[face] = factor
    changed = False
    for element in document._element.body.iter(qn('w:p')):
        paragraph = Paragraph(element, None)
        spacing = paragraph.paragraph_format.line_spacing
        if spacing is None or not isinstance(spacing, float):
            continue
        sizes = []
        for run in paragraph.runs:
            if not run.font.size or not run.text.strip():
                continue
            face = ((run.font.name or '').casefold(), bool(run.bold), bool(run.italic))
            if face not in metrics:
                sizes = []
                break
            sizes.append(run.font.size.pt * metrics[face])
        if not sizes:
            continue
        paragraph.paragraph_format.line_spacing = Pt(max(sizes) * spacing)
        changed = True
    return changed


def align_rendered_lines(source: Path, word: Path, aliases=None, font_config=None) -> Path:
    """Taratura limitata ai run abbinabili per testo, occorrenza e pagina.

    Non corregge differenze di testo o struttura né inventa corrispondenze.
    Ogni render ha un profilo distinto: nessuna sessione Writer condivisa.
    """
    document = Document(word)
    split = _split_line_runs(document)
    frozen = _freeze_line_heights(document, font_config)
    if split or frozen:
        document.save(word)
    initial_pdf = render_word(word, word.parent / 'render-initial', font_config)
    original, initial = _lines(source, aliases), _lines(initial_pdf)
    runs = defaultdict(list)
    for element in document._element.body.iter(qn('w:r')):
        run = Run(element, None)
        key = ' '.join(run.text.split())
        if key:
            runs[key].append(run)
    adjustments = []
    for key, matching_runs in runs.items():
        if len(original[key]) != len(matching_runs) or len(initial[key]) != len(matching_runs):
            continue
        for run, before, wanted in zip(matching_runs, initial[key], original[key]):
            page, baseline, size = before
            wanted_page, wanted_baseline, wanted_size = wanted
            difference = baseline - wanted_baseline
            if page != wanted_page or abs(size - wanted_size) > 0.2 or abs(difference) > max(12, size * 4):
                continue
            halfpoints = round(difference * 2)
            if halfpoints:
                _set_position(run, halfpoints)
                adjustments.append((key, run, before, wanted, halfpoints))
    if not adjustments:
        return initial_pdf
    document.save(word)
    measured_pdf = render_word(word, word.parent / 'render-measured', font_config)
    measured = _lines(measured_pdf)
    occurrence = defaultdict(int)
    changed = False
    # Iterate all runs to preserve occurrence order, including unmodified runs.
    by_run = {id(run._r): item for item in adjustments for run in [item[1]]}
    for key, matching_runs in runs.items():
        for run in matching_runs:
            index = occurrence[key]
            occurrence[key] += 1
            item = by_run.get(id(run._r))
            if item is None or len(measured[key]) != len(matching_runs):
                continue
            _, _, before, wanted, halfpoints = item
            now = measured[key][index]
            response = (before[1] - now[1]) / halfpoints
            if now[0] != wanted[0] or not 0.1 <= response <= 2:
                continue
            position = round((before[1] - wanted[1]) / response)
            if position != halfpoints:
                _set_position(run, position)
                changed = True
    if not changed:
        return measured_pdf
    document.save(word)
    return render_word(word, word.parent / 'render-final', font_config)
