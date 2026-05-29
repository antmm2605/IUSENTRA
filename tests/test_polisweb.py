from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.clienti import GestioneClienti
from pct.fascicoli import (
    EsitoAttivita,
    GestioneFascicoli,
    StatoFascicolo,
    TipoAttivita,
    TipoDocumento,
    TipoFascicolo,
)
from pct.config_studio import ConfigPEC, GestioneConfigStudio
from pct.polisWeb import (
    ClientPolisWeb,
    ClientPolisWebDemo,
    FascicoloPolisWeb,
    _matches_parte_filters,
    _pst_namespace_qbuilder,
)
from pct.soggetti import GestioneSoggetti
from pct.telematico_workflow import TelematicoWorkflowRepository


def _client() -> ClientPolisWeb:
    return ClientPolisWeb(
        cert_pem_path="cert.pem",
        key_pem_path="key.pem",
        codice_fiscale_avvocato="MNTRRT64L01L063H",
    )


def _cfg_web(tmp_path: Path) -> dict:
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)
    return {
        "TESTING": True,
        "MULTI_TENANT": False,
        "STORAGE_MODE_DEFAULT": "json",
        "AUTH_DB": str(tmp_path / "utenti.json"),
        "AUDIT_DB": str(tmp_path / "audit.json"),
        "CLIENTI_DB": str(tmp_path / "clienti.json"),
        "CONDIVISIONI_DB": str(tmp_path / "condivisioni.json"),
        "FASCICOLI_DB": str(tmp_path / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "docs"),
        "FASCICOLI_ARCH": str(tmp_path / "arch"),
        "AGENDA_DB": str(tmp_path / "agenda.json"),
        "SCADENZIARIO_DB": str(tmp_path / "scadenze.json"),
        "MESSAGGI_DB": str(tmp_path / "messaggi.json"),
        "BACKUP_DIR": str(tmp_path / "backup"),
        "SEARCH_INDEX": str(tmp_path / "search.db"),
        "SOGGETTI_DB": str(tmp_path / "soggetti.json"),
        "SOGGETTI_PARTI_DB": str(tmp_path / "parti.json"),
        "PST_IMPORT_DIR": str(tmp_path / "pst_import"),
        "TELEMATICO_DB": str(tmp_path / "telematico" / "workflow.db"),
    }


def test_polisweb_qbuilder_namespace_sicid():
    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"
    assert _pst_namespace_qbuilder(base) == "urn:CONS-SICC-BE"


def test_polisweb_qbuilder_namespace_cassazione_alias_e_catalogo():
    assert _pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLCC/JPW_CASS") == "urn:CONS-CASSCI"
    assert _pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLCC/JPW_CASSCI") == "urn:CONS-CASSCI"
    assert _pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLCC/JPW_CASSPE") == "urn:CONS-CASSPE"


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
    assert '<value name="anno" type="string">2024</value>' in xml
    assert '<value name="numero" type="integer">1025</value>' in xml
    assert 'name="subProc"' not in xml
    assert 'name="annoRuolo"' not in xml
    assert 'name="numeroRuolo"' not in xml
    assert 'name="subpro"' not in xml


def test_polisweb_qbuilder_documenti_e_profilo_usano_parametri_pst_live():
    client = _client()
    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"
    fascicolo = FascicoloPolisWeb(
        numero_rg="1025",
        anno_rg=2024,
        ruolo="CIVILE_COGNIZIONE",
        stato="PENDENTE",
        oggetto="Vendita di cose immobili",
    )

    documenti_xml = client._soap_documenti_qbuilder(base, "0800570094", "1025", 2024)
    profilo_xml = client._soap_profilo_fascicolo_qbuilder(base, "0800570094", fascicolo)

    for xml in (documenti_xml, profilo_xml):
        assert '<value name="anno" type="string">2024</value>' in xml
        assert '<value name="numero" type="string">1025</value>' in xml
        assert 'name="subProc"' not in xml
        assert 'name="annoRuolo"' not in xml
        assert 'name="numeroRuolo"' not in xml
        assert 'name="subpro"' not in xml


