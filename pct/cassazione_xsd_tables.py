"""Tabelle ministeriali degli schemi Cassazione in esercizio (atti di parte).

Fonte: PST, "XSD per la Corte Suprema di Cassazione", pacchetto XSD_Cassazione_20260227
(Processo Telematico di legittimita - Schemi XSD v.21), applicato in esercizio dal
04/03/2026. Gli schemi sono versionati in `docs/specs/ministero/parte/`. La versione attiva
e dichiarata una sola volta in `pct.pst_catalog.PST_CASSAZIONE_XSD_ACTIVE_VERSION`: generatore
DatiAtto, validatore e campi del deposito leggono le stesse enumerazioni, cosi un valore
eliminato dal Ministero non puo restare selezionabile.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from lxml import etree

from pct.pst_catalog import PST_CASSAZIONE_XSD_ACTIVE_VERSION

XSD_NS = {"xs": "http://www.w3.org/2001/XMLSchema"}
CASSAZIONE_SCHEMI_DIR = Path(__file__).resolve().parents[1] / "docs" / "specs" / "ministero" / "parte"


def cassazione_tipi_base_path() -> Path:
    return CASSAZIONE_SCHEMI_DIR / f"base_{PST_CASSAZIONE_XSD_ACTIVE_VERSION}" / "tipi-base.xsd"


def cassazione_parte_schema_path() -> Path:
    return CASSAZIONE_SCHEMI_DIR / f"parte_{PST_CASSAZIONE_XSD_ACTIVE_VERSION}" / "Parte-cassazione.xsd"


def _documentation(node: etree._Element) -> str:
    return " ".join("".join(node.xpath("./xs:annotation/xs:documentation//text()", namespaces=XSD_NS)).split())


@lru_cache(maxsize=16)
def cassazione_enumeration(type_name: str) -> tuple[tuple[str, str], ...]:
    """Valori e descrizioni del tipo semplice `type_name` di tipi-base.xsd in esercizio."""
    root = etree.parse(str(cassazione_tipi_base_path())).getroot()
    simple = root.find(f"xs:simpleType[@name='{type_name}']", XSD_NS)
    if simple is None:
        return ()
    return tuple(
        (str(node.get("value") or "").strip(), _documentation(node))
        for node in simple.findall("xs:restriction/xs:enumeration", XSD_NS)
        if str(node.get("value") or "").strip()
    )


def cassazione_enumeration_values(type_name: str) -> frozenset[str]:
    return frozenset(value for value, _ in cassazione_enumeration(type_name))


@lru_cache(maxsize=1)
def cassazione_parte_roots() -> frozenset[str]:
    """Radici DatiAtto dichiarate dallo schema Parte-cassazione.xsd in esercizio."""
    root = etree.parse(str(cassazione_parte_schema_path())).getroot()
    return frozenset(str(node.get("name")) for node in root.findall("xs:element", XSD_NS) if node.get("name"))


__all__ = [
    "CASSAZIONE_SCHEMI_DIR",
    "cassazione_enumeration",
    "cassazione_enumeration_values",
    "cassazione_parte_roots",
    "cassazione_parte_schema_path",
    "cassazione_tipi_base_path",
]
