"""Allineamento delle linee Word misurato sulla resa, senza alterare il testo."""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from time import monotonic

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
                    spans = line['spans']
                    if not spans:
                        continue
                    # A word in a mixed paragraph is not an independent line.
                    # Moving that run alone breaks its baseline relative to the
                    # surrounding text (bold names, links and underlines).
                    key = ' '.join(''.join(span['text'] for span in spans).split())
                    if aliases:
                        key = aliases.get((page.number, key), key)
                    if key:
                        # Leading spaces can use a different font size from
                        # the visible text. They must not govern the match.
                        anchor = next((span for span in spans if span['text'].strip()), spans[0])
                        output[key].append((page.number, anchor['origin'][1], anchor['size']))
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
    started = monotonic()
    document = Document(word)
    split = _split_line_runs(document)
    frozen = _freeze_line_heights(document, font_config)
    if split or frozen:
        document.save(word)
    initial_pdf = render_word(word, word.parent / 'render-initial', font_config)
    original, initial = _lines(source, aliases), _lines(initial_pdf)
    # Align a whole paragraph before considering individual plain lines. Its
    # bold spans, links and normal runs must retain one common baseline.
    occurrences = defaultdict(int)
    attempts = 0
    current_pdf, current_lines = initial_pdf, initial
    matches = []
    for element in document._element.body.iter(qn('w:p')):
        paragraph = Paragraph(element, None)
        # Use only visible Word text, without instruction XML.
        text = ' '.join(''.join(node.text or '' for node in element.iter(qn('w:t'))).split())
        matching = [key for key in original if len(key) > 10 and text.startswith(key) and key in initial]
        if not matching:
            continue
        key = max(matching, key=len)
        matches.append((paragraph, key))
    counts = defaultdict(int)
    for _, key in matches:
        counts[key] += 1
    for paragraph_index, (paragraph, key) in enumerate(matches):
        # A repeated line may be inline on page one and a separate paragraph
        # on page two. Do not pair that paragraph with the first occurrence.
        if counts[key] != len(original[key]) or counts[key] != len(initial[key]):
            continue
        index = occurrences[key]
        occurrences[key] += 1
        if index >= len(original[key]) or index >= len(initial[key]):
            continue
        wanted, before = original[key][index], current_lines[key][index]
        if wanted[0] != before[0] or abs(wanted[2] - before[2]) > .2:
            continue
        shift = wanted[1] - before[1]
        spacing = paragraph.paragraph_format.space_before
        current = spacing.pt if spacing is not None else 0
        if abs(shift) > 24 or current + shift < 0:
            continue
        if abs(shift) <= .25:
            continue
        # Measure each change before proceeding. Predicting the accumulated
        # offset fails across page breaks and independent anchored sections.
        # A finite attempt count and time budget bound the isolated worker.
        if attempts >= 16 or monotonic() - started >= 40:
            break
        attempts += 1
        retained = word.read_bytes()
        paragraph.paragraph_format.space_before = Pt(current + shift)
        document.save(word)
        candidate_pdf = render_word(word, word.parent / f'render-paragraphs-{paragraph_index}', font_config)
        measured = _lines(candidate_pdf)
        # Spacing changes also affect following paragraphs. Keep a candidate
        # only when no matched physical line has worsened or changed page.
        worsened = False
        for line_key, wanted_lines in original.items():
            before_lines, after_lines = current_lines.get(line_key, []), measured.get(line_key, [])
            if len(wanted_lines) != len(before_lines):
                continue
            if len(after_lines) != len(before_lines) or any(
                after[0] != wanted[0] or
                abs(after[1] - wanted[1]) > abs(before[1] - wanted[1]) + .25
                for wanted, before, after in zip(wanted_lines, before_lines, after_lines)
            ):
                worsened = True
                break
        target = measured.get(key, [])
        improved = len(target) == len(original[key]) and abs(target[index][1] - wanted[1]) < abs(before[1] - wanted[1]) - .1
        if worsened or not improved:
            word.write_bytes(retained)
            # Restore the in-memory property as well; following candidates
            # must not accidentally reintroduce a rejected change.
            paragraph.paragraph_format.space_before = spacing
        else:
            current_pdf, current_lines = candidate_pdf, measured
    # Remaining differences may be inside a paragraph with explicit breaks.
    # Its physical line is a group of runs, including hyperlink children;
    # never move a bold word or a link independently of that line.
    retained = word.read_bytes()
    groups = defaultdict(list)
    def physical_key(group):
        text = ' '.join(''.join(item.text for item in group).split())
        if text not in original and text.startswith(('- ', '• ', '– ', '— ')) and text[2:] in original:
            # PDF text extraction may expose the list marker as a separate
            # span/line. Move its whole Word line using the exact body match.
            return text[2:]
        return text
    for paragraph in document._element.body.iter(qn('w:p')):
        group = []
        for element in paragraph.iter(qn('w:r')):
            run = Run(element, None)
            if run.text:
                group.append(run)
            if element.find(qn('w:br')) is not None:
                key = physical_key(group)
                if key:
                    groups[key].append(group)
                group = []
        key = physical_key(group)
        if key:
            groups[key].append(group)
    changed_lines = False
    adjusted_runs = set()
    for key, line_groups in groups.items():
        wanted_lines, measured_lines = original[key], current_lines[key]
        if len(wanted_lines) != len(line_groups) or len(measured_lines) != len(line_groups):
            continue
        for group, wanted, before in zip(line_groups, wanted_lines, measured_lines):
            difference = before[1] - wanted[1]
            if (wanted[0] != before[0] or abs(wanted[2] - before[2]) > .2 or
                    not .25 < abs(difference) <= 24):
                continue
            if any(run._r.get_or_add_rPr().find(qn('w:position')) is not None for run in group):
                continue
            for run in group:
                _set_position(run, round(difference * 2))
                adjusted_runs.add(id(run._r))
            changed_lines = True
    if not changed_lines or monotonic() - started >= 40:
        word.write_bytes(retained)
        return current_pdf
    document.save(word)
    candidate_pdf = render_word(word, word.parent / 'render-physical-lines', font_config)
    measured = _lines(candidate_pdf)
    improved = False
    for key, wanted_lines in original.items():
        before_lines, after_lines = current_lines.get(key, []), measured.get(key, [])
        if len(wanted_lines) != len(before_lines):
            continue
        if len(after_lines) != len(before_lines) or any(
            after[0] != wanted[0] or
            abs(after[1] - wanted[1]) > abs(before[1] - wanted[1]) + .25
            for wanted, before, after in zip(wanted_lines, before_lines, after_lines)
        ):
            word.write_bytes(retained)
            return current_pdf
        if any(abs(after[1] - wanted[1]) < abs(before[1] - wanted[1]) - .1
               for wanted, before, after in zip(wanted_lines, before_lines, after_lines)):
            improved = True
    if not improved:
        word.write_bytes(retained)
        return current_pdf
    # One measured refinement accounts for Writer's actual response. Only
    # runs changed above are eligible; source superscripts remain untouched.
    if monotonic() - started >= 40:
        return candidate_pdf
    retained = word.read_bytes()
    refined = False
    for key, line_groups in groups.items():
        if len(original[key]) != len(line_groups) or len(measured[key]) != len(line_groups):
            continue
        for group, wanted, before in zip(line_groups, original[key], measured[key]):
            difference = before[1] - wanted[1]
            if not .25 < abs(difference) <= 24 or any(id(run._r) not in adjusted_runs for run in group):
                continue
            for run in group:
                position = run._r.rPr.find(qn('w:position'))
                _set_position(run, int(position.get(qn('w:val'))) + round(difference * 2))
            refined = True
    if not refined:
        return candidate_pdf
    document.save(word)
    refined_pdf = render_word(word, word.parent / 'render-physical-refined', font_config)
    after_lines = _lines(refined_pdf)
    improved = False
    for key, wanted_lines in original.items():
        before_lines, after = measured.get(key, []), after_lines.get(key, [])
        if len(wanted_lines) != len(before_lines):
            continue
        if len(after) != len(before_lines) or any(
            now[0] != wanted[0] or
            abs(now[1] - wanted[1]) > abs(before[1] - wanted[1]) + .25
            for wanted, before, now in zip(wanted_lines, before_lines, after)
        ):
            word.write_bytes(retained)
            return candidate_pdf
        improved = improved or any(abs(now[1] - wanted[1]) < abs(before[1] - wanted[1]) - .1
                                  for wanted, before, now in zip(wanted_lines, before_lines, after))
    if not improved:
        word.write_bytes(retained)
        return candidate_pdf
    return refined_pdf