def test_api_portale_acquisizione_analyze_usa_alias_fascicolo_locale_per_update(tmp_path: Path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    utenti = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    utenti.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )
    fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post("/login", data={"username": "avvocato", "password": "Avv12345!"})
        response = client.post(
            "/api/portali/pst/acquisizione/analyze",
            json={
                "fascicolo_locale_id": fascicolo.id,
                "selection": {
                    "numero": "1025",
                    "anno": 2024,
                    "ufficio_codice": "0800570094",
                    "ufficio_nome": "Tribunale di Palmi",
                    "parti": ["Montagnese"],
                    "payload": {
                        "numero_rg": "1025",
                        "anno_rg": 2024,
                        "codice_ufficio": "0800570094",
                        "nome_ufficio": "Tribunale di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "1025",
                        "anno": 2024,
                        "ufficio_nome": "Tribunale di Palmi",
                    },
                    "parti": ["Montagnese"],
                    "documenti": [],
                    "counts": {"parti": 1, "documenti": 0, "depositi": 0},
                },
                "options": {
                    "importa_parti": False,
                    "importa_documenti": False,
                    "importa_eventi": False,
                    "importa_udienze": False,
                    "importa_scadenze": False,
                },
                "mapping": {"mode": "create_new"},
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["analysis"]["resolved_mode"] == "update_existing"
    assert data["analysis"]["auto_target_fascicolo_id"] == fascicolo.id
    assert all(
        item.get("label") != "Pratica locale non selezionata"
        for item in data["analysis"]["blockers"]
    )


def test_api_portale_acquisizione_analyze_usa_documento_fonte_se_udienza_non_esposta(tmp_path: Path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    utenti = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    utenti.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    documento_fonte = {
        "id_documento": "32899061",
        "nome": "FissazioneTermineNoteSostituzioneUdienza_32899061.pdf",
        "tipo": "FissazioneTermineNoteSostituzioneUdienza",
        "tipo_atto": "FissazioneTermineNoteSostituzioneUdienza",
        "data_deposito": "2025-11-05",
        "disponibile": True,
    }

    app = create_app(cfg)
    with app.test_client() as client:
        client.post("/login", data={"username": "avvocato", "password": "Avv12345!"})
        response = client.post(
            "/api/portali/pst/acquisizione/analyze",
            json={
                "selection": {
                    "numero": "3441",
                    "anno": 2025,
                    "ufficio_codice": "0800570094",
                    "ufficio_nome": "Tribunale di Palmi",
                    "procedimento": "RITO LAVORO 1 GRADO",
                    "oggetto": "Retribuzione",
                    "parti": ["Montagnese"],
                    "payload": {
                        "numero_rg": "3441",
                        "anno_rg": 2025,
                        "codice_ufficio": "0800570094",
                        "nome_ufficio": "Tribunale di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "3441",
                        "anno": 2025,
                        "ufficio_nome": "Tribunale di Palmi",
                        "procedimento": "RITO LAVORO 1 GRADO",
                        "data_udienza": "",
                    },
                    "parti": ["Montagnese"],
                    "documenti": [documento_fonte],
                    "counts": {"parti": 1, "documenti": 1, "depositi": 1, "udienze": 0},
                },
                "options": {
                    "importa_parti": True,
                    "importa_documenti": True,
                    "importa_eventi": True,
                    "importa_udienze": True,
                    "importa_scadenze": True,
                },
                "mapping": {"mode": "create_new"},
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    warnings = data["analysis"]["warnings"]
    warning = next(item for item in warnings if item["label"] == "Scadenza da documento fonte")
    assert "FissazioneTermineNoteSostituzioneUdienza_32899061.pdf" in warning["detail"]
    assert warning["documenti"][0]["id_documento"] == "32899061"
    assert all(item.get("label") != "Nessuna udienza importabile" for item in warnings)


def test_api_portale_acquisizione_analyze_preferisce_udienza_strutturata_al_documento_fonte(tmp_path: Path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    utenti = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    utenti.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post("/login", data={"username": "avvocato", "password": "Avv12345!"})
        response = client.post(
            "/api/portali/pst/acquisizione/analyze",
            json={
                "selection": {
                    "numero": "3441",
                    "anno": 2025,
                    "ufficio_codice": "0800570094",
                    "ufficio_nome": "Tribunale di Palmi",
                    "parti": ["Montagnese"],
                    "payload": {"numero_rg": "3441", "anno_rg": 2025},
                },
                "preview": {
                    "identity": {
                        "numero": "3441",
                        "anno": 2025,
                        "ufficio_nome": "Tribunale di Palmi",
                        "data_udienza": "2026-06-20",
                    },
                    "parti": ["Montagnese"],
                    "documenti": [
                        {
                            "id_documento": "32899061",
                            "nome": "FissazioneTermineNoteSostituzioneUdienza_32899061.pdf",
                            "tipo_atto": "FissazioneTermineNoteSostituzioneUdienza",
                        }
                    ],
                    "counts": {"parti": 1, "documenti": 1, "depositi": 1, "udienze": 1},
                },
                "options": {
                    "importa_parti": True,
                    "importa_documenti": True,
                    "importa_eventi": True,
                    "importa_udienze": True,
                    "importa_scadenze": True,
                },
                "mapping": {"mode": "create_new"},
            },
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    warnings = data["analysis"]["warnings"]
    assert all(item.get("label") != "Scadenza da documento fonte" for item in warnings)
    assert all(item.get("label") != "Nessuna udienza importabile" for item in warnings)


def test_polisweb_qbuilder_sigp_usa_registro_gdp_senza_subpro_implicito():
    client = _client()
    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP"
    fascicolo = FascicoloPolisWeb(
        numero_rg="466",
        anno_rg=2023,
        ruolo="GDP",
        stato="DEFINITO",
        oggetto="Responsabilita extracontrattuale",
    )

    ricerca_xml = client._soap_ricerca_fascicoli_qbuilder(base, "0800570152", "466", 2023, None, None)
    documenti_xml = client._soap_documenti_qbuilder(base, "0800570152", "466", 2023)
    profilo_xml = client._soap_profilo_fascicolo_qbuilder(base, "0800570152", fascicolo)

    assert '<value name="tipo" type="string">GDP</value>' in ricerca_xml
    for xml in (ricerca_xml, documenti_xml, profilo_xml):
        assert 'name="subpro"' not in xml
        assert 'name="subProc"' not in xml


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


def test_polisweb_parse_qbuilder_fascicoli_normalizza_date_e_codiceufficio():
    client = _client()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SICC-BE"><return available="1" time="2026-03-29 18:51:21" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType"><ns2:row class="InfoFascicoloExt"><ns2:property name="IDFASCICOLO" type="string">172944</ns2:property><ns2:property name="CODICEUFFICIO" type="string">0800570094</ns2:property><ns2:property name="ANNORUOLO" type="long">2024</ns2:property><ns2:property name="NUMERORUOLO" type="string">00001025</ns2:property><ns2:property name="DATAISCRIZIONERUOLO" type="date">05/09/2024 00:00:00.000</ns2:property><ns2:property name="DATAPROSSIMAUDIENZA" type="date">12/12/2024 00:00:00.000</ns2:property><ns2:property name="DESCRIZIONESEZIONE" type="string">CIVILE</ns2:property></ns2:row></return></ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    fascicoli = client._parse_fascicoli_qbuilder_xml(xml)

    assert len(fascicoli) == 1
    assert fascicoli[0].codice_ufficio == "0800570094"
    assert fascicoli[0].nome_ufficio == "Tribunale di Palmi"
    assert fascicoli[0].data_iscrizione == "2024-09-05"
    assert fascicoli[0].data_udienza == "2024-12-12"
    assert fascicoli[0].sezione == "CIVILE"


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


def test_polisweb_parse_documenti_supporta_container_soap_annidato():
    client = _client()

    risposta = SimpleNamespace(
        return_value="ignored",
        return_=None,
        returnData=None,
        result=None,
        returnContainer=SimpleNamespace(
            documenti=SimpleNamespace(
                documento=[
                    SimpleNamespace(
                        idDocumento="DOC-001",
                        nomeFile="ricorso.pdf.p7m",
                        tipoDocumento="ATTO",
                        dataDeposito="2026-03-29",
                        mittente="avv.demo@pec.it",
                        dimensione="12000",
                        disponibile="true",
                        idDeposito="BUSTA-PST-001",
                        tipoAtto="Ricorso introduttivo",
                    ),
                    SimpleNamespace(
                        idDocumento="DOC-002",
                        nomeFile="procura.pdf.p7m",
                        tipoDocumento="ALLEGATO",
                        dataDeposito="2026-03-29",
                        mittente="avv.demo@pec.it",
                        dimensione="8000",
                        disponibile="true",
                        idDeposito="BUSTA-PST-001",
                        tipoAtto="Ricorso introduttivo",
                    ),
                ]
            )
        ),
    )
    setattr(risposta, "return", risposta.returnContainer)

    documenti = client._parse_documenti(risposta)

    assert len(documenti) == 2
    assert documenti[0].id_documento == "DOC-001"
    assert documenti[1].id_documento == "DOC-002"
    assert {doc.id_deposito for doc in documenti} == {"BUSTA-PST-001"}
    assert {doc.tipo_atto for doc in documenti} == {"Ricorso introduttivo"}


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
    assert fascicolo.stato == StatoFascicolo.IN_CORSO
    assert fascicolo.data_prima_udienza == "2026-05-10"
    assert fascicolo.data_prossima_udienza == "2026-05-10"
    assert len(fascicolo.attivita) >= 2
    assert risultato.depositi_importati >= 1
    assert risultato.documenti_importati >= 1
    assert len(fascicolo.depositi_pct) >= 1
    assert fascicolo.depositi_pct[0].stato == "IMPORTATO_DA_PST"
    assert fascicolo.depositi_pct[0].documenti_portale

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


def test_importa_fascicolo_esistente_sincronizza_cliente_parti_e_attivita(tmp_path):
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

    fascicolo_locale = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024 —",
        tipo=TipoFascicolo.CIVILE,
        numero_rg="1025",
        anno_rg=2024,
        data_apertura="2026-03-29",
        note="Importato da PolisWeb il 2026-03-29",
    )

    fascicolo_pw = FascicoloPolisWeb(
        numero_rg="1025",
        anno_rg=2024,
        ruolo="CIVILE_COGNIZIONE",
        stato="PENDENTE",
        oggetto="Vendita di cose immobili",
        sezione="CIVILE",
        giudice="GIOVANNELLA MARIA ELENA",
        data_iscrizione="05/09/2024 00:00:00.000",
        data_udienza="12/12/2024 00:00:00.000",
        parti=["STILLITANO FRANCESCO", "BANCA ALFA S.P.A."],
        parti_dettaglio=[
            {
                "nome": "STILLITANO FRANCESCO",
                "tipo": "ATTORE",
                "codice_fiscale": "STLFNC45E26L063X",
            },
            {
                "nome": "BANCA ALFA S.P.A.",
                "tipo": "CONVENUTO",
                "codice_fiscale": "12345678901",
            },
        ],
        codice_ufficio="0800570094",
        nome_ufficio="Tribunale di Palmi",
    )

    client = ClientPolisWebDemo()
    risultato = client.sincronizza_fascicolo_esistente(
        fascicolo_pw=fascicolo_pw,
        fascicolo_locale=fascicolo_locale,
        gestione_fascicoli=gestione_fascicoli,
        gestione_clienti=gestione_clienti,
        gestione_soggetti=gestione_soggetti,
        avvocato_referente="admin",
    )

    assert risultato.successo is True
    fascicolo = gestione_fascicoli.get(fascicolo_locale.id)
    assert fascicolo is not None
    assert fascicolo.id_cliente
    assert fascicolo.nome_cliente == "Stillitano Francesco"
    assert fascicolo.tribunale == "Tribunale di Palmi"
    assert fascicolo.data_apertura == "2024-09-05"
    assert fascicolo.data_prima_udienza == "2024-12-12"
    assert fascicolo.data_prossima_udienza == ""
    assert fascicolo.oggetto == "Vendita di cose immobili"
    assert fascicolo.controparte == "BANCA ALFA S.P.A."
    assert len(fascicolo.attivita) >= 2
    assert risultato.depositi_importati >= 1
    assert risultato.documenti_importati >= 1
    assert len(fascicolo.depositi_pct) >= 1
    assert fascicolo.depositi_pct[0].stato == "IMPORTATO_DA_PST"
    assert fascicolo.depositi_pct[0].documenti_portale

    soggetti = gestione_soggetti.tutti()
    assert {s.nome_completo for s in soggetti} >= {"Stillitano Francesco", "BANCA ALFA S.P.A."}


def test_importa_fascicolo_esistente_crea_parti_da_cliente_locale_se_pst_non_espone_parti(tmp_path):
    from pct.clienti import TipoCliente

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

    cliente = gestione_clienti.nuovo(
        tipo=TipoCliente.PERSONA_FISICA,
        cognome="Loprete",
        nome="Domenico",
    )
    fascicolo_locale = gestione_fascicoli.nuovo(
        titolo="RG 274/2026 - Usucapione",
        tipo=TipoFascicolo.CIVILE,
        id_cliente=cliente.id,
        nome_cliente=cliente.nome_completo,
        controparte="Princi Concetta",
        cf_controparte="PRNCTT45C44L063Q",
        numero_rg="274",
        anno_rg=2026,
        tribunale="Tribunale di Palmi",
    )

    fascicolo_pw = FascicoloPolisWeb(
        numero_rg="274",
        anno_rg=2026,
        ruolo="CIVILE_COGNIZIONE",
        stato="PENDENTE",
        oggetto="Usucapione",
        data_iscrizione="2026-03-06",
        parti=[],
        parti_dettaglio=[],
        codice_ufficio="0910011",
        nome_ufficio="Tribunale di Palmi",
    )

    risultato = ClientPolisWebDemo().sincronizza_fascicolo_esistente(
        fascicolo_pw=fascicolo_pw,
        fascicolo_locale=fascicolo_locale,
        gestione_fascicoli=gestione_fascicoli,
        gestione_clienti=gestione_clienti,
        gestione_soggetti=gestione_soggetti,
        avvocato_referente="admin",
        documenti_pw=[],
    )

    assert risultato.successo is True
    parti = gestione_soggetti.parti_fascicolo(fascicolo_locale.id)
    by_name = {soggetto.nome_completo: parte.ruolo.value for parte, soggetto in parti}
    assert by_name["Loprete Domenico"] == "ASSISTITO"
    assert by_name["Princi Concetta"] == "CONTROPARTE"


def test_importa_fascicolo_portale_definito_mantiene_stato_definito(tmp_path):
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
        stato="PROCEDIMENTO DEFINITO",
        oggetto="Vendita di cose immobili",
        sezione="CIVILE",
        giudice="GIOVANNELLA MARIA ELENA",
        data_iscrizione="2024-09-05",
        data_udienza="2024-12-12",
        parti=["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
        parti_dettaglio=[
            {"nome": "MONTAGNESE ELISABETTA", "tipo": "ATTORE", "codice_fiscale": "MNTLBT80A41G273K"},
            {"nome": "STILLITANO FRANCESCO", "tipo": "CONVENUTO", "codice_fiscale": "STLFNC45E26L063X"},
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
    assert fascicolo.stato == StatoFascicolo.DEFINITO


def test_importa_fascicolo_esistente_promuove_rg_ufficiale_su_fascicolo_locale(tmp_path):
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

    fascicolo_locale = gestione_fascicoli.nuovo(
        titolo="Pratica interna da completare",
        tipo=TipoFascicolo.CIVILE,
    )
    numero_interno = fascicolo_locale.numero

    fascicolo_pw = FascicoloPolisWeb(
        numero_rg="2048",
        anno_rg=2026,
        ruolo="CIVILE_COGNIZIONE",
        stato="PENDENTE",
        oggetto="Opposizione a decreto ingiuntivo",
        sezione="CIVILE",
        giudice="GIUDICE DEMO",
        data_iscrizione="2026-03-15",
        parti=["ROSSI MARIO", "BETA S.R.L."],
        parti_dettaglio=[
            {
                "nome": "ROSSI MARIO",
                "tipo": "ATTORE",
                "codice_fiscale": "RSSMRA80A01H501U",
            },
            {
                "nome": "BETA S.R.L.",
                "tipo": "CONVENUTO",
                "codice_fiscale": "12345678901",
            },
        ],
        codice_ufficio="0800570094",
        nome_ufficio="Tribunale di Palmi",
    )

    client = ClientPolisWebDemo()
    risultato = client.sincronizza_fascicolo_esistente(
        fascicolo_pw=fascicolo_pw,
        fascicolo_locale=fascicolo_locale,
        gestione_fascicoli=gestione_fascicoli,
        gestione_clienti=gestione_clienti,
        gestione_soggetti=gestione_soggetti,
        avvocato_referente="admin",
        documenti_pw=[],
    )

    assert risultato.successo is True
    fascicolo = gestione_fascicoli.get(fascicolo_locale.id)
    assert fascicolo is not None
    assert fascicolo.numero == numero_interno
    assert fascicolo.numero_rg == "2048"
    assert fascicolo.anno_rg == 2026
    assert fascicolo.rg_completo == "RG 2048/2026"
    assert fascicolo.id_cliente
    assert fascicolo.nome_cliente == "Rossi Mario"


def test_create_app_default_soggetti_paths_follow_clienti_root(tmp_path):
    from web.app import create_app

    cfg = {
        "CLIENTI_DB": str(tmp_path / "data" / "clienti" / "anagrafica.json"),
        "FASCICOLI_DB": str(tmp_path / "data" / "fascicoli" / "fascicoli.json"),
        "FASCICOLI_DOCS": str(tmp_path / "data" / "fascicoli" / "documenti"),
        "FASCICOLI_ARCH": str(tmp_path / "data" / "fascicoli" / "archivio"),
    }
    app = create_app(cfg)

    assert app.config["SOGGETTI_DB"] == str(tmp_path / "data" / "soggetti" / "anagrafica.json")
    assert app.config["SOGGETTI_PARTI_DB"] == str(tmp_path / "data" / "soggetti" / "parti.json")


def test_route_importa_documenti_portale_salva_documenti_e_deposito(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/importa-portale",
            data={
                "note_importazione": "fascicolo completo scaricato dal portale",
                "files": [
                    (io.BytesIO(b"sentenza definitiva"), "Sentenza definitiva.txt"),
                    (io.BytesIO(b"verbale udienza"), "Verbale udienza.txt"),
                ],
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert response.status_code == 200

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)

    assert fascicolo_reload is not None
    assert len(fascicolo_reload.documenti) == 2
    assert len(fascicolo_reload.depositi_pct) == 1
    assert fascicolo_reload.depositi_pct[0].stato == "IMPORTATO_DA_PORTALE"
    assert fascicolo_reload.depositi_pct[0].tipo_atto == "Acquisizione documenti PolisWeb"
    assert len(fascicolo_reload.depositi_pct[0].documenti_ids) == 2
    assert not any(att.tipo.value == "CONSULTAZIONE" for att in fascicolo_reload.attivita)


def test_route_importa_documenti_portale_usa_inbox_temporanea(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 204/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="204",
        anno_rg=2025,
    )

    staging_dir = Path(cfg["PST_IMPORT_DIR"]) / fascicolo.id
    staging_dir.mkdir(parents=True, exist_ok=True)
    (staging_dir / "Memoria 183.txt").write_bytes(b"memoria 183")

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/importa-portale",
            data={"note_importazione": "import da inbox"},
            follow_redirects=True,
        )

    assert response.status_code == 200

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    archivio_inbox = Path(cfg["PST_IMPORT_DIR"]) / "_importati"

    assert fascicolo_reload is not None
    assert len(fascicolo_reload.documenti) == 1
    assert fascicolo_reload.depositi_pct[0].stato == "IMPORTATO_DA_PORTALE"
    assert archivio_inbox.exists()
    assert any(path.name.startswith(fascicolo.id + "_") for path in archivio_inbox.iterdir())


def test_api_importa_documenti_portale_aggancia_file_al_deposito_ufficiale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 303/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="303",
        anno_rg=2025,
    )
    deposito = gestione_fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-002",
        tipo_atto="Sentenza",
        data_deposito="2026-03-29",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-900",
                "nome": "Sentenza definitiva.pdf.p7m",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-29",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-002",
                "tipo_atto": "Sentenza",
                "id_repeatto": "ATTO-SIGP-900",
                "msg_id": "PEC-MSG-900",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/api/fascicoli/{fascicolo.id}/documenti/importa-portale",
            json={
                "note_importazione": "raccolta assistita",
                "files": [
                    {
                        "nome": "Sentenza definitiva.pdf",
                        "contenuto_b64": base64.b64encode(b"sentenza definitiva").decode("ascii"),
                        "origine": "C:/Users/test/Downloads/Sentenza definitiva.pdf",
                        "data_documento": "2026-03-29",
                        "id_deposito_esterno": "BUSTA-PST-002",
                        "id_deposito_pct": deposito.id,
                        "id_documento_portale": "DOC-900",
                        "id_repeatto": "ATTO-SIGP-900",
                        "msg_id": "PEC-MSG-900",
                        "tipo_atto": "Sentenza",
                    }
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["documenti_importati"] == 1
    assert data["depositi_agganciati"] == 1
    assert not data["lotto_generico"]

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert len(fascicolo_reload.documenti) == 1
    assert len(fascicolo_reload.depositi_pct) == 1
    assert fascicolo_reload.depositi_pct[0].documenti_ids == [fascicolo_reload.documenti[0].id]
    assert fascicolo_reload.documenti[0].id_deposito_pct == deposito.id
    assert fascicolo_reload.depositi_pct[0].servizio_portale == "DocumentiFascicolo"
    assert len(fascicolo_reload.attivita) == 0
    assert fascicolo_reload.depositi_pct[0].documenti_portale[0]["id_repeatto"] == "ATTO-SIGP-900"
    assert fascicolo_reload.depositi_pct[0].documenti_portale[0]["msg_id"] == "PEC-MSG-900"


def test_api_importa_documenti_portale_puo_archiviare_albero_tecnico_originale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 404/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="404",
        anno_rg=2025,
    )
    deposito = gestione_fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-404",
        tipo_atto="VerbaleUdienza",
        data_deposito="2026-03-29",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-404",
                "nome": "VerbaleUdienza_404.pdf",
                "tipo": "VERBALE",
                "data_deposito": "2026-03-29",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-404",
                "tipo_atto": "VerbaleUdienza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/api/fascicoli/{fascicolo.id}/documenti/importa-portale",
            json={
                "note_importazione": "acquisizione completa",
                "mantieni_albero_originale": True,
                "files": [
                    {
                        "nome": "VerbaleUdienza_404.pdf",
                        "contenuto_b64": base64.b64encode(b"verbale udienza").decode("ascii"),
                        "origine": "pst:JPW_SICID:DOC-404",
                        "data_documento": "2026-03-29",
                        "id_deposito_esterno": "BUSTA-PST-404",
                        "id_deposito_pct": deposito.id,
                        "id_documento_portale": "DOC-404",
                        "tipo_atto": "VerbaleUdienza",
                    }
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["albero_originale_salvato"] is True

    archivio = Path(cfg["PST_IMPORT_DIR"]) / "_alberi_originali" / fascicolo.id
    assert archivio.exists()
    assert any(path.is_file() and path.name == "VerbaleUdienza_404.pdf" for path in archivio.rglob("*"))


def test_route_importa_documenti_portale_aggancia_upload_al_deposito_ufficiale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 404/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="404",
        anno_rg=2025,
    )
    deposito = gestione_fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-404",
        tipo_atto="Sentenza",
        data_deposito="2026-03-30",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-404",
                "nome": "Sentenza definitiva.pdf.p7m",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-30",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 16000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-404",
                "tipo_atto": "Sentenza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            f"/fascicoli/{fascicolo.id}/documenti/importa-portale",
            data={
                "note_importazione": "upload manuale dal browser ufficiale",
                "files": (io.BytesIO(b"sentenza definitiva"), "Sentenza definitiva.pdf"),
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )

    assert response.status_code == 200

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)

    assert fascicolo_reload is not None
    assert len(fascicolo_reload.documenti) == 1
    assert len(fascicolo_reload.depositi_pct) == 1
    assert fascicolo_reload.depositi_pct[0].id == deposito.id
    assert fascicolo_reload.depositi_pct[0].documenti_ids == [fascicolo_reload.documenti[0].id]
    assert fascicolo_reload.documenti[0].id_deposito_pct == deposito.id
    assert fascicolo_reload.depositi_pct[0].servizio_portale == "DocumentiFascicolo"
    assert len(fascicolo_reload.attivita) == 0


def test_route_documenti_polisweb_consente_vista_completa_delle_buste(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(
            "/polisWeb/documenti?codice_ufficio=0580010&numero_rg=1025&anno_rg=2026",
            follow_redirects=True,
        )

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Espandi tutto" in body
    assert "Riduci" in body
    assert 'data-bs-parent="#accordionDepositi"' not in body
    assert "BUSTA-DI-001" in body
    assert "BUSTA-MEM-004" in body


def test_route_documenti_pdp_raggruppa_buste_e_fallback_senza_id(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    from pct.pdp import DocumentoPDP
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    class _FakePDPClient:
        def consulta_documenti(self, codice_ufficio, numero_rg, anno_rg):
            return [
                DocumentoPDP(
                    "PDP-001",
                    "richiesta_rinvio_giudizio.pdf.p7m",
                    "RICHIESTA",
                    "2026-03-10",
                    "pm.demo@pec.it",
                    189440,
                    True,
                    "",
                    "Richiesta di rinvio a giudizio",
                ),
                DocumentoPDP(
                    "PDP-002",
                    "allegato_richiesta.pdf.p7m",
                    "ALLEGATO",
                    "2026-03-10",
                    "pm.demo@pec.it",
                    65432,
                    True,
                    "",
                    "Richiesta di rinvio a giudizio",
                ),
                DocumentoPDP(
                    "PDP-003",
                    "decreto_che_dispone_giudizio.pdf.p7m",
                    "DECRETO",
                    "2026-04-22",
                    "cancelleria.penale@pec.it",
                    95000,
                    True,
                    "BUSTA-PDP-002",
                    "Decreto che dispone il giudizio",
                ),
            ]

    monkeypatch.setattr("pct.pdp.crea_client_pdp", lambda demo=False: _FakePDPClient())

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(
            "/pdp/documenti?codice_ufficio=0580010&numero_rg=4521&anno_rg=2026&demo_mode=1",
            follow_redirects=True,
        )

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Espandi tutto" in body
    assert "Riduci" in body
    assert 'data-bs-parent="#accordionDepositi"' not in body
    assert "2 atti" in body
    assert "3 file totali" in body
    assert "richiesta_rinvio_giudizio.pdf.p7m" in body
    assert "allegato_richiesta.pdf.p7m" in body
    assert "decreto_che_dispone_giudizio.pdf.p7m" in body
    assert "BUSTA-PDP-002" in body


def test_route_documenti_pat_reindirizza_a_home_con_portale_ufficiale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(
            "/pat/documenti?codice_ufficio=T0001&numero_ricorso=1876&anno=2026&demo_mode=1",
            follow_redirects=True,
        )

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Portale dell'Avvocato ufficiale" in body
    assert "Fascicolo PAT interno" in body
    assert "Acquisizione guidata" in body


def test_dettaglio_fascicolo_mostra_cartella_import_portale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1")

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Cartella tecnica locale del fascicolo" in body
    assert "pst_import" in body
    assert fascicolo.id in body


def test_dettaglio_fascicolo_mostra_download_ufficiale_portale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
    )
    gestione_fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-1025",
        tipo_atto="Sentenza",
        data_deposito="2026-03-29",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-1025",
                "nome": "SentenzaDefinitiva_33581101.pdf",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-29",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-1025",
                "tipo_atto": "Sentenza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)
        react_response = client.get(f"/api/v1/ui/fascicoli/{fascicolo.id}")

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert react_response.status_code == 200
    react_payload = react_response.get_json()
    assert react_payload["deposits"][0]["externalId"] == "BUSTA-PST-1025"
    assert react_payload["deposits"][0]["portalDocuments"][0]["name"] == "SentenzaDefinitiva_33581101.pdf"
    assert react_payload["deposits"][0]["portalDocuments"][0]["imported"] is False
    assert "Naviga fascicolo PST" in body
    assert "Scarica + importa selezionati" in body
    assert "Acquisisci intero fascicolo" in body
    assert "Conserva anche l'albero tecnico originale del portale" in body
    assert "Scarica duplicato/originale senza coccarda ministeriale" in body
    assert "Acquisisci fascicolo" not in body
    assert "_PST_NAV_ITEMS" in body
    assert "/pst/download-documenti-batch" in body
    assert "copia di consultazione del portale con annotazioni ministeriali visibili" in body
    assert "original: scaricaDuplicatoOriginale()" in body
    assert "scarica_originale_portale: scaricaDuplicatoOriginale()" in body


def test_dettaglio_fascicolo_segna_documento_portale_gia_importato(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 606/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="606",
        anno_rg=2025,
    )
    deposito = gestione_fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-606",
        tipo_atto="Sentenza",
        data_deposito="2026-03-30",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-606",
                "nome": "Sentenza definitiva.pdf",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-30",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 16000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-606",
                "tipo_atto": "Sentenza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )
    doc = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "Sentenza definitiva.pdf",
        TipoDocumento.SENTENZA,
        b"sentenza definitiva",
        id_deposito_pct=deposito.id,
        caricato_da="avvocato",
    )
    assert doc.id_deposito_pct == deposito.id

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert '"gia_importato": true' in body
    assert "RG 606/2025" in body
    assert f"Rif. interno {fascicolo.numero}" in body


def test_lista_fascicoli_mostra_rg_come_riferimento_principale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 909/2026",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="909",
        anno_rg=2026,
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get("/fascicoli?_legacy=1", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "RG 909/2026" in body
    assert f"Interno {fascicolo.numero}" in body


def test_dettaglio_fascicolo_non_mescola_documenti_portale_con_comunicazioni(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 505/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="505",
        anno_rg=2025,
    )
    gestione_fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-505",
        tipo_atto="Memoria conclusionale",
        data_deposito="2026-03-30",
        mittente="avv.rossi@pec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-505",
                "nome": "memoria conclusionale.pdf.p7m",
                "tipo": "ATTO",
                "data_deposito": "2026-03-30",
                "mittente": "avv.rossi@pec.it",
                "dimensione_bytes": 18000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-505",
                "tipo_atto": "Memoria conclusionale",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "documenti ufficiali" in body
    assert "Documenti fascicolo" in body
    assert re.search(r"Documenti fascicolo\s*<span[^>]*>\s*0\s*</span>", body)
    assert "Catalogo portale 1" in body
    assert "memoria conclusionale.pdf.p7m" in body
    assert re.search(r"Attivit.{1,8}processuali\s*<span[^>]*>\s*0\s*</span>", body)
    assert "nella sezione <strong>Comunicazioni di cancelleria</strong>" not in body
    assert "Nessuna comunicazione di cancelleria" in body


def test_dettaglio_fascicolo_sezioni_collassabili(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 606/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="606",
        anno_rg=2025,
    )
    gestione_fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-606",
        tipo_atto="Comparsa conclusionale",
        data_deposito="2026-03-30",
        mittente="avv.rossi@pec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-606",
                "nome": "comparsa conclusionale.pdf.p7m",
                "tipo": "ATTO",
                "data_deposito": "2026-03-30",
                "mittente": "avv.rossi@pec.it",
                "dimensione_bytes": 18000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-606",
                "tipo_atto": "Comparsa conclusionale",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert 'data-bs-target="#collapse-sezione-profilo"' in body
    assert 'data-bs-target="#collapse-documenti-portale-telematico"' in body
    assert 'data-bs-target="#collapse-sezione-documenti-fascicolo"' in body
    assert 'data-bs-target="#collapse-sezione-attivita-processuali"' in body
    assert 'data-bs-target="#collapse-sezione-udienze-scadenze"' in body
    assert 'data-bs-target="#collapse-sezione-comunicazioni-cancelleria"' in body
    assert 'data-bs-target="#collapse-sezione-istanze"' in body
    assert 'class="collapse" id="collapse-sezione-profilo"' in body
    assert 'class="collapse" id="collapse-documenti-portale-telematico"' in body
    assert 'class="collapse" id="collapse-sezione-documenti-fascicolo"' in body
    assert 'class="collapse" id="collapse-sezione-attivita-processuali"' in body
    assert 'class="collapse" id="collapse-sezione-udienze-scadenze"' in body
    assert 'class="collapse" id="collapse-sezione-comunicazioni-cancelleria"' in body
    assert 'class="collapse" id="collapse-sezione-istanze"' in body


def test_dettaglio_fascicolo_mostra_ricevute_pec_in_cancelleria(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 707/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="707",
        anno_rg=2025,
    )
    gestione_fascicoli.aggiungi_esito_deposito(
        fascicolo.id,
        tipo_atto="Comparsa conclusionale",
        pec_destinatario="tribunale.palmi@giustiziapec.it",
        stato="ACCETTATO_CANCELLERIA",
        ricevuta_accettazione="ACC MSG 001",
        ricevuta_consegna="CONS MSG 002",
        ricevuta_controlli_automatici="CTRL OK 003",
        esito_controlli="OK",
        ricevuta_cancelleria="CANC OK 004",
        registrato_da="admin",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Visualizza ricevute e comunicazioni PEC" in body
    assert "Ricevuta di accettazione PEC" in body
    assert "Ricevuta di avvenuta consegna" in body
    assert "Esito controlli automatici" in body
    assert "Esito cancelleria" in body
    assert "ACC MSG 001" in body
    assert "CONS MSG 002" in body
    assert "CTRL OK 003" in body
    assert "CANC OK 004" in body
    sezione_cancelleria = body.split('id="sezione-comunicazioni-cancelleria"', 1)[1][:2500]
    assert "Prepara atto" not in sezione_cancelleria


def test_dettaglio_fascicolo_mostra_email_comunicazione_cancelleria(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 808/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="808",
        anno_rg=2025,
    )
    gestione_fascicoli.aggiungi_attivita(
        fascicolo.id,
        tipo=TipoAttivita.COMUNICAZIONE_CANCELLERIA,
        data="2026-04-09",
        titolo="PEC: ACCETTAZIONE DEPOSITO RG 808/2025",
        descrizione="Da: posta-certificata@legalmail.it",
        esito=EsitoAttivita.NON_APPLICABILE,
        email_mittente="posta-certificata@legalmail.it",
        email_oggetto="ACCETTAZIONE DEPOSITO RG 808/2025",
        email_uid_imap="IMAP-808",
        email_testo="Questo è il corpo completo della PEC di ricevuta.",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Apri email ricevuta" in body
    assert "ACCETTAZIONE DEPOSITO RG 808/2025" in body
    assert "posta-certificata@legalmail.it" in body
    assert "IMAP-808" in body
    assert "Questo è il corpo completo della PEC di ricevuta." in body


def test_dettaglio_fascicolo_firma_usa_conversione_base64_sicura(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 909/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="909",
        anno_rg=2025,
    )
    gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "comparsa.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-1.4\n%%EOF",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)

    body = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "_detFArrayBufferToBase64Safe" in body
    assert "_detFBase64ToUint8ArraySafe" in body
    assert "String.fromCharCode(...new Uint8Array(buf))" not in body


def test_route_importa_polisweb_sincronizza_fascicolo_esistente(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024 —",
        tipo=TipoFascicolo.CIVILE,
        numero_rg="1025",
        anno_rg=2024,
        data_apertura="2026-03-29",
        note="Importato da PolisWeb il 2026-03-29",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/polisWeb/importa",
            data={
                "id_fasc": fascicolo.id,
                "demo_mode": "1",
                "numero_rg": "1025",
                "anno_rg": "2024",
                "ruolo": "CIVILE_COGNIZIONE",
                "stato": "PENDENTE",
                "oggetto": "Vendita di cose immobili",
                "sezione": "CIVILE",
                "giudice": "GIOVANNELLA MARIA ELENA",
                "data_iscrizione": "05/09/2024 00:00:00.000",
                "data_udienza": "12/12/2024 00:00:00.000",
                "parti_json": json.dumps(["STILLITANO FRANCESCO", "BANCA ALFA S.P.A."]),
                "parti_dettaglio_json": json.dumps(
                    [
                        {"nome": "STILLITANO FRANCESCO", "tipo": "ATTORE", "codice_fiscale": "STLFNC45E26L063X"},
                        {"nome": "BANCA ALFA S.P.A.", "tipo": "CONVENUTO", "codice_fiscale": "12345678901"},
                    ]
                ),
                "codice_ufficio": "0800570094",
                "nome_ufficio": "",
            },
            follow_redirects=True,
        )

    assert response.status_code == 200

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    gestione_clienti_reload = GestioneClienti(cfg["CLIENTI_DB"])
    gestione_soggetti_reload = GestioneSoggetti(
        soggetti_path=cfg["SOGGETTI_DB"],
        parti_path=cfg["SOGGETTI_PARTI_DB"],
    )

    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.id_cliente
    assert fascicolo_reload.nome_cliente == "Stillitano Francesco"
    assert fascicolo_reload.tribunale == "Tribunale di Palmi"
    assert fascicolo_reload.data_apertura == "2024-09-05"
    assert fascicolo_reload.data_prima_udienza == "2024-12-12"
    assert fascicolo_reload.controparte == "BANCA ALFA S.P.A."
    assert len(fascicolo_reload.attivita) >= 2
    assert len(fascicolo_reload.depositi_pct) >= 1
    assert fascicolo_reload.depositi_pct[0].stato == "IMPORTATO_DA_PST"
    assert fascicolo_reload.depositi_pct[0].documenti_portale
    assert gestione_clienti_reload.get(fascicolo_reload.id_cliente) is not None
    assert {s.nome_completo for s in gestione_soggetti_reload.tutti()} >= {"Stillitano Francesco", "BANCA ALFA S.P.A."}


def test_route_importa_polisweb_via_local_signer_non_richiede_certificato_server(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    import pct.polisWeb as polisweb_module
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    def _crea_client_non_atteso(*args, **kwargs):
        raise AssertionError("crea_client non deve essere usato quando l'import arriva dal Local Signer.")

    monkeypatch.setattr(polisweb_module, "crea_client", _crea_client_non_atteso)

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/polisWeb/importa",
            data={
                "demo_mode": "0",
                "canale_accesso_pst": "local_signer",
                "numero_rg": "1025",
                "anno_rg": "2024",
                "ruolo": "CIVILE_COGNIZIONE",
                "stato": "PENDENTE",
                "oggetto": "Vendita di cose immobili",
                "sezione": "CIVILE",
                "giudice": "GIOVANNELLA MARIA ELENA",
                "data_iscrizione": "05/09/2024 00:00:00.000",
                "data_udienza": "12/12/2024 00:00:00.000",
                "parti_json": json.dumps(["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"]),
                "parti_dettaglio_json": json.dumps(
                    [
                        {"nome": "MONTAGNESE ELISABETTA", "tipo": "AP", "codice_fiscale": "MNTLBT49E47H558L"},
                        {"nome": "STILLITANO FRANCESCO", "tipo": "AS", "codice_fiscale": "STLFNC45E26L063X"},
                    ]
                ),
                "codice_ufficio": "0800570094",
                "nome_ufficio": "",
                "documenti_json": json.dumps(
                    [
                        {
                            "id_documento": "DOC-1",
                            "nome": "SentenzaDefinitiva_33581101.pdf",
                            "tipo": "SentenzaDefinitiva",
                            "data_deposito": "2026-01-08",
                            "mittente": "GIOVANNELLA MARIA ELENA",
                            "dimensione_bytes": 12345,
                            "disponibile": True,
                            "id_deposito": "DEP-1",
                            "tipo_atto": "SentenzaDefinitiva",
                        }
                    ]
                ),
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "/fascicoli/" in response.headers["Location"]
    assert "preserve_pst_tree=1" not in response.headers["Location"]
    assert "auto_pst_acquire=1" not in response.headers["Location"]

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicoli = gestione_fascicoli.tutti()
    assert len(fascicoli) == 1

    fascicolo = fascicoli[0]
    assert fascicolo.numero_rg == "1025"
    assert fascicolo.anno_rg == 2024
    assert fascicolo.tribunale == "Tribunale di Palmi"
    assert fascicolo.nome_cliente == "Montagnese Elisabetta"
    assert len(fascicolo.depositi_pct) == 1
    assert fascicolo.depositi_pct[0].documenti_portale


def test_route_importa_polisweb_puo_aprire_subito_naviga_pst(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/polisWeb/importa",
            data={
                "demo_mode": "1",
                "apri_portale": "1",
                "numero_rg": "1025",
                "anno_rg": "2024",
                "ruolo": "CIVILE_COGNIZIONE",
                "stato": "PENDENTE",
                "oggetto": "Vendita di cose immobili",
                "sezione": "CIVILE",
                "giudice": "GIOVANNELLA MARIA ELENA",
                "data_iscrizione": "05/09/2024 00:00:00.000",
                "data_udienza": "12/12/2024 00:00:00.000",
                "parti_json": json.dumps(["STILLITANO FRANCESCO", "BANCA ALFA S.P.A."]),
                "parti_dettaglio_json": json.dumps(
                    [
                        {"nome": "STILLITANO FRANCESCO", "tipo": "ATTORE", "codice_fiscale": "STLFNC45E26L063X"},
                        {"nome": "BANCA ALFA S.P.A.", "tipo": "CONVENUTO", "codice_fiscale": "12345678901"},
                    ]
                ),
                "codice_ufficio": "0800570094",
                "nome_ufficio": "",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "open_pst_nav=1" in response.headers["Location"]


def test_route_importa_polisweb_puo_avviare_subito_acquisizione_completa(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/polisWeb/importa",
            data={
                "demo_mode": "1",
                "apri_portale": "1",
                "acquisisci_portale": "1",
                "mantieni_albero_originale": "1",
                "numero_rg": "2048",
                "anno_rg": "2025",
                "ruolo": "CIVILE_COGNIZIONE",
                "stato": "PENDENTE",
                "oggetto": "Opposizione a decreto",
                "sezione": "CIVILE",
                "giudice": "GIUDICE TEST",
                "data_iscrizione": "04/03/2025 00:00:00.000",
                "data_udienza": "17/09/2025 00:00:00.000",
                "parti_json": json.dumps(["ROSSI MARIO", "BANCA BETA S.P.A."]),
                "parti_dettaglio_json": json.dumps(
                    [
                        {"nome": "ROSSI MARIO", "tipo": "ATTORE", "codice_fiscale": "RSSMRA80A01H501U"},
                        {"nome": "BANCA BETA S.P.A.", "tipo": "CONVENUTO", "codice_fiscale": "12345678901"},
                    ]
                ),
                "codice_ufficio": "0580910094",
                "nome_ufficio": "",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "open_pst_nav=1" in response.headers["Location"]
    assert "auto_pst_acquire=1" in response.headers["Location"]
    assert "preserve_pst_tree=1" in response.headers["Location"]


def test_route_importa_polisweb_riaggancia_fascicolo_target_ripulito(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="Fascicolo da sincronizzare (prova PST)",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/polisWeb/importa",
            data={
                "id_fasc": fascicolo.id,
                "demo_mode": "1",
                "numero_rg": "1025",
                "anno_rg": "2024",
                "ruolo": "CIVILE_COGNIZIONE",
                "stato": "PENDENTE",
                "oggetto": "Vendita di cose immobili",
                "sezione": "CIVILE",
                "giudice": "GIOVANNELLA MARIA ELENA",
                "data_iscrizione": "05/09/2024 00:00:00.000",
                "data_udienza": "12/12/2024 00:00:00.000",
                "parti_json": json.dumps(["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"]),
                "parti_dettaglio_json": json.dumps(
                    [
                        {"nome": "MONTAGNESE ELISABETTA", "tipo": "AP", "codice_fiscale": "MNTLBT49E47H558L"},
                        {"nome": "STILLITANO FRANCESCO", "tipo": "AS", "codice_fiscale": "STLFNC45E26L063X"},
                    ]
                ),
                "codice_ufficio": "0800570094",
                "nome_ufficio": "",
                "documenti_json": json.dumps(
                    [
                        {
                            "id_documento": "DOC-1",
                            "nome": "SentenzaDefinitiva_33581101.pdf",
                            "tipo": "SentenzaDefinitiva",
                            "data_deposito": "2026-01-08",
                            "mittente": "GIOVANNELLA MARIA ELENA",
                            "dimensione_bytes": 12345,
                            "disponibile": True,
                            "id_deposito": "DEP-1",
                            "tipo_atto": "SentenzaDefinitiva",
                        }
                    ]
                ),
            },
            follow_redirects=True,
        )

    assert response.status_code == 200

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicoli = gestione_fascicoli_reload.tutti()
    assert len(fascicoli) == 1

    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.numero_rg == "1025"
    assert fascicolo_reload.anno_rg == 2024
    assert fascicolo_reload.tribunale == "Tribunale di Palmi"
    assert fascicolo_reload.nome_cliente == "Montagnese Elisabetta"
    assert fascicolo_reload.controparte == "Stillitano Francesco"
    assert len(fascicolo_reload.depositi_pct) == 1
    assert fascicolo_reload.depositi_pct[0].documenti_portale


def test_dettaglio_fascicolo_mostra_metadati_documentali_importati_da_polisweb(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        note="Importato da PolisWeb il 2026-03-29",
    )
    gestione_fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-001",
        tipo_atto="Memoria conclusionale",
        data_deposito="2026-03-29",
        mittente="avv.demo@pec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-001",
                "nome": "memoria_conclusionale.pdf.p7m",
                "tipo": "ATTO",
                "data_deposito": "2026-03-29",
                "mittente": "avv.demo@pec.it",
                "dimensione_bytes": 12000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-001",
                "tipo_atto": "Memoria conclusionale",
            }
        ],
        registrato_da="admin",
        nome_atto_principale="memoria_conclusionale.pdf.p7m",
        servizio_portale="DocumentiFascicolo",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1")

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "memoria_conclusionale.pdf.p7m" in body
    assert "documenti ufficiali" in body
    assert "Nessuna comunicazione di cancelleria" in body


def test_dettaglio_fascicolo_backfilla_metadati_documentali_dal_core_telematico(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        source="PST",
        note="Importato da PolisWeb il 2026-03-29",
    )
    doc = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "SentenzaDefinitiva_33581101.pdf",
        TipoDocumento.SENTENZA,
        b"sentenza",
    )
    gestione_fascicoli.registra_import_documenti_portale(
        id_fasc=fascicolo.id,
        fonte="PolisWeb / PST",
        documenti_ids=[doc.id],
        tipo_atto="Documenti ufficiali PolisWeb",
        note="Lotto locale in attesa di catalogo ufficiale",
        registrato_da="admin",
    )

    repo = TelematicoWorkflowRepository(cfg["TELEMATICO_DB"])
    case = repo.upsert_case(
        practice_id=fascicolo.id,
        channel_family="ministero",
        service_code="polisweb_consultazione",
        office_name="Tribunale di Palmi",
        register_type="RGN",
        register_number="1025",
        register_year=2024,
        subject_name="Montagnese Elisabetta",
        counsel_name="Avv. Demo",
        counsel_cf="MNTRRT64L01L063H",
        portal_case_ref="PALMI-1025-2024",
        internal_status="download_available",
    )
    repo.upsert_document(
        str(case["id"]),
        document_role="judgment",
        document_category="SentenzaDefinitiva",
        title="SentenzaDefinitiva_33581101.pdf",
        original_filename="SentenzaDefinitiva_33581101.pdf",
        source_type="portal",
        portal_document_ref="DOC-001",
        id_deposito="DEP-PORTALE-001",
        tipo_atto="Sentenza definitiva",
        data_deposito="2026-01-08",
        mittente="GIOVANNELLA MARIA ELENA",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?focus=documenti&_legacy=1")

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Metadati portale 1" in body
    assert "Da riallineare" not in body
    assert "Classificazione: SentenzaDefinitiva" in body

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert len(fascicolo_reload.depositi_pct) == 1
    assert fascicolo_reload.depositi_pct[0].id_deposito_esterno == "DEP-PORTALE-001"
    doc_reload = fascicolo_reload.documenti[0]
    assert doc_reload.classificazione_portale == "SentenzaDefinitiva"
    assert doc_reload.tipo_atto_portale == "Sentenza definitiva"
    assert doc_reload.id_documento_portale == "DOC-001"


def test_sync_polisweb_riallinea_anagrafiche_persona_fisica_con_nome_misto(tmp_path):
    from pct.clienti import TipoCliente
    from pct.soggetti import TipoSoggetto

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

    cliente_invertito = gestione_clienti.nuovo(
        tipo=TipoCliente.PERSONA_FISICA,
        nome="Montagnese",
        cognome="Elisabetta",
        codice_fiscale="MNTLBT49E47H558L",
    )
    soggetto_invertito = gestione_soggetti.crea(
        TipoSoggetto.PERSONA_FISICA,
        nome="Montagnese",
        cognome="Elisabetta",
        codice_fiscale="MNTLBT49E47H558L",
        id_cliente=cliente_invertito.id,
    )

    fascicolo_locale = gestione_fascicoli.nuovo(
        titolo="Fascicolo da sincronizzare",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
    )

    fascicolo_pw = FascicoloPolisWeb(
        numero_rg="1025",
        anno_rg=2024,
        ruolo="CIVILE_COGNIZIONE",
        stato="PENDENTE",
        oggetto="Vendita di cose immobili",
        sezione="CIVILE",
        giudice="GIOVANNELLA MARIA ELENA",
        data_iscrizione="2024-09-05",
        data_udienza="2024-12-12",
        parti=["Elisabetta Montagnese", "Francesco Stillitano"],
        parti_dettaglio=[
            {
                "nome": "Elisabetta Montagnese",
                "nome_proprio": "Elisabetta",
                "cognome": "Montagnese",
                "tipo": "ATTORE",
                "codice_fiscale": "MNTLBT49E47H558L",
            },
            {
                "nome": "Francesco Stillitano",
                "nome_proprio": "Francesco",
                "cognome": "Stillitano",
                "tipo": "CONVENUTO",
                "codice_fiscale": "STLFNC45E26L063X",
            },
        ],
        codice_ufficio="0800570094",
        nome_ufficio="Tribunale di Palmi",
    )

    esito = ClientPolisWebDemo().sincronizza_fascicolo_esistente(
        fascicolo_pw=fascicolo_pw,
        fascicolo_locale=fascicolo_locale,
        gestione_fascicoli=gestione_fascicoli,
        gestione_clienti=gestione_clienti,
        gestione_soggetti=gestione_soggetti,
        avvocato_referente="admin",
        documenti_pw=[],
    )

    assert esito.successo is True
    cliente_reload = gestione_clienti.get(cliente_invertito.id)
    soggetto_reload = next(s for s in gestione_soggetti.tutti() if s.id == soggetto_invertito.id)
    fascicolo_reload = gestione_fascicoli.get(fascicolo_locale.id)

    assert cliente_reload is not None
    assert cliente_reload.nome == "Elisabetta"
    assert cliente_reload.cognome == "Montagnese"
    assert cliente_reload.nome_completo == "Montagnese Elisabetta"
    assert soggetto_reload.nome == "Elisabetta"
    assert soggetto_reload.cognome == "Montagnese"
    assert fascicolo_reload.nome_cliente == "Montagnese Elisabetta"
    assert fascicolo_reload.controparte == "Stillitano Francesco"


def test_dettaglio_fascicolo_mostra_azioni_per_documento_ufficiale_acquisito(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 707/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="707",
        anno_rg=2025,
    )
    deposito = gestione_fascicoli.sincronizza_deposito_portale(
        fascicolo.id,
        fonte="PolisWeb / PST",
        id_deposito_esterno="BUSTA-PST-707",
        tipo_atto="Sentenza",
        data_deposito="2026-03-30",
        mittente="cancelleria@tribunale.giustiziapec.it",
        documenti_portale=[
            {
                "id_documento": "DOC-707",
                "nome": "Sentenza definitiva.pdf.p7m",
                "tipo": "PROVVEDIMENTO",
                "data_deposito": "2026-03-30",
                "mittente": "cancelleria@tribunale.giustiziapec.it",
                "dimensione_bytes": 16000,
                "disponibile": True,
                "id_deposito": "BUSTA-PST-707",
                "tipo_atto": "Sentenza",
            }
        ],
        registrato_da="admin",
        servizio_portale="DocumentiFascicolo",
    )
    doc = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "Sentenza definitiva.pdf.p7m",
        TipoDocumento.SENTENZA,
        b"sentenza firmata",
        id_deposito_pct=deposito.id,
        firmato=True,
        caricato_da="avvocato",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Acquisito nel fascicolo" in body
    assert f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/scarica" in body
    assert f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/visualizza" in body
    assert f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/editor" not in body


def test_dettaglio_fascicolo_visualizzatore_prefetch_blob_per_pdf(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 708/2025",
        tipo=TipoFascicolo.CIVILE,
    )
    gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "memoria.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        b"%PDF-1.4\n% test\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF",
        caricato_da="avvocato",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "response.blob()" in body
    assert "URL.createObjectURL" in body
    assert "Impossibile caricare l\\'anteprima" in body


def test_editor_documento_firmato_reindirizza_a_visualizzazione(tmp_path):
    from asn1crypto import cms, algos
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 807/2025",
        tipo=TipoFascicolo.CIVILE,
    )
    pdf_bytes = b"%PDF-1.4\n% demo\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data", "content": pdf_bytes},
            "signer_infos": [],
        }
    )
    p7m_bytes = cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump()
    doc = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "attoACQ.pdf.p7m",
        TipoDocumento.ATTO_GIUDIZIARIO,
        p7m_bytes,
        firmato=True,
        caricato_da="avvocato",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(
            f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/editor",
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert response.headers["Location"].endswith(
        f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/visualizza"
    )


def test_visualizza_documento_estrae_pdf_da_p7m(tmp_path):
    from asn1crypto import cms, algos
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 808/2025",
        tipo=TipoFascicolo.CIVILE,
    )
    pdf_bytes = b"%PDF-1.4\n% demo\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data", "content": pdf_bytes},
            "signer_infos": [],
        }
    )
    p7m_bytes = cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump()
    doc = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "attoACQ.pdf.p7m",
        TipoDocumento.ATTO_GIUDIZIARIO,
        p7m_bytes,
        firmato=True,
        caricato_da="avvocato",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/visualizza")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert "attoACQ.pdf" in response.headers.get("Content-Disposition", "")


def test_visualizza_documento_p7m_detached_usa_pdf_originale_da_storico(tmp_path):
    from asn1crypto import cms, algos
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 909/2025",
        tipo=TipoFascicolo.CIVILE,
    )
    pdf_bytes = b"%PDF-1.4\n% originale\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    doc = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "citazione.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdf_bytes,
        caricato_da="avvocato",
    )

    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data"},
            "signer_infos": [],
        }
    )
    p7m_detached = cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump()
    gestione_fascicoli.sostituisci_documento(
        fascicolo.id,
        doc.id,
        nome_file="citazione.pdf.p7m",
        contenuto=p7m_detached,
        caricato_da="avvocato",
        note="Versione firmata per deposito",
    )
    gestione_fascicoli.segna_firmato(fascicolo.id, doc.id)

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/visualizza")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")


def test_visualizza_documento_p7m_mostra_timbro_firma_visibile(tmp_path, monkeypatch):
    from asn1crypto import cms, algos
    from pct.auth import GestioneUtenti, RuoloUtente
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from visible_signature import has_visible_signature_stamp
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
        nome_completo="Roberto Montagnese",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 910/2025",
        tipo=TipoFascicolo.CIVILE,
    )
    buf_pdf = io.BytesIO()
    c = canvas.Canvas(buf_pdf, pagesize=A4)
    c.drawString(90, 760, "Citazione di prova")
    c.save()
    pdf_bytes = buf_pdf.getvalue()
    doc = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "citazione.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdf_bytes,
        caricato_da="avvocato",
    )

    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data"},
            "signer_infos": [],
        }
    )
    p7m_detached = cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump()
    gestione_fascicoli.sostituisci_documento(
        fascicolo.id,
        doc.id,
        nome_file="citazione.pdf.p7m",
        contenuto=p7m_detached,
        caricato_da="avvocato",
        note="Versione firmata per deposito",
    )
    gestione_fascicoli.segna_firmato(fascicolo.id, doc.id)

    monkeypatch.setattr(
        "pct.firma.analizza_firma_documento",
        lambda data, nome_file="": [
            {
                "intestatario": "ROBERTO MONTAGNESE",
                "data_firma": "2024-12-11T17:46:00",
                "formato": "CAdES",
                "scaduto": False,
                "avviso_imminente": False,
            }
        ],
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/visualizza")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF-")
    assert has_visible_signature_stamp(response.data) is True
    assert b"ROBERTO MONTAGNESE" in response.data


