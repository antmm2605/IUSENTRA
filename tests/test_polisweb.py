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
from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
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
    assert "Scarica dal portale ufficiale" in body
    assert "/pst/download-documento" in body


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
    assert "RG ufficiale" in body
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
