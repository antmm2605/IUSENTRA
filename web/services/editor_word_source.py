"""Fonte Word dei font, limitata alle versioni SQL del medesimo documento."""
from io import BytesIO
from zipfile import ZipFile
import hashlib


def restore_legacy_tab_stops(document, source, html):
    """Recupera gli stop persi dal vecchio roundtrip, con geometria concordante.

    I paragrafi nuovi hanno metadati espliciti. Il recupero storico non sposta
    paragrafi modificati né sostituisce testo, stili o campi collegati.
    """
    from copy import deepcopy
    from docx.oxml.ns import qn
    from lxml import html as parser

    nodes = list(parser.fragment_fromstring(html, create_parent='div').iter('p'))
    targets = document._element.body.findall('.//' + qn('w:p'))
    originals = source._element.body.findall('.//' + qn('w:p'))
    if len(nodes) != len(targets):
        return 0
    def normalized(properties):
        return {name: {key: val for key, val in item.attrib.items()
                       if val != '0' and not (name == 'jc' and val == 'left')}
                if item is not None else {} for name in ('ind', 'spacing', 'jc')
                for item in [properties.find(qn('w:' + name))]}
    def structure(paragraph):
        return tuple(len(paragraph.findall('.//' + qn('w:r') + '/' + qn('w:' + name))) for name in ('tab', 'br'))
    restored = 0
    for node, target in zip(nodes, targets):
        if '--iu-word-tab-stops:' in (node.get('style') or ''):
            continue
        after = target.find(qn('w:pPr'))
        if after is None:
            continue
        current = after.find(qn('w:tabs'))
        if current is None:
            continue
        # Word omette attributi zero e allineamento sinistro: normalizzare solo
        # questi equivalenti, senza tollerare differenze di misure.
        candidates = []
        for original in originals:
            before = original.find(qn('w:pPr'))
            stops = before.find(qn('w:tabs')) if before is not None else None
            if (stops is not None and len(stops) > len(current)
                    and normalized(before) == normalized(after)
                    and structure(original) == structure(target)
                    and all(tab.attrib in [entry.attrib for entry in stops] for tab in current)):
                candidates.append(stops)
        if len(candidates) != 1:
            continue
        after.replace(current, deepcopy(candidates[0]))
        restored += 1
    return restored


def editor_word_source(repository, matter_id, document, decrypt):
    if document is None:
        return None
    root = repository.documents_dir.resolve()
    matter = (root / matter_id).resolve()
    if matter == root or not matter.is_relative_to(root):
        raise ValueError('Percorso del fascicolo non valido.')
    candidates = [(document.percorso, document.hash_sha256)]
    candidates.extend((version.percorso, version.hash_sha256) for version in document.versioni[:30])
    for relative, fingerprint in candidates:
        if not relative:
            continue
        path = (root / relative).resolve()
        if not path.is_relative_to(matter):
            raise ValueError('La versione Word non appartiene al fascicolo.')
        if path.suffix.lower() != '.docx':
            continue
        if not path.is_file():
            continue
        if path.stat().st_size > 50_000_000:
            raise ValueError('La versione Word supera la dimensione consentita.')
        stored = path.read_bytes()
        if fingerprint and hashlib.sha256(stored).hexdigest() != fingerprint:
            raise ValueError('La versione Word non coincide con la sua impronta.')
        raw = decrypt(stored)
        with ZipFile(BytesIO(raw)) as archive:
            if 'word/_rels/fontTable.xml.rels' in archive.namelist():
                return raw
    return None