@pytest.mark.parametrize(
    ("mode", "label"),
    [
        ("laterale", "Laterale verticale"),
        ("basso_sinistra", "In basso a sinistra"),
        ("basso_destra", "In basso a destra"),
    ],
)
def test_visualizza_documento_p7m_usa_posizione_firma_visibile_salvata_nel_pdf(tmp_path, monkeypatch, mode, label):
    fitz = pytest.importorskip("fitz")
    from asn1crypto import algos, cms
    from pct.auth import GestioneUtenti, RuoloUtente
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    ).crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
        nome_completo="Roberto Montagnese",
    )
    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(titolo="RG 910/2025", tipo=TipoFascicolo.CIVILE)
    buf_pdf = io.BytesIO()
    c = canvas.Canvas(buf_pdf, pagesize=A4)
    c.drawString(90, 760, "Citazione di prova senza timbri in basso")
    c.save()
    doc = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "citazione.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        buf_pdf.getvalue(),
        caricato_da="avvocato",
    )
    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data"},
            "signer_infos": [],
        }
    )
    gestione_fascicoli.sostituisci_documento(
        fascicolo.id,
        doc.id,
        nome_file="citazione.pdf.p7m",
        contenuto=cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump(),
        caricato_da="avvocato",
        note=f"Versione firmata per deposito. Posizione firma visibile: {label}.",
    )
    gestione_fascicoli.segna_firmato(fascicolo.id, doc.id)
    monkeypatch.setattr(
        "pct.firma.analizza_firma_documento",
        lambda data, nome_file="": [
            {
                "intestatario": "ROBERTO MONTAGNESE",
                "data_firma": "2024-12-11T17:46:00",
                "formato": "CAdES",
                "scaduto": False,
                "avviso_imminente": False,
            }
        ],
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post("/login", data={"username": "avvocato", "password": "Avv12345!"}, follow_redirects=True)
        response = client.get(f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/visualizza")

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    pdf_doc = fitz.open(stream=response.data, filetype="pdf")
    page = pdf_doc[0]
    width, height = page.rect.width, page.rect.height

    def dark_ratio(rect):
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(*rect), alpha=False)
        channels = pix.n
        samples = pix.samples
        dark = 0
        for index in range(0, len(samples), channels):
            if min(samples[index], samples[index + 1], samples[index + 2]) < 245:
                dark += 1
        return dark / max(pix.width * pix.height, 1)

    left_bottom = dark_ratio((18, height - 124, width / 2, height - 18))
    right_bottom = dark_ratio((width / 2, height - 124, width - 18, height - 18))
    right_side = dark_ratio((width - 96, 132, width - 2, height - 140))

    if mode == "basso_sinistra":
        assert left_bottom > 0.004
        assert left_bottom > right_bottom * 1.7
    elif mode == "basso_destra":
        assert right_bottom > 0.004
        assert right_bottom > left_bottom * 1.7
    else:
        assert right_side > 0.002
        assert right_side > max(left_bottom, right_bottom) * 1.2


def test_api_info_firma_documento_espone_stato_payload_p7m_detached(tmp_path):
    from asn1crypto import algos, cms
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 911/2025",
        tipo=TipoFascicolo.CIVILE,
    )
    pdf_bytes = b"%PDF-1.4\n% detached\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    documento = gestione_fascicoli.aggiungi_documento(
        fascicolo.id,
        "comparsa.pdf",
        TipoDocumento.ATTO_GIUDIZIARIO,
        pdf_bytes,
        caricato_da="avvocato",
    )
    signed = cms.SignedData(
        {
            "version": "v1",
            "digest_algorithms": [algos.DigestAlgorithm({"algorithm": "sha256"})],
            "encap_content_info": {"content_type": "data"},
            "signer_infos": [],
        }
    )
    gestione_fascicoli.sostituisci_documento(
        fascicolo.id,
        documento.id,
        nome_file="comparsa.pdf.p7m",
        contenuto=cms.ContentInfo({"content_type": "signed_data", "content": signed}).dump(),
        caricato_da="avvocato",
        note="Versione firmata",
    )
    gestione_fascicoli.segna_firmato(fascicolo.id, documento.id)

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(f"/api/fascicoli/{fascicolo.id}/documenti/{documento.id}/info-firma")

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["signed_status"]["payload_available"] is True
    assert payload["signed_status"]["detached_signature"] is True
    assert payload["signed_ui"]["content_label"] == "Contenuto estratto"
    assert payload["signed_ui"]["signature_label"] in {"Firma verificata", "Firma da verificare"}


