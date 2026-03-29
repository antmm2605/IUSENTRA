from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli
from pct.polisWeb import (
    ClientPolisWeb,
    ClientPolisWebDemo,
    FascicoloPolisWeb,
    _matches_parte_filters,
    _pst_namespace_qbuilder,
)
from pct.soggetti import GestioneSoggetti


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


def test_importa_fascicolo_popola_cliente_parti_e_attivita(tmp_path):
    gestione_clienti = GestioneClienti(str(tmp_path / "clienti.json"))
    gestione_fascicoli = GestioneFascicoli(
        db_path=str(tmp_path / "fascicoli.json"),
        documents_dir=str(tmp_path / "documenti"),
        archive_dir=str(tmp_path / "archivio"),
    )
    gestione_soggetti = GestioneSoggetti(
        soggetti_path=str(tmp_path / "soggetti.json"),
        parti_path=str(tmp_path / "parti.json"),
    )

    fascicolo_pw = FascicoloPolisWeb(
        numero_rg="1025",
        anno_rg=2024,
        ruolo="CIVILE_COGNIZIONE",
        stato="PENDENTE",
        oggetto="Vendita di cose immobili",
        sezione="CIVILE",
        giudice="GIOVANNELLA MARIA ELENA",
        data_iscrizione="2026-03-29",
        data_udienza="2026-05-10",
        parti=["STILLITANO FRANCESCO", "BANCA ALFA S.P.A."],
        parti_dettaglio=[
            {
                "nome": "STILLITANO FRANCESCO",
                "tipo": "ATTORE",
                "codice_fiscale": "STLFNC45E26L063X",
                "avvocato": "",
                "cf_avvocato": "",
            },
            {
                "nome": "BANCA ALFA S.P.A.",
                "tipo": "CONVENUTO",
                "codice_fiscale": "12345678901",
                "avvocato": "",
                "cf_avvocato": "",
            },
        ],
        codice_ufficio="0800570094",
        nome_ufficio="Tribunale di Palmi",
    )

    client = ClientPolisWebDemo()
    risultato = client.importa_fascicolo(
        fascicolo_pw=fascicolo_pw,
        gestione_fascicoli=gestione_fascicoli,
        gestione_clienti=gestione_clienti,
        gestione_soggetti=gestione_soggetti,
        avvocato_referente="admin",
    )

    assert risultato.successo is True
    fascicolo = gestione_fascicoli.get(risultato.id_fascicolo_locale)
    assert fascicolo is not None
    assert fascicolo.id_cliente
    assert fascicolo.nome_cliente == "Stillitano Francesco"
    assert fascicolo.controparte == "BANCA ALFA S.P.A."
    assert fascicolo.cf_controparte == "12345678901"
    assert fascicolo.data_prima_udienza == "2026-05-10"
    assert fascicolo.data_prossima_udienza == "2026-05-10"
    assert len(fascicolo.attivita) >= 2

    cliente = gestione_clienti.get(fascicolo.id_cliente)
    assert cliente is not None
    assert cliente.codice_fiscale == "STLFNC45E26L063X"
    assert any(p.numero_rg == "1025" and p.anno == 2024 for p in cliente.procedimenti)

    parti = gestione_soggetti.parti_fascicolo(fascicolo.id)
    ruoli = {parte.ruolo.value for parte, _ in parti}
    nomi = {soggetto.nome_completo for _, soggetto in parti}

    assert "ASSISTITO" in ruoli
    assert "CONTROPARTE" in ruoli
    assert "Stillitano Francesco" in nomi
    assert "BANCA ALFA S.P.A." in nomi
