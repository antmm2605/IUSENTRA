from __future__ import annotations

from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "import_pst_xsd_codici_oggetto", ROOT / "scripts" / "import_pst_xsd_codici_oggetto.py"
)
assert _spec and _spec.loader
_importer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_importer)
merge_records = _importer.merge_records
parse_xsd_file = _importer.parse_xsd_file


def test_parse_xsd_enumerations_with_documentation(tmp_path: Path):
    sample = tmp_path / "tipi-base.xsd"
    sample.write_text(
        """<?xml version='1.0' encoding='UTF-8'?>
        <xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema'>
          <xs:simpleType name='CodiciOggettoSICID'>
            <xs:restriction base='xs:string'>
              <xs:enumeration value='030'>
                <xs:annotation><xs:documentation>Procedimento per convalida di sfratto</xs:documentation></xs:annotation>
              </xs:enumeration>
              <xs:enumeration value='030011'>
                <xs:annotation><xs:documentation>Intimazione di sfratto per morosità - uso abitativo</xs:documentation></xs:annotation>
              </xs:enumeration>
            </xs:restriction>
          </xs:simpleType>
        </xs:schema>
        """,
        encoding="utf-8",
    )
    records = merge_records(parse_xsd_file(sample))
    by_code = {record["codice"]: record for record in records}
    assert by_code["030011"]["descrizione"].startswith("Intimazione")
    assert by_code["030011"]["codicePadre"] == "030"
    assert by_code["030011"]["descrizionePadre"] == "Procedimento per convalida di sfratto"
