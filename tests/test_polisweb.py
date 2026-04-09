from __future__ import annotations

import base64
import io
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pct.clienti import GestioneClienti
from pct.fascicoli import GestioneFascicoli, StatoFascicolo, TipoDocumento, TipoFascicolo
from pct.config_studio import ConfigPEC, GestioneConfigStudio
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


def _cfg_web(tmp_path: Path) -> dict:
    os.makedirs(str(tmp_path / "backup"), exist_ok=True)
    return {
        "TESTING": True,
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
    }


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
    assert any(att.tipo.value == "CONSULTAZIONE" for att in fascicolo_reload.attivita)


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
    assert len(fascicolo_reload.attivita) == 1
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
    assert len(fascicolo_reload.attivita) == 1


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


def test_route_documenti_pat_raggruppa_buste_e_fallback_senza_id(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    from pct.pat import DocumentoPAT
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

    class _FakePATClient:
        def consulta_documenti(self, codice_ufficio, numero_ricorso, anno):
            return [
                DocumentoPAT(
                    "PAT-001",
                    "ricorso_principale.pdf.p7m",
                    "RICORSO",
                    "2026-02-28",
                    "avv.demo@pec.it",
                    312000,
                    True,
                    "",
                    "Ricorso principale",
                ),
                DocumentoPAT(
                    "PAT-002",
                    "allegato_ricorso.pdf.p7m",
                    "ALLEGATO",
                    "2026-02-28",
                    "avv.demo@pec.it",
                    88000,
                    True,
                    "",
                    "Ricorso principale",
                ),
                DocumentoPAT(
                    "PAT-003",
                    "ordinanza_cautelare.pdf.p7m",
                    "ORDINANZA",
                    "2026-03-10",
                    "tar.demo@giustizia-amministrativa.it",
                    48000,
                    True,
                    "BUSTA-PAT-003",
                    "Ordinanza cautelare",
                ),
            ]

    monkeypatch.setattr("pct.pat.crea_client_pat", lambda demo=False: _FakePATClient())

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
    assert "Espandi tutto" in body
    assert "Riduci" in body
    assert 'data-bs-parent="#accordionDepositi"' not in body
    assert "2 atti" in body
    assert "3 file totali" in body
    assert "ricorso_principale.pdf.p7m" in body
    assert "allegato_ricorso.pdf.p7m" in body
    assert "ordinanza_cautelare.pdf.p7m" in body
    assert "BUSTA-PAT-003" in body


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
        response = client.get(f"/fascicoli/{fascicolo.id}")

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
        response = client.get(f"/fascicoli/{fascicolo.id}", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Naviga fascicolo PST" in body
    assert "Scarica + importa selezionati" in body
    assert "Acquisisci intero fascicolo" in body
    assert "Conserva anche l'albero tecnico originale del portale" in body
    assert "Acquisisci fascicolo" in body
    assert "_PST_NAV_ITEMS" in body
    assert "/pst/download-documenti-batch" in body


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
        response = client.get(f"/fascicoli/{fascicolo.id}", follow_redirects=True)

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
        response = client.get("/fascicoli", follow_redirects=True)

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
        response = client.get(f"/fascicoli/{fascicolo.id}", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "documenti ufficiali" in body
    assert "Documenti fascicolo" in body
    assert "nella sezione <strong>Comunicazioni di cancelleria</strong>" not in body
    assert "Nessuna comunicazione di cancelleria" in body


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
            follow_redirects=True,
        )

    assert response.status_code == 200
    assert "Nessun certificato configurato per l'accesso al PST" not in response.data.decode("utf-8")

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
        response = client.get(f"/fascicoli/{fascicolo.id}")

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "memoria_conclusionale.pdf.p7m" in body
    assert "documenti ufficiali" in body
    assert "Nessuna comunicazione di cancelleria" in body


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
        response = client.get(f"/fascicoli/{fascicolo.id}", follow_redirects=True)

    body = response.data.decode("utf-8")
    assert response.status_code == 200
    assert "Acquisito nel fascicolo" in body
    assert f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/scarica" in body
    assert f"/fascicoli/{fascicolo.id}/documenti/{doc.id}/visualizza" in body


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
        "atto.pdf.p7m",
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
    assert response.data.startswith(b"%PDF-1.4")


def test_route_home_sigit_mostra_selettore_cpt_cgt(tmp_path):
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
    assert "Ufficio giudiziario tributario" in body
    assert 'data-tipo="CPT"' in body
    assert 'data-tipo="CGT"' in body
    assert 'id="commissione-value"' in body
    assert "/api/uffici?q=" in body


def test_route_documenti_sigit_raggruppa_buste_e_risolve_nome_commissione(tmp_path, monkeypatch):
    from pct.auth import GestioneUtenti, RuoloUtente
    from pct.sigit import DocumentoSIGIT
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

    class _FakeSIGITClient:
        def consulta_documenti(self, codice_commissione, numero_rgt, anno_rgt):
            return [
                DocumentoSIGIT(
                    "SIGIT-001",
                    "ricorso_introduttivo.pdf.p7m",
                    "RICORSO",
                    "2026-02-18",
                    "avv.demo@pec.it",
                    210000,
                    True,
                    "",
                    "Ricorso tributario",
                ),
                DocumentoSIGIT(
                    "SIGIT-002",
                    "allegato_fatture.pdf.p7m",
                    "ALLEGATO",
                    "2026-02-18",
                    "avv.demo@pec.it",
                    83000,
                    True,
                    "",
                    "Ricorso tributario",
                ),
                DocumentoSIGIT(
                    "SIGIT-003",
                    "sentenza_primo_grado.pdf",
                    "SENTENZA",
                    "2026-05-04",
                    "segreteria.tributaria@pec.mef.gov.it",
                    54000,
                    True,
                    "BUSTA-SIGIT-003",
                    "Sentenza",
                ),
            ]

    monkeypatch.setattr("pct.sigit.crea_client_sigit", lambda demo=False: _FakeSIGITClient())

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
    assert "Espandi tutto" in body
    assert "Riduci" in body
    assert 'data-bs-parent="#accordionDepositi"' not in body
    assert "2 atti" in body
    assert "3 file totali" in body
    assert "ricorso_introduttivo.pdf.p7m" in body
    assert "allegato_fatture.pdf.p7m" in body
    assert "sentenza_primo_grado.pdf" in body
    assert "BUSTA-SIGIT-003" in body
    assert "CPT Milano" in body


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
            ("/polisWeb", "/portali/pst/acquisizione"),
            ("/pdp", "/portali/pdp/acquisizione"),
            ("/pat", "/portali/pat/acquisizione"),
            ("/sigit", "/portali/ptt/acquisizione"),
        ]
        for route, expected in checks:
            response = client.get(route, follow_redirects=True)
            body = response.data.decode("utf-8")
            assert response.status_code == 200
            assert expected in body


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

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert fascicolo_reload.stato == StatoFascicolo.DEFINITO
    assert len(fascicolo_reload.documenti) == 1
    assert len(fascicolo_reload.depositi_pct) == 1
    doc = fascicolo_reload.documenti[0]
    assert doc.nome.endswith(".p7m")
    assert doc.firmato is True
    assert doc.tipo == TipoDocumento.VERBALE
    assert fascicolo_reload.depositi_pct[0].documenti_ids == [doc.id]

    albero_root = Path(cfg["PST_IMPORT_DIR"]) / "_alberi_originali" / fascicolo.id
    assert albero_root.exists()
    assert any(path.is_file() for path in albero_root.rglob("*"))


def test_api_portale_acquisizione_import_pst_blocca_import_se_i_file_non_arrivano(tmp_path):
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
    assert "wizard non ha ricevuto alcun file" in data["errore"]

    gestione_fascicoli_reload = GestioneFascicoli(
        db_path=cfg["FASCICOLI_DB"],
        documents_dir=cfg["FASCICOLI_DOCS"],
        archive_dir=cfg["FASCICOLI_ARCH"],
    )
    fascicolo_reload = gestione_fascicoli_reload.get(fascicolo.id)
    assert fascicolo_reload is not None
    assert len(fascicolo_reload.documenti) == 0
    assert len(fascicolo_reload.depositi_pct) == 0


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
    from web.app import create_app

    cfg = _cfg_web(tmp_path)
    studio_cfg = tmp_path / "config" / "studio.json"
    cfg["STUDIO_CONFIG"] = str(studio_cfg)

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

    def _fake_poll_cancelleria_pec(gf, config_pec, state_path):
        osservato["indirizzo"] = config_pec.indirizzo
        osservato["imap_host"] = config_pec.imap_host
        osservato["state_path"] = state_path
        return {"trovati": 0, "associati": 0, "duplicati": 0, "errori": 0}

    monkeypatch.setattr("pct.polling_depositi.poll_cancelleria_pec", _fake_poll_cancelleria_pec)

    app = create_app(cfg)
    with app.test_client() as client:
        login = client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
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
