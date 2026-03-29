from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.polisWeb import ClientPolisWeb, _matches_parte_filters, _pst_namespace_qbuilder


def _client() -> ClientPolisWeb:
    return ClientPolisWeb(
        cert_pem_path="cert.pem",
        key_pem_path="key.pem",
        codice_fiscale_avvocato="MNTRRT64L01L063H",
    )


def test_polisweb_qbuilder_namespace_sicid():
    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"
    assert _pst_namespace_qbuilder(base) == "urn:CONS-SICC-BE"


def test_polisweb_costruisce_body_qbuilder_ricerca_per_tipo():
    client = _client()
    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"

    xml = client._soap_ricerca_fascicoli_qbuilder(
        base,
        "0800570094",
        "1025",
        2024,
        None,
        None,
    )

    assert 'InvocationDomain name="JPW" role="AVV" group="0800570094"' in xml
    assert '<execute xmlns="urn:CONS-SICC-BE">' in xml
    assert "<name>RicercaInformazioniFascicoloPerTipo</name>" in xml
    assert '<value name="tipo" type="string">RGN</value>' in xml


def test_polisweb_parse_qbuilder_fascicoli_xml():
    client = _client()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SICC-BE"><return available="1" time="2026-03-29 18:51:21" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType"><ns2:row class="InfoFascicoloExt"><ns2:property name="IDFASCICOLO" type="string">172944</ns2:property><ns2:property name="IDUFFICIO" type="string">0800570094</ns2:property><ns2:property name="ANNORUOLO" type="long">2024</ns2:property><ns2:property name="NUMERORUOLO" type="string">00001025</ns2:property><ns2:property name="GIUDICE" type="string">GIOVANNELLA MARIA ELENA</ns2:property><ns2:property name="RUOLODESCRIZIONE" type="string">GENERALE DEGLI AFFARI CIVILI CONTENZIOSI</ns2:property><ns2:property name="STATOFASCICOLODESCRIZIONE" type="string">PROCEDIMENTO DEFINITO</ns2:property><ns2:property name="OGGETTOFASCICOLO" type="string">Vendita di cose immobili</ns2:property><ns2:subRows class="InfoParte"><ns2:row><ns2:property name="COGNOME" type="string">STILLITANO</ns2:property><ns2:property name="NOME" type="string">FRANCESCO</ns2:property><ns2:property name="CODICEFISCALEPARTE" type="string">STLFNC45E26L063X</ns2:property></ns2:row></ns2:subRows></ns2:row></return></ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    fascicoli = client._parse_fascicoli_qbuilder_xml(xml)

    assert len(fascicoli) == 1
    assert fascicoli[0].numero_rg == "1025"
    assert fascicoli[0].anno_rg == 2024
    assert fascicoli[0].codice_ufficio == "0800570094"
    assert fascicoli[0].ruolo == "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI"
    assert fascicoli[0].stato == "PROCEDIMENTO DEFINITO"
    assert fascicoli[0].parti == ["STILLITANO FRANCESCO"]
    assert getattr(fascicoli[0], "parti_dettaglio")[0]["codice_fiscale"] == "STLFNC45E26L063X"


def test_polisweb_parse_qbuilder_documenti_xml():
    client = _client()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SICC-BE"><return available="1" time="2026-03-29 18:52:17" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType"><ns2:row class="DocumentoFascicolo"><ns2:property name="IDUFFICIO" type="string">0800570094</ns2:property><ns2:property name="IDDOCUMENTO" type="string">33581101</ns2:property><ns2:property name="TIPO" type="string">{http://schemi.processotelematico.giustizia.it/sicid/magistrato/Sentenza/v3}:SentenzaDefinitiva</ns2:property><ns2:property name="STATO" type="string">depositato</ns2:property><ns2:property name="AUTORE" type="string">GIOVANNELLA MARIA ELENA</ns2:property><ns2:property name="NUMERODOCUMENTO" type="string">33581101</ns2:property><ns2:property name="DATADEPOSITO" type="date">08/01/2026 18:55:28.000</ns2:property></ns2:row></return></ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    documenti = client._parse_documenti_qbuilder_xml(xml)

    assert len(documenti) == 1
    assert documenti[0].id_documento == "33581101"
    assert documenti[0].tipo == "SentenzaDefinitiva"
    assert documenti[0].nome == "Documento_33581101.pdf"


def test_polisweb_filtro_parti_qbuilder_per_cf():
    client = _client()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SICC-BE"><return available="1" time="2026-03-29 18:51:21" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType"><ns2:row class="InfoFascicoloExt"><ns2:property name="IDUFFICIO" type="string">0800570094</ns2:property><ns2:property name="ANNORUOLO" type="long">2024</ns2:property><ns2:property name="NUMERORUOLO" type="string">00001025</ns2:property><ns2:subRows class="InfoParte"><ns2:row><ns2:property name="COGNOME" type="string">STILLITANO</ns2:property><ns2:property name="NOME" type="string">FRANCESCO</ns2:property><ns2:property name="CODICEFISCALEPARTE" type="string">STLFNC45E26L063X</ns2:property></ns2:row></ns2:subRows></ns2:row></return></ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    fascicolo = client._parse_fascicoli_qbuilder_xml(xml)[0]

    assert _matches_parte_filters(fascicolo, None, "STLFNC45E26L063X")
    assert not _matches_parte_filters(fascicolo, None, "AAAAAA00A00A000A")
