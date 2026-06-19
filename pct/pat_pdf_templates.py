"""Compilazione dei moduli PAT ufficiali in formato XFA.

I moduli della Giustizia Amministrativa sono PDF XFA/LiveCycle: non espongono
campi AcroForm normali. Per questo IUSENTRA deve partire dal template
ministeriale e aggiornare i valori XFA, preservando struttura e script del PDF.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from xml.etree import ElementTree as ET

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject


TEMPLATE_DIR = Path(__file__).resolve().parent / "data" / "pat_moduli"


@dataclass(frozen=True, slots=True)
class PatPdfTemplate:
    module_id: str
    filename: str
    official_code: str

    @property
    def path(self) -> Path:
        return TEMPLATE_DIR / self.filename

    @property
    def output_name(self) -> str:
        stem = self.filename.removesuffix(".pdf")
        return f"{stem}_compilato_iusentra.pdf"


PAT_PDF_TEMPLATES: dict[str, PatPdfTemplate] = {
    "deposito_ricorso": PatPdfTemplate("deposito_ricorso", "ModuloDepositoRicorso_4.02.pdf", "DEPOSITO_RICORSO"),
    "deposito_atto": PatPdfTemplate("deposito_atto", "ModuloDepositoAtto_4.02.pdf", "DEPOSITO_ATTO"),
    "richieste_segreteria": PatPdfTemplate("richieste_segreteria", "ModuloDepositoRichiesteSegreteria_4.01.pdf", "DEPOSITO_RICHIESTE"),
    "ausiliari_parti_non_rituali": PatPdfTemplate(
        "ausiliari_parti_non_rituali",
        "ModuloDepositoPerAusiliariDelGiudiceEPartiNonRituali_4.01.pdf",
        "DEPOSITO_NON_RITUALI",
    ),
    "istanza_ante_causam": PatPdfTemplate("istanza_ante_causam", "ModuloDepositoIstanza_4.01.pdf", "DEPOSITO_ISTANZA"),
    "rimborso_contributo_unificato": PatPdfTemplate(
        "rimborso_contributo_unificato",
        "ModuloDepositoRimborso_4.01_2026.pdf",
        "DEPOSITO_RIMBORSI",
    ),
}


def _local_name(tag: Any) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.split("}", 1)[-1]


def _clean(value: Any, fallback: str = "") -> str:
    text = str(value or fallback).strip()
    return re.sub(r"\s+", " ", text)


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _value_child(field: ET.Element) -> ET.Element:
    for child in list(field):
        if _local_name(child.tag) == "value":
            return child
    tag = str(field.tag)
    namespace = tag.split("}", 1)[0].strip("{") if tag.startswith("{") else ""
    return ET.SubElement(field, f"{{{namespace}}}value" if namespace else "value")


def _text_child(value: ET.Element) -> ET.Element:
    for child in list(value):
        if _local_name(child.tag) in {"text", "integer", "decimal"}:
            return child
    tag = str(value.tag)
    namespace = tag.split("}", 1)[0].strip("{") if tag.startswith("{") else ""
    return ET.SubElement(value, f"{{{namespace}}}text" if namespace else "text")


def _set_field_text(field: ET.Element, value: str) -> None:
    text_node = _text_child(_value_child(field))
    text_node.text = _clean(value)


def _field_matches(field: ET.Element, name: str, path: tuple[str, ...], path_contains: str = "") -> bool:
    if field.attrib.get("name") != name:
        return False
    if not path_contains:
        return True
    return path_contains.casefold() in "/".join(path).casefold()


def _iter_fields(root: ET.Element) -> Iterable[tuple[ET.Element, tuple[str, ...]]]:
    def walk(element: ET.Element, path: tuple[str, ...]) -> Iterable[tuple[ET.Element, tuple[str, ...]]]:
        name = element.attrib.get("name") or _local_name(element.tag)
        current_path = (*path, name)
        if _local_name(element.tag) == "field":
            yield element, current_path
        for child in list(element):
            yield from walk(child, current_path)

    yield from walk(root, ())


def _set_first(root: ET.Element, name: str, value: Any, *, path_contains: str = "") -> bool:
    text = _clean(value)
    if not text:
        return False
    for field, path in _iter_fields(root):
        if _field_matches(field, name, path, path_contains):
            _set_field_text(field, text)
            return True
    return False


def _field_items(field: ET.Element) -> list[str]:
    values: list[str] = []
    for child in list(field):
        if _local_name(child.tag) != "items":
            continue
        for item in list(child):
            if item.text and item.text.strip():
                values.append(item.text.strip())
    return values


def _choice_export(field: ET.Element, wanted: str) -> str:
    cleaned = _normalise(wanted)
    if not cleaned:
        return ""
    items = _field_items(field)
    if not items:
        return wanted
    midpoint = len(items) // 2 if len(items) % 2 == 0 else len(items)
    labels = items[:midpoint]
    exports = items[midpoint:] if midpoint < len(items) else labels
    label_pairs = list(zip(labels, exports))
    for label, export in label_pairs:
        if _normalise(label) == cleaned or _normalise(export) == cleaned:
            return export
    wanted_tokens = set(cleaned.split())
    best: tuple[int, str] = (0, "")
    for label, export in label_pairs:
        label_tokens = set(_normalise(label).split())
        score = len(wanted_tokens & label_tokens)
        if score > best[0]:
            best = (score, export)
    return best[1] if best[0] >= 2 else wanted


def _set_choice(root: ET.Element, name: str, value: Any, *, path_contains: str = "") -> bool:
    text = _clean(value)
    if not text:
        return False
    for field, path in _iter_fields(root):
        if _field_matches(field, name, path, path_contains):
            _set_field_text(field, _choice_export(field, text))
            return True
    return False


def _split_person(value: str) -> tuple[str, str, str]:
    text = _clean(value)
    if not text:
        return "", "", ""
    legal_tokens = ("comune", "ministero", "agenzia", "regione", "provincia", "universita", "azienda", "societa", "spa", "srl")
    if any(token in _normalise(text) for token in legal_tokens):
        return "", "", text
    parts = text.split()
    if len(parts) == 1:
        return parts[0], "", ""
    return parts[0], " ".join(parts[1:]), ""


def _set_party(root: ET.Element, value: Any, fiscal_code: Any = "", *, path_contains: str) -> None:
    cognome, nome, denominazione = _split_person(_clean(value))
    if denominazione:
        _set_first(root, "denominazione", denominazione, path_contains=path_contains)
    else:
        _set_first(root, "cognome", cognome, path_contains=path_contains)
        _set_first(root, "nome", nome, path_contains=path_contains)
    _set_first(root, "codiceFiscale", fiscal_code, path_contains=path_contains)


def _selected_document_names(documents: Iterable[Mapping[str, Any]], *roles: str) -> str:
    role_set = {role for role in roles if role}
    names: list[str] = []
    for document in documents:
        role = _clean(document.get("role") or document.get("ruolo") or document.get("suggestedRole"))
        if role_set and role not in role_set:
            continue
        name = _clean(document.get("name") or document.get("nome") or document.get("filename"))
        if name:
            names.append(name)
    return "; ".join(names)


def _apply_common(root: ET.Element, fields: Mapping[str, Any], documents: list[Mapping[str, Any]]) -> None:
    _set_choice(root, "selectSede", fields.get("sede"))
    _set_first(root, "oggetto", fields.get("oggetto"), path_contains="tableOggetto")
    _set_first(root, "oggettoEsteso", fields.get("oggetto"), path_contains="tableOggettoEsteso")
    _set_first(root, "numeroRicorso", fields.get("nrg") or fields.get("numero_rg"), path_contains="subFormRicorso")
    _set_first(root, "annoRicorso", fields.get("anno_rg"), path_contains="subFormRicorso")
    _set_first(root, "numeroNRGRiferimento", fields.get("nrg") or fields.get("numero_rg"))
    _set_first(root, "annoNRGRiferimento", fields.get("anno_rg"))

    atto = _selected_document_names(documents, "atto_principale", "ricorso", "istanza")
    allegati = _selected_document_names(documents, "allegato", "documento", "ricevuta")
    procura = _selected_document_names(documents, "procura")
    notifiche = _selected_document_names(documents, "notifica", "relata")
    pagamento = _selected_document_names(documents, "contributo", "ricevuta_pagamento")
    _set_first(root, "txtAllegatoRicorso", atto)
    _set_first(root, "txtAllegatoAtto", atto)
    _set_first(root, "txtAllegatoIndice", allegati or _clean(fields.get("descrizione_allegati")))
    _set_first(root, "txtAllegatoProcura", procura)
    _set_first(root, "txtAllegatoRelazione", notifiche)
    _set_first(root, "txtAllegatoVersamento", pagamento)


def _apply_ricorso(root: ET.Element, fields: Mapping[str, Any], documents: list[Mapping[str, Any]]) -> None:
    _set_choice(root, "tipoRicorsoTar", fields.get("tipo_ricorso"))
    _set_party(root, fields.get("ricorrente") or fields.get("parte_depositante"), fields.get("codice_fiscale"), path_contains="tableRicorrente")
    _set_party(root, fields.get("resistente") or fields.get("amministrazione_resistente"), "", path_contains="tableResistente")
    contributo = _normalise(_clean(fields.get("contributo_unificato")))
    if "esente" in contributo:
        _set_first(root, "esente", "2")
        _set_first(root, "nonEsente", "")
    elif "prenot" in contributo:
        _set_first(root, "prenotazioneADebito", "1")
        _set_first(root, "nonEsente", "")
    elif contributo:
        _set_first(root, "nonEsente", "3")
    _apply_common(root, fields, documents)


def _apply_atto(root: ET.Element, fields: Mapping[str, Any], documents: list[Mapping[str, Any]]) -> None:
    _set_choice(root, "tipoAtto", fields.get("tipologia_atto"))
    _set_party(root, fields.get("parte_depositante") or fields.get("ricorrente"), fields.get("codice_fiscale"), path_contains="tableRicorrente")
    _set_party(root, fields.get("resistente") or fields.get("amministrazione_resistente"), "", path_contains="tableResistente")
    _apply_common(root, fields, documents)


def _apply_istanza(root: ET.Element, fields: Mapping[str, Any], documents: list[Mapping[str, Any]]) -> None:
    _set_choice(root, "tipoRicorsoTar", fields.get("tipo_ricorso") or "Cautelare")
    _set_party(root, fields.get("istante") or fields.get("parte_depositante"), fields.get("codice_fiscale"), path_contains="tableRicorrente")
    _set_party(root, fields.get("amministrazione_resistente") or fields.get("resistente"), "", path_contains="tableResistente")
    if fields.get("ragioni_urgenza"):
        _set_first(root, "oggettoEsteso", fields.get("ragioni_urgenza"), path_contains="tableOggettoEsteso")
    _apply_common(root, fields, documents)


def _apply_ausiliari(root: ET.Element, fields: Mapping[str, Any], documents: list[Mapping[str, Any]]) -> None:
    _set_choice(root, "tipoDepositante", fields.get("qualifica_depositante"))
    _set_first(root, "oggettoEsteso", fields.get("descrizione_deposito") or fields.get("oggetto"), path_contains="tableOggettoEsteso")
    _set_party(root, fields.get("parte_depositante"), fields.get("codice_fiscale"), path_contains="subFormRicorrente")
    _apply_common(root, fields, documents)


def _apply_rimborso(root: ET.Element, fields: Mapping[str, Any], documents: list[Mapping[str, Any]]) -> None:
    cognome, nome, denominazione = _split_person(_clean(fields.get("richiedente") or fields.get("parte_depositante")))
    _set_first(root, "tfIban", fields.get("iban"))
    _set_first(root, "motivazioneRichiesta", fields.get("motivo_rimborso"))
    _set_first(root, "tfEstremiVersamento", fields.get("dati_pagamento"))
    _set_first(root, "tfImportoVersamento", fields.get("contributo_unificato"))
    _set_first(root, "tfNomeRichiedente", nome)
    _set_first(root, "tfCognomeRichiedente", cognome)
    _set_first(root, "tfCodiceFiscale", fields.get("codice_fiscale"))
    _set_first(root, "tfDenominazioneRichiedente", denominazione or fields.get("richiedente") or fields.get("parte_depositante"))
    _set_first(root, "tfPartitaIvaCodiceFiscale", fields.get("codice_fiscale"), path_contains="subFormPersonaGiuridica")
    _apply_common(root, fields, documents)


def _apply_module_values(module_id: str, root: ET.Element, fields: Mapping[str, Any], documents: list[Mapping[str, Any]]) -> None:
    if module_id == "deposito_ricorso":
        _apply_ricorso(root, fields, documents)
    elif module_id == "deposito_atto":
        _apply_atto(root, fields, documents)
    elif module_id == "istanza_ante_causam":
        _apply_istanza(root, fields, documents)
    elif module_id == "ausiliari_parti_non_rituali":
        _apply_ausiliari(root, fields, documents)
    elif module_id == "rimborso_contributo_unificato":
        _apply_rimborso(root, fields, documents)
    else:
        _apply_common(root, fields, documents)


def _parse_template_xml(data: bytes) -> ET.Element:
    parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
    return ET.fromstring(data, parser=parser)


def build_pat_official_pdf(module_id: str, fields: Mapping[str, Any], documents: Iterable[Mapping[str, Any]] = ()) -> tuple[io.BytesIO, str]:
    """Restituisce il modulo ufficiale PAT compilato preservando XFA e layout."""

    template = PAT_PDF_TEMPLATES.get(module_id)
    if template is None:
        raise ValueError("Modulo PAT ufficiale non configurato.")
    if not template.path.exists():
        raise FileNotFoundError(f"Template ufficiale PAT mancante: {template.path}")

    reader = PdfReader(str(template.path))
    writer = PdfWriter(clone_from=reader)
    acro = writer._root_object["/AcroForm"].get_object()
    xfa = acro.get("/XFA")
    if not isinstance(xfa, list):
        raise ValueError("Il modulo PAT ufficiale non contiene il pacchetto XFA atteso.")

    docs = [dict(document) for document in documents]
    for index in range(0, len(xfa), 2):
        if str(xfa[index]) != "template":
            continue
        original_stream = xfa[index + 1].get_object()
        root = _parse_template_xml(original_stream.get_data())
        namespace = root.tag.split("}", 1)[0].strip("{") if root.tag.startswith("{") else ""
        if namespace:
            ET.register_namespace("", namespace)
        _apply_module_values(module_id, root, fields, docs)
        compiled_xml = ET.tostring(root, encoding="utf-8", xml_declaration=False)
        stream = DecodedStreamObject()
        stream.set_data(compiled_xml)
        xfa[index + 1] = writer._add_object(stream)
        break

    acro[NameObject("/XFA")] = xfa
    for document in docs:
        name = _clean(document.get("name") or document.get("nome") or document.get("filename"))
        content = document.get("contentBytes") or document.get("content_bytes")
        if not name or not isinstance(content, (bytes, bytearray)):
            continue
        writer.add_attachment(name, bytes(content))
    buffer = io.BytesIO()
    writer.write(buffer)
    buffer.seek(0)
    return buffer, template.output_name


__all__ = ["PAT_PDF_TEMPLATES", "build_pat_official_pdf"]
