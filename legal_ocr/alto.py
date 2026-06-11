"""Esportazione ALTO-XML dei token OCR.

ALTO (Analyzed Layout and Text Object, schema v4 della Library of Congress) è il
formato standard per testo OCR con coordinate: lo produciamo dai token già
calcolati dal motore (token, bbox, confidenza, riga, pagina) senza dipendere da
alcun motore OCR, così è sempre generabile e verificabile.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Any, Iterable

from .models import PageArtifact

_ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _page_dims(pages: list[PageArtifact]) -> dict[int, tuple[int, int]]:
    dims: dict[int, tuple[int, int]] = {}
    for page in pages or []:
        dims[int(page.page)] = (_int(page.width, 0), _int(page.height, 0))
    return dims


def _grouped_by_page(tokens: Iterable[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    by_page: dict[int, list[dict[str, Any]]] = {}
    for token in tokens or []:
        page = _int(token.get("page", 1), 1)
        by_page.setdefault(page, []).append(token)
    return by_page


def build_alto_xml(
    tokens: list[dict[str, Any]],
    pages: list[PageArtifact] | None = None,
    *,
    source_file: str = "",
) -> str:
    """Costruisce un documento ALTO-XML v4 dai token OCR.

    I token sono raggruppati per pagina e per riga (``line_id``); ogni parola
    diventa un elemento ``String`` con coordinate (HPOS/VPOS/WIDTH/HEIGHT) e
    confidenza (WC). Funziona anche con token a bbox degenerato (fallback).
    """

    pages = pages or []
    dims = _page_dims(pages)
    by_page = _grouped_by_page(tokens)
    page_numbers = sorted(set(dims) | set(by_page)) or [1]

    alto = ET.Element("alto", {"xmlns": _ALTO_NS})
    description = ET.SubElement(alto, "Description")
    ET.SubElement(description, "MeasurementUnit").text = "pixel"
    source = ET.SubElement(description, "sourceImageInformation")
    ET.SubElement(source, "fileName").text = source_file or "documento"
    processing = ET.SubElement(description, "OCRProcessing", {"ID": "ocr-1"})
    step = ET.SubElement(processing, "ocrProcessingStep")
    sw = ET.SubElement(step, "processingSoftware")
    ET.SubElement(sw, "softwareName").text = "IUSENTRA legal_ocr"

    layout = ET.SubElement(alto, "Layout")
    string_seq = 0
    for page_no in page_numbers:
        width, height = dims.get(page_no, (0, 0))
        page_el = ET.SubElement(
            layout,
            "Page",
            {
                "ID": f"page_{page_no}",
                "PHYSICAL_IMG_NR": str(page_no),
                "WIDTH": str(width),
                "HEIGHT": str(height),
            },
        )
        print_space = ET.SubElement(
            page_el,
            "PrintSpace",
            {"HPOS": "0", "VPOS": "0", "WIDTH": str(width), "HEIGHT": str(height)},
        )
        block = ET.SubElement(print_space, "TextBlock", {"ID": f"block_{page_no}"})

        lines: dict[str, list[dict[str, Any]]] = {}
        order: list[str] = []
        for token in by_page.get(page_no, []):
            line_id = str(token.get("line_id") or f"p{page_no}-l0")
            if line_id not in lines:
                lines[line_id] = []
                order.append(line_id)
            lines[line_id].append(token)

        for line_id in order:
            line_tokens = sorted(lines[line_id], key=lambda t: _int((t.get("bbox") or [0])[0], 0))
            safe_line = line_id.replace(" ", "_")
            line_el = ET.SubElement(block, "TextLine", {"ID": f"line_{safe_line}"})
            for token in line_tokens:
                bbox = token.get("bbox") or [0, 0, 0, 0]
                string_seq += 1
                conf = max(0.0, min(1.0, float(token.get("confidence") or 0.0)))
                ET.SubElement(
                    line_el,
                    "String",
                    {
                        "ID": f"s{string_seq}",
                        "CONTENT": str(token.get("token") or ""),
                        "HPOS": str(_int(bbox[0] if len(bbox) > 0 else 0)),
                        "VPOS": str(_int(bbox[1] if len(bbox) > 1 else 0)),
                        "WIDTH": str(_int(bbox[2] if len(bbox) > 2 else 0)),
                        "HEIGHT": str(_int(bbox[3] if len(bbox) > 3 else 0)),
                        "WC": f"{conf:.2f}",
                    },
                )

    ET.indent(alto)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(alto, encoding="unicode")


__all__ = ["build_alto_xml"]
