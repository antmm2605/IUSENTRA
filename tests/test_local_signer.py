from __future__ import annotations

import importlib.util
import os
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

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/installa-windows")

    assert r.status_code == 200
    assert "attachment; filename=\"installa_local_signer.ps1\"" in r.headers.get("Content-Disposition", "")
    body = r.data.decode("utf-8")
    assert "HACS Local Signer" in body
    assert "Invoke-WebRequest" in body
    assert "/polisWeb/local-signer/download" in body


def test_download_local_signer_python_e_pubblico(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/download")

    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert "local_signer.py" in r.headers.get("Content-Disposition", "")
    body = r.data.decode("utf-8")
    assert "HACS Local Signer" in body
    assert "def main()" in body


def test_installer_local_signer_windows_setup_route_e_pubblica(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/windows")

    assert r.status_code == 200
    disposition = r.headers.get("Content-Disposition", "")
    assert "attachment;" in disposition
    assert (
        "SetupLocalSigner.exe" in disposition
        or "installa_local_signer.ps1" in disposition
    )


def test_installer_local_signer_windows_exe_route_se_bundle_presente(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/windows-exe")

    assert r.status_code in (200, 404)
    if r.status_code == 200:
        assert "SetupLocalSigner.exe" in r.headers.get("Content-Disposition", "")


def test_installer_local_signer_macos_e_pubblico(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/macos")

    assert r.status_code == 200
    assert 'attachment; filename="InstallaLocalSigner.command"' in r.headers.get("Content-Disposition", "")
    body = r.data.decode("utf-8")
    assert "LaunchAgents" in body
    assert "/polisWeb/local-signer/download" in body


def test_installer_local_signer_linux_e_pubblico(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/linux")

    assert r.status_code == 200
    assert 'attachment; filename="installa_local_signer.sh"' in r.headers.get("Content-Disposition", "")
    body = r.data.decode("utf-8")
    assert "systemd/user" in body
    assert "/polisWeb/local-signer/download" in body
