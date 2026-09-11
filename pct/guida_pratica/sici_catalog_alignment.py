"""Allineamento del registro SICID del catalogo codici oggetto agli XSD SICI in esercizio.

Base: enumeration ``CodiceOggetto`` di ``Atti/sici/tipi-base.xsd`` del pacchetto PST in
esercizio (XSD_SICI_20260508, pubblicato il 12/05/2026 e in esercizio dal 14/05/2026;
Nota modifiche XSD, versione 1 dell'11/05/2026). Il deposito puo usare solo codici presenti
nell'enumeration ufficiale e con la descrizione ministeriale: il catalogo non deve
conservare descrizioni superate che il Ministero ha corretto perche inducevano in errore.

Il modulo e puro: riceve dizionari gia caricati e restituisce le modifiche, cosi lo script
di aggiornamento e i test di regressione usano la stessa regola.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from lxml import etree

XSD_NS = {"xs": "http://www.w3.org/2001/XMLSchema"}
REGISTRY_ORDER = ("SICID", "SIGP", "CASSAZIONE", "UNEP")
SICID = "SICID"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())


def load_sici_codici_oggetto(tipi_base_xsd: str | Path) -> dict[str, str]:
    """Legge codice -> descrizione ufficiale dal tipo ``CodiceOggetto`` di tipi-base.xsd."""
    root = etree.parse(str(tipi_base_xsd)).getroot()
    simple = root.find("xs:simpleType[@name='CodiceOggetto']", XSD_NS)
    if simple is None:
        raise ValueError(f"Tipo CodiceOggetto assente in {tipi_base_xsd}")
    out: dict[str, str] = {}
    for node in simple.findall("xs:restriction/xs:enumeration", XSD_NS):
        code = _clean(node.get("value"))
        text = _clean(" ".join(node.xpath("./xs:annotation/xs:documentation//text()", namespaces=XSD_NS)))
        if code:
            out[code] = text or f"Codice {code}"
    return out


@dataclass
class AlignmentReport:
    descrizioni_corrette: list[str] = field(default_factory=list)
    registro_aggiunto: list[str] = field(default_factory=list)
    registro_rimosso: list[str] = field(default_factory=list)
    codici_mancanti: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, list[str]]:
        return {
            "descrizioni_corrette": self.descrizioni_corrette,
            "registro_aggiunto": self.registro_aggiunto,
            "registro_rimosso": self.registro_rimosso,
            "codici_mancanti": self.codici_mancanti,
        }


def _ordered_registries(registries: list[str]) -> list[str]:
    known = [item for item in REGISTRY_ORDER if item in registries]
    return known + sorted(item for item in registries if item not in REGISTRY_ORDER)


def _refresh_descriptions(record: dict[str, Any]) -> None:
    per_registry = record.get("descrizioniPerRegistro") or {}
    registries = record.get("registri") or []
    primary = per_registry.get(registries[0], record.get("descrizione", "")) if registries else record.get("descrizione", "")
    alternatives: list[str] = []
    for registry in registries:
        value = per_registry.get(registry, "")
        if value and value != primary and value not in alternatives:
            alternatives.append(value)
    record["descrizione"] = primary
    record["descrizioniAlternative"] = alternatives


def _refresh_sources(record: dict[str, Any], *, old_source: str, new_source: str, with_sicid: bool) -> None:
    sources = [new_source if item == old_source else item for item in record.get("fileFonti") or []]
    if with_sicid and new_source not in sources:
        sources.append(new_source)
    if not with_sicid:
        sources = [item for item in sources if item != new_source]
    record["fileFonti"] = sorted(dict.fromkeys(sources))
    if with_sicid and (record.get("registri") or [""])[0] == SICID:
        record["fileFonte"] = new_source
    elif record.get("fileFonte") in {old_source, new_source} or record.get("fileFonte") not in record["fileFonti"]:
        record["fileFonte"] = record["fileFonti"][0] if record["fileFonti"] else ""


def align_catalog_records(
    records: list[dict[str, Any]],
    official: dict[str, str],
    *,
    old_source: str,
    new_source: str,
) -> tuple[list[dict[str, Any]], AlignmentReport]:
    """Allinea registri, descrizioni SICID e fonti dei record del catalogo tecnico."""
    report = AlignmentReport()
    aligned: list[dict[str, Any]] = []
    present: set[str] = set()
    for original in records:
        record = deepcopy(original)
        code = str(record.get("codice") or "")
        present.add(code)
        registries = list(record.get("registri") or [])
        per_registry = dict(record.get("descrizioniPerRegistro") or {})
        before = (list(registries), dict(per_registry))
        if code in official:
            if SICID not in registries:
                registries.append(SICID)
                report.registro_aggiunto.append(code)
            elif per_registry.get(SICID) != official[code]:
                report.descrizioni_corrette.append(code)
            per_registry[SICID] = official[code]
        elif SICID in registries:
            registries.remove(SICID)
            per_registry.pop(SICID, None)
            report.registro_rimosso.append(code)
        record["registri"] = _ordered_registries(registries)
        record["descrizioniPerRegistro"] = {key: per_registry[key] for key in record["registri"] if key in per_registry}
        if (record["registri"], record["descrizioniPerRegistro"]) != before:
            _refresh_descriptions(record)
        _refresh_sources(record, old_source=old_source, new_source=new_source, with_sicid=code in official)
        aligned.append(record)
    report.codici_mancanti = sorted(code for code in official if code not in present)
    return aligned, report


def build_ui_catalog(catalog: dict[str, Any], ui_keys: list[str]) -> dict[str, Any]:
    """Proiezione compatta usata dalla ricerca React (stesso ordine e stessi campi)."""
    return {
        "versione": catalog["versione"],
        "fonte": catalog["fonte"],
        "supportoUi": catalog["supportoUi"],
        "totaleCodici": len(catalog["records"]),
        "records": [{key: record.get(key) for key in ui_keys} for record in catalog["records"]],
    }


def _replace_text(node: Any, old: str, new: str) -> Any:
    """Sostituisce la denominazione superata in tutti i testi della scheda (es. contesto Lex)."""
    if isinstance(node, dict):
        for key, value in node.items():
            node[key] = _replace_text(value, old, new)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            node[index] = _replace_text(value, old, new)
    elif isinstance(node, str) and old in node:
        return node.replace(old, new)
    return node


def align_kb_items(
    items: list[dict[str, Any]],
    catalog_by_code: dict[str, dict[str, Any]],
    codes: set[str],
    *,
    old_source: str,
    new_source: str,
) -> list[str]:
    """Allinea le schede Guida Pratica dei soli codici cambiati negli XSD SICI in esercizio.

    Le denominazioni curate delle altre schede non si toccano: cambiano nome, uffici e schema
    solo le schede dei codici con descrizione ministeriale corretta o registro SICID aggiunto.
    """
    changed: list[str] = []
    for item in items:
        code = str(item.get("codice") or "")
        record = catalog_by_code.get(code)
        if code not in codes or record is None:
            continue
        before = deepcopy(item)
        previous_name = str(item.get("denominazione") or "")
        if previous_name and previous_name != record["descrizione"]:
            _replace_text(item, previous_name, record["descrizione"])
        item["denominazione"] = record["descrizione"]
        offices = [office for office in item.get("uffici_destinatari") or [] if office != SICID]
        item["uffici_destinatari"] = [SICID, *offices]
        xsd = item.get("catalogo_pst_xsd") if isinstance(item.get("catalogo_pst_xsd"), dict) else None
        previous_source = (xsd or {}).get("file_fonte")
        if xsd is not None:
            xsd["file_fonte"] = new_source
        atto = item.get("atto_principale") if isinstance(item.get("atto_principale"), dict) else None
        if atto is not None:
            if atto.get("schema_xsd_ministeriale") in {old_source, previous_source}:
                atto["schema_xsd_ministeriale"] = new_source
        if item != before:
            changed.append(code)
    return changed


__all__ = [
    "AlignmentReport",
    "align_catalog_records",
    "align_kb_items",
    "build_ui_catalog",
    "load_sici_codici_oggetto",
]
