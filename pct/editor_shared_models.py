"""Pubblicazione esplicita di modelli generici nel catalogo SQL di piattaforma."""
from __future__ import annotations

import hashlib
import json
import re
from uuid import UUID

from lxml import html as parser

from pct.editor_linked_fields import template_linked_html


def prepare_shared_model(payload):
    """Rimuove associazioni tenant e rifiuta identificativi personali non collegati."""
    body, _ = template_linked_html(str(payload['corpo']))
    root = parser.fragment_fromstring(body, create_parent='div')
    for node in root.iter():
        for attribute in ('data-iu-font-template', 'data-iu-linked-matter', 'data-iu-linked-client'):
            node.attrib.pop(attribute, None)
        if any(key != 'href' and (str(value).lower().startswith(('http:', 'https:')) or 'url(' in str(value).lower()) for key, value in node.attrib.items()):
            raise ValueError('Risorse esterne non consentite nel modello condiviso.')
    text = root.text_content()
    if re.search(r'\b[A-Z]{6}[0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]\b', text, re.I) or re.search(r'[\w.+-]+@[\w.-]+\.[a-z]{2,}', text, re.I):
        raise ValueError('Il modello contiene identificativi personali non collegati.')
    identifier = str(UUID(str(payload['id'])))
    return {'id': identifier, 'titolo': str(payload['titolo']).strip(),
            'categoria': 'Altro', 'collezione': 'Editor condiviso', 'builtin': True,
            'corpo': ''.join(parser.tostring(node, encoding='unicode') for node in root)}


def publish_shared_model(repository, payload, *, font_source, reviewed_sha256, publisher):
    """Impronta approvata, inserimento ripetibile e ricevuta SQL senza dati di studio."""
    item = prepare_shared_model(payload)
    fingerprint = hashlib.sha256(json.dumps({'payload': item, 'font_source': font_source}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if fingerprint != reviewed_sha256 or not publisher.strip():
        raise ValueError('Impronta di revisione o autore della pubblicazione non validi.')
    receipt = {'id': item['id'], 'sha256': fingerprint, 'publisher': publisher.strip()}
    repository.create_shared_editor_template(item, font_source=font_source, publication_receipt=receipt)
    return receipt