def test_route_home_sigit_mostra_hub_ptt_guidato(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get("/sigit", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Portale ufficiale PTT / SIGIT - Telecontenzioso" in body
    assert "Apri PTT / SIGIT" in body
    assert "Apri Telecontenzioso" in body
    assert "Accesso temporaneo al fascicolo" in body
    assert "Fascicolo Tributario Interno" in body
    assert "Cerca nel SIGIT" not in body


def test_route_documenti_sigit_reindirizza_al_wizard_guidato(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get(
            "/sigit/documenti?codice_commissione=CPT030000&numero_rgt=1234&anno_rgt=2026&demo_mode=1",
            follow_redirects=True,
        )

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Acquisizione guidata" in body
    assert "PTT / SIGIT" in body
    assert "Telecontenzioso" in body


def test_route_wizard_acquisizione_portali_renderizza_step_guida(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        for portale, titolo in [
            ("pst", "Importa pratica da PST"),
            ("pdp", "Importa pratica da PDP Penale"),
            ("pat", "Importa pratica da PAT"),
            ("ptt", "Importa pratica da PTT"),
        ]:
            response = client.get(f"/portali/{portale}/acquisizione", follow_redirects=True)
            body = response.data.decode("utf-8")
            assert response.status_code == 200
            assert titolo in body
            assert "Step 1" in body
            assert "Step 7" in body
            assert "Riepilogo sempre visibile" in body
            assert "Importa ZIP, file o cartella gia scaricati" in body
            assert "awManualUploadFiles" in body
            assert "awManualUploadFolder" in body
            if portale == "pst":
                assert "scarica_originale_portale: awSelectionValue('scarica_originale_portale', AW_BOOT.portale === 'pst' ? false : true)" in body
                assert 'id="scarica_originale_portale" checked' not in body
                assert "Scarica duplicato/originale senza coccarda ministeriale" in body
                assert "Default PST: copia di consultazione/copia informatica con annotazioni ministeriali" in body
        manual_response = client.get("/portali/pat/acquisizione?focus=manual-upload", follow_redirects=True)
        manual_body = manual_response.data.decode("utf-8")
        assert manual_response.status_code == 200
        assert "Importazione dei file gia scaricati" in manual_body
        assert "Step 7 - Importazione finale" in manual_body


def test_route_wizard_acquisizione_portali_espone_fallback_manuale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get("/portali/pdp/acquisizione", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Prosegui con inserimento manuale" in body
    assert "Acquisizione assistita via browser ufficiale" in body
    assert "Consultazione via browser ufficiale" in body
    assert "Servizio remoto non disponibile" not in body


def test_api_acquisizione_status_portale_p12_non_forza_browser_only(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    p12_path = tmp_path / "firma-test.p12"
    p12_path.write_bytes(b"fake-p12")

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.p12_path = str(p12_path)
    studio.firma.backend_preferito = "p12"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get("/api/portali/pdp/acquisizione/status", follow_redirects=True)

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"]["browser_channel_required"] is False
    assert data["status"]["status_text"] == "Connessione pronta"
    assert data["status"]["environment_label"] == "Produzione guidata"


def test_api_acquisizione_status_pst_usa_local_signer_anche_senza_libreria_server(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.backend_preferito = "pkcs11"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get("/api/portali/pst/acquisizione/status", follow_redirects=True)

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"]["auth_mode"] == "pkcs11"
    assert data["status"]["pkcs11_mode"] is True
    assert data["status"]["demo_mode"] is False
    assert data["status"]["status_text"] == "Accesso via Local Signer / Aruba Key"
    assert data["status"]["environment_label"] == "Produzione guidata via browser locale"


def test_api_acquisizione_preview_pst_local_signer_non_apre_circuito_preview(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from pct.runtime_resilience import clear_runtime_circuit_breakers
    from web.app import create_app
    from web.services.telematico_resilience import get_portale_circuit_breaker

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.backend_preferito = "pkcs11"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    clear_runtime_circuit_breakers("portale:pst:preview")
    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/preview",
            json={
                "selection": {
                    "external_id": "0800570152:466:2023:GDP",
                    "numero": "466",
                    "anno": 2023,
                    "ufficio_codice": "0800570152",
                    "ufficio_nome": "Ufficio del Giudice di Pace di Palmi",
                    "procedimento": "GDP",
                    "parti": ["ALESSI ROBERTINO"],
                    "controparti": ["ZURICH ASS.NI"],
                    "payload": {
                        "numero_rg": "466",
                        "anno_rg": 2023,
                        "ruolo": "GDP",
                        "registro_portale": "GDP",
                    },
                }
            },
            follow_redirects=True,
        )

    data = response.get_json()
    snapshot = get_portale_circuit_breaker("pst", operation="preview").snapshot()
    assert response.status_code == 200
    assert data["ok"] is False
    assert "Local Signer del browser" in data["errore"]
    assert "temporaneamente sospeso" not in data["errore"]
    assert snapshot["open"] is False
    assert snapshot["failure_count"] == 0


def test_api_acquisizione_preview_pst_accetta_documenti_da_browser_locale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.backend_preferito = "pkcs11"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/preview",
            json={
                "selection": {
                    "external_id": "0800570152:466:2023:GDP",
                    "numero": "466",
                    "anno": 2023,
                    "ufficio_codice": "0800570152",
                    "ufficio_nome": "Ufficio del Giudice di Pace di Palmi",
                    "procedimento": "GDP",
                    "manual_mode": True,
                    "parti": ["ALESSI ROBERTINO"],
                    "controparti": ["ZURICH ASS.NI"],
                    "payload": {
                        "numero_rg": "466",
                        "anno_rg": 2023,
                        "ruolo": "GDP",
                        "registro_portale": "GDP",
                        "data_iscrizione": "2023-02-23",
                        "data_udienza": "2023-03-01",
                    },
                },
                "documenti": [
                    {
                        "id_documento": "DOC-001",
                        "id_deposito": "DEP-001",
                        "nome": "atto introduttivo.pdf",
                        "tipo_atto": "Atto introduttivo",
                        "data_deposito": "2023-02-23",
                        "mittente": "MONTAGNESE ROBERTO",
                    },
                    {
                        "id_documento": "DOC-002",
                        "id_deposito": "DEP-002",
                        "nome": "verbale udienza.pdf",
                        "tipo_atto": "Verbale",
                        "data_deposito": "2023-03-01",
                        "mittente": "Cancelleria GDP",
                    },
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["preview"]["counts"]["documenti"] == 2
    assert data["preview"]["counts"]["depositi"] == 2
    assert data["preview"]["identity"]["data_iscrizione"] == "2023-02-23"
    assert data["preview"]["documenti"][0]["nome"] in {"atto introduttivo.pdf", "verbale udienza.pdf"}


def test_acquisizione_wizard_pst_preview_error_usa_fallback_assistito():
    template = (Path(__file__).resolve().parents[1] / "web" / "templates" / "portale" / "acquisizione_wizard.html").read_text(encoding="utf-8")

    assert "function awPstRecoverablePreviewError" in template
    assert "temporaneamente sospeso" in template
    assert "awPortaleBrowserOnlyError(err) || awPstRecoverablePreviewError(err)" in template
    assert "awBuildManualSelection(query, reason, portaleUrl)" in template
    assert "PST/PolisWeb" in template


def test_acquisizione_wizard_pst_carica_documenti_local_signer_anche_in_modalita_assistita():
    template = (Path(__file__).resolve().parents[1] / "web" / "templates" / "portale" / "acquisizione_wizard.html").read_text(encoding="utf-8")

    assert 'id="awLoadDocuments"' in template
    assert "Carica documenti dal Local Signer" in template
    assert "function awCanPreviewPstViaBrowser" in template
    assert "function awShouldLoadPreviewViaLocalSigner" in template
    assert "if (awCanPreviewPstViaBrowser(selection)) return true;" in template
    assert "return !selection?.manual_mode && awShouldUseLocalSigner();" in template
    assert "payload.documenti = await awPreviewViaLocalSigner(selection)" in template
    assert "document.getElementById('awLoadDocuments').addEventListener('click', awLoadDocumentsFromLocalSigner)" in template
    assert "function awEnsurePstPreviewDocumentCatalog" in template
    assert "await awEnsurePstPreviewDocumentCatalog()" in template
    assert "/pst/ricerca-snapshot" in template
    assert "function awCanUsePstSearchSnapshot" in template
    assert "async function awNormalizeInitialOfficeCode" in template
    assert "item?.codice_ministero" in template
    assert "officeValue.value = codice" in template
    assert "await awApplyInitialQueryFromNotification()" in template
    assert "/pst/download-documenti-batch" in template
    assert "`${AW_PST_LS_BASE}/pst/preflight-auth`" not in template
    assert "function awEnsurePstPortalSession" not in template
    assert "function awGetActivePstSession" in template
    assert "preflight_auth: false" in template
    assert "purpose: 'view'" in template
    assert "purpose: 'import'" not in template
    assert "const exactByRg = !!(String(query.numero || '').trim() && String(query.anno || '').trim());" in template
    assert "nome_parte: exactByRg ? '' : (query.assistito || query.controparte || '')" in template
    assert "cf_parte: exactByRg ? '' : (query.cf || '')" in template
    assert "function awPstAttorneyCf()" in template
    assert "codice_fiscale: data.codice_fiscale || data.codiceFiscale || data.codice_fiscale_avvocato || ''" in template
    assert "cf_avvocato: awPstAttorneyCf()" in template
    assert "cf_avvocato: exactByRg ? ''" not in template
    assert "AW_PST_IMPORT_SESSION?.session_id" not in template
    assert "Importazione interrotta: non salvo il fascicolo solo come metadati" in template
    assert "function awCanProceedWithPartialPstDownload" in template
    assert "Aggiorno la pratica locale selezionata con i file ricevuti" in template
    assert "Usa pratica esistente" in template
    assert "Destinazione pratica" in template
    assert "Collega a pratica esistente" not in template
    assert "Aggiorna pratica esistente" not in template
    assert "Array.isArray(data.value) ? data.value : []" in template
    assert "window.location.href = autoOpenUrl" in template
    assert "Importa tutto" in template
    assert "awFormatDate(identity.data_iscrizione)" in template
    assert "awEscape(dep.data_deposito || 'n.d.')" not in template


def test_polisweb_classico_non_chiede_preflight_pin_prima_delle_operazioni_reali():
    root = Path(__file__).resolve().parents[1]
    for template_path in (root / "web" / "templates" / "polisWeb.html", root / "web" / "polisWeb.html"):
        source = template_path.read_text(encoding="utf-8")
        assert "/pst/preflight-auth" not in source
        assert "_lsPreflightAuthPst" not in source
        assert "Apri PIN Windows" not in source
        assert "Richiesta PIN" not in source
        assert "_lsGetKnownPstSessionId" in source
        assert "_lsRememberPstSession" in source
        assert "/pst/ricerca" in source
        assert "/pst/documenti" in source


def test_api_acquisizione_status_pat_forza_browser_ufficiale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    p12_path = tmp_path / "firma-test.p12"
    p12_path.write_bytes(b"fake-p12")

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.p12_path = str(p12_path)
    studio.firma.backend_preferito = "p12"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get("/api/portali/pat/acquisizione/status", follow_redirects=True)

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"]["browser_channel_required"] is True
    assert data["status"]["status_text"] == "Consultazione via Portale dell'Avvocato"
    assert data["status"]["environment_label"] == "Produzione guidata assistita"


def test_api_acquisizione_status_ptt_forza_browser_ufficiale(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    p12_path = tmp_path / "firma-test.p12"
    p12_path.write_bytes(b"fake-p12")

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.p12_path = str(p12_path)
    studio.firma.backend_preferito = "p12"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.get("/api/portali/ptt/acquisizione/status", follow_redirects=True)

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["status"]["browser_channel_required"] is True
    assert data["status"]["status_text"] == "Consultazione via PTT / SIGIT"
    assert data["status"]["environment_label"] == "Produzione guidata assistita"


def test_api_acquisizione_status_portali_browser_guided_restano_fuori_demo_senza_certificato(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        for portale, expected_status in (
            ("pdp", "Consultazione via PDP Penale ufficiale"),
            ("pat", "Consultazione via Portale dell'Avvocato"),
            ("ptt", "Consultazione via PTT / SIGIT"),
        ):
            response = client.get(f"/api/portali/{portale}/acquisizione/status", follow_redirects=True)
            data = response.get_json()
            assert response.status_code == 200
            assert data["ok"] is True
            assert data["status"]["demo_mode"] is False
            assert data["status"]["browser_channel_required"] is True
            assert data["status"]["status_text"] == expected_status


def test_route_home_portali_mostra_link_acquisizione_guidata(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        checks = [
            ("/polisWeb?_legacy=1", "/portali/pst/acquisizione"),
            ("/pdp?_legacy=1", "/portali/pdp/acquisizione"),
            ("/pat?_legacy=1", "/portali/pat/acquisizione"),
            ("/sigit?_legacy=1", "/portali/ptt/acquisizione"),
        ]
        for route, expected in checks:
            response = client.get(route, follow_redirects=True)
            body = response.data.decode("utf-8")
            assert response.status_code == 200
            assert expected in body
        pat_response = client.get("/pat?_legacy=1", follow_redirects=True)
        ptt_response = client.get("/sigit?_legacy=1", follow_redirects=True)
        pdp_response = client.get("/pdp?_legacy=1", follow_redirects=True)

    pat_body = pat_response.data.decode("utf-8")
    ptt_body = ptt_response.data.decode("utf-8")
    assert "Apri Portale Avvocato" in pat_body
    assert "Nuovo deposito Form Web" in pat_body
    assert "Consulta fascicolo sul portale" in pat_body
    assert "Acquisizione guidata e import file" in pat_body
    assert "Importa file già scaricati" in pat_body
    assert "focus=manual-upload" in pat_body
    assert "Fascicolo PAT interno" in pat_body
    assert "Cerca nel SIGA" not in pat_body
    assert "portal-hub-pane" in pat_body
    assert "portal-hub-note" in pat_body
    assert "MODALITA DEMO" not in pat_body
    assert "modalita demo (offline)" not in pat_body
    assert "Apri PTT / SIGIT" in ptt_body
    assert "Apri Telecontenzioso" in ptt_body
    assert "Accesso temporaneo al fascicolo" in ptt_body
    assert "Acquisizione guidata e import file" in ptt_body
    assert "Importa file già scaricati" in ptt_body
    assert "focus=manual-upload" in ptt_body
    assert "Fascicolo Tributario Interno" in ptt_body
    assert "Cerca nel SIGIT" not in ptt_body
    assert "portal-hub-pane" in ptt_body
    assert "portal-hub-note" in ptt_body
    assert "MODALITA DEMO" not in ptt_body
    assert "modalita demo (offline)" not in ptt_body
    assert 'href="https://sigit.giustiziatributaria.gov.it/Sigit/index.do"' in ptt_body
    pdp_body = pdp_response.data.decode("utf-8")
    assert "Apri PDP Penale" in pdp_body
    assert "Acquisizione guidata e import file" in pdp_body
    assert "Fascicolo Penale Interno" in pdp_body
    assert "workflow PDP" in pdp_body
    assert "portal-hub-pane" in pdp_body
    assert "portal-hub-note" in pdp_body
    assert "MODALITA DEMO" not in pdp_body
    assert "modalita demo (offline)" not in pdp_body
    assert "Importa file già scaricati" in pdp_body
    assert "focus=manual-upload" in pdp_body
    assert 'href="https://sigit.giustiziatributaria.gov.it/FascicoloProcessuale/login.jsp"' in ptt_body
    assert 'href="https://sigit.giustiziatributaria.gov.it/Sigit/"' not in ptt_body


def test_portale_acquisizione_wizard_renderizza_javascript_valido(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    if shutil.which("node") is None:
        pytest.skip("node non disponibile nel runner di test")

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        for route in (
            "/portali/pst/acquisizione",
            "/portali/pdp/acquisizione",
            "/portali/pat/acquisizione",
            "/portali/ptt/acquisizione",
        ):
            response = client.get(route, follow_redirects=True)
            body = response.data.decode("utf-8")
            match = re.search(r"<script>\s*(const AW_BOOT = .*?)</script>", body, re.S)
            assert match, f"Script wizard non trovato per {route}"
            with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as handle:
                handle.write(match.group(1))
                script_path = handle.name
            try:
                result = subprocess.run(
                    ["node", "--check", script_path],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                assert result.returncode == 0, f"JavaScript wizard non valido per {route}: {result.stderr}"
            finally:
                try:
                    os.unlink(script_path)
                except OSError:
                    pass


def test_portale_wizard_mappa_fallback_sigp_come_manuale_assistita():
    template = (Path(__file__).resolve().parents[1] / "web" / "templates" / "portale" / "acquisizione_wizard.html").read_text(
        encoding="utf-8"
    )

    assert "row.verifica_browser_ufficiale" in template
    assert "row.portale_url" in template
    assert "row.controparti" in template
    assert "parti_dettaglio" in template
    assert "awSplitPeople(query.assistito)" in template
    assert "awSplitPeople(query.controparte)" in template
    assert "awMarkSelectionManual(mapped" in template


def test_route_pat_ricerca_reindirizza_al_wizard_guidato(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/pat/ricerca",
            data={"ufficio": "TARLZ", "numero_ricorso": "1876", "anno": "2026"},
            follow_redirects=True,
        )

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Acquisizione guidata" in body
    assert "Portale dell'Avvocato ufficiale" in body


def test_route_ptt_ricerca_reindirizza_al_wizard_guidato(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/sigit/ricerca",
            data={"commissione": "CPT030000", "numero_rgt": "1234", "anno_rgt": "2026"},
            follow_redirects=True,
        )

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Acquisizione guidata" in body
    assert "PTT / SIGIT" in body
    assert "Telecontenzioso" in body


def test_api_acquisizione_search_portali_p12_usa_backend_server(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    import pct.pdp as pdp_module
    import pct.pat as pat_module
    import pct.sigit as sigit_module
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    p12_path = tmp_path / "firma-test.p12"
    p12_path.write_bytes(b"fake-p12")

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.p12_path = str(p12_path)
    studio.firma.backend_preferito = "p12"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    class _FakePdpClient:
        def ricerca_fascicoli(self, **kwargs):
            return [
                SimpleNamespace(
                    numero_rg="4521",
                    anno_rg=2026,
                    tipo_registro="RGNR",
                    fase="INDAGINI",
                    stato="PENDENTE",
                    reato="Truffa",
                    sezione="GIP",
                    giudice="Dott. Verdi",
                    data_iscrizione="2026-01-10",
                    data_udienza="2026-05-12",
                    imputati=["Mario Rossi"],
                    parti_offese=["Parte Offesa"],
                    note="",
                    codice_ufficio="0580010",
                    nome_ufficio="Procura di Reggio Calabria",
                )
            ]

    monkeypatch.setattr(pdp_module, "crea_client_pdp", lambda demo=False: _FakePdpClient())
    monkeypatch.setattr(
        pat_module,
        "crea_client_pat",
        lambda demo=False: (_ for _ in ()).throw(AssertionError("PAT non deve usare una ricerca live lato backend.")),
    )
    monkeypatch.setattr(
        sigit_module,
        "crea_client_sigit",
        lambda demo=False: (_ for _ in ()).throw(AssertionError("PTT non deve usare una ricerca live lato backend.")),
    )

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        ok_checks = [
            ("pdp", {"ufficio_codice": "0580010", "numero": "4521", "anno": "2026"}),
        ]
        for portale, payload in ok_checks:
            response = client.post(
                f"/api/portali/{portale}/acquisizione/search",
                json=payload,
                follow_redirects=True,
            )
            data = response.get_json()
            assert response.status_code == 200
            assert data["ok"] is True
            assert len(data["results"]) == 1

        pat_response = client.post(
            "/api/portali/pat/acquisizione/search",
            json={"ufficio_codice": "TARLZ", "numero": "1876", "anno": "2026"},
            follow_redirects=True,
        )
        ptt_response = client.post(
            "/api/portali/ptt/acquisizione/search",
            json={"ufficio_codice": "CPT030000", "numero": "1234", "anno": "2026"},
            follow_redirects=True,
        )

    pat_data = pat_response.get_json()
    ptt_data = ptt_response.get_json()
    assert pat_response.status_code == 200
    assert pat_data["ok"] is False
    assert "Portale dell'Avvocato" in pat_data["errore"]
    assert ptt_response.status_code == 200
    assert ptt_data["ok"] is False
    assert "PTT / SIGIT" in ptt_data["errore"]
    assert "Telecontenzioso" in ptt_data["errore"]


def test_api_acquisizione_search_pst_subpro_restituisce_messaggio_operativo(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    import pct.polisWeb as polisweb_module
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    p12_path = tmp_path / "firma-test.p12"
    p12_path.write_bytes(b"fake-p12")

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.p12_path = str(p12_path)
    studio.firma.backend_preferito = "p12"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    class _FakePstClient:
        def ricerca_fascicoli(self, **kwargs):
            raise ConnectionError("Il PST ha restituito una SOAP Fault: SUBPRO | SOAP-ENV:Client")

    monkeypatch.setattr(polisweb_module, "crea_client", lambda demo=False: _FakePstClient())

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/search",
            json={"ufficio_codice": "0910401", "numero": "466", "anno": "2023"},
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is False
    assert "sotto-procedimento" in data["errore"]
    assert "SOAP-ENV" not in data["errore"]


def test_api_portale_acquisizione_analyze_manual_mode_non_blocca_parti_mancanti(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pdp/acquisizione/analyze",
            json={
                "selection": {
                    "external_id": "manual:pdp:0580010:4521:2026:RGNR",
                    "numero": "4521",
                    "anno": 2026,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Procura di Reggio Calabria",
                    "procedimento": "RGNR",
                    "oggetto": "Truffa",
                    "parti": [],
                    "controparti": [],
                    "manual_mode": True,
                    "payload": {
                        "numero_rg": "4521",
                        "anno_rg": 2026,
                        "tipo_registro": "RGNR",
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Procura di Reggio Calabria",
                        "manual_mode": True,
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "4521",
                        "anno": 2026,
                        "ufficio_nome": "Procura di Reggio Calabria",
                        "ufficio_codice": "0580010",
                        "procedimento": "RGNR",
                        "stato": "",
                    },
                    "parti": [],
                    "controparti": [],
                    "eventi": [],
                    "documenti": [],
                    "depositi": [],
                    "counts": {
                        "parti": 0,
                        "documenti": 0,
                        "depositi": 0,
                        "eventi": 0,
                        "udienze": 0,
                        "provvedimenti": 0,
                    },
                },
                "mapping": {"mode": "create_new"},
                "options": {
                    "importa_parti": True,
                    "importa_documenti": False,
                    "importa_scadenze": False,
                    "importa_eventi": False,
                },
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert not any(item["label"] == "Parti non disponibili" for item in data["analysis"]["blockers"])
    assert any(item["label"] == "Parti da completare manualmente" for item in data["analysis"]["warnings"])


def test_api_portale_acquisizione_analyze_pst_pratica_esistente_non_blocca_parti_mancanti(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )
    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 3173/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Ufficio del Giudice di Pace di Palmi",
        numero_rg="3173",
        anno_rg=2025,
        oggetto="Importazione PST",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/analyze",
            json={
                "selection": {
                    "external_id": "SIGP:3173:2025",
                    "numero": "3173",
                    "anno": 2025,
                    "ufficio_codice": "0800570152",
                    "ufficio_nome": "Ufficio del Giudice di Pace di Palmi",
                    "procedimento": "GDP",
                    "parti": [],
                    "controparti": [],
                    "payload": {
                        "numero_rg": "3173",
                        "anno_rg": 2025,
                        "ruolo": "GDP",
                        "codice_ufficio": "0800570152",
                        "nome_ufficio": "Ufficio del Giudice di Pace di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "3173",
                        "anno": 2025,
                        "ufficio_nome": "Ufficio del Giudice di Pace di Palmi",
                        "ufficio_codice": "0800570152",
                    },
                    "parti": [],
                    "controparti": [],
                    "documenti": [
                        {"id_documento": "DOC-3173", "nome": "Atto_2767510.pdf", "id_cat": "2767510"}
                    ],
                    "depositi": [],
                    "counts": {"parti": 0, "documenti": 1, "depositi": 0, "eventi": 0, "udienze": 0},
                },
                "options": {
                    "importa_parti": True,
                    "importa_documenti": True,
                    "importa_eventi": False,
                    "importa_scadenze": False,
                },
                "mapping": {"mode": "update_existing", "target_fascicolo_id": fascicolo.id},
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert not any(item["label"] == "Parti non disponibili" for item in data["analysis"]["blockers"])
    assert any(item["label"] == "Parti non esposte dal portale" for item in data["analysis"]["warnings"])


def test_api_portale_acquisizione_import_pdp_via_local_signer_non_richiede_certificato_server(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    import pct.pdp as pdp_module
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    dll_path = tmp_path / "bit4xpki.dll"
    dll_path.write_bytes(b"fake-dll")

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.pkcs11_library = str(dll_path)
    studio.firma.backend_preferito = "pkcs11"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    def _crea_client_non_atteso(*args, **kwargs):
        raise AssertionError("crea_client_pdp non deve essere usato in modalità Local Signer.")

    monkeypatch.setattr(pdp_module, "crea_client_pdp", _crea_client_non_atteso)

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pdp/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:4521:2026:RGNR",
                    "numero": "4521",
                    "anno": 2026,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Procura di Reggio Calabria",
                    "procedimento": "RGNR",
                    "stato": "PENDENTE",
                    "oggetto": "Truffa",
                    "parti": ["Mario Rossi"],
                    "controparti": ["Parte Offesa"],
                    "payload": {
                        "numero_rg": "4521",
                        "anno_rg": 2026,
                        "tipo_registro": "RGNR",
                        "fase": "INDAGINI",
                        "stato": "PENDENTE",
                        "reato": "Truffa",
                        "sezione": "GIP",
                        "giudice": "Giudice Penale",
                        "data_iscrizione": "2026-03-01",
                        "data_udienza": "2026-06-20",
                        "imputati": ["Mario Rossi"],
                        "parti_offese": ["Parte Offesa"],
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Procura di Reggio Calabria",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "4521",
                        "anno": 2026,
                        "ufficio_nome": "Procura di Reggio Calabria",
                        "ufficio_codice": "0580010",
                        "procedimento": "RGNR",
                        "stato": "PENDENTE",
                        "data_udienza": "2026-06-20",
                    },
                    "parti": ["Mario Rossi"],
                    "controparti": ["Parte Offesa"],
                    "eventi": [],
                    "documenti": [],
                    "depositi": [],
                    "counts": {
                        "parti": 2,
                        "documenti": 0,
                        "depositi": 0,
                        "eventi": 0,
                        "udienze": 0,
                        "provvedimenti": 0,
                    },
                },
                "mapping": {"mode": "create_new"},
                "options": {
                    "importa_parti": True,
                    "importa_documenti": False,
                    "importa_scadenze": False,
                    "importa_eventi": False,
                },
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["result"]["created"] is True
    assert data["result"]["id_fascicolo"]
    assert data["result"]["workflow_url"]


def test_api_portale_acquisizione_import_pdp_importa_file_raccolti_dal_browser(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pdp/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:4521:2026:RGNR",
                    "numero": "4521",
                    "anno": 2026,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Procura di Reggio Calabria",
                    "procedimento": "RGNR",
                    "stato": "PENDENTE",
                    "oggetto": "Truffa",
                    "parti": ["Mario Rossi"],
                    "controparti": ["Parte Offesa"],
                    "payload": {
                        "numero_rg": "4521",
                        "anno_rg": 2026,
                        "tipo_registro": "RGNR",
                        "fase": "INDAGINI",
                        "stato": "PENDENTE",
                        "reato": "Truffa",
                        "sezione": "GIP",
                        "giudice": "Giudice Penale",
                        "data_iscrizione": "2026-03-01",
                        "data_udienza": "2026-06-20",
                        "imputati": ["Mario Rossi"],
                        "parti_offese": ["Parte Offesa"],
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Procura di Reggio Calabria",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "4521",
                        "anno": 2026,
                        "ufficio_nome": "Procura di Reggio Calabria",
                        "ufficio_codice": "0580010",
                        "procedimento": "RGNR",
                        "stato": "PENDENTE",
                        "oggetto": "Truffa",
                    },
                    "parti": ["Mario Rossi"],
                    "controparti": ["Parte Offesa"],
                    "difensori": [],
                    "eventi": [],
                    "documenti": [
                        {
                            "id_documento": "PDP-DOC-001",
                            "nome": "MemoriaDifensiva.pdf",
                            "tipo": "MEMORIA",
                            "tipo_atto": "MEMORIA",
                            "data_deposito": "2026-04-11",
                            "mittente": "Studio Rossi",
                            "dimensione_bytes": 128,
                            "disponibile": True,
                            "id_deposito": "BUSTA-PDP-001",
                            "id_deposito_esterno": "BUSTA-PDP-001",
                        }
                    ],
                    "depositi": [
                        {
                            "id_deposito": "BUSTA-PDP-001",
                            "id_deposito_esterno": "BUSTA-PDP-001",
                            "tipo_atto": "MEMORIA",
                            "data_deposito": "2026-04-11",
                            "mittente": "Studio Rossi",
                            "documenti": [
                                {
                                    "id_documento": "PDP-DOC-001",
                                    "nome": "MemoriaDifensiva.pdf",
                                    "tipo": "MEMORIA",
                                    "tipo_atto": "MEMORIA",
                                    "data_deposito": "2026-04-11",
                                    "mittente": "Studio Rossi",
                                    "dimensione_bytes": 128,
                                    "disponibile": True,
                                    "id_deposito": "BUSTA-PDP-001",
                                    "id_deposito_esterno": "BUSTA-PDP-001",
                                }
                            ],
                        }
                    ],
                    "counts": {
                        "parti": 2,
                        "documenti": 1,
                        "depositi": 1,
                        "eventi": 0,
                        "udienze": 0,
                        "provvedimenti": 0,
                    },
                },
                "mapping": {"mode": "create_new"},
                "options": {
                    "importa_parti": True,
                    "importa_documenti": True,
                    "importa_provvedimenti": False,
                    "importa_scadenze": False,
                    "importa_eventi": False,
                    "importa_udienze": False,
                    "mantieni_albero_originale": False,
                    "scarica_originale_portale": True,
                },
                "downloaded_files": [
                    {
                        "nome": "MemoriaDifensiva.pdf",
                        "contenuto_b64": base64.b64encode(b"%PDF-1.4 PDP browser download").decode("ascii"),
                        "origine": r"C:\\Users\\HelpdeskCSC4\\Downloads\\MemoriaDifensiva.pdf",
                        "data_documento": "2026-04-11",
                        "dimensione_bytes": 28,
                        "id_deposito_esterno": "BUSTA-PDP-001",
                        "id_documento_portale": "PDP-DOC-001",
                        "tipo_atto": "MEMORIA",
                    }
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["result"]["summary"]["documenti"] == 1
    assert data["result"]["summary"]["depositi"] == 1
    assert data["result"]["workflow_url"]

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.get(data["result"]["id_fascicolo"])
    assert fascicolo is not None
    assert fascicolo.source == "PDP"
    assert len(fascicolo.documenti) == 1
    assert fascicolo.documenti[0].nome == "MemoriaDifensiva.pdf"

    deposito = next((dep for dep in fascicolo.depositi_pct if dep.id_deposito_esterno == "BUSTA-PDP-001"), None)
    assert deposito is not None
    assert deposito.stato == "IMPORTATO_DA_PORTALE"
    assert deposito.fonte_portale == "PDP"
    assert deposito.documenti_portale
    assert deposito.documenti_portale[0]["id_documento"] == "PDP-DOC-001"
    assert deposito.documenti_ids
    assert fascicolo.documenti[0].id_deposito_pct == deposito.id


def test_route_importa_pdp_via_local_signer_non_richiede_certificato_server(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    import pct.pdp as pdp_module
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    dll_path = tmp_path / "bit4xpki.dll"
    dll_path.write_bytes(b"fake-dll")

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.pkcs11_library = str(dll_path)
    studio.firma.backend_preferito = "pkcs11"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    def _crea_client_non_atteso(*args, **kwargs):
        raise AssertionError("crea_client_pdp non deve essere usato in modalita Local Signer.")

    def _importa_fascicolo_stub(self, fascicolo, gestione_fascicoli, gestione_clienti, avvocato):
        return SimpleNamespace(
            successo=True,
            id_fascicolo_locale="FASC-PDP-1",
            messaggio="Importazione PDP completata.",
            avvisi=[],
        )

    monkeypatch.setattr(pdp_module, "crea_client_pdp", _crea_client_non_atteso)
    monkeypatch.setattr(pdp_module.ClientPDP, "importa_fascicolo", _importa_fascicolo_stub)

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/pdp/importa",
            data={
                "demo_mode": "0",
                "numero_rg": "4521",
                "anno_rg": "2026",
                "tipo_registro": "RGNR",
                "fase": "INDAGINI_PRELIMINARI",
                "stato": "PENDENTE",
                "reato": "Truffa",
                "sezione": "GIP",
                "giudice": "GIUDICE TEST",
                "data_iscrizione": "2026-01-10",
                "data_udienza": "2026-06-20",
                "imputati_json": json.dumps(["Mario Rossi"]),
                "parti_offese_json": json.dumps(["Parte Offesa"]),
                "codice_ufficio": "0580010",
                "nome_ufficio": "Procura di Reggio Calabria",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "/fascicoli/FASC-PDP-1" in response.headers["Location"]


def test_route_importa_pat_via_local_signer_non_richiede_certificato_server(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    import pct.pat as pat_module
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    dll_path = tmp_path / "bit4xpki.dll"
    dll_path.write_bytes(b"fake-dll")

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.pkcs11_library = str(dll_path)
    studio.firma.backend_preferito = "pkcs11"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    def _crea_client_non_atteso(*args, **kwargs):
        raise AssertionError("crea_client_pat non deve essere usato in modalita Local Signer.")

    def _importa_fascicolo_stub(self, fascicolo, gestione_fascicoli, gestione_clienti, avvocato):
        return SimpleNamespace(
            successo=True,
            id_fascicolo_locale="FASC-PAT-1",
            messaggio="Importazione PAT completata.",
            avvisi=[],
        )

    monkeypatch.setattr(pat_module, "crea_client_pat", _crea_client_non_atteso)
    monkeypatch.setattr(pat_module.ClientPAT, "importa_fascicolo", _importa_fascicolo_stub)

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/pat/importa",
            data={
                "demo_mode": "0",
                "numero_ricorso": "1876",
                "anno": "2026",
                "tipo": "RICORSO",
                "stato": "PENDENTE",
                "materia": "APPALTI",
                "sezione": "TAR LAZIO",
                "giudice_relatore": "RELATORE TEST",
                "data_deposito": "2026-02-10",
                "data_udienza": "2026-09-15",
                "oggetto": "Revoca aggiudicazione",
                "ricorrenti_json": json.dumps(["Alfa S.r.l."]),
                "resistenti_json": json.dumps(["Comune di Roma"]),
                "codice_ufficio": "TARLZ",
                "nome_ufficio": "TAR Lazio",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "/fascicoli/FASC-PAT-1" in response.headers["Location"]


def test_route_importa_sigit_via_local_signer_non_richiede_certificato_server(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    import pct.sigit as sigit_module
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    dll_path = tmp_path / "bit4xpki.dll"
    dll_path.write_bytes(b"fake-dll")

    gs = GestioneConfigStudio(str(studio_cfg))
    studio = gs.config
    studio.firma.pkcs11_library = str(dll_path)
    studio.firma.backend_preferito = "pkcs11"
    studio.firma.cf_avvocato = "RSSMRA80A01H501Z"
    gs.aggiorna(studio)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    def _crea_client_non_atteso(*args, **kwargs):
        raise AssertionError("crea_client_sigit non deve essere usato in modalita Local Signer.")

    def _importa_fascicolo_stub(self, fascicolo, gestione_fascicoli, gestione_clienti, avvocato):
        return SimpleNamespace(
            successo=True,
            id_fascicolo_locale="FASC-PTT-1",
            messaggio="Importazione PTT completata.",
            avvisi=[],
        )

    monkeypatch.setattr(sigit_module, "crea_client_sigit", _crea_client_non_atteso)
    monkeypatch.setattr(sigit_module.ClientSIGIT, "importa_fascicolo", _importa_fascicolo_stub)

    app = create_app({**cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/sigit/importa",
            data={
                "demo_mode": "0",
                "numero_rgt": "1234",
                "anno_rgt": "2026",
                "tipo": "RICORSO",
                "stato": "PENDENTE",
                "materia": "IVA",
                "sezione": "CGT I grado",
                "giudice_relatore": "RELATORE TEST",
                "data_deposito": "2026-03-12",
                "data_udienza": "2026-10-01",
                "oggetto_controversia": "Accertamento IVA",
                "valore_controversia": "15000",
                "ricorrenti_json": json.dumps(["Mario Rossi"]),
                "resistenti_json": json.dumps(["Agenzia delle Entrate"]),
                "codice_commissione": "CPT030000",
                "nome_commissione": "Corte di Giustizia Tributaria di primo grado di Catanzaro",
            },
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "/fascicoli/FASC-PTT-1" in response.headers["Location"]


def test_api_portale_acquisizione_import_pst_importa_file_reali_e_salva_albero(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:1025:2024:RG",
                    "numero": "1025",
                    "anno": 2024,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Tribunale di Palmi",
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "stato": "PROCEDIMENTO DEFINITO",
                    "oggetto": "Vendita di cose immobili",
                    "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                    "controparti": [],
                    "payload": {
                        "numero_rg": "1025",
                        "anno_rg": 2024,
                        "ruolo": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "PROCEDIMENTO DEFINITO",
                        "oggetto": "Vendita di cose immobili",
                        "sezione": "CIVILE",
                        "data_iscrizione": "2024-09-05",
                        "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Tribunale di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "1025",
                        "anno": 2024,
                        "ufficio_nome": "Tribunale di Palmi",
                        "ufficio_codice": "0580010",
                        "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "PROCEDIMENTO DEFINITO",
                    },
                    "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                    "controparti": [],
                    "difensori": [],
                    "eventi": [],
                    "documenti": [
                        {
                            "id_documento": "DOC-VERBALE-1",
                            "nome": "VerbaleUdienza_29740536.pdf.p7m",
                            "tipo": "VERBALE",
                            "tipo_atto": "VerbaleUdienza",
                            "data_deposito": "2025-01-21",
                            "mittente": "cancelleria@tribunale.giustiziapec.it",
                            "id_deposito": "BUSTA-PST-001",
                            "id_cat": "CAT-001",
                        }
                    ],
                    "depositi": [
                        {
                            "id_deposito": "BUSTA-PST-001",
                            "tipo_atto": "VerbaleUdienza",
                            "data_deposito": "2025-01-21",
                            "mittente": "cancelleria@tribunale.giustiziapec.it",
                            "documenti": [
                                {
                                    "id_documento": "DOC-VERBALE-1",
                                    "nome": "VerbaleUdienza_29740536.pdf.p7m",
                                    "tipo": "VERBALE",
                                    "tipo_atto": "VerbaleUdienza",
                                    "data_deposito": "2025-01-21",
                                    "mittente": "cancelleria@tribunale.giustiziapec.it",
                                    "id_deposito": "BUSTA-PST-001",
                                    "id_cat": "CAT-001",
                                }
                            ],
                        }
                    ],
                    "counts": {
                        "parti": 2,
                        "difensori": 0,
                        "eventi": 0,
                        "udienze": 0,
                        "documenti": 1,
                        "provvedimenti": 0,
                        "depositi": 1,
                        "esiti": 0,
                    },
                },
                "options": {
                    "importa_dati_pratica": True,
                    "importa_parti": True,
                    "importa_difensori": False,
                    "importa_eventi": False,
                    "importa_udienze": False,
                    "importa_scadenze": False,
                    "importa_documenti": True,
                    "importa_provvedimenti": True,
                    "importa_cronologia_depositi": True,
                    "importa_esiti_telematici": False,
                    "solo_nuovi": True,
                    "aggiorna_pratica_esistente": True,
                    "sovrascrivi_solo_vuoti": True,
                    "non_toccare_note_interne": True,
                    "non_duplicare_documenti": True,
                    "conserva_log_origine_pst": True,
                    "mantieni_albero_originale": True,
                },
                "mapping": {
                    "mode": "attach_existing",
                    "target_fascicolo_id": fascicolo.id,
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "materia": "Civile",
                    "grado": "Primo grado",
                },
                "downloaded_files": [
                    {
                        "nome": "VerbaleUdienza_29740536.pdf.p7m",
                        "contenuto_b64": base64.b64encode(b"fake-signed-verbale").decode("ascii"),
                        "content_type": "application/pkcs7-mime",
                        "data_documento": "2025-01-21",
                        "origine": "pst:JPW_SICID:DOC-VERBALE-1",
                        "id_deposito_esterno": "BUSTA-PST-001",
                        "id_documento_portale": "DOC-VERBALE-1",
                        "tipo_atto": "VerbaleUdienza",
                        "tipo": "VERBALE",
                        "id_cat": "CAT-001",
                    }
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["result"]["summary"]["documenti"] == 1
    assert data["result"]["summary"]["albero_originale_salvato"] is True
    assert data["result"]["summary"]["modalita_documento_portale"] == "copia"

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.stato == StatoFascicolo.DEFINITO
    assert fascicolo_reload.source_snapshot["portale"] == "PST"
    assert fascicolo_reload.source_snapshot["counts"]["documenti"] == 1
    assert fascicolo_reload.source_snapshot["parti"] == ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"]
    assert len(fascicolo_reload.documenti) == 1
    assert len(fascicolo_reload.depositi_pct) == 1
    doc = fascicolo_reload.documenti[0]
    assert doc.nome.endswith(".p7m")
    assert doc.firmato is True
    assert doc.tipo == TipoDocumento.VERBALE
    assert doc.data_documento == "2025-01-21"
    assert doc.data_deposito_portale == "2025-01-21"
    assert "Copia di consultazione" in doc.tags
    assert "Documenti fascicolo" in doc.tags
    assert "VerbaleUdienza" in doc.tags
    assert "VerbaleUdienza" in doc.tags
    assert re.search(r"Importato da PolisWeb / PST il \d{2}/\d{2}/\d{4}", doc.note or "")
    assert fascicolo_reload.depositi_pct[0].documenti_ids == [doc.id]

    albero_root = Path(cfg["PST_IMPORT_DIR"]) / "_alberi_originali" / fascicolo.id
    assert albero_root.exists()
    assert any(path.is_file() for path in albero_root.rglob("*"))

    import_log_path = tmp_path / "portale" / "import_log.json"
    assert import_log_path.exists()
    import_rows = json.loads(import_log_path.read_text(encoding="utf-8"))
    assert any(
        str(row.get("id") or "").strip() == data["result"]["import_log_id"]
        and str(row.get("portale") or "").strip() == "PST"
        for row in import_rows
    )


def test_api_portale_acquisizione_import_pst_blocca_catalogo_senza_file(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)

    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:1025:2024:RG",
                    "numero": "1025",
                    "anno": 2024,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Tribunale di Palmi",
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "stato": "PROCEDIMENTO DEFINITO",
                    "oggetto": "Vendita di cose immobili",
                    "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                    "controparti": [],
                    "payload": {
                        "numero_rg": "1025",
                        "anno_rg": 2024,
                        "ruolo": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "PROCEDIMENTO DEFINITO",
                        "oggetto": "Vendita di cose immobili",
                        "sezione": "CIVILE",
                        "data_iscrizione": "2024-09-05",
                        "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Tribunale di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "1025",
                        "anno": 2024,
                        "ufficio_nome": "Tribunale di Palmi",
                        "ufficio_codice": "0580010",
                        "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "PROCEDIMENTO DEFINITO",
                    },
                    "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                    "controparti": [],
                    "difensori": [],
                    "eventi": [],
                    "documenti": [
                        {
                            "id_documento": "DOC-VERBALE-1",
                            "nome": "VerbaleUdienza_29740536.pdf.p7m",
                            "tipo": "VERBALE",
                            "tipo_atto": "VerbaleUdienza",
                            "data_deposito": "2025-01-21",
                            "mittente": "cancelleria@tribunale.giustiziapec.it",
                            "id_deposito": "BUSTA-PST-001",
                            "id_cat": "CAT-001",
                        }
                    ],
                    "depositi": [
                        {
                            "id_deposito": "BUSTA-PST-001",
                            "tipo_atto": "VerbaleUdienza",
                            "data_deposito": "2025-01-21",
                            "mittente": "cancelleria@tribunale.giustiziapec.it",
                            "documenti": [
                                {
                                    "id_documento": "DOC-VERBALE-1",
                                    "nome": "VerbaleUdienza_29740536.pdf.p7m",
                                    "tipo": "VERBALE",
                                    "tipo_atto": "VerbaleUdienza",
                                    "data_deposito": "2025-01-21",
                                    "mittente": "cancelleria@tribunale.giustiziapec.it",
                                    "id_deposito": "BUSTA-PST-001",
                                    "id_cat": "CAT-001",
                                }
                            ],
                        }
                    ],
                    "counts": {
                        "parti": 2,
                        "difensori": 0,
                        "eventi": 0,
                        "udienze": 0,
                        "documenti": 1,
                        "provvedimenti": 0,
                        "depositi": 1,
                        "esiti": 0,
                    },
                },
                "options": {
                    "importa_dati_pratica": True,
                    "importa_parti": True,
                    "importa_difensori": False,
                    "importa_eventi": False,
                    "importa_udienze": False,
                    "importa_scadenze": False,
                    "importa_documenti": True,
                    "importa_provvedimenti": True,
                    "importa_cronologia_depositi": True,
                    "importa_esiti_telematici": False,
                    "solo_nuovi": True,
                    "aggiorna_pratica_esistente": True,
                    "sovrascrivi_solo_vuoti": True,
                    "non_toccare_note_interne": True,
                    "non_duplicare_documenti": True,
                    "conserva_log_origine_pst": True,
                    "mantieni_albero_originale": False,
                },
                "mapping": {
                    "mode": "attach_existing",
                    "target_fascicolo_id": fascicolo.id,
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "materia": "Civile",
                    "grado": "Primo grado",
                },
                "downloaded_files": [],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is False
    assert "non sono arrivati file reali" in data["errore"]
    assert "solo catalogo o metadati" in data["errore"]

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert len(fascicolo_reload.documenti) == 0
    assert len(fascicolo_reload.depositi_pct) == 0


def test_api_portale_acquisizione_import_pst_prima_pratica_non_crea_vuoto_senza_file(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:63:2025:RG",
                    "numero": "63",
                    "anno": 2025,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Tribunale di Roma",
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "oggetto": "Test prima importazione",
                    "parti": ["ROSSI MARIO"],
                    "controparti": [],
                    "payload": {
                        "numero_rg": "63",
                        "anno_rg": 2025,
                        "ruolo": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "oggetto": "Test prima importazione",
                        "parti": ["ROSSI MARIO"],
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Tribunale di Roma",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "63",
                        "anno": 2025,
                        "ufficio_nome": "Tribunale di Roma",
                        "ufficio_codice": "0580010",
                    },
                    "parti": ["ROSSI MARIO"],
                    "controparti": [],
                    "documenti": [
                        {
                            "id_documento": "DOC-ROMA-63",
                            "nome": "Atto_63_2025.pdf",
                            "tipo": "ATTO PRINCIPALE",
                            "tipo_atto": "Atto",
                            "data_deposito": "2025-01-15",
                            "id_deposito": "BUSTA-ROMA-63",
                            "id_cat": "CAT-ROMA-63",
                        }
                    ],
                    "depositi": [],
                    "counts": {
                        "parti": 1,
                        "documenti": 1,
                        "depositi": 0,
                        "eventi": 0,
                        "udienze": 0,
                    },
                },
                "options": {
                    "importa_dati_pratica": True,
                    "importa_parti": True,
                    "importa_eventi": False,
                    "importa_scadenze": False,
                    "importa_documenti": True,
                    "importa_cronologia_depositi": True,
                    "mantieni_albero_originale": False,
                },
                "mapping": {"mode": "create_new"},
                "downloaded_files": [],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is False
    assert "non sono arrivati file reali" in data["errore"]

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    assert gestione_fascicoli_reload.tutti() == []


def test_api_portale_acquisizione_import_pst_parziale_aggiorna_pratica_esistente(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 274/2026 - Usucapione",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="274",
        anno_rg=2026,
        oggetto="Usucapione",
    )

    preview_documenti = [
        {
            "id_documento": "DOC-DECRETO-35052610",
            "nome": "Decreto_35052610.pdf",
            "tipo": "Decreto",
            "tipo_atto": "Decreto",
            "data_deposito": "2026-05-07",
            "mittente": "RUSCIO EMANUELA",
            "id_deposito": "BUSTA-PST-274",
            "id_cat": "35052610",
        },
        {
            "id_documento": "DOC-ATTO-34341272",
            "nome": "AttoNonCodificato_34341272.pdf",
            "tipo": "AttoNonCodificato",
            "tipo_atto": "AttoNonCodificato",
            "data_deposito": "2026-03-09",
            "mittente": "MONTAGNESE ROBERTO",
            "id_deposito": "BUSTA-PST-274",
            "id_cat": "34341272",
        },
    ]

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:274:2026:RG",
                    "numero": "274",
                    "anno": 2026,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Tribunale di Palmi",
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "stato": "Attesa Esito Udienza Prima Comp. / Trattazione (art. 183)",
                    "oggetto": "Usucapione",
                    "parti": ["MONTAGNESE ROBERTO"],
                    "controparti": [],
                    "payload": {
                        "numero_rg": "274",
                        "anno_rg": 2026,
                        "ruolo": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "Attesa Esito Udienza Prima Comp. / Trattazione (art. 183)",
                        "oggetto": "Usucapione",
                        "data_iscrizione": "2026-03-07",
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Tribunale di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "274",
                        "anno": 2026,
                        "ufficio_nome": "Tribunale di Palmi",
                        "ufficio_codice": "0580010",
                        "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "Attesa Esito Udienza Prima Comp. / Trattazione (art. 183)",
                        "oggetto": "Usucapione",
                        "data_iscrizione": "2026-03-07",
                    },
                    "parti": ["MONTAGNESE ROBERTO"],
                    "controparti": [],
                    "difensori": [],
                    "eventi": [],
                    "documenti": preview_documenti,
                    "depositi": [
                        {
                            "id_deposito": "BUSTA-PST-274",
                            "tipo_atto": "DocumentiFascicolo",
                            "data_deposito": "2026-05-07",
                            "mittente": "PST",
                            "documenti": preview_documenti,
                        }
                    ],
                    "counts": {
                        "parti": 1,
                        "difensori": 0,
                        "eventi": 0,
                        "udienze": 0,
                        "documenti": 2,
                        "provvedimenti": 1,
                        "depositi": 1,
                        "esiti": 0,
                    },
                },
                "options": {
                    "importa_dati_pratica": True,
                    "importa_parti": True,
                    "importa_difensori": False,
                    "importa_eventi": False,
                    "importa_udienze": False,
                    "importa_scadenze": False,
                    "importa_documenti": True,
                    "importa_provvedimenti": True,
                    "importa_cronologia_depositi": True,
                    "importa_esiti_telematici": False,
                    "solo_nuovi": True,
                    "aggiorna_pratica_esistente": True,
                    "sovrascrivi_solo_vuoti": True,
                    "non_toccare_note_interne": True,
                    "non_duplicare_documenti": True,
                    "conserva_log_origine_pst": True,
                    "mantieni_albero_originale": False,
                },
                "mapping": {
                    "mode": "update_existing",
                    "target_fascicolo_id": fascicolo.id,
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "materia": "Civile",
                    "grado": "Primo grado",
                },
                "downloaded_files": [
                    {
                        "nome": "Decreto_35052610.pdf",
                        "contenuto_b64": base64.b64encode(b"%PDF-1.4 decreto").decode("ascii"),
                        "content_type": "application/pdf",
                        "origine": "pst:JPW_SICID:35052610",
                        "data_documento": "2026-05-07",
                        "id_deposito_esterno": "BUSTA-PST-274",
                        "id_documento_portale": "DOC-DECRETO-35052610",
                        "id_cat": "35052610",
                        "tipo_atto": "Decreto",
                        "tipo": "Decreto",
                        "mittente": "RUSCIO EMANUELA",
                    }
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["result"]["created"] is False
    assert data["result"]["summary"]["documenti"] == 1
    assert data["result"]["summary"]["documenti_catalogo"] == 2
    assert data["result"]["summary"]["documenti_da_acquisire"] == 1
    assert data["result"]["summary"]["download_parziale_portale"] is True

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert len(fascicolo_reload.documenti) == 1
    assert len(fascicolo_reload.depositi_pct) == 1
    deposito = fascicolo_reload.depositi_pct[0]
    assert len(deposito.documenti_portale) == 2
    assert len(deposito.documenti_ids) == 1
    assert any(row["id_cat"] == "34341272" for row in deposito.documenti_portale)
    assert fascicolo_reload.documenti[0].id_cat_portale == "35052610"


def test_api_portale_acquisizione_import_pst_arricchisce_file_locali_con_metadati_preview(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:1025:2024:RG",
                    "numero": "1025",
                    "anno": 2024,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Tribunale di Palmi",
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "stato": "PROCEDIMENTO DEFINITO",
                    "oggetto": "Vendita di cose immobili",
                    "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                    "controparti": [],
                    "payload": {
                        "numero_rg": "1025",
                        "anno_rg": 2024,
                        "ruolo": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "PROCEDIMENTO DEFINITO",
                        "oggetto": "Vendita di cose immobili",
                        "sezione": "CIVILE",
                        "data_iscrizione": "2024-09-05",
                        "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Tribunale di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "1025",
                        "anno": 2024,
                        "ufficio_nome": "Tribunale di Palmi",
                        "ufficio_codice": "0580010",
                        "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "PROCEDIMENTO DEFINITO",
                    },
                    "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                    "controparti": [],
                    "difensori": [],
                    "eventi": [],
                    "documenti": [
                        {
                            "id_documento": "DOC-CITAZIONE-1",
                            "nome": "CitazioneStillitanoMontagnese.PDF",
                            "tipo": "ATTO PRINCIPALE",
                            "tipo_atto": "Citazione",
                            "data_deposito": "2024-09-05",
                            "mittente": "avv.montagnese@pec.it",
                            "id_deposito": "BUSTA-PST-001",
                            "id_cat": "CAT-CIT-001",
                        }
                    ],
                    "depositi": [
                        {
                            "id_deposito": "BUSTA-PST-001",
                            "tipo_atto": "Citazione",
                            "data_deposito": "2024-09-05",
                            "mittente": "avv.montagnese@pec.it",
                            "documenti": [
                                {
                                    "id_documento": "DOC-CITAZIONE-1",
                                    "nome": "CitazioneStillitanoMontagnese.PDF",
                                    "tipo": "ATTO PRINCIPALE",
                                    "tipo_atto": "Citazione",
                                    "data_deposito": "2024-09-05",
                                    "mittente": "avv.montagnese@pec.it",
                                    "id_deposito": "BUSTA-PST-001",
                                    "id_cat": "CAT-CIT-001",
                                }
                            ],
                        }
                    ],
                    "counts": {
                        "parti": 2,
                        "difensori": 0,
                        "eventi": 0,
                        "udienze": 0,
                        "documenti": 1,
                        "provvedimenti": 0,
                        "depositi": 1,
                        "esiti": 0,
                    },
                },
                "options": {
                    "importa_dati_pratica": True,
                    "importa_parti": True,
                    "importa_difensori": False,
                    "importa_eventi": False,
                    "importa_udienze": False,
                    "importa_scadenze": False,
                    "importa_documenti": True,
                    "importa_provvedimenti": False,
                    "importa_cronologia_depositi": True,
                    "importa_esiti_telematici": False,
                    "solo_nuovi": True,
                    "aggiorna_pratica_esistente": True,
                    "sovrascrivi_solo_vuoti": True,
                    "non_toccare_note_interne": True,
                    "non_duplicare_documenti": True,
                    "conserva_log_origine_pst": True,
                    "mantieni_albero_originale": False,
                },
                "mapping": {
                    "mode": "attach_existing",
                    "target_fascicolo_id": fascicolo.id,
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "materia": "Civile",
                    "grado": "Primo grado",
                },
                "downloaded_files": [
                    {
                        "filename": "CitazioneStillitanoMontagnese.PDF",
                        "content_base64": base64.b64encode(b"%PDF-1.4 manual upload").decode("ascii"),
                        "content_type": "application/pdf",
                        "source": r"C:\\QuickOrganizer\\ATTI\\CitazioneStillitanoMontagnese.PDF",
                        "data_deposito": "",
                        "id_documento": "DOC-CITAZIONE-1",
                        "id_deposito": "BUSTA-PST-001",
                    }
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["result"]["summary"]["documenti"] == 1

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert len(fascicolo_reload.documenti) == 1
    doc = fascicolo_reload.documenti[0]
    assert doc.nome == "CitazioneStillitanoMontagnese.PDF"
    assert doc.tipo == TipoDocumento.CITAZIONE
    assert doc.data_documento == "2024-09-05"
    assert doc.id_documento_portale == "DOC-CITAZIONE-1"
    assert doc.id_cat_portale == "CAT-CIT-001"
    assert doc.classificazione_portale == "ATTO PRINCIPALE"
    assert "Documenti fascicolo" in doc.tags
    assert "Attivita processuali" not in doc.tags
    assert "Citazione" in doc.tags
    assert "Atto Principale" in doc.tags
    assert "Copia di consultazione" in doc.tags

    with app.test_client() as detail_client:
        detail_client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        detail_response = detail_client.get(f"/fascicoli/{fascicolo.id}?_legacy=1", follow_redirects=True)

    detail_body = detail_response.data.decode("utf-8")
    assert detail_response.status_code == 200
    assert "05/09/2024" in detail_body
    assert "Classificazione: ATTO PRINCIPALE" in detail_body
    assert "Copia di consultazione" in detail_body
    assert "Portale telematico" in detail_body


def test_api_portale_acquisizione_import_pst_salva_lotto_sette_documenti_nel_fascicolo(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )
    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="GdP Palmi R.G. 3173/2025",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Ufficio del Giudice di Pace di Palmi",
        numero_rg="3173",
        anno_rg=2025,
        oggetto="Importazione documenti PST",
    )
    preview_documenti = [
        {
            "id_documento": f"DOC-3173-{index}",
            "nome": nome,
            "tipo": "Atto" if index == 0 else "Documento",
            "tipo_atto": "Atto" if index == 0 else "Documento",
            "data_deposito": "2025-11-07",
            "mittente": "Cancelleria",
            "id_deposito": "BUSTA-3173-2025",
            "id_cat": id_cat,
            "id_repeatto": id_cat,
        }
        for index, (nome, id_cat) in enumerate(
            [
                ("Atto_2767510.pdf", "2767510"),
                ("Verbale_2767511.pdf", "2767511"),
                ("Comunicazione_2767512.pdf", "2767512"),
                ("Nota_2767513.pdf", "2767513"),
                ("Allegato_2767514.pdf", "2767514"),
                ("Provvedimento_2767515.pdf", "2767515"),
                ("Ricevuta_2767516.pdf", "2767516"),
            ]
        )
    ]
    downloaded_files = [
        {
            "filename": row["nome"],
            "content_base64": base64.b64encode(f"%PDF-1.4 {row['nome']}".encode("ascii")).decode("ascii"),
            "content_type": "application/pdf",
            "source": f"pst:JPW_SIGP:{row['id_cat']}",
            "data_deposito": row["data_deposito"],
            "id_documento": row["id_documento"],
            "id_deposito": row["id_deposito"],
            "id_cat": row["id_cat"],
            "id_repeatto": row["id_repeatto"],
            "tipo_atto": row["tipo_atto"],
        }
        for row in preview_documenti
    ]

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/import",
            json={
                "selection": {
                    "external_id": "SIGP:3173:2025",
                    "numero": "3173",
                    "anno": 2025,
                    "ufficio_codice": "0800570152",
                    "ufficio_nome": "Ufficio del Giudice di Pace di Palmi",
                    "procedimento": "GDP",
                    "oggetto": "Importazione documenti PST",
                    "parti": [],
                    "controparti": [],
                    "payload": {
                        "numero_rg": "3173",
                        "anno_rg": 2025,
                        "ruolo": "GDP",
                        "oggetto": "Importazione documenti PST",
                        "codice_ufficio": "0800570152",
                        "nome_ufficio": "Ufficio del Giudice di Pace di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "3173",
                        "anno": 2025,
                        "ufficio_nome": "Ufficio del Giudice di Pace di Palmi",
                        "ufficio_codice": "0800570152",
                        "procedimento": "GDP",
                    },
                    "parti": [],
                    "controparti": [],
                    "documenti": preview_documenti,
                    "depositi": [
                        {
                            "id_deposito": "BUSTA-3173-2025",
                            "tipo_atto": "Documenti fascicolo",
                            "data_deposito": "2025-11-07",
                            "mittente": "Cancelleria",
                            "documenti": preview_documenti,
                        }
                    ],
                    "counts": {
                        "parti": 0,
                        "documenti": 7,
                        "depositi": 1,
                        "eventi": 0,
                        "udienze": 0,
                    },
                },
                "options": {
                    "importa_dati_pratica": True,
                    "importa_parti": True,
                    "importa_eventi": False,
                    "importa_scadenze": False,
                    "importa_documenti": True,
                    "importa_cronologia_depositi": True,
                    "mantieni_albero_originale": False,
                },
                "mapping": {"mode": "update_existing", "target_fascicolo_id": fascicolo.id},
                "downloaded_files": downloaded_files,
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["result"]["summary"]["documenti"] == 7
    assert data["result"]["summary"]["documenti_da_acquisire"] == 0

    fascicolo_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    ).get(fascicolo.id)
    assert fascicolo_reload is not None
    nomi = {doc.nome for doc in fascicolo_reload.documenti}
    assert "Atto_2767510.pdf" in nomi
    assert len(nomi) == 7
    assert {doc.id_cat_portale for doc in fascicolo_reload.documenti} >= {"2767510", "2767516"}
    assert len(fascicolo_reload.depositi_pct) == 1
    assert len(fascicolo_reload.depositi_pct[0].documenti_ids) == 7


def test_api_portale_acquisizione_import_pst_salva_lotto_otto_documenti_con_alias_local_signer(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )
    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="Divorzio consensuale R.G. 1025/2026",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2026,
        oggetto="Divorzio",
    )
    nomi = [
        "RicorsoDivorzio_243923088.pdf",
        "Procura_243923089.pdf",
        "EstrattoMatrimonio_243923090.pdf",
        "StatoFamiglia_243923091.pdf",
        "CertificatoResidenza_243923092.pdf",
        "DichiarazioneRedditi_243923093.pdf",
        "DocumentoIdentita_243923094.pdf",
        "RicevutaContributo_243923095.pdf",
    ]
    preview_documenti = [
        {
            "id_documento": f"DOC-DIV-{index}",
            "nome": nome,
            "tipo": "Ricorso" if index == 1 else "Documento",
            "tipo_atto": "Ricorso" if index == 1 else "Documento",
            "data_deposito": "2026-05-20",
            "mittente": "Local Signer",
            "id_deposito": "BUSTA-DIV-1025",
            "id_cat": f"CAT-DIV-{index}",
            "id_repeatto": f"REP-DIV-{index}",
        }
        for index, nome in enumerate(nomi, start=1)
    ]
    downloaded_files = [
        {
            "nome_file": row["nome"],
            "contenuto_base64": base64.b64encode(f"%PDF-1.4 {row['nome']}".encode("ascii")).decode("ascii"),
            "content_type": "application/pdf",
            "source": f"pst:JPW_SICID:{row['id_cat']}",
            "data_deposito": row["data_deposito"],
            "idDocumento": row["id_documento"],
            "idDeposito": row["id_deposito"],
            "idCat": row["id_cat"],
            "idRepeatTo": row["id_repeatto"],
            "tipo_atto": row["tipo_atto"],
        }
        for row in preview_documenti
    ]

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:1025:2026:RG",
                    "numero": "1025",
                    "anno": 2026,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Tribunale di Palmi",
                    "procedimento": "CC",
                    "oggetto": "Divorzio",
                    "parti": ["ROSSI MARIA"],
                    "controparti": ["BIANCHI LUCA"],
                    "payload": {
                        "numero_rg": "1025",
                        "anno_rg": 2026,
                        "ruolo": "CC",
                        "oggetto": "Divorzio",
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Tribunale di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "1025",
                        "anno": 2026,
                        "ufficio_nome": "Tribunale di Palmi",
                        "ufficio_codice": "0580010",
                        "procedimento": "CC",
                    },
                    "parti": ["ROSSI MARIA"],
                    "controparti": ["BIANCHI LUCA"],
                    "documenti": preview_documenti,
                    "depositi": [
                        {
                            "id_deposito": "BUSTA-DIV-1025",
                            "tipo_atto": "Documenti fascicolo",
                            "data_deposito": "2026-05-20",
                            "mittente": "Local Signer",
                            "documenti": preview_documenti,
                        }
                    ],
                    "counts": {"parti": 1, "documenti": 8, "depositi": 1, "eventi": 0, "udienze": 0},
                },
                "options": {
                    "importa_dati_pratica": True,
                    "importa_parti": True,
                    "importa_eventi": False,
                    "importa_scadenze": False,
                    "importa_documenti": True,
                    "importa_cronologia_depositi": True,
                    "mantieni_albero_originale": False,
                },
                "mapping": {"mode": "update_existing", "target_fascicolo_id": fascicolo.id},
                "downloaded_files": downloaded_files,
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    summary = data["result"]["summary"]
    assert summary["documenti"] == 8
    assert summary["documenti_reali"] == 8
    assert summary["documenti_da_acquisire"] == 0
    assert summary["report_documentale"]["documenti_senza_contenuto"] == 0

    fascicolo_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    ).get(fascicolo.id)
    assert fascicolo_reload is not None
    assert len(fascicolo_reload.documenti) == 8
    assert "RicorsoDivorzio_243923088.pdf" in {doc.nome for doc in fascicolo_reload.documenti}

    import_rows = json.loads((tmp_path / "portale" / "import_log.json").read_text(encoding="utf-8"))
    row = next(item for item in import_rows if item["id"] == data["result"]["import_log_id"])
    assert "Importazione PST avviata" in row["audit_studio"]
    assert any("Documento reale riconosciuto" in item for item in row["audit_studio"])
    assert "Importazione completata" in row["audit_studio"]


def test_api_portale_acquisizione_import_pst_blocca_file_senza_contenuto_con_report(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )
    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:1025:2026:RG",
                    "numero": "1025",
                    "anno": 2026,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Tribunale di Palmi",
                    "procedimento": "CC",
                    "oggetto": "Divorzio",
                    "parti": ["ROSSI MARIA"],
                    "controparti": [],
                    "payload": {"numero_rg": "1025", "anno_rg": 2026, "ruolo": "CC"},
                },
                "preview": {
                    "identity": {"numero": "1025", "anno": 2026, "ufficio_nome": "Tribunale di Palmi"},
                    "documenti": [
                        {
                            "id_documento": "DOC-DIV-1",
                            "nome": "RicorsoDivorzio_243923088.pdf",
                            "tipo": "Ricorso",
                            "tipo_atto": "Ricorso",
                            "data_deposito": "2026-05-20",
                            "id_deposito": "BUSTA-DIV-1025",
                            "id_cat": "CAT-DIV-1",
                        }
                    ],
                    "depositi": [],
                    "counts": {"documenti": 1, "depositi": 0, "eventi": 0, "udienze": 0},
                },
                "options": {
                    "importa_dati_pratica": True,
                    "importa_parti": False,
                    "importa_eventi": False,
                    "importa_scadenze": False,
                    "importa_documenti": True,
                },
                "mapping": {"mode": "create_new"},
                "downloaded_files": [{"nome_file": "RicorsoDivorzio_243923088.pdf", "contenuto_base64": ""}],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is False
    assert "documenti reali presenti 0" in data["errore"]
    assert "senza contenuto 1" in data["errore"]
    assert "RicorsoDivorzio_243923088.pdf" in data["errore"]


def test_api_portale_acquisizione_preview_pst_usa_fallback_payload_e_id_fascicolo(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/preview",
            json={
                "selection": {
                    "external_id": "0580010:1025:2024:",
                    "id_fascicolo": "FASC-1025",
                    "numero": "1025",
                    "anno": 2024,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Tribunale di Palmi",
                    "procedimento": "",
                    "sub_procedimento": "CONTENZIOSO",
                    "sezione": "",
                    "stato": "",
                    "oggetto": "",
                    "parti": ["MONTAGNESE ELISABETTA"],
                    "controparti": ["STILLITANO FRANCESCO"],
                    "ultima_attivita": "",
                    "payload": {
                        "id_fascicolo": "FASC-1025",
                        "numero_rg": "1025",
                        "anno_rg": 2024,
                        "ruolo": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "sub_procedimento": "CONTENZIOSO",
                        "stato": "PROCEDIMENTO DEFINITO",
                        "oggetto": "Vendita di cose immobili",
                        "sezione": "CIVILE",
                        "data_iscrizione": "2024-09-05",
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Tribunale di Palmi",
                    },
                },
                "documenti": [
                    {
                        "id_documento": "DOC-1",
                        "nome": "Documento_33584995.pdf",
                        "tipo": "DOCUMENTO",
                        "tipo_atto": "Documento",
                        "data_deposito": "2026-01-09 09:39:19.000",
                        "mittente": "cancelleria@tribunale.giustiziapec.it",
                        "id_deposito": "BUSTA-PST-001",
                        "id_cat": "CAT-001",
                    }
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    identity = data["preview"]["identity"]
    assert identity["id_fascicolo"] == "FASC-1025"
    assert identity["procedimento"] == "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI"
    assert identity["sub_procedimento"] == "CONTENZIOSO"
    assert identity["stato"] == "PROCEDIMENTO DEFINITO"
    assert identity["oggetto"] == "Vendita di cose immobili"
    assert identity["data_iscrizione"] == "2024-09-05"
    assert identity["ultima_attivita"] == "2026-01-09 09:39:19.000"


def test_api_portale_acquisizione_preview_pst_preserva_iscrizione_da_snapshot(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/preview",
            json={
                "selection": {
                    "external_id": "0580910:63:2025:RG",
                    "numero": "63",
                    "anno": 2025,
                    "ufficio_codice": "0580910",
                    "ufficio_nome": "Tribunale di Roma",
                    "procedimento": "",
                    "payload": {
                        "numero_rg": "63",
                        "anno_rg": 2025,
                        "ruolo": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    },
                    "snapshot": {
                        "fascicolo": {
                            "data_iscrizione": "2025-01-14",
                            "data_udienza": "2025-06-20",
                            "stato": "In trattazione",
                            "oggetto": "Responsabilita contrattuale",
                        }
                    },
                },
                "documenti": [
                    {
                        "id_documento": "DOC-ROMA-63-1",
                        "nome": "Atto_roma_63.pdf",
                        "tipo_atto": "Atto",
                        "data_deposito": "2025-01-15",
                        "id_deposito": "DEP-ROMA-63",
                        "id_cat": "ROMA63",
                    }
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    identity = data["preview"]["identity"]
    assert identity["numero"] == "63"
    assert identity["anno"] == 2025
    assert identity["ufficio_nome"] == "Tribunale di Roma"
    assert identity["data_iscrizione"] == "2025-01-14"
    assert identity["data_udienza"] == "2025-06-20"
    assert identity["stato"] == "In trattazione"
    assert identity["oggetto"] == "Responsabilita contrattuale"


def test_api_portale_acquisizione_import_pst_filtra_i_file_secondo_step4(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    gestione_fascicoli = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo = gestione_fascicoli.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )

    app = create_app(cfg)
    with app.test_client() as client:
        client.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=True,
        )
        response = client.post(
            "/api/portali/pst/acquisizione/import",
            json={
                "selection": {
                    "external_id": "0580010:1025:2024:RG",
                    "numero": "1025",
                    "anno": 2024,
                    "ufficio_codice": "0580010",
                    "ufficio_nome": "Tribunale di Palmi",
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "stato": "PROCEDIMENTO DEFINITO",
                    "oggetto": "Vendita di cose immobili",
                    "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                    "controparti": [],
                    "payload": {
                        "numero_rg": "1025",
                        "anno_rg": 2024,
                        "ruolo": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "PROCEDIMENTO DEFINITO",
                        "oggetto": "Vendita di cose immobili",
                        "sezione": "CIVILE",
                        "data_iscrizione": "2024-09-05",
                        "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                        "codice_ufficio": "0580010",
                        "nome_ufficio": "Tribunale di Palmi",
                    },
                },
                "preview": {
                    "identity": {
                        "numero": "1025",
                        "anno": 2024,
                        "ufficio_nome": "Tribunale di Palmi",
                        "ufficio_codice": "0580010",
                        "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                        "stato": "PROCEDIMENTO DEFINITO",
                    },
                    "parti": ["MONTAGNESE ELISABETTA", "STILLITANO FRANCESCO"],
                    "controparti": [],
                    "difensori": [],
                    "eventi": [],
                    "documenti": [
                        {
                            "id_documento": "DOC-DECRETO-1",
                            "nome": "Decreto_29033905.pdf.p7m",
                            "tipo": "DECRETO",
                            "tipo_atto": "Decreto",
                            "data_deposito": "2025-01-21",
                            "mittente": "cancelleria@tribunale.giustiziapec.it",
                            "id_deposito": "BUSTA-PST-001",
                            "id_cat": "CAT-001",
                        },
                        {
                            "id_documento": "DOC-ALLEGATO-1",
                            "nome": "Documento_33584995.pdf.p7m",
                            "tipo": "DOCUMENTO",
                            "tipo_atto": "Documento",
                            "data_deposito": "2025-01-21",
                            "mittente": "cancelleria@tribunale.giustiziapec.it",
                            "id_deposito": "BUSTA-PST-001",
                            "id_cat": "CAT-002",
                        },
                    ],
                    "depositi": [
                        {
                            "id_deposito": "BUSTA-PST-001",
                            "tipo_atto": "Decreto",
                            "data_deposito": "2025-01-21",
                            "mittente": "cancelleria@tribunale.giustiziapec.it",
                            "documenti": [
                                {
                                    "id_documento": "DOC-DECRETO-1",
                                    "nome": "Decreto_29033905.pdf.p7m",
                                    "tipo": "DECRETO",
                                    "tipo_atto": "Decreto",
                                    "data_deposito": "2025-01-21",
                                    "mittente": "cancelleria@tribunale.giustiziapec.it",
                                    "id_deposito": "BUSTA-PST-001",
                                    "id_cat": "CAT-001",
                                },
                                {
                                    "id_documento": "DOC-ALLEGATO-1",
                                    "nome": "Documento_33584995.pdf.p7m",
                                    "tipo": "DOCUMENTO",
                                    "tipo_atto": "Documento",
                                    "data_deposito": "2025-01-21",
                                    "mittente": "cancelleria@tribunale.giustiziapec.it",
                                    "id_deposito": "BUSTA-PST-001",
                                    "id_cat": "CAT-002",
                                },
                            ],
                        }
                    ],
                    "counts": {
                        "parti": 2,
                        "difensori": 0,
                        "eventi": 0,
                        "udienze": 0,
                        "documenti": 2,
                        "provvedimenti": 1,
                        "depositi": 1,
                        "esiti": 0,
                    },
                },
                "options": {
                    "importa_dati_pratica": True,
                    "importa_parti": True,
                    "importa_difensori": False,
                    "importa_eventi": False,
                    "importa_udienze": False,
                    "importa_scadenze": False,
                    "importa_documenti": False,
                    "importa_provvedimenti": True,
                    "importa_cronologia_depositi": True,
                    "importa_esiti_telematici": False,
                    "solo_nuovi": True,
                    "aggiorna_pratica_esistente": True,
                    "sovrascrivi_solo_vuoti": True,
                    "non_toccare_note_interne": True,
                    "non_duplicare_documenti": True,
                    "conserva_log_origine_pst": True,
                    "mantieni_albero_originale": False,
                },
                "mapping": {
                    "mode": "attach_existing",
                    "target_fascicolo_id": fascicolo.id,
                    "procedimento": "GENERALE DEGLI AFFARI CIVILI CONTENZIOSI",
                    "materia": "Civile",
                    "grado": "Primo grado",
                },
                "downloaded_files": [
                    {
                        "nome": "Decreto_29033905.pdf.p7m",
                        "contenuto_b64": base64.b64encode(b"fake-signed-decreto").decode("ascii"),
                        "content_type": "application/pkcs7-mime",
                        "data_documento": "2025-01-21",
                        "origine": "pst:JPW_SICID:DOC-DECRETO-1",
                        "id_deposito_esterno": "BUSTA-PST-001",
                        "id_documento_portale": "DOC-DECRETO-1",
                        "tipo_atto": "Decreto",
                        "tipo": "DECRETO",
                        "id_cat": "CAT-001",
                    },
                    {
                        "nome": "Documento_33584995.pdf.p7m",
                        "contenuto_b64": base64.b64encode(b"fake-signed-documento").decode("ascii"),
                        "content_type": "application/pkcs7-mime",
                        "data_documento": "2025-01-21",
                        "origine": "pst:JPW_SICID:DOC-ALLEGATO-1",
                        "id_deposito_esterno": "BUSTA-PST-001",
                        "id_documento_portale": "DOC-ALLEGATO-1",
                        "tipo_atto": "Documento",
                        "tipo": "DOCUMENTO",
                        "id_cat": "CAT-002",
                    },
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert data["result"]["summary"]["documenti"] == 1

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.stato == StatoFascicolo.DEFINITO
    assert len(fascicolo_reload.documenti) == 1
    assert fascicolo_reload.documenti[0].nome == "Decreto_29033905.pdf.p7m"
    assert fascicolo_reload.documenti[0].tipo == TipoDocumento.DECRETO
    albero_root = Path(cfg["PST_IMPORT_DIR"]) / "_alberi_originali" / fascicolo.id
    assert not albero_root.exists()


def test_api_pec_poll_cancelleria_legge_la_config_pec_da_studio_config(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    cfg["STUDIO_CONFIG"] = str(studio_cfg)
    gu = GestioneUtenti(
        db_path=cfg["AUTH_DB"],
        audit_path=cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="adminpec",
        password="Admin1234!",
        ruolo=RuoloUtente.AMMINISTRATORE,
        email="adminpec@example.com",
        must_change_password=False,
    )

    gf = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    gf.nuovo(
        titolo="RG 1025/2024",
        tipo=TipoFascicolo.CIVILE,
        tribunale="Tribunale di Palmi",
        numero_rg="1025",
        anno_rg=2024,
        oggetto="Vendita di cose immobili",
    )

    gs = GestioneConfigStudio(str(studio_cfg))
    config = gs.config
    config.pec = ConfigPEC(
        indirizzo="studio@example.pec.it",
        password="segreta",
        smtp_host="smtp.pec.aruba.it",
        smtp_port=465,
        imap_host="imaps.pec.aruba.it",
        imap_port=993,
        use_ssl=True,
    )
    gs.aggiorna(config)

    osservato = {}

    def _fake_sincronizza_pec_e_fascicoli(
        *,
        gestione_email,
        gestione_fascicoli,
        config_pec,
        state_path,
        limite=100,
    ):
        osservato["indirizzo"] = config_pec.indirizzo
        osservato["imap_host"] = config_pec.imap_host
        osservato["state_path"] = state_path
        osservato["limite"] = limite
        osservato["documents_dir"] = str(gestione_fascicoli.documents_dir)
        osservato["archive_dir"] = str(gestione_fascicoli.archive_dir)
        return {
            "sync": {"errore": ""},
            "auto_esiti": [],
            "poll": {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0},
        }

    monkeypatch.setattr("pct.email_client.sincronizza_pec_e_fascicoli", _fake_sincronizza_pec_e_fascicoli)

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "adminpec", "password": "Admin1234!"},
            follow_redirects=True,
        )
        assert login.status_code == 200

        response = client.post(
            "/api/pec/poll-cancelleria",
            json={},
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    assert osservato["indirizzo"] == "studio@example.pec.it"
    assert osservato["imap_host"] == "imaps.pec.aruba.it"
    assert osservato["state_path"].endswith("pec_cancelleria_state.json")
    assert osservato["limite"] == 100
    assert osservato["documents_dir"] == cfg["FASCICOLI_DOCS"]
    assert osservato["archive_dir"] == cfg["FASCICOLI_ARCH"]
