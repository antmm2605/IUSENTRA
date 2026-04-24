from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_local_signer():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "local_signer.py"
    spec = importlib.util.spec_from_file_location("hacs_local_signer_matrix", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("servizio", "distretto", "namespace"),
    [
        ("JPW_SICID", "GLRC", "urn:CONS-SICC-BE"),
        ("JPW_SIECIC", "GLRC", "urn:CONS-SIECIC-BE"),
        ("JPW_SIGP", "GLRC", "urn:CONS-SIGP-BE"),
        ("JPW_CASSCI", "GLCC", "urn:CONS-CASSCI"),
        ("JPW_CASSPE", "GLCC", "urn:CONS-CASSPE"),
    ],
)
def test_pst_qbuilder_matrix_servizi_ufficiali(servizio, distretto, namespace):
    module = _load_local_signer()
    base_url = f"https://ext.processotelematico.giustizia.it/pda/pycons/{distretto}/{servizio}"

    ricerca_xml = module._soap_ricerca_fascicoli_body(
        base_url=base_url,
        codice_ufficio="0800570094",
        numero_rg="1025",
        anno_rg=2024,
        cf_avvocato="MNTRRT64L01L063H",
    )
    documenti_xml = module._soap_documenti_body(
        base_url=base_url,
        codice_ufficio="0800570094",
        numero_rg="1025",
        anno_rg=2024,
        sub_procedimento="",
    )
    profilo_xml = module._soap_profilo_fascicolo_body(
        base_url=base_url,
        codice_ufficio="0800570094",
        numero_rg="1025",
        anno_rg=2024,
        sub_procedimento="",
    )
    documenti_subproc_xml = module._soap_documenti_body(
        base_url=base_url,
        codice_ufficio="0800570094",
        numero_rg="1025",
        anno_rg=2024,
        sub_procedimento="1",
    )

    assert module._pst_namespace_qbuilder(base_url) == namespace
    assert f'<execute xmlns="{namespace}">' in ricerca_xml
    assert "<name>RicercaInformazioniFascicoloPerTipo</name>" in ricerca_xml
    assert '<value name="anno" type="string">2024</value>' in ricerca_xml
    assert '<value name="numero" type="integer">1025</value>' in ricerca_xml

    for xml in (ricerca_xml, documenti_xml, profilo_xml):
        assert 'name="subProc"' not in xml
        assert 'name="annoRuolo"' not in xml
        assert 'name="numeroRuolo"' not in xml

    if servizio == "JPW_SIGP":
        assert '<value name="tipo" type="string">GDP</value>' in ricerca_xml
        for xml in (ricerca_xml, documenti_xml, profilo_xml):
            assert '<value name="subpro" type="string">0</value>' in xml
        assert '<value name="subpro" type="string">1</value>' in documenti_subproc_xml
        assert 'name="subProc"' not in documenti_subproc_xml
    else:
        for xml in (ricerca_xml, documenti_xml, profilo_xml):
            assert 'name="subpro"' not in xml
        assert '<value name="subProc" type="string">1</value>' in documenti_subproc_xml
        assert 'name="subpro"' not in documenti_subproc_xml


def test_pst_resolver_matrix_uffici_chiave():
    module = _load_local_signer()
    casi = [
        ("0580010", "0151460094", "JPW_SICID"),
        ("0910401", "0800570152", "JPW_SIGP"),
        ("9990000", "80417740588", "JPW_CASSCI"),
    ]

    for codice_hacs, codice_ministero, servizio in casi:
        base = module._risolvi_base_pst_runtime(codice_hacs)
        assert module._risolvi_codice_ufficio_pst(codice_hacs) == codice_ministero
        assert base.endswith(f"/{servizio}")
        assert module._pst_namespace_qbuilder(base)


def test_portali_browser_assist_matrix_url_ufficiali():
    module = _load_local_signer()
    expected = {
        "pdp": "https://pst.giustizia.it/PST/it/services.page",
        "pat": "https://www.giustizia-amministrativa.it/portale-avvocato",
        "ptt": "https://sigit.finanze.it/NIRWeb/login.jsp",
    }

    for portale, url in expected.items():
        for phase in ("ricerca", "documenti"):
            payload = module._portale_browser_assist_payload(portale, phase)
            assert payload["ok"] is False
            assert payload["manual_required"] is True
            assert payload["manual_phase"] == phase
            assert payload["manual_title"] == "Consultazione via browser ufficiale"
            assert payload["portale_url"] == url


