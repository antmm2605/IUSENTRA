import json
from pathlib import Path
import zipfile

from pct.pst_services import PSTOfficialCatalogAdapter


def _write_wsdl_catalog_zip(tmp_path: Path) -> Path:
    wsdl = """<?xml version="1.0" encoding="UTF-8"?>
<wsdl:definitions
  xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"
  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
  xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/"
  xmlns:tns="http://www.giustizia.it/serviziTelematici/catalogo"
  targetNamespace="http://www.giustizia.it/serviziTelematici/catalogo">
  <wsdl:types>
    <xsd:schema targetNamespace="http://www.giustizia.it/serviziTelematici/catalogo">
      <xsd:complexType name="registro">
        <xsd:sequence>
          <xsd:element name="codice" type="xsd:string"/>
          <xsd:element name="descrizione" type="xsd:string"/>
          <xsd:element name="codiceApplicazione" type="xsd:string"/>
        </xsd:sequence>
      </xsd:complexType>
      <xsd:complexType name="ufficiGiudiziari">
        <xsd:sequence>
          <xsd:element name="codiceUfficio" type="xsd:string"/>
          <xsd:element name="descrizione" type="xsd:string"/>
          <xsd:element name="tipoUfficio" type="xsd:string"/>
          <xsd:element name="descTipoUfficio" type="xsd:string"/>
          <xsd:element name="distretto" type="xsd:string"/>
          <xsd:element name="comune" type="xsd:string"/>
        </xsd:sequence>
      </xsd:complexType>
      <xsd:complexType name="rito">
        <xsd:sequence>
          <xsd:element name="idRito" type="xsd:string"/>
          <xsd:element name="descrizione" type="xsd:string"/>
          <xsd:element name="registro" type="xsd:string"/>
        </xsd:sequence>
      </xsd:complexType>
      <xsd:element name="getRegistriFromUfficio">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="codiceUfficio" type="xsd:string"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="getRegistriFromUfficioResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="return" type="tns:registro" minOccurs="0" maxOccurs="unbounded"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="getRito">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="codiceRegistro" type="xsd:string"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="getRitoResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="return" type="tns:rito" minOccurs="0" maxOccurs="unbounded"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="getListaUfficiGiudiziari">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="distretto" type="xsd:string"/>
            <xsd:element name="comune" type="xsd:string"/>
            <xsd:element name="tipoUfficio" type="xsd:string"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
      <xsd:element name="getListaUfficiGiudiziariResponse">
        <xsd:complexType>
          <xsd:sequence>
            <xsd:element name="return" type="tns:ufficiGiudiziari" minOccurs="0" maxOccurs="unbounded"/>
          </xsd:sequence>
        </xsd:complexType>
      </xsd:element>
    </xsd:schema>
  </wsdl:types>
  <wsdl:portType name="CatalogoServiziPortType">
    <wsdl:operation name="getRegistriFromUfficio"/>
    <wsdl:operation name="getRito"/>
    <wsdl:operation name="getListaUfficiGiudiziari"/>
  </wsdl:portType>
  <wsdl:service name="CatalogoServiziBeanService">
    <wsdl:port name="CatalogoServiziBean" binding="tns:CatalogoServiziBeanBinding">
      <soap:address location="http://sdm-pst/servizi/CatalogoServizi"/>
    </wsdl:port>
  </wsdl:service>
</wsdl:definitions>
"""
    zip_path = tmp_path / "A1_WSDL_CATALOG_v1.52b.zip"
    entry = "A1_WSDL_CATALOG_v1.52/WSDL/Altri Servizi/Catalogo UG/CatalogoServiziBeanService.wsdl"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr(entry, wsdl)
    return zip_path


def test_adapter_parsa_il_catalogo_wsdl_ufficiale(tmp_path):
    zip_path = _write_wsdl_catalog_zip(tmp_path)
    adapter = PSTOfficialCatalogAdapter(
        wsdl_catalog_zip_path=str(zip_path),
        cache_path=str(tmp_path / "pst_cache.json"),
    )

    snapshot = adapter.get_runtime_snapshot()

    assert snapshot["wsdl_catalog_present"] is True
    assert snapshot["catalog_namespace"] == "http://www.giustizia.it/serviziTelematici/catalogo"
    assert snapshot["catalog_service_address"] == "http://sdm-pst/servizi/CatalogoServizi"
    assert "getRegistriFromUfficio" in snapshot["methods"]
    assert snapshot["methods"]["getRegistriFromUfficio"]["request_fields"] == ["codiceUfficio"]
    assert "getListaUfficiGiudiziari" in snapshot["methods"]


def test_adapter_usa_cache_per_registri_e_uffici(tmp_path):
    zip_path = _write_wsdl_catalog_zip(tmp_path)
    cache_path = tmp_path / "pst_cache.json"
    adapter = PSTOfficialCatalogAdapter(
        wsdl_catalog_zip_path=str(zip_path),
        cache_path=str(cache_path),
    )

    cache_payload = {
        "calls": {
            adapter._cache_key("getRegistriFromUfficio", {"codiceUfficio": "0580010"}): {
                "items": [{"codice": "RG", "descrizione": "Ruolo Generale", "codiceApplicazione": "SICI"}],
                "source": "live",
                "method": "getRegistriFromUfficio",
                "params": {"codiceUfficio": "0580010"},
                "fetched_at": "2026-04-03T10:00:00",
            },
            adapter._cache_key(
                "getListaUfficiGiudiziari",
                {"distretto": "Reggio Calabria", "comune": "Palmi", "tipoUfficio": ""},
            ): {
                "items": [
                    {
                        "codiceUfficio": "0580010",
                        "descrizione": "Tribunale di Palmi",
                        "tipoUfficio": "TRIBUNALE",
                        "descTipoUfficio": "Tribunale",
                        "distretto": "Reggio Calabria",
                        "comune": "Palmi",
                    }
                ],
                "source": "live",
                "method": "getListaUfficiGiudiziari",
                "params": {"distretto": "Reggio Calabria", "comune": "Palmi", "tipoUfficio": ""},
                "fetched_at": "2026-04-03T10:05:00",
            },
        },
        "wsdl": adapter.get_runtime_snapshot(),
    }
    cache_path.write_text(json.dumps(cache_payload), encoding="utf-8")

    registri = adapter.get_registries_for_office("0580010")
    office = adapter.find_office(
        office_name="Tribunale di Palmi",
        office_code="0580010",
        comune="Palmi",
        distretto="Reggio Calabria",
    )

    assert registri.source == "cache"
    assert registri.items[0]["codice"] == "RG"
    assert office["source"] == "cache"
    assert office["item"]["codice_ufficio"] == "0580010"
