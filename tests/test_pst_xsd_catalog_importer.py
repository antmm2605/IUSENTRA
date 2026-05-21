from __future__ import annotations

from io import BytesIO
import json
import zipfile

from pct.guida_pratica.xsd_catalog_importer import (
    build_catalog_payload,
    load_kb_records,
    parse_xsd_bytes,
    records_from_zip_bytes,
)


def _sample_xsd() -> bytes:
    return b'''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
  <xs:simpleType name="CodiceOggettoPST">
    <xs:restriction base="xs:string">
      <xs:enumeration value="030011">
        <xs:annotation><xs:documentation>Intimazione di sfratto per morosita</xs:documentation></xs:annotation>
      </xs:enumeration>
      <xs:enumeration value="2026">
        <xs:annotation><xs:documentation>Anno tecnico da ignorare</xs:documentation></xs:annotation>
      </xs:enumeration>
    </xs:restriction>
  </xs:simpleType>
</xs:schema>'''


def test_parse_xsd_bytes_extracts_codici_oggetto() -> None:
    records = parse_xsd_bytes(_sample_xsd(), file_name="tipi-base.xsd", package_key="sici", package_label="XSD SICI")
    assert any(record.codice == "030011" for record in records)
    assert all(record.codice != "2026" for record in records)


def test_records_from_nested_zip() -> None:
    inner = BytesIO()
    with zipfile.ZipFile(inner, "w") as zf:
        zf.writestr("tipi-base.xsd", _sample_xsd())
    outer = BytesIO()
    with zipfile.ZipFile(outer, "w") as zf:
        zf.writestr("nested.zip", inner.getvalue())
    records = records_from_zip_bytes(outer.getvalue(), archive_name="outer.zip", package_key="sici", package_label="XSD SICI")
    assert [record.codice for record in records] == ["030011"]


def test_build_catalog_payload_is_json_serializable() -> None:
    records = parse_xsd_bytes(_sample_xsd(), file_name="tipi-base.xsd", package_key="sici", package_label="XSD SICI")
    payload = build_catalog_payload(records, source_label="test")
    dumped = json.dumps(payload, ensure_ascii=False)
    assert "030011" in dumped
    assert payload["records"][0]["confidence"] in {"alta", "media"}


def test_load_kb_records_keeps_curated_codes() -> None:
    records = load_kb_records("pct/data/legal_knowledge_base.json")
    codes = {record.codice for record in records}
    assert "030001" in codes
    assert "030011" in codes
