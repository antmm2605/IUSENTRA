from __future__ import annotations

import base64
import io
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace


def _load_local_signer():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "local_signer.py"
    spec = importlib.util.spec_from_file_location("hacs_local_signer", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _local_signer_version():
    return _load_local_signer().VERSION


def test_rileva_endpoint_pst_legacy():
    module = _load_local_signer()

    assert module._pst_endpoint_configurato_e_legacy("https://wspa.giustizia.it/wspa")
    assert not module._pst_endpoint_configurato_e_legacy("https://pda.processotelematico.giustizia.it")
    assert not module._pst_endpoint_configurato_e_legacy("https://ext.processotelematico.giustizia.it")


def test_errore_dns_endpoint_legacy_e_istruttivo():
    module = _load_local_signer()

    msg = module._curl_errore_leggibile(
        6,
        "",
        "https://wspa.giustizia.it/wspa/RicercaFascicoliRegistroService",
    )

    assert "wspa.giustizia.it" in msg
    assert "pda.processotelematico.giustizia.it" in msg
    assert "ext.processotelematico.giustizia.it" in msg
    assert "PCT_PST_BASE_URL" in msg


def test_format_cert_not_valid_after_supporta_api_utc():
    module = _load_local_signer()

    class DummyCert:
        not_valid_after_utc = __import__("datetime").datetime(2026, 5, 10, 12, 0, 0)
        not_valid_after = __import__("datetime").datetime(2024, 1, 1, 0, 0, 0)

    assert module._format_cert_not_valid_after(DummyCert()) == "2026-05-10"


def test_local_signer_risolve_proxy_pst_dal_codice_hacs():
    module = _load_local_signer()

    base = module._risolvi_base_pst_runtime("0580010")
    url = module._pst_url_ricerca(base)

    assert base.endswith("/pda/pycons/GLMI/JPW_SICID")
    assert url == base
    assert module._risolvi_codice_ufficio_pst("0580010") == "0151460094"


def test_local_signer_risolve_proxy_pst_da_snapshot_quando_pct_non_e_disponibile():
    module = _load_local_signer()

    orig_base = module._risolvi_base_pst_hacs
    orig_code = module._risolvi_codice_ministero_hacs
    orig_cache = module._uffici_snapshot_cache
    try:
        module._risolvi_base_pst_hacs = None
        module._risolvi_codice_ministero_hacs = None
        module._uffici_snapshot_cache = None

        base = module._risolvi_base_pst_runtime("0910011")

        assert base.endswith("/pda/pycons/GLRC/JPW_SICID")
        assert module._risolvi_codice_ufficio_pst("0910011") == "0800570094"
        assert not module._pst_endpoint_configurato_e_legacy()
        assert module._pst_base_diagnostico().startswith("AUTO")
    finally:
        module._risolvi_base_pst_hacs = orig_base
        module._risolvi_codice_ministero_hacs = orig_code
        module._uffici_snapshot_cache = orig_cache


def test_thumbprint_windows_viene_formattato_per_schannel():
    module = _load_local_signer()

    assert module._format_windows_cert_spec("AA BB CC 11") == r"CurrentUser\MY\AABBCC11"
    assert module._format_windows_cert_spec(r"CurrentUser\MY\ABCDEF") == r"CurrentUser\MY\ABCDEF"


def test_http_401_pst_diventa_messaggio_operativo():
    module = _load_local_signer()

    msg = module._http_errore_leggibile(
        401,
        "<html><title>401 Unauthorized</title></html>",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
        "text/html; charset=iso-8859-1",
    )

    assert "401 Unauthorized" in msg
    assert "certificato" in msg.lower()
    assert "PIN" in msg
    assert "Content-Type risposta" in msg


def test_richiede_certificato_pst_se_nessuno_e_stato_selezionato():
    module = _load_local_signer()

    if module.sys.platform != "win32":
        return

    module._ultimo_certificato_windows = None

    try:
        module._require_certificato_pst(None)
    except RuntimeError as exc:
        msg = str(exc)
    else:
        raise AssertionError("Atteso RuntimeError quando manca il certificato PST")

    assert "Seleziona certificato" in msg
    assert "Cerca su PST" in msg
    assert "PIN" in msg


def test_preflight_auth_accetta_http_405_come_handshake_valido():
    module = _load_local_signer()

    orig_run = module.subprocess.run
    try:
        def _fake_run(cmd, capture_output, text, timeout, encoding, errors):
            header_file = cmd[cmd.index("--dump-header") + 1]
            body_file = cmd[cmd.index("-o") + 1]
            Path(header_file).write_text(
                "HTTP/1.1 405 Method Not Allowed\r\n"
                "Content-Type: text/html; charset=iso-8859-1\r\n\r\n",
                encoding="utf-8",
            )
            Path(body_file).write_text("<html>405</html>", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        module.subprocess.run = _fake_run
        esito = module._pst_preflight_auth_curl(
            "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            cert_thumbprint="AABBCC11",
        )
    finally:
        module.subprocess.run = orig_run

    assert esito["ok"] is True
    assert esito["http_code"] == 405


def test_preflight_auth_timeout_non_blocca_la_ricerca_reale():
    module = _load_local_signer()

    orig_run = module.subprocess.run
    try:
        def _fake_run(cmd, capture_output, text, timeout, encoding, errors):
            return SimpleNamespace(returncode=28, stdout="", stderr="operation timed out")

        module.subprocess.run = _fake_run
        esito = module._pst_preflight_auth_curl(
            "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            cert_thumbprint="AABBCC11",
        )
    finally:
        module.subprocess.run = orig_run

    assert esito["ok"] is True
    assert "non blocca la ricerca reale" in esito["warning"].lower()


def test_messaggio_timeout_usa_il_timeout_reale_della_ricerca():
    module = _load_local_signer()

    msg = module._curl_errore_leggibile(
        28,
        "",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
        timeout_sec=90,
    )

    assert "90s" in msg
    assert "ext.processotelematico.giustizia.it" in msg


def test_server_locale_usa_threading_e_connessioni_close():
    module = _load_local_signer()

    assert issubclass(module._ThreadingLocalSignerServer, module.ThreadingHTTPServer)
    assert module._Handler.protocol_version == "HTTP/1.0"


def test_cors_consentito_per_loopback_locale():
    module = _load_local_signer()

    assert module._origin_cors_consentita("http://localhost:8080")
    assert module._origin_cors_consentita("https://127.0.0.1:27272")
    assert module._origin_cors_consentita("http://[::1]:5000")


def test_cors_consentito_per_origine_hacs_configurata():
    module = _load_local_signer()

    orig = module.LOCAL_SIGNER_ALLOWED_ORIGINS
    try:
        module.LOCAL_SIGNER_ALLOWED_ORIGINS = (
            "https://studio-legale-pct-production.up.railway.app, "
            "https://antmm2605-hacs.vercel.app/"
        )
        assert module._origin_cors_consentita("https://studio-legale-pct-production.up.railway.app")
        assert module._origin_cors_consentita("https://antmm2605-hacs.vercel.app")
        assert not module._origin_cors_consentita("https://evil.example.com")
    finally:
        module.LOCAL_SIGNER_ALLOWED_ORIGINS = orig


def test_cors_preflight_private_network_risponde_header_atteso():
    module = _load_local_signer()

    captured = []

    class _FakeHandler:
        headers = {
            "Origin": "https://studio-legale-pct-production.up.railway.app",
            "Access-Control-Request-Private-Network": "true",
        }

        def send_header(self, key, value):
            captured.append((key, value))

    orig = module.LOCAL_SIGNER_ALLOWED_ORIGINS
    try:
        module.LOCAL_SIGNER_ALLOWED_ORIGINS = "https://studio-legale-pct-production.up.railway.app"
        module._Handler._add_cors(_FakeHandler())
    finally:
        module.LOCAL_SIGNER_ALLOWED_ORIGINS = orig

    assert ("Access-Control-Allow-Origin", "https://studio-legale-pct-production.up.railway.app") in captured
    assert ("Access-Control-Allow-Private-Network", "true") in captured


def test_riusa_certificato_windows_selezionato_per_chiamate_pst_successive():
    module = _load_local_signer()

    module._ultimo_certificato_windows = {"thumbprint": "AABBCC11"}

    assert module._require_certificato_pst(None) == "AABBCC11"
    assert module._require_certificato_pst("FFEEDD22") == "FFEEDD22"


def test_ping_windows_espone_certificati_store_anche_senza_token_pkcs11():
    module = _load_local_signer()

    orig_platform = module.sys.platform
    orig_trova = module._trova_libreria
    orig_curl = module._curl_disponibile
    orig_lista = module._windows_lista_certificati
    orig_cached = module._ultimo_certificato_windows
    captured = {}

    class _FakeHandler:
        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module.sys.platform = "win32"
        module._trova_libreria = lambda: None
        module._curl_disponibile = lambda: True
        module._windows_lista_certificati = lambda: [
            {
                "thumbprint": "AD98A31AFF1D88DE24C62969F26102D827C24E21",
                "soggetto": "ROBERTO MONTAGNESE",
                "emittente": "ArubaPEC EU Qualified Certificates CA G1",
                "scadenza": "2029-02-23",
            }
        ]
        module._ultimo_certificato_windows = {
            "thumbprint": "AD98A31AFF1D88DE24C62969F26102D827C24E21",
            "soggetto": "ROBERTO MONTAGNESE",
            "emittente": "ArubaPEC EU Qualified Certificates CA G1",
            "scadenza": "2029-02-23",
        }

        module._Handler._ping(_FakeHandler())
    finally:
        module.sys.platform = orig_platform
        module._trova_libreria = orig_trova
        module._curl_disponibile = orig_curl
        module._windows_lista_certificati = orig_lista
        module._ultimo_certificato_windows = orig_cached

    payload = captured["payload"]
    assert payload["ok"] is True
    assert payload["certificati_windows"] == 1
    assert payload["certificato_windows_selezionato"]["thumbprint"] == "AD98A31AFF1D88DE24C62969F26102D827C24E21"
    assert "Certificate Store" in payload["nota_autenticazione"]


def test_local_signer_usa_qbuilder_sicid_sulla_root_del_proxy():
    module = _load_local_signer()

    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"

    assert module._pst_servizio_proxy(base) == "JPW_SICID"
    assert module._pst_namespace_qbuilder(base) == "urn:CONS-SICC-BE"
    assert module._pst_url_documenti(base) == base


def test_estrai_codice_fiscale_dal_certificato_windows():
    module = _load_local_signer()

    module._ultimo_certificato_windows = {
        "thumbprint": "AABBCC11",
        "soggetto": "MNTRRT64L01L063H/7430010029148677.255hHgKCPtfSkIn6w4MBTjOX0QQ=",
    }

    assert module._estrai_codice_fiscale_testo("MNTRRT64L01L063H/123") == "MNTRRT64L01L063H"
    assert module._cf_avvocato_pst("", "AABBCC11") == "MNTRRT64L01L063H"


def test_costruisce_body_qbuilder_ricerca_per_tipo():
    module = _load_local_signer()

    xml = module._soap_ricerca_fascicoli_body(
        base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
        codice_ufficio="0800570094",
        numero_rg="1025",
        anno_rg=2024,
        cf_avvocato="MNTRRT64L01L063H",
    )

    assert 'InvocationDomain name="JPW" role="AVV" group="0800570094"' in xml
    assert '<execute xmlns="urn:CONS-SICC-BE">' in xml
    assert "<name>RicercaInformazioniFascicoloPerTipo</name>" in xml
    assert '<value name="tipo" type="string">RGN</value>' in xml
    assert '<entry property="ANNORUOLO, NUMERORUOLO" mode="asc"/>' in xml


def test_parse_qbuilder_fascicoli_xml():
    module = _load_local_signer()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SICC-BE"><return available="1" time="2026-03-29 18:51:21" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType"><ns2:row class="InfoFascicoloExt"><ns2:property name="IDFASCICOLO" type="string">172944</ns2:property><ns2:property name="IDUFFICIO" type="string">0800570094</ns2:property><ns2:property name="ANNORUOLO" type="long">2024</ns2:property><ns2:property name="NUMERORUOLO" type="string">00001025</ns2:property><ns2:property name="GIUDICE" type="string">GIOVANNELLA</ns2:property><ns2:property name="ATTOREPRINCIPALE" type="string">MONTAGNESE ELISABETTA</ns2:property><ns2:subRows class="InfoParte"><ns2:row><ns2:property name="COGNOME" type="string">STILLITANO</ns2:property><ns2:property name="NOME" type="string">FRANCESCO</ns2:property><ns2:property name="CODICEFISCALEPARTE" type="string">STLFNC45E26L063X</ns2:property></ns2:row></ns2:subRows></ns2:row></return></ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    fascicoli = module._parse_fascicoli_xml(xml)

    assert len(fascicoli) == 1
    assert fascicoli[0]["numero_rg"] == "1025"
    assert fascicoli[0]["anno_rg"] == 2024
    assert fascicoli[0]["codice_ufficio"] == "0800570094"
    assert fascicoli[0]["parti"] == ["STILLITANO FRANCESCO"]
    assert fascicoli[0]["parti_dettaglio"][0]["codice_fiscale"] == "STLFNC45E26L063X"


def test_parse_qbuilder_fascicoli_xml_supporta_codiceufficio_e_date_estese():
    module = _load_local_signer()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SICC-BE"><return available="1" time="2026-03-29 18:51:21" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType"><ns2:row class="InfoFascicoloExt"><ns2:property name="IDFASCICOLO" type="string">172944</ns2:property><ns2:property name="CODICEUFFICIO" type="string">0800570094</ns2:property><ns2:property name="ANNORUOLO" type="long">2024</ns2:property><ns2:property name="NUMERORUOLO" type="string">00001025</ns2:property><ns2:property name="DATAISCRIZIONERUOLO" type="date">05/09/2024 00:00:00.000</ns2:property><ns2:property name="DATAPROSSIMAUDIENZA" type="date">12/12/2024 00:00:00.000</ns2:property><ns2:property name="DESCRIZIONESEZIONE" type="string">CIVILE</ns2:property></ns2:row></return></ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    fascicoli = module._parse_fascicoli_xml(xml)

    assert len(fascicoli) == 1
    assert fascicoli[0]["codice_ufficio"] == "0800570094"
    assert fascicoli[0]["nome_ufficio"] == "Tribunale di Palmi"
    assert fascicoli[0]["data_iscrizione"] == "2024-09-05"
    assert fascicoli[0]["data_udienza"] == "2024-12-12"
    assert fascicoli[0]["sezione"] == "CIVILE"


def test_parse_qbuilder_documenti_xml():
    module = _load_local_signer()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SICC-BE"><return available="1" time="2026-03-29 18:52:17" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType"><ns2:row class="DocumentoFascicolo"><ns2:property name="IDUFFICIO" type="string">0800570094</ns2:property><ns2:property name="IDDOCUMENTO" type="string">33581101</ns2:property><ns2:property name="IDDOCMITTENTE" type="string">#DOCIDMITTENTE</ns2:property><ns2:property name="TIPO" type="string">{http://schemi.processotelematico.giustizia.it/sicid/magistrato/Sentenza/v3}:SentenzaDefinitiva</ns2:property><ns2:property name="STATO" type="string">depositato</ns2:property><ns2:property name="AUTORE" type="string">GIOVANNELLA MARIA ELENA</ns2:property><ns2:property name="NUMERODOCUMENTO" type="string">33581101</ns2:property><ns2:property name="DATADEPOSITO" type="date">08/01/2026 18:55:28.000</ns2:property></ns2:row></return></ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    documenti = module._parse_documenti_xml(xml)

    assert len(documenti) == 1
    assert documenti[0]["id_documento"] == "33581101"
    assert documenti[0]["tipo"] == "SentenzaDefinitiva"
    assert documenti[0]["tipo_atto"] == "SentenzaDefinitiva"
    assert documenti[0]["id_deposito"] == ""
    assert documenti[0]["mittente"] == "GIOVANNELLA MARIA ELENA"


def test_parse_documenti_xml_supporta_container_annidato():
    module = _load_local_signer()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
  <soapenv:Body>
    <ns1:consultazioneDocumentiResponse xmlns:ns1="urn:it:giustizia:pst">
      <return>
        <documenti>
          <item>
            <idDocumento>DOC-001</idDocumento>
            <nomeFile>ricorso.pdf.p7m</nomeFile>
            <tipoDocumento>ATTO</tipoDocumento>
            <dataDeposito>29/03/2026 10:15:00.000</dataDeposito>
            <mittente>avv.demo@pec.it</mittente>
            <dimensione>12000</dimensione>
            <idDeposito>BUSTA-PST-001</idDeposito>
            <tipoAtto>Ricorso introduttivo</tipoAtto>
            <disponibile>true</disponibile>
          </item>
          <item>
            <idDocumento>DOC-002</idDocumento>
            <nomeFile>procura.pdf.p7m</nomeFile>
            <tipoDocumento>ALLEGATO</tipoDocumento>
            <dataDeposito>29/03/2026 10:15:00.000</dataDeposito>
            <mittente>avv.demo@pec.it</mittente>
            <dimensione>8000</dimensione>
            <idDeposito>BUSTA-PST-001</idDeposito>
            <tipoAtto>Ricorso introduttivo</tipoAtto>
            <disponibile>true</disponibile>
          </item>
        </documenti>
      </return>
    </ns1:consultazioneDocumentiResponse>
  </soapenv:Body>
</soapenv:Envelope>"""

    documenti = module._parse_documenti_xml(xml)

    assert len(documenti) == 2
    assert documenti[0]["id_documento"] == "DOC-001"
    assert documenti[1]["id_documento"] == "DOC-002"
    assert {doc["id_deposito"] for doc in documenti} == {"BUSTA-PST-001"}
    assert {doc["data_deposito"] for doc in documenti} == {"2026-03-29"}


def test_parse_qbuilder_documenti_xml_supporta_piu_return():
    module = _load_local_signer()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SICC-BE">
  <return available="1" time="2026-03-29 18:52:17" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType">
    <ns2:row class="DocumentoFascicolo">
      <ns2:property name="IDDOCUMENTO" type="string">33581101</ns2:property>
      <ns2:property name="TIPO" type="string">Memoria</ns2:property>
      <ns2:property name="DATADEPOSITO" type="date">08/01/2026 18:55:28.000</ns2:property>
    </ns2:row>
  </return>
  <return available="1" time="2026-03-29 18:53:17" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType">
    <ns2:row class="DocumentoFascicolo">
      <ns2:property name="IDDOCUMENTO" type="string">33581102</ns2:property>
      <ns2:property name="TIPO" type="string">Allegato</ns2:property>
      <ns2:property name="DATADEPOSITO" type="date">08/01/2026 18:56:28.000</ns2:property>
    </ns2:row>
  </return>
</ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    documenti = module._parse_documenti_xml(xml)

    assert len(documenti) == 2
    assert {doc["id_documento"] for doc in documenti} == {"33581101", "33581102"}


def test_parse_download_documento_response_multipart():
    module = _load_local_signer()

    body = (
        b"--abc123\r\n"
        b"Content-Type: text/xml\r\n"
        b"Content-Transfer-Encoding: 7bit\r\n\r\n"
        b"<?xml version='1.0' encoding='UTF-8'?><SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>"
        b"<SOAP-ENV:Body><ns1:downloadDocumentoResponse xmlns:ns1='urn:BEAFascicoloInformatico-distr'>"
        b"<return href ='cid:test-doc-1'/></ns1:downloadDocumentoResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>\r\n"
        b"--abc123\r\n"
        b"Content-Type: application/pdf\r\n"
        b"Content-Transfer-Encoding: base64\r\n"
        b"Content-ID: <test-doc-1>\r\n\r\n"
        b"JVBERi0xLjcK\r\n"
        b"--abc123--\r\n"
    )

    parsed = module._parse_download_documento_response(
        body,
        'multipart/related; boundary="abc123"',
    )

    assert "downloadDocumentoResponse" in parsed["soap_xml"]
    assert parsed["content"].startswith(b"%PDF")
    assert parsed["content_type"] == "application/pdf"
    assert parsed["content_id"] == "test-doc-1"


def test_pst_download_documento_payload_sicid_usa_profilo_e_allegato():
    module = _load_local_signer()

    profile_xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <ns1:estraiProfiloDocumentoResponse xmlns:ns1="urn:BEAFascicoloInformatico-distr">
      <return>
        <idDocumento>33581101</idDocumento>
        <idCat>33581101</idCat>
        <nomeFileOriginale>31789737s.pdf</nomeFileOriginale>
        <dataDeposito>2026-01-08T18:55:28Z</dataDeposito>
      </return>
    </ns1:estraiProfiloDocumentoResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
    raw_body = (
        b"--abc123\r\n"
        b"Content-Type: text/xml\r\n"
        b"Content-Transfer-Encoding: 7bit\r\n\r\n"
        b"<?xml version='1.0' encoding='UTF-8'?><SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>"
        b"<SOAP-ENV:Body><ns1:downloadDocumentoResponse xmlns:ns1='urn:BEAFascicoloInformatico-distr'>"
        b"<return href ='cid:test-doc-1'/></ns1:downloadDocumentoResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>\r\n"
        b"--abc123\r\n"
        b"Content-Type: application/pdf\r\n"
        b"Content-Transfer-Encoding: base64\r\n"
        b"Content-ID: <test-doc-1>\r\n\r\n"
        b"JVBERi0xLjcK\r\n"
        b"--abc123--\r\n"
    )

    calls = {"profile": 0, "download": 0}
    orig_call = module._soap_call_curl
    orig_raw = module._soap_call_curl_raw
    try:
        def _fake_call(*args, **kwargs):
            calls["profile"] += 1
            return profile_xml

        def _fake_raw(*args, **kwargs):
            calls["download"] += 1
            return raw_body, 'Content-Type: multipart/related; boundary="abc123"'

        module._soap_call_curl = _fake_call
        module._soap_call_curl_raw = _fake_raw

        payload = module._pst_download_documento_payload(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
            id_documento="33581101",
            nome_documento="SentenzaDefinitiva_33581101.pdf",
            cert_thumbprint="AABBCC11",
            cf_avvocato="MNTRRT64L01L063H",
        )
    finally:
        module._soap_call_curl = orig_call
        module._soap_call_curl_raw = orig_raw

    assert calls["profile"] == 1
    assert calls["download"] == 1
    assert payload["id_documento_portale"] == "33581101"
    assert payload["id_cat"] == "33581101"
    assert payload["nome"] == "SentenzaDefinitiva_33581101.pdf"
    assert payload["data_documento"] == "2026-01-08"
    assert payload["content_type"] == "application/pdf"
    assert payload["servizio_portale"] == "DocumentiFascicolo"
    assert payload["contenuto_b64"].startswith("JVBERi0xLjcK")


def test_normalizza_nome_download_match_rimuove_suffissi_e_duplicati():
    module = _load_local_signer()

    assert module._normalizza_nome_download_match("Sentenza definitiva (1).pdf.p7m") == "sentenzadefinitiva"
    assert module._normalizza_nome_download_match("Verbale udienza.pdf") == "verbaleudienza"


def test_raccogli_download_recenti_trova_file_attesi(tmp_path):
    module = _load_local_signer()

    sentenza = tmp_path / "Sentenza definitiva.pdf"
    sentenza.write_bytes(b"sentenza")
    verbale = tmp_path / "Verbale udienza (1).pdf"
    verbale.write_bytes(b"verbale")
    (tmp_path / "irrilevante.txt").write_bytes(b"altro")

    esito = module._raccogli_download_recenti(
        [
            {
                "nome": "Sentenza definitiva.pdf.p7m",
                "id_deposito_esterno": "BUSTA-PST-001",
                "id_deposito_pct": "DEP-001",
                "id_documento_portale": "DOC-001",
            },
            {
                "nome": "Verbale udienza.pdf",
                "id_deposito_esterno": "BUSTA-PST-001",
                "id_deposito_pct": "DEP-001",
                "id_documento_portale": "DOC-002",
            },
        ],
        base_dir=str(tmp_path),
        max_age_hours=24,
        limit=10,
    )

    assert esito["matched"] == 2
    assert {item["id_documento_portale"] for item in esito["files"]} == {"DOC-001", "DOC-002"}
    assert {item["id_deposito_pct"] for item in esito["files"]} == {"DEP-001"}


def test_trova_libreria_prefers_candidate_with_detected_token():
    module = _load_local_signer()

    orig_cache = module._lib_cache
    orig_candidates = module._candidate_pkcs11_libs
    orig_score = module._score_pkcs11_lib
    try:
        module._lib_cache = None
        module._candidate_pkcs11_libs = lambda override=None: ["middleware-a.dll", "middleware-b.dll"]
        module._score_pkcs11_lib = lambda path: 3 if path.endswith("b.dll") else 1

        assert module._trova_libreria() == "middleware-b.dll"
    finally:
        module._lib_cache = orig_cache
        module._candidate_pkcs11_libs = orig_candidates
        module._score_pkcs11_lib = orig_score


def _cfg_web(tmp_path):
    base = tmp_path
    backup_dir = str(base / "backup")
    os.makedirs(backup_dir, exist_ok=True)
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "AUTH_DB": str(base / "utenti.json"),
        "AUDIT_DB": str(base / "audit.json"),
        "CLIENTI_DB": str(base / "clienti.json"),
        "CONDIVISIONI_DB": str(base / "condivisioni.json"),
        "FASCICOLI_DB": str(base / "fascicoli.json"),
        "AGENDA_DB": str(base / "agenda.json"),
        "SCADENZIARIO_DB": str(base / "scadenze.json"),
        "MESSAGGI_DB": str(base / "messaggi.json"),
        "BACKUP_DIR": backup_dir,
        "SEARCH_INDEX": str(base / "search.db"),
        "FASCICOLI_DOCS": str(base / "docs"),
        "FASCICOLI_ARCH": str(base / "arch"),
    }


def test_installer_local_signer_e_scaricabile_senza_login(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/installa-windows")

    assert r.status_code == 200
    assert (
        f'attachment; filename="InstallaLocalSigner-{version}.ps1"'
        in r.headers.get("Content-Disposition", "")
    )
    body = r.data.decode("utf-8")
    assert f"HACS Local Signer v{version}" in body
    assert "Invoke-WebRequest" in body
    assert "/polisWeb/local-signer/download" in body
    assert "hacs-local-signer" in body
    assert "127.0.0.1:27272/ping" in body


def test_download_local_signer_python_e_pubblico(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/download")

    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert f"local_signer-{version}.py" in r.headers.get("Content-Disposition", "")
    body = r.data.decode("utf-8")
    assert "HACS Local Signer" in body
    assert "def main()" in body


def test_download_registro_uffici_local_signer_e_pubblico(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/download/uffici")

    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert "uffici_ministero.json" in r.headers.get("Content-Disposition", "")
    body = r.data.decode("utf-8")
    assert '"uffici"' in body
    assert '"0530010"' in body


def test_installer_local_signer_windows_setup_route_e_pubblica(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/windows")

    assert r.status_code == 200
    disposition = r.headers.get("Content-Disposition", "")
    assert "attachment;" in disposition
    assert (
        f"SetupLocalSigner-{version}.exe" in disposition
        or f"InstallaLocalSigner-{version}.ps1" in disposition
    )


def test_installer_local_signer_windows_exe_route_se_bundle_presente(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/windows-exe")

    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert f"SetupLocalSigner-{version}.exe" in r.headers.get("Content-Disposition", "")


def test_installer_local_signer_macos_e_pubblico(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/macos")

    assert r.status_code == 200
    assert (
        f"InstallaLocalSigner-{version}.command"
        in r.headers.get("Content-Disposition", "")
    )
    body = r.data.decode("utf-8")
    assert "LaunchAgents" in body
    assert "/polisWeb/local-signer/download" in body


def test_installer_local_signer_linux_e_pubblico(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/linux")

    assert r.status_code == 200
    assert (
        f"InstallaLocalSigner-{version}.run"
        in r.headers.get("Content-Disposition", "")
    )
    body = r.data.decode("utf-8")
    assert "systemd/user" in body
    assert "/polisWeb/local-signer/download" in body


def test_tab_firma_mostra_download_local_signer_per_tutte_le_piattaforme(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        login = c.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code in (302, 303)

        r = c.get("/impostazioni?tab=firma")

    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "Scarica Local Signer" in body
    assert "/polisWeb/local-signer/setup/windows" in body
    assert "/polisWeb/local-signer/setup/macos" in body
    assert "/polisWeb/local-signer/setup/linux" in body
    assert "/polisWeb/local-signer/download" in body
    assert "/polisWeb/local-signer/download/uffici" in body
    assert f"SetupLocalSigner-{version}.exe" in body
    assert f"InstallaLocalSigner-{version}.command" in body
    assert f"InstallaLocalSigner-{version}.run" in body
    assert "https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma" in body


def test_impostazioni_firma_carica_p12_nel_volume_configurato(tmp_path):
    from pct.config_studio import GestioneConfigStudio
    from web.app import create_app

    studio_cfg = tmp_path / "config" / "studio.json"
    app = create_app({**_cfg_web(tmp_path), "STUDIO_CONFIG": str(studio_cfg)})

    with app.test_client() as c:
        login = c.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code in (302, 303)

        r = c.post(
            "/impostazioni",
            data={
                "_tab": "firma",
                "firma_formato": "p12",
                "firma_p12_path": "",
                "firma_password": "segreta",
                "firma_cf_avvocato": "RSSMRA80A01H501Z",
                "firma_p12_file": (io.BytesIO(b"contenuto-p12"), "firma_professionista.p12"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert r.status_code in (302, 303)
    cfg = GestioneConfigStudio(str(studio_cfg)).config
    assert cfg.firma.backend_preferito == "p12"
    assert cfg.firma.p12_path.endswith("/firma_uploads/firma.p12")
    assert Path(cfg.firma.p12_path).read_bytes() == b"contenuto-p12"
    assert cfg.firma.password == "segreta"
    assert cfg.firma.cf_avvocato == "RSSMRA80A01H501Z"


def test_polisweb_non_mostra_demo_se_pkcs11_e_configurato(tmp_path):
    from pct.config_studio import GestioneConfigStudio
    from web.app import create_app

    studio_cfg = tmp_path / "config" / "studio.json"
    dll_path = tmp_path / "bit4xpki.dll"
    dll_path.write_bytes(b"fake-dll")

    gs = GestioneConfigStudio(str(studio_cfg))
    cfg = gs.config
    cfg.firma.pkcs11_library = str(dll_path)
    gs.aggiorna(cfg)

    app = create_app({**_cfg_web(tmp_path), "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as c:
        login = c.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code in (302, 303)
        r = c.get("/polisWeb")

    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert 'name="demo_mode" value="0"' in body
    assert 'name="server_demo_mode" value="1"' in body
    assert 'id="badge-demo-mode"' not in body
    assert 'id="banner-demo"' not in body


def test_polisweb_ricerca_non_torna_in_demo_se_pkcs11_e_configurato(tmp_path, monkeypatch):
    from pct.config_studio import GestioneConfigStudio
    from web.app import create_app

    studio_cfg = tmp_path / "config" / "studio.json"
    dll_path = tmp_path / "bit4xpki.dll"
    dll_path.write_bytes(b"fake-dll")

    gs = GestioneConfigStudio(str(studio_cfg))
    cfg = gs.config
    cfg.firma.pkcs11_library = str(dll_path)
    gs.aggiorna(cfg)

    chiamate_demo = []

    class _ClientStub:
        def ricerca_fascicoli(self, **kwargs):
            return []

    def _crea_client_stub(*args, **kwargs):
        chiamate_demo.append(kwargs.get("demo"))
        return _ClientStub()

    monkeypatch.setattr("pct.polisWeb.crea_client", _crea_client_stub)

    app = create_app({**_cfg_web(tmp_path), "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as c:
        login = c.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=False,
        )
        assert login.status_code in (302, 303)
        r = c.post(
            "/polisWeb/ricerca",
            data={
                "tribunale": "0580010",
                "demo_mode": "0",
                "server_demo_mode": "1",
            },
        )

    assert r.status_code == 200
    assert chiamate_demo == [False]
    body = r.data.decode("utf-8")
    assert 'name="demo_mode" value="0"' in body
    assert 'name="server_demo_mode" value="1"' in body
    assert 'id="badge-demo-mode"' not in body
    assert 'id="banner-demo"' not in body


def test_installer_locale_windows_registra_protocollo_e_attesa_ping():
    script = (
        Path(__file__).resolve().parents[1]
        / "tools"
        / "installa_local_signer_locale.ps1"
    ).read_text(encoding="utf-8")

    assert "hacs-local-signer" in script
    assert "Wait-LocalSigner" in script
    assert "start_local_signer.cmd" in script
    assert "Stop-LocalSignerProcesses" in script
    assert "Test-LocalSignerOnline" in script


def test_firma_documento_riusa_sessione_pin_in_ram():
    module = _load_local_signer()

    class _FakeSigner:
        def __init__(self):
            self.calls = 0
            self.closed = False
            self.intestatario = "Avv. Test"
            self.scadenza = __import__("datetime").datetime(2029, 2, 23, 12, 0, 0)

        def firma_cades(self, documento, detached=False):
            self.calls += 1
            return documento + b".p7m"

        def close(self):
            self.closed = True

    signer = _FakeSigner()
    orig_create = module._create_pin_session
    orig_cache = module._pin_session_cache
    try:
        module._pin_session_cache = {}

        def _fake_create(lib_path, pin, slot_id=None):
            dt = __import__("datetime")
            now = dt.datetime.now(dt.UTC).replace(tzinfo=None)
            entry = {
                "session_id": "sess-1",
                "signer": signer,
                "lib_path": lib_path,
                "slot_id": slot_id if slot_id is not None else 0,
                "created_at": now,
                "last_used_at": now,
                "expires_at": now + dt.timedelta(seconds=module.PIN_SESSION_TTL_SECONDS),
            }
            module._pin_session_cache["sess-1"] = entry
            return "sess-1", signer

        module._create_pin_session = _fake_create

        firmato1, info1 = module._firma_documento("fake.dll", b"doc-1", "123456", 0)
        firmato2, info2 = module._firma_documento("fake.dll", b"doc-2", "", 0, pin_session_id="sess-1")
    finally:
        module._create_pin_session = orig_create
        module._pin_session_cache = orig_cache

    assert firmato1.endswith(b".p7m")
    assert firmato2.endswith(b".p7m")
    assert info1["pin_session_id"] == "sess-1"
    assert info2["pin_session_id"] == "sess-1"
    assert info2["pin_session_cached"] is True
    assert signer.calls == 2


def test_pick_preferred_windows_cert_privilegia_aruba_auth():
    module = _load_local_signer()

    certs = [
        {
            "thumbprint": "GENERIC-1",
            "soggetto": "ROSSI MARIO",
            "emittente": "Generic CA",
            "scadenza": "2027-01-01",
        },
        {
            "thumbprint": "QUAL-1",
            "soggetto": "ROSSI MARIO",
            "emittente": "ArubaPEC EU Qualified Certificates CA G1",
            "scadenza": "2029-02-23",
        },
        {
            "thumbprint": "AUTH-1",
            "soggetto": "ROSSI MARIO - AUTENTICAZIONE WEB",
            "emittente": "ArubaPEC EU Authentica Certificates CA G1",
            "scadenza": "2029-02-23",
        },
    ]

    cert = module._pick_preferred_windows_cert(
        certs,
        prefer_issuer="ArubaPEC EU Authentica Certificates CA G1|ArubaPEC EU Qualified Certificates CA G1",
        prefer_subject="auth|autenticazione|client",
        auto=True,
    )

    assert cert is not None
    assert cert["thumbprint"] == "AUTH-1"


def test_firma_batch_riusa_sessione_pin_per_tutto_il_lotto():
    module = _load_local_signer()

    calls = []
    captured = {}
    orig_trova = module._trova_libreria
    orig_firma = module._firma_documento

    class _FakeHandler:
        def __init__(self, payload):
            self.payload = payload

        def _read_json(self):
            return self.payload

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._trova_libreria = lambda: "fake.dll"

        def _fake_firma_documento(lib_path, documento, pin, slot_id, pin_session_id=None):
            calls.append({
                "lib_path": lib_path,
                "documento": documento,
                "pin": pin,
                "slot_id": slot_id,
                "pin_session_id": pin_session_id,
            })
            session_id = pin_session_id or "sess-1"
            return documento + b".p7m", {
                "pin_session_id": session_id,
                "pin_session_cached": bool(pin_session_id),
                "intestatario": "Avv. Test",
                "scadenza": "2029-02-23",
            }

        module._firma_documento = _fake_firma_documento

        handler = _FakeHandler(
            {
                "documenti": [
                    {"documento": base64.b64encode(b"doc-1").decode(), "nome": "doc-1.pdf"},
                    {"documento": base64.b64encode(b"doc-2").decode(), "nome": "doc-2.pdf"},
                ],
                "pin": "123456",
                "slot_id": 0,
            }
        )

        module._Handler._firma_batch(handler)
    finally:
        module._trova_libreria = orig_trova
        module._firma_documento = orig_firma

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["firmati"] == 2
    assert captured["payload"]["pin_session_id"] == "sess-1"
    assert calls[0]["pin"] == "123456"
    assert calls[0]["pin_session_id"] is None
    assert calls[1]["pin"] == ""
    assert calls[1]["pin_session_id"] == "sess-1"


def test_download_documenti_batch_esegue_preflight_una_sola_volta():
    module = _load_local_signer()

    orig_preflight = module._pst_preflight_auth_curl
    orig_download = module._pst_download_documento_payload
    calls = {"preflight": 0, "download": []}

    try:
        def _fake_preflight(url, cert_thumbprint=None, pkcs11_uri=None):
            calls["preflight"] += 1
            return {"ok": True, "nota": "warmup ok"}

        def _fake_download(**kwargs):
            calls["download"].append(kwargs["id_documento"])
            return {
                "nome": kwargs["nome_documento"] or f"documento_{kwargs['id_documento']}.pdf",
                "contenuto_b64": "ZmFrZQ==",
                "content_type": "application/pdf",
                "id_documento_portale": kwargs["id_documento"],
                "id_cat": kwargs.get("id_cat") or "",
                "data_documento": kwargs.get("data_documento") or "",
                "nome_file_originale": kwargs["nome_documento"] or "",
                "servizio_portale": "DocumentiFascicolo",
            }

        module._pst_preflight_auth_curl = _fake_preflight
        module._pst_download_documento_payload = _fake_download

        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
            documenti=[
                {"id_documento": "33581101", "nome_documento": "Sentenza.pdf"},
                {"id_documento": "33393309", "nome_documento": "Verbale.pdf"},
            ],
            do_preflight=True,
        )
    finally:
        module._pst_preflight_auth_curl = orig_preflight
        module._pst_download_documento_payload = orig_download

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 2
    assert esito["failures"] == []
    assert calls["preflight"] == 1
    assert calls["download"] == ["33581101", "33393309"]
