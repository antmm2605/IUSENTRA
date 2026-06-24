"""Schema XFA dei moduli ministeriali PAT/SIGA.

L'interfaccia PAT di IUSENTRA deve seguire il modulo ministeriale selezionato:
questo file estrae campi, sezioni, azioni e righe ripetibili direttamente dal
template XFA ufficiale, evitando una lista statica di campi generici.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any
from xml.etree import ElementTree as ET

from pypdf import PdfReader

from pct.pat_pdf_templates import PAT_PDF_TEMPLATES


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.split("}", 1)[-1]


def _clean(value: Any) -> str:
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def _slug(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip()).strip("-").lower()
    return text or "campo"


def _humanise_name(value: str) -> str:
    text = re.sub(r"^(txt|tf|rb|btn)", "", value or "", flags=re.IGNORECASE)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = text.replace("_", " ").strip()
    return text[:1].upper() + text[1:] if text else "Campo"


def _read_template_xml(module_id: str) -> ET.Element:
    template = PAT_PDF_TEMPLATES[module_id]
    reader = PdfReader(str(template.path))
    acro = reader.trailer["/Root"]["/AcroForm"].get_object()
    xfa = acro.get("/XFA")
    if not isinstance(xfa, list):
        raise ValueError("Il modulo PAT ufficiale non contiene il pacchetto XFA atteso.")
    for index in range(0, len(xfa), 2):
        if str(xfa[index]) == "template":
            return ET.fromstring(xfa[index + 1].get_object().get_data())
    raise ValueError("Template XFA non trovato nel modulo PAT ufficiale.")


def _iter_named(element: ET.Element, path: tuple[str, ...] = ()) -> list[tuple[ET.Element, tuple[str, ...]]]:
    name = element.attrib.get("name") or _local_name(element.tag)
    current = (*path, name)
    rows = [(element, current)]
    for child in list(element):
        rows.extend(_iter_named(child, current))
    return rows


def _field_caption(field: ET.Element) -> str:
    captions: list[str] = []
    for node in field.iter():
        if _local_name(node.tag) == "caption":
            for child in node.iter():
                if _local_name(child.tag) == "text" and child.text and child.text.strip():
                    captions.append(child.text.strip())
    return _clean(" ".join(captions))


def _field_items(field: ET.Element) -> list[str]:
    values: list[str] = []
    for child in list(field):
        if _local_name(child.tag) != "items":
            continue
        for item in list(child):
            if item.text and item.text.strip():
                values.append(item.text.strip())
    return values


def _field_options(field: ET.Element) -> list[dict[str, str]]:
    items = _field_items(field)
    if len(items) > 2 and len(items) % 2 == 0:
        half = len(items) // 2
        labels = items[:half]
        exports = items[half:]
        return [{"value": export, "label": label} for label, export in zip(labels, exports)]
    return [{"value": item, "label": item} for item in items]


def _field_type(field: ET.Element, path: tuple[str, ...], *, grouped_radio: bool = False) -> str:
    name = field.attrib.get("name") or path[-1]
    caption = _field_caption(field)
    items = _field_items(field)
    lowered = " ".join([name, caption, "/".join(path)]).casefold()
    if grouped_radio:
        return "radio"
    if name.startswith("txtAllegato") or name.startswith("tfAllegato"):
        return "document"
    if items:
        if set(items) <= {"S", "N"} and len(items) == 2:
            return "checkbox"
        return "select"
    if "data" in lowered or name.lower().startswith("date"):
        return "date"
    if any(token in lowered for token in ("oggetto", "descrizione", "motivazione", "note", "ragioni")):
        return "textarea"
    return "text"


def _section_for(path: tuple[str, ...]) -> tuple[str, str]:
    joined = "/".join(path)
    rules = (
        ("subFormIntestazione", "intestazione", "Intestazione modulo"),
        ("selectSede", "sede", "Sede"),
        ("subFormRicorso", "ricorso", "Ricorso"),
        ("tableRicorso", "ricorso", "Ricorso"),
        ("subFormAtto", "atti", "Atti di causa"),
        ("tableAtti", "atti", "Atti di causa"),
        ("subFormIndiceDocumenti", "documenti", "Documenti di causa"),
        ("tableIndiceDocumenti", "documenti", "Documenti di causa"),
        ("subFormRicorrente", "ricorrenti", "Ricorrenti e parti depositanti"),
        ("tableRicorrente", "ricorrenti", "Ricorrenti e parti depositanti"),
        ("subFormResistente", "resistenti", "Resistenti e controparti"),
        ("tableResistente", "resistenti", "Resistenti e controparti"),
        ("subFormDifensori", "difensori", "Difensori"),
        ("tableDifensori", "difensori", "Difensori"),
        ("subFormDomiciliatario", "domiciliatario", "Domiciliatario e comunicazioni"),
        ("tableDomiciliatario", "domiciliatario", "Domiciliatario e comunicazioni"),
        ("subFormComunicazioni", "domiciliatario", "Domiciliatario e comunicazioni"),
        ("tableOggetto", "oggetto", "Oggetto"),
        ("tableOggettoEsteso", "oggetto", "Oggetto"),
        ("subFormRitoAppalti", "rito-appalti", "Rito appalti e CIG"),
        ("subFormRitoSport", "rito-sportivo", "Rito sportivo"),
        ("subFormPNRR", "pnrr", "PNRR"),
        ("subFormProvvedimentoImpugnato", "provvedimenti", "Provvedimenti impugnati"),
        ("tableProvvedimentoImpugnato", "provvedimenti", "Provvedimenti impugnati"),
        ("SubformAttiImpugnati", "atti-impugnati", "Atti impugnati"),
        ("tableAttiImpugnati", "atti-impugnati", "Atti impugnati"),
        ("subFormProcura", "procura", "Procura"),
        ("tableProcura", "procura", "Procura"),
        ("subFormRelazione", "notifiche", "Notifica"),
        ("tableRelazione", "notifiche", "Notifica"),
        ("subFormCopiaNotificata", "notifiche", "Notifica"),
        ("subFormRicorsiConnessi", "ricorsi-connessi", "Ricorsi connessi"),
        ("tableRicorsiConnessi", "ricorsi-connessi", "Ricorsi connessi"),
        ("subFormContributo", "contributo", "Contributo unificato"),
        ("tableContributo", "contributo", "Contributo unificato"),
        ("subFormAsseverazione", "firma", "Firma digitale e asseverazione"),
        ("Firma", "firma", "Firma digitale e asseverazione"),
        ("Rimborso", "rimborso", "Richiesta rimborso"),
        ("Versamento", "versamento", "Dati versamento"),
    )
    for needle, section_id, title in rules:
        if needle in joined:
            return section_id, title
    return "altri-dati", "Altri dati ministeriali"


def _repeatable_group(path: tuple[str, ...]) -> tuple[str, str] | tuple[None, None]:
    for index, part in enumerate(path):
        if part.lower().startswith("riga"):
            group = "/".join(path[: index + 1])
            return group, _humanise_name(part)
    return None, None


def _is_button(field: ET.Element) -> bool:
    name = field.attrib.get("name") or ""
    caption = _field_caption(field).casefold()
    return name.lower().startswith("btn") or name in {"Button1"} or caption in {"aggiungi", "allega", "x"} or caption.startswith("carica ")


def _is_technical(field: ET.Element, path: tuple[str, ...]) -> bool:
    name = field.attrib.get("name") or path[-1]
    if name.startswith("txtAllegato") or name.startswith("tfAllegato"):
        return False
    if name in {"txtModuleName", "txtModuleVersion", "txtIdFile", "selectLingua"}:
        return True
    if field.attrib.get("presence") in {"hidden", "invisible"}:
        return True
    if field.attrib.get("access") == "readOnly":
        return True
    return False


_BINDING_BY_FIELD_NAME: dict[str, str] = {
    "selectSede": "sede",
    "annoRicorso": "anno_rg",
    "numeroRicorso": "nrg",
    "numeroNRGRiferimento": "nrg",
    "annoNRGRiferimento": "anno_rg",
    "tipoAtto": "tipologia_atto",
    "tipoRicorsoTar": "tipo_ricorso",
    "tipoRicorsoCds": "tipo_ricorso",
    "oggetto": "oggetto",
    "oggettoEsteso": "oggetto",
    "codiceFiscale": "codice_fiscale",
    "txtAllegatoAtto": "descrizione_allegati",
    "txtAllegatoRicorso": "descrizione_allegati",
    "txtAllegatoIndice": "descrizione_allegati",
    "motivazioneRichiesta": "motivo_rimborso",
    "tfIban": "iban",
    "tfEstremiVersamento": "dati_pagamento",
    "tfImportoVersamento": "contributo_unificato",
    "tfCodiceFiscale": "codice_fiscale",
}


def _schema_field(field: ET.Element, path: tuple[str, ...], *, grouped_radio: bool = False) -> dict[str, Any]:
    name = field.attrib.get("name") or path[-1]
    xfa_path = "/".join(path)
    caption = _field_caption(field)
    items = _field_items(field)
    group_path, group_label = _repeatable_group(path)
    section_id, section_title = _section_for(path)
    label = caption or _humanise_name(name)
    binding = _BINDING_BY_FIELD_NAME.get(name, "")
    return {
        "id": _slug(xfa_path),
        "path": xfa_path,
        "name": name,
        "label": label,
        "type": _field_type(field, path, grouped_radio=grouped_radio),
        "required": False,
        "technical": _is_technical(field, path),
        "readOnly": field.attrib.get("access") == "readOnly",
        "presence": field.attrib.get("presence") or "",
        "bindingFieldId": binding,
        "sectionId": section_id,
        "sectionTitle": section_title,
        "repeatableGroup": group_path or "",
        "repeatableLabel": group_label or "",
        "options": _field_options(field),
    }


def _radio_group_schema(parent_path: tuple[str, ...], fields: list[tuple[ET.Element, tuple[str, ...]]]) -> dict[str, Any]:
    section_id, section_title = _section_for(parent_path)
    group_path, group_label = _repeatable_group(parent_path)
    options = []
    for field, path in fields:
        name = field.attrib.get("name") or path[-1]
        item_values = _field_items(field)
        label = _field_caption(field) or _humanise_name(name)
        options.append({
            "value": name,
            "label": label,
            "export": item_values[0] if item_values else name,
            "path": "/".join(path),
        })
    name = parent_path[-1]
    return {
        "id": _slug("/".join(parent_path)),
        "path": "/".join(parent_path),
        "name": name,
        "label": _humanise_name(name),
        "type": "radio",
        "required": False,
        "technical": False,
        "readOnly": False,
        "presence": "",
        "bindingFieldId": "",
        "sectionId": section_id,
        "sectionTitle": section_title,
        "repeatableGroup": group_path or "",
        "repeatableLabel": group_label or "",
        "options": options,
    }


def _section_order(section_id: str) -> int:
    order = [
        "intestazione",
        "sede",
        "ricorso",
        "atti",
        "documenti",
        "ricorrenti",
        "resistenti",
        "difensori",
        "domiciliatario",
        "oggetto",
        "rito-appalti",
        "rito-sportivo",
        "pnrr",
        "provvedimenti",
        "atti-impugnati",
        "procura",
        "notifiche",
        "ricorsi-connessi",
        "contributo",
        "versamento",
        "rimborso",
        "firma",
        "altri-dati",
    ]
    try:
        return order.index(section_id)
    except ValueError:
        return len(order)


@lru_cache(maxsize=16)
def build_pat_xfa_schema_payload(module_id: str) -> dict[str, Any]:
    """Restituisce lo schema operativo ricavato dal template XFA ufficiale."""

    template = PAT_PDF_TEMPLATES.get(module_id)
    if template is None:
        return {
            "moduleId": module_id,
            "templateFile": "",
            "rawFieldCount": 0,
            "fieldCount": 0,
            "operationalFieldCount": 0,
            "technicalFieldCount": 0,
            "actionCount": 0,
            "sections": [],
        }
    root = _read_template_xml(module_id)
    named = _iter_named(root)
    field_rows = [(element, path) for element, path in named if _local_name(element.tag) == "field"]
    radio_groups: dict[tuple[str, ...], list[tuple[ET.Element, tuple[str, ...]]]] = {}
    for field, path in field_rows:
        if len(path) >= 2 and path[-2].startswith("rb"):
            radio_groups.setdefault(path[:-1], []).append((field, path))

    grouped_paths = {path for rows in radio_groups.values() for _field, path in rows}
    fields: list[dict[str, Any]] = []
    actions: list[dict[str, str]] = []
    for parent_path, rows in radio_groups.items():
        fields.append(_radio_group_schema(parent_path, rows))
    for field, path in field_rows:
        xfa_path = "/".join(path)
        if path in grouped_paths:
            continue
        if _is_button(field):
            section_id, section_title = _section_for(path)
            group_path, group_label = _repeatable_group(path)
            actions.append({
                "id": _slug(xfa_path),
                "path": xfa_path,
                "name": field.attrib.get("name") or path[-1],
                "label": _field_caption(field) or _humanise_name(field.attrib.get("name") or path[-1]),
                "sectionId": section_id,
                "sectionTitle": section_title,
                "repeatableGroup": group_path or "",
                "repeatableLabel": group_label or "",
                "presence": field.attrib.get("presence") or "",
            })
            continue
        fields.append(_schema_field(field, path))

    section_map: dict[str, dict[str, Any]] = {}
    for field in fields:
        section = section_map.setdefault(
            field["sectionId"],
            {
                "id": field["sectionId"],
                "title": field["sectionTitle"],
                "fields": [],
                "actions": [],
                "fieldCount": 0,
                "technicalCount": 0,
            },
        )
        section["fields"].append(field)
        section["fieldCount"] += 1
        if field.get("technical"):
            section["technicalCount"] += 1
    for action in actions:
        section = section_map.setdefault(
            action["sectionId"],
            {
                "id": action["sectionId"],
                "title": action["sectionTitle"],
                "fields": [],
                "actions": [],
                "fieldCount": 0,
                "technicalCount": 0,
            },
        )
        section["actions"].append(action)

    sections = sorted(section_map.values(), key=lambda item: _section_order(str(item["id"])))
    repeatable_groups = sorted({
        field["repeatableGroup"]: field["repeatableLabel"]
        for field in fields
        if field.get("repeatableGroup")
    }.items())
    technical_field_count = sum(section["technicalCount"] for section in sections)
    return {
        "moduleId": module_id,
        "templateFile": template.filename,
        "officialCode": template.official_code,
        "rawFieldCount": len(field_rows),
        "fieldCount": len(fields),
        "operationalFieldCount": len(fields) - technical_field_count,
        "technicalFieldCount": technical_field_count,
        "actionCount": len(actions),
        "repeatableGroups": [{"path": path, "label": label} for path, label in repeatable_groups],
        "sections": sections,
    }


def build_all_pat_xfa_schema_payloads() -> dict[str, dict[str, Any]]:
    return {module_id: build_pat_xfa_schema_payload(module_id) for module_id in PAT_PDF_TEMPLATES}


__all__ = ["build_all_pat_xfa_schema_payloads", "build_pat_xfa_schema_payload"]
