"""Dettagli letti, con posizione, senza scritture anagrafiche o contabili.

Un valore estratto è un'evidenza del file, non una decisione sul fascicolo.
XML non validato XSD; parser senza DTD, entità o richieste esterne.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

from legal_ocr.ner_legal import extract_numero_ruolo
from pct.formatting import format_date_it, format_euro_it

FATTURAPA_NS = "http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2"


def catalog_xml(text: str):
    raw = text.strip()
    if not raw.startswith('<') or len(raw) > 2_000_000:
        return None
    try:
        return ElementTree.fromstring(raw, forbid_dtd=True)
    except (ElementTree.ParseError, ValueError, DefusedXmlException):
        return None


def xml_children(node, name: str, namespace: str = FATTURAPA_NS):
    return [child for child in node if child.tag in {name, f'{{{namespace}}}{name}'}]


def invoice_bodies(root):
    if root.tag != f'{{{FATTURAPA_NS}}}FatturaElettronica':
        return []
    if not xml_children(root, 'FatturaElettronicaHeader'):
        return []
    return xml_children(root, 'FatturaElettronicaBody')


def invoice_data(body):
    generals = xml_children(body, 'DatiGenerali')
    return xml_children(generals[0], 'DatiGeneraliDocumento') if generals else []


def xml_value(node, name: str) -> str:
    matches = xml_children(node, name)
    return str(matches[0].text or '').strip() if matches else ''


def document_fields(text: str, nature: str) -> list[tuple[str, str]]:
    """Ogni coppia contiene localizzatore leggibile e valore non inventato."""
    raw = str(text or '')
    fields: list[tuple[str, str]] = []
    root = catalog_xml(raw)
    if root is not None:
        for index, body in enumerate(invoice_bodies(root), 1):
            for data in invoice_data(body):
                base = f'XML / FatturaElettronicaBody[{index}] / DatiGeneraliDocumento'
                number = xml_value(data, 'Numero')
                if number:
                    fields.append((f'Numero documento · {base}/Numero', number[:200]))
                day = xml_value(data, 'Data')
                try:
                    parsed = date.fromisoformat(day)
                except ValueError:
                    pass
                else:
                    fields.append((f'Data documento · {base}/Data', format_date_it(parsed)))
                currency = xml_value(data, 'Divisa')
                if currency:
                    fields.append((f'Valuta dichiarata · {base}/Divisa', currency[:20]))
                total = xml_value(data, 'ImportoTotaleDocumento')
                if currency == 'EUR' and re.fullmatch(r'-?\d{1,15}(?:\.\d{1,8})?', total):
                    try:
                        formatted = format_euro_it(Decimal(total))
                    except (InvalidOperation, ValueError):
                        pass
                    else:
                        fields.append((f'Totale dichiarato · {base}/ImportoTotaleDocumento', formatted))
        return fields
    if raw.lstrip().startswith('<'):
        return fields
    # Riutilizza il riconoscitore legale esistente, senza dedurre che il RG
    # citato sia quello della pratica aperta e senza normalizzare anni ambigui.
    for item in extract_numero_ruolo(raw):
        value = item['testo']
        fields.append((f'RG citato · {text_position(raw, value)}', value))
    if nature in {'fattura', 'proforma'}:
        number_re = re.compile(
            r'\bfattura(?:[ \t]+pro[ -]?forma)?[ \t]*(?:n(?:umero)?[.°º]?|numero)'
            r'[ \t]*[:#]?[ \t]*([A-Z0-9][A-Z0-9./-]{0,19})(?![A-Z0-9./-])', re.I,
        )
        for match in number_re.finditer(raw):
            number = match.group(1)
            if any(char.isdigit() for char in number):
                fields.append((f'Numero fattura letto · {text_position(raw, match.group(0))}', number))
    return list(dict.fromkeys(fields))


def text_position(text: str, value: str) -> str:
    position = text.casefold().find(value.casefold())
    if position < 0:
        return 'testo indicizzato'
    line = text.count('\n', 0, position) + 1
    # Numero di riga dell'estrazione, non pagina PDF dedotta da interruzioni.
    return f'riga {line} del testo indicizzato'
