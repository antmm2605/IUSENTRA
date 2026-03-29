from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_local_signer():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "local_signer.py"
    spec = importlib.util.spec_from_file_location("hacs_local_signer", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


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
    assert url.endswith("/pda/pycons/GLMI/JPW_SICID/RicercaFascicoliRegistroService")
    assert module._risolvi_codice_ufficio_pst("0580010") == "0151460094"


def test_thumbprint_windows_viene_formattato_per_schannel():
    module = _load_local_signer()

    assert module._format_windows_cert_spec("AA BB CC 11") == r"CurrentUser\MY\AABBCC11"
    assert module._format_windows_cert_spec(r"CurrentUser\MY\ABCDEF") == r"CurrentUser\MY\ABCDEF"


def test_http_401_pst_diventa_messaggio_operativo():
    module = _load_local_signer()

    msg = module._http_errore_leggibile(
        401,
        "<html><title>401 Unauthorized</title></html>",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID/RicercaFascicoliRegistroService",
        "text/html; charset=iso-8859-1",
    )

    assert "401 Unauthorized" in msg
    assert "certificato" in msg.lower()
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


def test_riusa_certificato_windows_selezionato_per_chiamate_pst_successive():
    module = _load_local_signer()

    module._ultimo_certificato_windows = {"thumbprint": "AABBCC11"}

    assert module._require_certificato_pst(None) == "AABBCC11"
    assert module._require_certificato_pst("FFEEDD22") == "FFEEDD22"


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