def test_local_signer_matrix_pdp_pat_ptt_operazioni_wsdl():
    module = _load_local_signer()
    captured: list[dict] = []

    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_portale_wsdl_diretto_abilitato": module._portale_wsdl_diretto_abilitato,
        "_require_certificato_pst": module._require_certificato_pst,
        "_require_cf_avvocato_locale": module._require_cf_avvocato_locale,
        "_soap_call_zeep_operation_via_curl": module._soap_call_zeep_operation_via_curl,
        "_risolvi_codice_ufficio_pdp_runtime": module._risolvi_codice_ufficio_pdp_runtime,
        "_risolvi_codice_ufficio_pat_runtime": module._risolvi_codice_ufficio_pat_runtime,
        "_risolvi_codice_commissione_ptt_runtime": module._risolvi_codice_commissione_ptt_runtime,
        "_parse_pdp_fascicoli_response": module._parse_pdp_fascicoli_response,
        "_parse_pdp_documenti_response": module._parse_pdp_documenti_response,
        "_parse_pat_fascicoli_response": module._parse_pat_fascicoli_response,
        "_parse_pat_documenti_response": module._parse_pat_documenti_response,
        "_parse_ptt_fascicoli_response": module._parse_ptt_fascicoli_response,
        "_parse_ptt_documenti_response": module._parse_ptt_documenti_response,
    }

    class _FakeHandler:
        def __init__(self, payload):
            self._payload = payload
            self.sent = None
            self.status = None

        def _read_json(self):
            return self._payload

        def _send_json(self, payload, status=200):
            self.sent = payload
            self.status = status

    def _bridge(**kwargs):
        captured.append(kwargs)
        return SimpleNamespace()

    cases = [
        (
            "_pdp_ricerca",
            {"ufficio": "Procura di Reggio Calabria", "numero_rg": "4521", "anno_rg": 2026, "tipo_registro": "RGNR", "cert_thumbprint": "AABBCC11"},
            "ricercaFascicoliPenale",
            "fascicoli",
            {"codiceUfficio": "PDP-UFF", "numeroRG": "4521", "annoRG": 2026, "tipoRegistro": "RGNR"},
        ),
        (
            "_pdp_documenti",
            {"codice_ufficio": "PDP-UFF", "numero_rg": "4521", "anno_rg": 2026, "cert_thumbprint": "AABBCC11"},
            "consultaDocumentiPenale",
            "documenti",
            {"codiceUfficio": "PDP-UFF", "numeroRG": "4521", "annoRG": 2026},
        ),
        (
            "_pat_ricerca",
            {"ufficio": "TAR Lazio", "numero_ricorso": "1876", "anno": 2026, "materia": "APPALTI", "cert_thumbprint": "AABBCC11"},
            "ricercaRicorsi",
            "fascicoli",
            {"codiceUfficio": "PAT-UFF", "numeroRicorso": "1876", "anno": 2026, "materia": "APPALTI"},
        ),
        (
            "_pat_documenti",
            {"codice_ufficio": "PAT-UFF", "numero_ricorso": "1876", "anno": 2026, "cert_thumbprint": "AABBCC11"},
            "consultazioneDocumenti",
            "documenti",
            {"codiceUfficio": "PAT-UFF", "numeroRicorso": "1876", "anno": 2026},
        ),
        (
            "_ptt_ricerca",
            {"commissione": "CGT Milano", "numero_rgt": "1234", "anno_rgt": 2026, "tipo": "RICORSO", "cert_thumbprint": "AABBCC11"},
            "ricercaFascicoliTributari",
            "fascicoli",
            {"codiceCommissione": "PTT-COM", "numeroRGT": "1234", "annoRGT": 2026, "tipoRicorso": "RICORSO"},
        ),
        (
            "_ptt_documenti",
            {"codice_commissione": "PTT-COM", "numero_rgt": "1234", "anno_rgt": 2026, "cert_thumbprint": "AABBCC11"},
            "consultaDocumentiTributari",
            "documenti",
            {"codiceCommissione": "PTT-COM", "numeroRGT": "1234", "annoRGT": 2026},
        ),
    ]

    try:
        module._curl_disponibile = lambda: True
        module._portale_wsdl_diretto_abilitato = lambda portale: True
        module._require_certificato_pst = lambda thumb: "AABBCC11"
        module._require_cf_avvocato_locale = lambda cf, thumb: "RSSMRA80A01H501Z"
        module._soap_call_zeep_operation_via_curl = _bridge
        module._risolvi_codice_ufficio_pdp_runtime = lambda ufficio: "PDP-UFF"
        module._risolvi_codice_ufficio_pat_runtime = lambda ufficio: "PAT-UFF"
        module._risolvi_codice_commissione_ptt_runtime = lambda commissione: "PTT-COM"
        module._parse_pdp_fascicoli_response = lambda risposta: [{"numero_rg": "4521"}]
        module._parse_pdp_documenti_response = lambda risposta: [{"id_documento": "PDP-DOC"}]
        module._parse_pat_fascicoli_response = lambda risposta: [{"numero_ricorso": "1876"}]
        module._parse_pat_documenti_response = lambda risposta: [{"id_documento": "PAT-DOC"}]
        module._parse_ptt_fascicoli_response = lambda risposta: [{"numero_rgt": "1234"}]
        module._parse_ptt_documenti_response = lambda risposta: [{"id_documento": "PTT-DOC"}]

        for method_name, payload, operation_name, response_key, expected_payload in cases:
            captured.clear()
            handler = _FakeHandler(payload)
            getattr(module._Handler, method_name)(handler)

            assert handler.status == 200
            assert handler.sent["ok"] is True
            assert handler.sent[response_key]
            assert captured[0]["operation_name"] == operation_name
            assert captured[0]["cert_thumbprint"] == "AABBCC11"
            for key, value in expected_payload.items():
                assert captured[0]["payload"][key] == value
    finally:
        for name, value in originals.items():
            setattr(module, name, value)
