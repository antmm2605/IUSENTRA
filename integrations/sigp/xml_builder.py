"""Builder XML iniziale per il deposito SIGP.

La struttura e' intenzionalmente conservativa: produce una bozza XML tecnica
validabile appena gli XSD ufficiali sono presenti. I tag specifici vanno
allineati al pacchetto ministeriale installato prima di abilitare invio/busta.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom


def _text(parent: ET.Element, tag: str, value: object) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = "" if value is None else str(value)
    return child


def build_sigp_xml(data: dict) -> bytes:
    root = ET.Element(
        "Professionista",
        {
            "versioneBozzaIusentra": "1",
            "schemaVersione": str(data.get("schema_version") or "2024-08-27"),
        },
    )

    _text(root, "Ufficio", data.get("ufficio", ""))
    _text(root, "Ambiente", data.get("ambiente", "produzione"))
    _text(root, "Procedimento", data.get("procedimento", ""))
    _text(root, "TipoAtto", data.get("tipo_atto", ""))

    parti = ET.SubElement(root, "Parti")
    for parte_data in data.get("parti", []) or []:
        parte = ET.SubElement(parti, "Parte")
        _text(parte, "Ruolo", parte_data.get("ruolo", ""))
        _text(parte, "Nome", parte_data.get("nome", ""))
        _text(parte, "CodiceFiscale", parte_data.get("codice_fiscale", ""))

    difensore_data = data.get("difensore") or {}
    difensore = ET.SubElement(root, "Difensore")
    _text(difensore, "Nome", difensore_data.get("nome", ""))
    _text(difensore, "CodiceFiscale", difensore_data.get("codice_fiscale", ""))
    _text(difensore, "PEC", difensore_data.get("pec", ""))

    allegati = ET.SubElement(root, "Allegati")
    for allegato_data in data.get("allegati", []) or []:
        allegato = ET.SubElement(allegati, "Allegato")
        allegato.set("nome", str(allegato_data.get("nome", "")))
        allegato.set("tipo", str(allegato_data.get("tipo", "")))
        allegato.set("sha256", str(allegato_data.get("sha256", "")))
        allegato.set("obbligatorio", "true" if allegato_data.get("obbligatorio") else "false")

    raw = ET.tostring(root, encoding="utf-8")
    pretty = minidom.parseString(raw).toprettyxml(indent="  ", encoding="UTF-8")
    return bytes(pretty)
