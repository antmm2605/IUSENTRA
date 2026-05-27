from __future__ import annotations

import base64
import io
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _load_local_signer():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "local_signer.py"
    spec = importlib.util.spec_from_file_location("hacs_local_signer", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_local_ai_host_bridge():
    root = Path(__file__).resolve().parents[1]
    path = root / "tools" / "local_ai_host_bridge.py"
    spec = importlib.util.spec_from_file_location("hacs_local_ai_host_bridge", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_pst_session_manager_riusa_view_e_separa_import():
    module = _load_local_signer()
    module._pst_session_cache.clear()
    try:
        view = module._get_or_create_pst_session(
            cert_thumbprint="CERT-123",
            tribunale="0800570152",
            base_url="https://ext.processotelematico.giustizia.it",
            cf_avvocato="RSSMRA80A01H501Z",
            purpose="view",
            cert_key="CERT-123",
        )
        reused = module._get_or_create_pst_session(
            session_id=view["session_id"],
            cert_thumbprint="CERT-123",
            tribunale="0800570152",
            base_url="https://ext.processotelematico.giustizia.it",
            cf_avvocato="RSSMRA80A01H501Z",
            purpose="view",
            cert_key="CERT-123",
        )
        import_session = module._get_or_create_pst_session(
            session_id=view["session_id"],
            cert_thumbprint="CERT-123",
            tribunale="0800570152",
            base_url="https://ext.processotelematico.giustizia.it",
            cf_avvocato="RSSMRA80A01H501Z",
            purpose="import",
            cert_key="CERT-123",
        )

        assert reused["session_id"] == view["session_id"]
        assert import_session["session_id"] != view["session_id"]
        assert view["purpose"] == "view"
        assert import_session["purpose"] == "import"
        assert Path(view["cookie_file"]).exists()
        assert hasattr(module._pst_session_cache[view["session_id"]]["lock"], "acquire")
        assert not any("pin" in key.lower() for key in module._pst_session_cache[view["session_id"]])
    finally:
        for session_id in list(module._pst_session_cache):
            module._drop_pst_session(session_id)


def test_pst_session_manager_scaduta_restituisce_errore_controllato():
    module = _load_local_signer()
    module._pst_session_cache.clear()
    try:
        session = module._get_or_create_pst_session(
            cert_thumbprint="CERT-EXPIRED",
            tribunale="0800570152",
            base_url="https://ext.processotelematico.giustizia.it",
            cf_avvocato="RSSMRA80A01H501Z",
            purpose="view",
        )
        module._pst_session_cache[session["session_id"]]["expires_at"] = (
            module._utcnow_naive() - module.timedelta(seconds=1)
        )
        with pytest.raises(RuntimeError, match="session_expired"):
            module._get_or_create_pst_session(
                session_id=session["session_id"],
                cert_thumbprint="CERT-EXPIRED",
                tribunale="0800570152",
                base_url="https://ext.processotelematico.giustizia.it",
                cf_avvocato="RSSMRA80A01H501Z",
                purpose="view",
            )
    finally:
        for session_id in list(module._pst_session_cache):
            module._drop_pst_session(session_id)


def test_local_signer_logs_recent_espone_coda_sanificata(tmp_path, monkeypatch):
    module = _load_local_signer()
    captured = {}
    (tmp_path / "local_signer.err.log").write_text(
        "10:00:01 [LocalSigner] INFO avvio\nPIN=123456\n10:00:02 PST ricerca-snapshot\n",
        encoding="utf-8",
    )

    class _FakeHandler:
        path = "/logs/recent?lines=20"

        def _query_params(self):
            return {"lines": "20"}

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    monkeypatch.setattr(module, "_THIS_DIR", tmp_path)

    module._Handler._logs_recent(_FakeHandler())

    assert captured["status"] == 200
    payload = captured["payload"]
    assert payload["ok"] is True
    assert payload["versione"] == module.VERSION
    err_log = next(item for item in payload["logs"] if item["name"] == "local_signer.err.log")
    assert "PST ricerca-snapshot" in err_log["tail"]
    assert "PIN=[omesso]" in err_log["tail"]
    assert "123456" not in err_log["tail"]


def test_wizard_pst_usa_snapshot_e_sessione_unica_anche_per_download():
    root = Path(__file__).resolve().parents[1]
    template = (root / "web" / "templates" / "portale" / "acquisizione_wizard.html").read_text(
        encoding="utf-8"
    )
    signer = (root / "tools" / "local_signer.py").read_text(encoding="utf-8")

    assert "/pst/ricerca-snapshot" in signer
    assert "/pst/ricerca-snapshot" in template
    assert "function awCanUsePstSearchSnapshot" in template
    assert "/pst/fascicolo-snapshot" in signer
    assert "/pst/fascicolo-snapshot" in template
    assert "AW_PST_SNAPSHOT_PROMISE" in template
    assert "/pst/download-documenti-batch" in template
    assert "purpose: 'view'" in template
    assert "purpose: 'import'" not in template
    assert "AW_PST_IMPORT_SESSION?.session_id" not in template
    assert "function awGetActivePstSession" in template
    assert "pst_session_id: activeSession?.session_id || ''" in template
    assert "`${AW_PST_LS_BASE}/pst/preflight-auth`" not in template
    assert "`${AW_PST_LS_BASE}/pst/documenti`" not in template
    preview_fn = template[
        template.index("async function awPstPreviewViaLocalSigner"):
        template.index("function awMapLocalSignerSearchRows")
    ]
    assert preview_fn.index("AW_STATE.pstSnapshot?.documenti?.length") < preview_fn.index(
        "awEnsurePstCertReady"
    )


def test_local_signer_pst_curl_attiva_foreground_prompt_pin_windows():
    root = Path(__file__).resolve().parents[1]
    source = (root / "tools" / "local_signer.py").read_text(encoding="utf-8")

    assert "def _windows_pin_prompt_foreground_pump" in source
    assert "def _run_curl_with_pin_foreground" in source
    assert '"sicurezza di windows"' in source
    assert '"windows security"' in source
    assert '"credential"' in source
    assert '"credentialuibroker"' in source
    assert '"bit4id"' in source
    assert '"minva"' in source
    assert "EnumChildWindows" in source
    assert "GetClassNameW" in source
    assert "QueryFullProcessImageNameW" in source
    assert "AttachThreadInput" in source
    assert "SetWindowPos" in source
    assert "FlashWindow" in source
    assert "CREATE_NO_WINDOW" in source
    assert "STARTF_USESHOWWINDOW" in source
    assert source.count("_run_curl_with_pin_foreground(") >= 5

    raw = source[
        source.index("def _soap_call_curl_raw"):
        source.index("def _soap_call_curl_batch_raw")
    ]
    batch = source[
        source.index("def _soap_call_curl_batch_raw("):
        source.index("def _soap_call_curl_batch_raw_best_effort")
    ]
    best_effort_start = source.index("def _soap_call_curl_batch_raw_best_effort")
    best_effort = source[
        best_effort_start:
        source.index("def _soap_call_curl", best_effort_start + 1)
    ]
    preflight_start = source.index("def _pst_preflight_auth_curl")
    preflight = source[
        preflight_start:
        source.index("def _esc", preflight_start + 1)
    ]

    assert "_run_curl_with_pin_foreground(" in raw
    assert "_run_curl_with_pin_foreground(" in batch
    assert "_run_curl_with_pin_foreground(" in best_effort
    assert "_run_curl_with_pin_foreground(" in preflight


def test_run_curl_windows_silenzia_console_senza_perdere_foreground_pin(monkeypatch):
    module = _load_local_signer()
    captured = {}

    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(module.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(module.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(module.subprocess, "SW_HIDE", 0, raising=False)
    monkeypatch.setattr(
        module,
        "_windows_pin_prompt_foreground_pump",
        lambda stop_event, deadline_seconds: None,
    )

    def _fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(module.subprocess, "run", _fake_run)

    result = module._run_curl_with_pin_foreground(
        ["curl.exe", "--version"],
        capture_output=True,
        timeout=7,
        creationflags=0x00000002,
    )

    assert result.returncode == 0
    assert captured["cmd"][0] == "curl.exe"
    assert captured["kwargs"]["capture_output"] is True
    assert captured["kwargs"]["timeout"] == 7
    assert captured["kwargs"]["creationflags"] & 0x08000000
    assert captured["kwargs"]["creationflags"] & 0x00000002
    startupinfo = captured["kwargs"].get("startupinfo")
    if startupinfo is not None:
        assert getattr(startupinfo, "dwFlags", 0) & 1
        assert getattr(startupinfo, "wShowWindow", None) == 0


def test_local_signer_foreground_pin_riconosce_dialog_windows_senza_titolo():
    module = _load_local_signer()

    assert module._windows_pin_prompt_candidate_score("", "Credential Dialog Xaml Host", "") >= 5
    assert module._windows_pin_prompt_candidate_score(
        "Richiesta credenziali",
        "#32770",
        "Inserire il PIN della smart card",
    ) >= 15
    assert module._windows_pin_prompt_candidate_score(
        "",
        "ApplicationFrameWindow",
        "",
        r"C:\Windows\System32\CredentialUIBroker.exe",
    ) >= 9
    assert module._windows_pin_prompt_candidate_score(
        "",
        "NativeHWNDHost",
        "",
        r"C:\Program Files\Bit4id\MinVa\MinVa.exe",
    ) >= 9
    assert module._windows_pin_prompt_candidate_score("Google Chrome", "Chrome_WidgetWin_1", "") == 0


def test_pst_import_test_reale_note_blinda_passaggi_grafica_e_multi_studio():
    root = Path(__file__).resolve().parents[1]
    note = (
        root
        / "docs"
        / "specs"
        / "ministero"
        / "PST_FASCICOLO_IMPORT_TEST_REALE_2026-05-26.md"
    ).read_text(encoding="utf-8")
    baseline = (
        root
        / "docs"
        / "specs"
        / "ministero"
        / "PST_LOCAL_SIGNER_BASELINE_CERTIFICATO.md"
    ).read_text(encoding="utf-8")

    assert "Tribunale di Palmi" in note
    assert "R.G. 274/2026" in note
    assert "`B6A03AE6`" in note
    assert "`/pst/download-documenti-batch`" in note
    assert "non deve tornare al download singolo ripetuto" in note
    assert "Dati fascicolo" in note
    assert "Documenti nel fascicolo" in note
    assert "Importazione completata con avvisi" in note
    assert "codice fiscale ricavato dal certificato selezionato prevale" in note
    assert "non deve cercare la finestra PIN nella barra delle applicazioni" in note
    assert "PST_FASCICOLO_IMPORT_TEST_REALE_2026-05-26.md" in baseline


def test_pst_preflight_import_riusa_sessione_view_attiva_senza_nuovo_handshake(monkeypatch):
    module = _load_local_signer()
    captured = {}
    calls = {"preflight": 0, "ensure": 0}

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0580010",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "RSSMRA80A01H501Z",
                "purpose": "import",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    monkeypatch.setattr(module, "_curl_disponibile", lambda: True)
    monkeypatch.setattr(
        module,
        "_risolvi_base_pst_runtime",
        lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
    )
    monkeypatch.setattr(module, "_require_certificato_pst", lambda thumbprint: "AABBCC11")
    monkeypatch.setattr(module, "_cf_avvocato_pst", lambda cf, thumbprint: "RSSMRA80A01H501Z")
    monkeypatch.setattr(
        module,
        "_find_view_session_for_cert",
        lambda thumbprint, tribunale: {
            "session_id": "SID-VIEW",
            "purpose": "view",
            "tribunale": tribunale,
            "cert_thumbprint": thumbprint,
            "auth_ready": True,
            "base_url": "https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SIL",
        },
    )

    def _unexpected_preflight(**kwargs):
        calls["preflight"] += 1
        return {"ok": True}

    def _unexpected_ensure(*args, **kwargs):
        calls["ensure"] += 1
        raise AssertionError("non deve creare una seconda sessione import")

    monkeypatch.setattr(module, "_pst_preflight_auth_curl", _unexpected_preflight)
    monkeypatch.setattr(module, "_ensure_pst_session_entry", _unexpected_ensure)

    module._Handler._pst_preflight_auth(_FakeHandler())

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["cached"] is True
    assert captured["payload"]["pst_session_id"] == "SID-VIEW"
    assert captured["payload"]["pst_session_purpose"] == "view"
    assert calls == {"preflight": 0, "ensure": 0}


def test_pst_download_batch_riusa_sessione_view_anche_se_client_chiede_import(monkeypatch):
    module = _load_local_signer()
    captured = {}
    calls = {}

    class _NullLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0580010",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "RSSMRA80A01H501Z",
                "pst_session_id": "SID-VIEW",
                "purpose": "import",
                "preflight_auth": False,
                "documents": [{"id_documento": "DOC-1", "nome_documento": "atto.pdf"}],
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    monkeypatch.setattr(module, "_curl_disponibile", lambda: True)
    monkeypatch.setattr(
        module,
        "_resolve_pst_session_entry",
        lambda session_id: {
            "session_id": session_id,
            "purpose": "view",
            "cookie_file": "C:\\temp\\pst.cookies",
            "auth_ready": True,
            "base_url": "https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SIL",
        },
    )
    monkeypatch.setattr(
        module,
        "_risolvi_base_pst_runtime",
        lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
    )
    monkeypatch.setattr(module, "_risolvi_codice_ufficio_pst", lambda tribunale: "0151460094")
    monkeypatch.setattr(module, "_require_certificato_pst", lambda thumbprint: "AABBCC11")
    monkeypatch.setattr(module, "_cf_avvocato_pst", lambda cf, thumbprint: "RSSMRA80A01H501Z")
    monkeypatch.setattr(module, "_pst_session_lock_for", lambda session_entry: _NullLock())

    def _fake_ensure(requested_session_id, **kwargs):
        calls["ensure_purpose"] = kwargs.get("purpose")
        calls["requested_session_id"] = requested_session_id
        return (
            {
                "session_id": requested_session_id,
                "purpose": kwargs.get("purpose"),
                "cookie_file": "C:\\temp\\pst.cookies",
                "auth_ready": True,
                "cf_avvocato": "RSSMRA80A01H501Z",
            },
            False,
        )

    def _fake_prepare(session_entry, **kwargs):
        calls["prepare_force"] = kwargs.get("force")
        return session_entry, True

    def _fake_batch(**kwargs):
        calls["batch_cookie_file"] = kwargs.get("cookie_file")
        calls["batch_do_preflight"] = kwargs.get("do_preflight")
        return {
            "ok": True,
            "files": [],
            "failures": [],
            "documenti_richiesti": 1,
            "documenti_scaricati": 0,
        }

    monkeypatch.setattr(module, "_ensure_pst_session_entry", _fake_ensure)
    monkeypatch.setattr(module, "_pst_prepare_authenticated_session", _fake_prepare)
    monkeypatch.setattr(module, "_pst_download_documenti_batch_payloads", _fake_batch)
    monkeypatch.setattr(module, "_update_pst_session", lambda *args, **kwargs: None)

    module._Handler._pst_download_documenti_batch(_FakeHandler())

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["pst_session_id"] == "SID-VIEW"
    assert captured["payload"]["pst_session_purpose"] == "view"
    assert calls["requested_session_id"] == "SID-VIEW"
    assert calls["ensure_purpose"] == "view"
    assert calls["prepare_force"] is False
    assert calls["batch_do_preflight"] is False
    assert calls["batch_cookie_file"] == "C:\\temp\\pst.cookies"


def test_pst_download_batch_recupera_sessione_view_se_client_non_la_invia(monkeypatch):
    module = _load_local_signer()
    captured = {}
    calls = {}

    class _NullLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0580010",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "RSSMRA80A01H501Z",
                "preflight_auth": False,
                "documents": [{"id_documento": "DOC-1", "nome_documento": "atto.pdf"}],
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    monkeypatch.setattr(module, "_curl_disponibile", lambda: True)
    monkeypatch.setattr(
        module,
        "_find_view_session_for_cert",
        lambda thumbprint, tribunale: {
            "session_id": "SID-VIEW",
            "purpose": "view",
            "tribunale": tribunale,
            "cert_thumbprint": thumbprint,
            "auth_ready": True,
            "base_url": "https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SIL",
        },
    )
    monkeypatch.setattr(
        module,
        "_resolve_pst_session_entry",
        lambda session_id: {
            "session_id": session_id,
            "purpose": "view",
            "cookie_file": "C:\\temp\\pst.cookies",
            "auth_ready": True,
            "base_url": "https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SIL",
        },
    )
    monkeypatch.setattr(
        module,
        "_risolvi_base_pst_runtime",
        lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
    )
    monkeypatch.setattr(module, "_risolvi_codice_ufficio_pst", lambda tribunale: "0151460094")
    monkeypatch.setattr(module, "_require_certificato_pst", lambda thumbprint: "AABBCC11")
    monkeypatch.setattr(module, "_cf_avvocato_pst", lambda cf, thumbprint: "RSSMRA80A01H501Z")
    monkeypatch.setattr(module, "_pst_session_lock_for", lambda session_entry: _NullLock())

    def _fake_ensure(requested_session_id, **kwargs):
        calls["requested_session_id"] = requested_session_id
        calls["ensure_purpose"] = kwargs.get("purpose")
        calls["ensure_base_url"] = kwargs.get("base_url")
        return (
            {
                "session_id": requested_session_id,
                "purpose": kwargs.get("purpose"),
                "cookie_file": "C:\\temp\\pst.cookies",
                "auth_ready": True,
                "cf_avvocato": "RSSMRA80A01H501Z",
                "base_url": kwargs.get("base_url"),
            },
            False,
        )

    monkeypatch.setattr(module, "_ensure_pst_session_entry", _fake_ensure)
    monkeypatch.setattr(module, "_pst_prepare_authenticated_session", lambda session_entry, **kwargs: (session_entry, True))
    def _fake_download_payloads(**kwargs):
        calls["batch_base_url"] = kwargs.get("base_url")
        return {
            "ok": True,
            "files": [],
            "failures": [],
            "documenti_richiesti": 1,
            "documenti_scaricati": 0,
        }

    monkeypatch.setattr(module, "_pst_download_documenti_batch_payloads", _fake_download_payloads)
    monkeypatch.setattr(module, "_update_pst_session", lambda *args, **kwargs: None)

    module._Handler._pst_download_documenti_batch(_FakeHandler())

    assert captured["status"] == 200
    assert captured["payload"]["pst_session_id"] == "SID-VIEW"
    assert captured["payload"]["pst_session_purpose"] == "view"
    assert calls["requested_session_id"] == "SID-VIEW"
    assert calls["ensure_purpose"] == "view"
    assert calls["ensure_base_url"].endswith("/JPW_SIL")
    assert calls["batch_base_url"].endswith("/JPW_SIL")


def _local_signer_version():
    return _load_local_signer().VERSION


def test_local_signer_dist_allineato_a_sorgente_e_installer_versionati(tmp_path):
    root = Path(__file__).resolve().parents[1]
    version = _local_signer_version()
    source = root / "tools" / "local_signer.py"
    dist = root / "tools" / "dist"

    assert (dist / "local_signer.py").read_text(encoding="utf-8") == source.read_text(
        encoding="utf-8"
    )
    for name in (
        f"SetupLocalSigner-{version}.exe",
        "SetupLocalSigner.exe",
        f"InstallaLocalSigner-{version}.command",
        f"InstallaLocalSigner-{version}.run",
        f"LocalSigner-{version}.txt",
    ):
        assert (dist / name).exists(), name

    assert (dist / f"SetupLocalSigner-{version}.exe").read_bytes() == (
        dist / "SetupLocalSigner.exe"
    ).read_bytes()
    exe_path = dist / "SetupLocalSigner.exe"
    assert exe_path.read_bytes().startswith(b"MZ")
    assert exe_path.stat().st_size < 400_000
    if os.name == "nt":
        target = tmp_path / "iexpress-probe"
        target.mkdir()
        probe = subprocess.run(
            [str(exe_path), "/Q", f"/T:{target}", "/C:cmd /c exit 0"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        assert probe.returncode == 0
    assert f"Versione: {version}" in (dist / f"LocalSigner-{version}.txt").read_text(
        encoding="utf-8"
    )


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


def test_errore_dns_portali_telematici_e_istruttivo():
    module = _load_local_signer()

    msg_pdp = module._curl_errore_leggibile(
        6,
        "",
        "https://appweb.giustizia.it/snt/RicercaFascicoliPenaleService?wsdl",
    )
    msg_pat = module._curl_errore_leggibile(
        6,
        "",
        "https://pac.giustizia-amministrativa.it/pac/RicercaRicorsiService?wsdl",
    )
    msg_ptt = module._curl_errore_leggibile(
        6,
        "",
        "https://sigit.finanze.it/ptt/RicercaFascicoliTributarioService?wsdl",
    )

    assert "appweb.giustizia.it" in msg_pdp
    assert "PCT_PDP_BASE_URL" in msg_pdp
    assert "pac.giustizia-amministrativa.it" in msg_pat
    assert "PCT_PAT_BASE_URL" in msg_pat
    assert "sigit.finanze.it" in msg_ptt
    assert "PCT_SIGIT_BASE_URL" in msg_ptt


def test_wsdl_zeep_dns_error_diventa_messaggio_operativo():
    module = _load_local_signer()
    original = sys.modules.get("zeep")

    class _FakeZeep:
        class Client:
            def __init__(self, wsdl):
                raise RuntimeError(
                    "HTTPSConnectionPool(host='appweb.giustizia.it', port=443): "
                    "Max retries exceeded with url: /snt/RicercaFascicoliPenaleService?wsdl "
                    "(Caused by NameResolutionError(\"getaddrinfo failed\"))"
                )

    module._ZEEP_WSDL_CACHE.clear()
    sys.modules["zeep"] = _FakeZeep
    try:
        try:
            module._get_zeep_wsdl_client(
                "https://appweb.giustizia.it/snt/RicercaFascicoliPenaleService?wsdl"
            )
            raise AssertionError("Il caricamento WSDL doveva fallire con messaggio istruttivo.")
        except RuntimeError as exc:
            msg = str(exc)
            assert "appweb.giustizia.it" in msg
            assert "PCT_PDP_BASE_URL" in msg
    finally:
        if original is None:
            sys.modules.pop("zeep", None)
        else:
            sys.modules["zeep"] = original


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


def test_local_signer_risolve_proxy_pst_cassazione_sul_catalogo_ufficiale():
    module = _load_local_signer()

    base = module._risolvi_base_pst_runtime("9990000")

    assert base.endswith("/pda/pycons/GLCC/JPW_CASSCI")
    assert module._pst_namespace_qbuilder(base) == "urn:CONS-CASSCI"


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


def test_firma_inline_usa_privkey_sign_e_signed_attrs(monkeypatch):
    module = _load_local_signer()
    chiamate = {}

    fake_attribute = SimpleNamespace(CLASS="class", VALUE="value")
    fake_object_class = SimpleNamespace(PRIVATE_KEY="private_key", CERTIFICATE="certificate")
    fake_mechanism = SimpleNamespace(SHA256_RSA_PKCS="sha256-rsa")

    class _FakePrivateKey:
        def sign(self, payload, mechanism=None):
            chiamate["payload"] = payload
            chiamate["mechanism"] = mechanism
            return b"firma-inline"

    class _FakeCert:
        def __getitem__(self, key):
            if key == fake_attribute.VALUE:
                return b"certificato-der-fittizio"
            raise KeyError(key)

    class _FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get_objects(self, query):
            kind = query[fake_attribute.CLASS]
            if kind == fake_object_class.PRIVATE_KEY:
                return [_FakePrivateKey()]
            if kind == fake_object_class.CERTIFICATE:
                return [_FakeCert()]
            return []

        def sign(self, *args, **kwargs):
            raise AssertionError("session.sign non deve essere usato nel fallback inline")

    class _FakeToken:
        def open(self, user_pin=None):
            assert user_pin == "123456"
            return _FakeSession()

    class _FakeSlot:
        def get_token(self):
            return _FakeToken()

    class _FakeLib:
        def get_slots(self, token_present=True):
            assert token_present is True
            return [_FakeSlot()]

    fake_pkcs11 = SimpleNamespace(
        lib=lambda _path: _FakeLib(),
        Attribute=fake_attribute,
        Mechanism=fake_mechanism,
        ObjectClass=fake_object_class,
    )

    monkeypatch.setitem(sys.modules, "pkcs11", fake_pkcs11)
    monkeypatch.setattr(
        "pct.firma_pkcs11._build_cades_bes",
        lambda documento, signature_bytes, cert_der, signed_attrs_der=None, detached=False: {
            "documento": documento,
            "firma": signature_bytes,
            "cert_der": cert_der,
            "signed_attrs_der": signed_attrs_der,
            "detached": detached,
        },
    )
    monkeypatch.setattr(
        module,
        "_build_cades_bes_inline",
        lambda documento, firma, cert_der, signed_attrs_der=None: {
            "documento": documento,
            "firma": firma,
            "cert_der": cert_der,
            "signed_attrs_der": signed_attrs_der,
        },
    )

    firmato, info = module._firma_inline("C:\\Windows\\System32\\bit4xpki.dll", b"abc", "123456", 0)

    assert firmato["firma"] == b"firma-inline"
    assert firmato["documento"] == b"abc"
    assert firmato["cert_der"] == b"certificato-der-fittizio"
    assert firmato["signed_attrs_der"] == chiamate["payload"]
    assert firmato["detached"] is False
    assert chiamate["payload"] != b"abc"
    assert chiamate["mechanism"] == fake_mechanism.SHA256_RSA_PKCS
    assert info == {"intestatario": "", "scadenza": ""}


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
        def _fake_run(cmd, capture_output, text, timeout, encoding, errors, **kwargs):
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
        def _fake_run(cmd, capture_output, text, timeout, encoding, errors, **kwargs):
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


def test_preflight_auth_timeout_expired_non_diventa_errore_500():
    module = _load_local_signer()

    orig_run = module.subprocess.run
    try:
        def _fake_run(cmd, capture_output, text, timeout, encoding, errors, **kwargs):
            raise module.subprocess.TimeoutExpired(cmd, timeout)

        module.subprocess.run = _fake_run
        esito = module._pst_preflight_auth_curl(
            "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP",
            cert_thumbprint="AABBCC11",
        )
    finally:
        module.subprocess.run = orig_run

    assert esito["ok"] is True
    assert esito["http_code"] is None
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


def test_cors_consentito_per_origine_hacs_default():
    module = _load_local_signer()

    assert module._origin_cors_consentita("https://app.iusentra.it") is True
    assert (
        module._origin_cors_consentita("https://studio-legale-pct-production.up.railway.app")
        is True
    )


def test_cors_consentito_per_origine_hacs_configurata():
    module = _load_local_signer()

    orig = module.LOCAL_SIGNER_ALLOWED_ORIGINS
    try:
        module.LOCAL_SIGNER_ALLOWED_ORIGINS = (
            "https://studio-legale-pct-production.up.railway.app, "
            "https://studio-esterno.example.test/"
        )
        assert module._origin_cors_consentita("https://studio-legale-pct-production.up.railway.app")
        assert module._origin_cors_consentita("https://studio-esterno.example.test")
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
    assert ("Access-Control-Allow-Headers", "Content-Type, X-Signer-Token, X-Requested-With") in captured


def test_endpoint_pec_locale_viene_dispatchato_dal_local_signer():
    module = _load_local_signer()
    captured = {}
    original = module.test_pec_smtp_local

    def _fake_test(payload):
        captured["payload"] = payload
        return {"ok": True, "messaggio": "ok locale"}

    class _FakeHandler:
        path = "/pec/smtp/test"

        def _cors_ok(self):
            return True

        def _read_json(self):
            return {"smtp_host": "smtp.example.test"}

        def _send_json(self, data, status=200):
            captured["data"] = data
            captured["status"] = status

        def _pec_smtp_test(self):
            module._Handler._pec_smtp_test(self)

    try:
        module.test_pec_smtp_local = _fake_test
        module._Handler.do_POST(_FakeHandler())
    finally:
        module.test_pec_smtp_local = original

    assert captured["status"] == 200
    assert captured["payload"]["smtp_host"] == "smtp.example.test"
    assert captured["data"]["ok"] is True


def test_ui_pec_locale_auto_avvia_signer_e_mostra_pacchetto():
    root = Path(__file__).resolve().parents[1]
    template = (root / "web" / "templates" / "impostazioni" / "index.html").read_text(
        encoding="utf-8"
    )
    script = (root / "web" / "static" / "js" / "impostazioni-common.js").read_text(
        encoding="utf-8"
    )
    firma_script = (root / "web" / "static" / "js" / "impostazioni-firma.js").read_text(
        encoding="utf-8"
    )
    ai_script = (root / "web" / "static" / "js" / "impostazioni-ai.js").read_text(
        encoding="utf-8"
    )

    assert "btn-test-smtp-locale" in template
    assert "Testa SMTP" in template
    assert "data-windows-url" in template
    assert "data-latest-version" in template
    assert "data-has-saved-password" in template
    assert "testPecSmtpLocale" in script
    assert "iusentra.pec.localSignerPassword.once" in script
    assert "collectPecPasswordForLocalSigner" in script
    assert "Connessione SMTP PEC riuscita." in script
    assert "iusentra-local-signer://restart" in script
    assert "iusentra-local-signer://restart" in firma_script
    assert "iusentra-local-signer://restart" in ai_script
    assert "isDesktopLocalSignerHost" in script
    assert "isDesktopLocalSignerHost" in firma_script
    assert "Da mobile o tablet il controllo non viene eseguito" in script
    assert "Da mobile o tablet il controllo non viene eseguito" in firma_script
    assert "localSignerOutdatedHtml" in script
    assert "compareVersions" in script
    assert "viene inviata solo al Local Signer su questo dispositivo" in script
    assert "fetch('/impostazioni/test/pec-smtp'" not in script
    assert "Diagnostica server (non invio reale)" in template
    assert "L'invio PEC reale deve passare dal PC locale tramite Local Signer" in template
    assert "localSignerMissingMessage" in firma_script
    assert "ensureLocalSignerCompanionStarted" in ai_script
    assert "Local Signer non rilevato" in script
    assert "Scarica Local Signer per Windows" in script


def test_metadata_impostazioni_windows_pubblica_solo_exe():
    from web.blueprints.impostazioni import _local_signer_meta

    meta = _local_signer_meta()

    assert meta["windows_filename"].startswith("SetupLocalSigner-")
    assert meta["windows_filename"].endswith(".exe")
    assert meta["windows_script_filename"] == meta["windows_filename"]
    assert meta["windows_installer_filename"] == meta["windows_filename"]
    assert not meta["windows_script_filename"].endswith(".ps1")


def test_ai_status_bridge_locale_restituisce_snapshot():
    module = _load_local_signer()
    original = module._get_local_ai_bridge
    captured = {}

    class _FakeBridge:
        def health_snapshot(self, payload):
            captured["payload"] = payload
            return {
                "ok": True,
                "runtime": {"status": "ready"},
                "installer": {"strategy_label": "Companion locale"},
                "models": [],
                "counts": {},
            }

    class _FakeHandler:
        command = "GET"
        path = "/ai/status?base_url=http://127.0.0.1:11434/api&chat_model=gemma3%3A1b"
        headers = {}

        def _read_json(self):
            return {}

        def _query_params(self):
            return module._Handler._query_params(self)

        def _local_ai_request_payload(self, payload_override=None):
            return module._Handler._local_ai_request_payload(self, payload_override)

        def _stream_sse(self, iterable):
            captured["stream"] = iterable

        def _ai_facade(self):
            return module._Handler._ai_facade(self)

        def _send_json(self, data, status=200):
            captured["data"] = data
            captured["status"] = status

    try:
        module._get_local_ai_bridge = lambda: _FakeBridge()
        module._Handler._ai_status(_FakeHandler())
    finally:
        module._get_local_ai_bridge = original

    assert captured["status"] == 200
    assert captured["data"]["runtime"]["status"] == "ready"
    assert captured["payload"]["base_url"] == "http://127.0.0.1:11434/api"
    assert captured["payload"]["chat_model"] == "gemma3:1b"


def test_root_locale_risponde_come_ping():
    module = _load_local_signer()
    captured = {}

    class _FakeHandler:
        headers = {}
        path = "/"

        def _cors_ok(self):
            return True

        def _send_json(self, data, status=200):
            captured["data"] = data
            captured["status"] = status

        def _ping(self):
            self._send_json({"ok": True, "versione": module.VERSION})

    module._Handler.do_GET(_FakeHandler())

    assert captured["status"] == 200
    assert captured["data"]["ok"] is True
    assert captured["data"]["versione"] == module.VERSION


def test_ai_bootstrap_bridge_locale_usa_force_e_payload():
    module = _load_local_signer()
    original = module._get_local_ai_bridge
    captured = {}

    class _FakeBridge:
        def bootstrap_runtime(self, payload, force=False):
            captured["payload"] = payload
            captured["force"] = force
            return {"ok": True, "result": {"status": "ready"}, "status_payload": {"runtime": {"status": "ready"}}}

    class _FakeHandler:
        command = "POST"
        path = "/ai/bootstrap"
        headers = {}

        def _read_json(self):
            return {
                "force": True,
                "base_url": "http://127.0.0.1:11434/api",
                "chat_model": "gemma3:1b",
            }

        def _query_params(self):
            return {}

        def _local_ai_request_payload(self, payload_override=None):
            return module._Handler._local_ai_request_payload(self, payload_override)

        def _stream_sse(self, iterable):
            captured["stream"] = iterable

        def _ai_facade(self):
            return module._Handler._ai_facade(self)

        def _send_json(self, data, status=200):
            captured["data"] = data
            captured["status"] = status

    try:
        module._get_local_ai_bridge = lambda: _FakeBridge()
        module._Handler._ai_bootstrap(_FakeHandler())
    finally:
        module._get_local_ai_bridge = original

    assert captured["status"] == 200
    assert captured["data"]["result"]["status"] == "ready"
    assert captured["force"] is True
    assert captured["payload"]["chat_model"] == "gemma3:1b"


def test_ai_attachments_parse_locale_restituisce_documenti_normalizzati():
    module = _load_local_signer()
    captured = {}

    payload_file = {
        "name": "nota.txt",
        "mime_type": "text/plain",
        "content_base64": "data:text/plain;base64," + base64.b64encode("Promemoria deposito telematico".encode("utf-8")).decode("ascii"),
    }

    class _FakeHandler:
        headers = {}
        command = "POST"
        path = "/ai/attachments/parse"

        def _read_json(self):
            return {"files": [payload_file]}

        def _query_params(self):
            return {}

        def _local_ai_request_payload(self, payload_override=None):
            return module._Handler._local_ai_request_payload(self, payload_override)

        def _stream_sse(self, iterable):
            captured["stream"] = iterable

        def _ai_facade(self):
            return module._Handler._ai_facade(self)

        def _send_json(self, data, status=200):
            captured["data"] = data
            captured["status"] = status

    module._Handler._ai_attachments_parse(_FakeHandler())

    assert captured["status"] == 200
    assert captured["data"]["ok"] is True
    assert captured["data"]["attachments"][0]["name"] == "nota.txt"
    assert "DOCUMENTI CARICATI DALL'UTENTE" in captured["data"]["prompt_block"]


def test_ai_rag_query_bridge_locale_inoltra_prompt_e_fonti():
    module = _load_local_signer()
    original = module._get_local_ai_bridge
    captured = {}

    class _FakeBridge:
        def rag_query(self, payload):
            captured["payload"] = payload
            return {
                "ok": True,
                "answer": "Risposta locale.",
                "citations": ["Fonte A"],
                "sources": payload.get("sources") or [],
            }

    class _FakeHandler:
        command = "POST"
        path = "/ai/rag/query"
        headers = {}

        def _read_json(self):
            return {
                "question": "Qual e' la prossima attivita' utile?",
                "prompt": "Contesto pronto",
                "sources": [{"id": "chunk-1"}],
                "base_url": "http://127.0.0.1:11434/api",
            }

        def _query_params(self):
            return {}

        def _local_ai_request_payload(self, payload_override=None):
            return module._Handler._local_ai_request_payload(self, payload_override)

        def _stream_sse(self, iterable):
            captured["stream"] = iterable

        def _ai_facade(self):
            return module._Handler._ai_facade(self)

        def _send_json(self, data, status=200):
            captured["data"] = data
            captured["status"] = status

    try:
        module._get_local_ai_bridge = lambda: _FakeBridge()
        module._Handler._ai_rag_query(_FakeHandler())
    finally:
        module._get_local_ai_bridge = original

    assert captured["status"] == 200
    assert captured["data"]["ok"] is True
    assert captured["payload"]["prompt"] == "Contesto pronto"
    assert captured["payload"]["question"] == "Qual e' la prossima attivita' utile?"
    assert captured["payload"]["base_url"] == "http://127.0.0.1:11434/api"


def test_local_ai_bridge_risolve_modello_effettivo_su_installato_disponibile(tmp_path):
    module = _load_local_ai_host_bridge()
    bridge = module.LocalAiHostBridge(root_dir=tmp_path)

    resolved = bridge.resolve_effective_models(
        {"enabled": True, "base_url": "http://127.0.0.1:11434/api", "chat_model": "", "embed_model": "", "keep_alive": "10m", "auto_bootstrap": True, "auto_index_documents": True},
        {"profile": "strong"},
        installed_models=[{"name": "gemma3:1b"}, {"name": "embeddinggemma:300m"}],
        running_models=[{"name": "gemma3:1b"}],
    )

    assert resolved["preferred_chat"] == "gemma3:4b"
    assert resolved["chat"] == "gemma3:1b"
    assert resolved["chat_source"] == "fallback"
    assert resolved["embed"] == "embeddinggemma:300m"


def test_local_ai_bridge_chat_usa_modello_effettivo_disponibile(tmp_path, monkeypatch):
    module = _load_local_ai_host_bridge()
    captured = {}

    class DummyClient:
        def __init__(self, base_url):
            self.base_url = base_url

        def get_version(self):
            return "0.20.5"

        def list_models(self):
            return [{"name": "gemma3:1b"}, {"name": "embeddinggemma:300m"}]

        def list_running_models(self):
            return [{"name": "gemma3:1b"}]

        def generate(self, model_name, prompt, keep_alive):
            captured["model_name"] = model_name
            captured["prompt"] = prompt
            captured["keep_alive"] = keep_alive
            return {"response": "ok"}

    monkeypatch.setattr(module, "OllamaLocalClient", DummyClient)
    bridge = module.LocalAiHostBridge(root_dir=tmp_path)
    monkeypatch.setattr(
        bridge,
        "detect_hardware",
        lambda: {"profile": "strong"},
    )

    result = bridge.chat("Ciao Lex")

    assert result["ok"] is True
    assert result["model"] == "gemma3:1b"
    assert captured["model_name"] == "gemma3:1b"


def test_local_ai_bridge_snapshot_windows_propone_installer_e_download_modello_automatico(tmp_path, monkeypatch):
    module = _load_local_ai_host_bridge()
    bridge = module.LocalAiHostBridge(root_dir=tmp_path)
    hardware = {
        "host_platform": "windows",
        "host_machine": "amd64",
        "profile": "medium",
    }
    monkeypatch.setattr(
        bridge,
        "fetch_latest_release",
        lambda **kwargs: {
            "version": "v0.20.7",
            "html_url": "https://example.test/releases/v0.20.7",
            "published_at": "2026-04-14T09:00:00Z",
            "assets": [
                {
                    "name": "OllamaSetup.exe",
                    "browser_download_url": "https://example.test/OllamaSetup.exe",
                    "size": 812000000,
                    "updated_at": "2026-04-14T09:00:00Z",
                },
                {
                    "name": "ollama-windows-amd64.zip",
                    "browser_download_url": "https://example.test/ollama-windows-amd64.zip",
                    "size": 781000000,
                    "updated_at": "2026-04-14T09:00:00Z",
                },
            ],
        },
    )

    snapshot = bridge.installer_snapshot(
        settings={"enabled": True},
        hardware=hardware,
        live_version=None,
    )

    assert snapshot["asset_name"] == "OllamaSetup.exe"
    assert snapshot["asset_label"] == "Installer consigliato"
    assert snapshot["asset_cta_label"] == "Scarica installer ufficiale"
    assert "profilo hardware" in snapshot["summary_body"]
    assert "profilo hardware" in snapshot["post_install_note"]


def test_local_ai_bridge_rag_query_stream_restituisce_token_e_fonti_finali(tmp_path, monkeypatch):
    module = _load_local_ai_host_bridge()

    class DummyClient:
        def __init__(self, base_url):
            self.base_url = base_url

        def get_version(self):
            return "0.20.5"

        def list_models(self):
            return [{"name": "gemma3:1b"}, {"name": "embeddinggemma:300m"}]

        def list_running_models(self):
            return [{"name": "gemma3:1b"}]

        def generate_stream(self, model_name, prompt, keep_alive):
            assert model_name == "gemma3:1b"
            assert "Contesto pronto" in prompt
            yield {"response": "Ciao "}
            yield {"response": "mondo"}
            yield {"done": True, "eval_count": 12}

    monkeypatch.setattr(module, "OllamaLocalClient", DummyClient)
    bridge = module.LocalAiHostBridge(root_dir=tmp_path)
    monkeypatch.setattr(bridge, "detect_hardware", lambda: {"profile": "strong"})

    events = list(
        bridge.rag_query_stream(
            {
                "question": "Che cosa devo fare adesso?",
                "prompt": "Contesto pronto",
                "sources": [{"id": "chunk-1", "citation": "Fonte 1"}],
            }
        )
    )

    assert events[0]["token"] == "Ciao "
    assert events[1]["token"] == "mondo"
    assert events[-1]["done"] is True
    assert events[-1]["answer"] == "Ciao mondo"
    assert events[-1]["citations"] == ["Fonte 1"]
    assert events[-1]["sources"][0]["id"] == "chunk-1"


def test_local_signer_launcher_windows_usa_avvio_silenzioso():
    installer = (Path(__file__).resolve().parents[1] / "tools" / "installa_local_signer_locale.ps1").read_text(encoding="utf-8")
    launcher = (Path(__file__).resolve().parents[1] / "tools" / "avvia_local_signer.bat").read_text(encoding="utf-8")

    assert 'set "SILENT_MODE=0"' in installer
    assert 'powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -FilePath $env:PYW -ArgumentList @($env:PY)"' in installer
    assert 'if "%SILENT_MODE%"=="1" exit /b 0' in installer
    assert "Register-LocalSignerScheduledTask" in installer
    assert "Register-LocalSignerStartupShortcut" in installer
    assert "IUSENTRA Local Signer.lnk" in installer
    assert "iusentra-local-signer://restart" in installer
    assert "iusentra-local-signer://update" in installer
    assert 'set "UPDATE_MODE=0"' in installer
    assert "IUSENTRA_LOCAL_SIGNER_UPDATE_URL" in installer
    assert "/polisWeb/local-signer/setup/windows" in installer
    assert "Invoke-Pip" in installer
    assert "PIP_NO_CACHE_DIR" in installer
    assert 'set "SILENT_MODE=0"' in launcher
    assert 'if "%SILENT_MODE%"=="1" exit /b 0' in launcher


def test_local_signer_update_endpoint_avvia_installer_ufficiale_windows(monkeypatch, tmp_path):
    module = _load_local_signer()
    calls = {}

    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setenv("IUSENTRA_LOCAL_SIGNER_UPDATE_URL", "https://app.iusentra.it/polisWeb/local-signer/setup/windows")

    class _FakePopen:
        def __init__(self, args, **kwargs):
            calls["args"] = args
            calls["kwargs"] = kwargs

    monkeypatch.setattr(module.subprocess, "Popen", _FakePopen)

    result = module._avvia_aggiornamento_local_signer()

    assert result["ok"] is True
    assert result["installer_url"] == "https://app.iusentra.it/polisWeb/local-signer/setup/windows"
    assert calls["args"][0] == "powershell"
    joined = " ".join(calls["args"])
    assert "Invoke-WebRequest" in joined
    assert "Start-Process" in joined
    assert "/Q" in joined


def test_local_signer_update_endpoint_rifiuta_url_non_ufficiale(monkeypatch):
    module = _load_local_signer()

    monkeypatch.setenv("IUSENTRA_LOCAL_SIGNER_UPDATE_URL", "https://example.test/SetupLocalSigner.exe")

    with pytest.raises(RuntimeError, match="non autorizzato"):
        module._local_signer_update_url()


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


def test_ping_windows_usa_il_filtro_cf_per_esporre_il_certificato_preferito():
    module = _load_local_signer()

    orig_platform = module.sys.platform
    orig_trova = module._trova_libreria
    orig_curl = module._curl_disponibile
    orig_lista = module._windows_lista_certificati
    orig_cached = module._ultimo_certificato_windows
    captured = {}

    class _FakeHandler:
        path = (
            "/ping?auto=1"
            "&prefer_issuer=ArubaPEC%20EU%20Authentica%20Certificates%20CA%20G1%7CArubaPEC%20EU%20Qualified%20Certificates%20CA%20G1"
            "&prefer_subject=auth%7Cautentica%7Cclient"
            "&prefer_cf=MNTRRT64L01L063H"
        )

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module.sys.platform = "win32"
        module._trova_libreria = lambda: None
        module._curl_disponibile = lambda: True
        module._windows_lista_certificati = lambda: [
            {
                "thumbprint": "QUAL-WRONG",
                "soggetto": "ROBERTO MONTAGNESE",
                "soggetto_completo": "CN=ROBERTO MONTAGNESE,SERIALNUMBER=CF:AAAAAA00A00A000A",
                "codice_fiscale": "AAAAAA00A00A000A",
                "emittente": "ArubaPEC EU Qualified Certificates CA G1",
                "scadenza": "2029-02-23",
            },
            {
                "thumbprint": "AUTH-CF",
                "soggetto": "ROBERTO MONTAGNESE",
                "soggetto_completo": "CN=ROBERTO MONTAGNESE,SERIALNUMBER=CF:MNTRRT64L01L063H",
                "codice_fiscale": "MNTRRT64L01L063H",
                "emittente": "ArubaPEC EU Authentica Certificates CA G1",
                "scadenza": "2029-02-23",
            },
        ]
        module._ultimo_certificato_windows = {
            "thumbprint": "QUAL-WRONG",
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
    assert payload["filtro_codice_fiscale"] == "MNTRRT64L01L063H"
    assert payload["certificato_windows_selezionato"]["thumbprint"] == "AUTH-CF"
    assert payload["certificato_windows_selezionato"]["emittente"] == "ArubaPEC EU Authentica Certificates CA G1"


def test_ping_windows_suggerisce_riavvio_quando_il_probe_fresco_vede_il_token():
    module = _load_local_signer()

    orig_platform = module.sys.platform
    orig_trova = module._trova_libreria
    orig_curl = module._curl_disponibile
    orig_lista = module._windows_lista_certificati
    orig_info = module._info_token
    orig_probe = module._probe_token_info_fresh
    captured = {}

    class _FakeHandler:
        path = "/ping"

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module.sys.platform = "win32"
        module._trova_libreria = lambda: "C:\\Windows\\System32\\bit4xpki.dll"
        module._curl_disponibile = lambda: True
        module._windows_lista_certificati = lambda: [
            {
                "thumbprint": "AUTH-CF",
                "soggetto": "ROBERTO MONTAGNESE",
                "emittente": "ArubaPEC EU Authentica Certificates CA G1",
                "scadenza": "2029-02-23",
            }
        ]

        def _fake_info_token(_lib_path):
            raise RuntimeError(
                "Nessun token PKCS#11 rilevato.\n"
                "Verificare che la smart card/token CNS-CIE sia inserita e che il middleware locale sia installato."
            )

        module._info_token = _fake_info_token
        module._probe_token_info_fresh = lambda _lib_path: [
            {
                "slot_id": 0,
                "label": "CNS",
                "manufacturer": "Bit4id",
                "model": "JS2048 (LB)",
                "serial": "7430010029148677",
            }
        ]

        module._Handler._ping(_FakeHandler())
    finally:
        module.sys.platform = orig_platform
        module._trova_libreria = orig_trova
        module._curl_disponibile = orig_curl
        module._windows_lista_certificati = orig_lista
        module._info_token = orig_info
        module._probe_token_info_fresh = orig_probe

    payload = captured["payload"]
    assert payload["ok"] is True
    assert payload["riavvio_signer_consigliato"] is True
    assert payload["token_probe_fresh"][0]["slot_id"] == 0
    assert "Riavvia il Local Signer" in payload["nota_riavvio_signer"]


def test_seleziona_certificato_windows_usa_dialog_nativo_quando_non_c_e_auto_pick():
    module = _load_local_signer()

    orig_platform = module.sys.platform
    orig_lista = module._windows_lista_certificati
    orig_pick = module._pick_preferred_windows_cert
    orig_select = module._windows_seleziona_cert
    orig_remember = module._ricorda_certificato_windows
    orig_cached = module._ultimo_certificato_windows
    captured = {}
    remembered = {}

    class _FakeHandler:
        path = "/seleziona-certificato?auto=1&prefer_cf=MNTRRT64L01L063H"

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module.sys.platform = "win32"
        module._windows_lista_certificati = lambda: []
        module._pick_preferred_windows_cert = lambda *args, **kwargs: None
        module._windows_seleziona_cert = lambda: {
            "thumbprint": "MANUAL-SELECT",
            "soggetto": "ROBERTO MONTAGNESE",
            "emittente": "ArubaPEC EU Authentica Certificates CA G1",
            "scadenza": "2029-02-23",
            "codice_fiscale": "MNTRRT64L01L063H",
        }
        module._ricorda_certificato_windows = lambda cert: remembered.update(cert or {})

        module._Handler._seleziona_certificato(_FakeHandler())
    finally:
        module.sys.platform = orig_platform
        module._windows_lista_certificati = orig_lista
        module._pick_preferred_windows_cert = orig_pick
        module._windows_seleziona_cert = orig_select
        module._ricorda_certificato_windows = orig_remember
        module._ultimo_certificato_windows = orig_cached

    payload = captured["payload"]
    assert payload["ok"] is True
    assert payload["auto_selezionato"] is False
    assert payload["thumbprint"] == "MANUAL-SELECT"
    assert remembered["thumbprint"] == "MANUAL-SELECT"


def test_ping_light_non_interroga_store_certificati_windows():
    module = _load_local_signer()

    orig_platform = module.sys.platform
    orig_trova = module._trova_libreria
    orig_curl = module._curl_disponibile
    orig_lista = module._windows_lista_certificati
    captured = {}

    class _FakeHandler:
        path = "/ping?light=1"

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    def _should_not_run():
        raise AssertionError("Lo store certificati non deve essere interrogato nel ping leggero")

    try:
        module.sys.platform = "win32"
        module._trova_libreria = lambda: None
        module._curl_disponibile = lambda: True
        module._windows_lista_certificati = _should_not_run

        module._Handler._ping(_FakeHandler())
    finally:
        module.sys.platform = orig_platform
        module._trova_libreria = orig_trova
        module._curl_disponibile = orig_curl
        module._windows_lista_certificati = orig_lista

    payload = captured["payload"]
    assert payload["ok"] is True
    assert payload["light"] is True
    assert "nota_light" in payload
    assert "certificati_windows" not in payload


def test_pst_session_cookie_only_solo_se_sessione_autenticata():
    module = _load_local_signer()

    assert module._pst_session_can_use_cookie_only(None) is False
    assert module._pst_session_can_use_cookie_only({"cookie_file": "x.cookies", "auth_ready": False}) is False
    assert module._pst_session_can_use_cookie_only({"cookie_file": "", "auth_ready": True}) is False
    assert module._pst_session_can_use_cookie_only({"cookie_file": "x.cookies", "auth_ready": True}) is True
    assert module._pst_session_can_use_cookie_only({"cookie_file": "x.cookies", "auth_ready": True}, created_now=True) is False


def test_local_signer_usa_qbuilder_sicid_sulla_root_del_proxy():
    module = _load_local_signer()

    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"

    assert module._pst_servizio_proxy(base) == "JPW_SICID"
    assert module._pst_namespace_qbuilder(base) == "urn:CONS-SICC-BE"
    assert module._pst_url_documenti(base) == base


def test_local_signer_normalizza_alias_e_namespace_qbuilder_catalogo_corrente():
    module = _load_local_signer()

    assert module._pst_servizio_proxy("https://ext.processotelematico.giustizia.it/pda/pycons/GLCC/JPW_CASS") == "JPW_CASSCI"
    assert module._pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIECIC") == "urn:CONS-SIECIC-BE"
    assert module._pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIL") == "urn:CONS-SIL-BE-DISTR"
    assert module._pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIVG") == "urn:CONS-SIVG-BE"
    assert module._pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_MIN") == "urn:CONS-MIN-BE"
    assert module._pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIMIN") == "urn:CONS-MIN-BE"
    assert module._pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP") == "urn:CONS-SIGP-BE"
    assert module._pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLCC/JPW_CASSCI") == "urn:CONS-CASSCI"
    assert module._pst_namespace_qbuilder("https://ext.processotelematico.giustizia.it/pda/pycons/GLCC/JPW_CASSPE") == "urn:CONS-CASSPE"


def test_pst_varianti_ricerca_esatta_palmi_prova_siecic_senza_cambiare_ufficio(monkeypatch):
    module = _load_local_signer()
    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"

    monkeypatch.setattr(
        module,
        "_risolvi_ufficio_da_snapshot",
        lambda value: {
            "codice_ministero": "0800570094",
            "codice_gl": "GLRC",
            "servizi_ministero": ["COM_TEL_136", "JPW_SICID", "JPW_SIECIC", "SICID", "SIECIC"],
            "servizio_pst_predefinito": "JPW_SICID",
        },
    )

    varianti = module._pst_base_varianti_ricerca_esatta("0800570094", base)

    assert varianti == [
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIL",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIVG",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_MIN",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIMIN",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIECIC",
    ]
    assert all("/pda/pycons/GLRC/" in variante for variante in varianti)


def test_pst_varianti_ricerca_esatta_fallback_disattivabile_da_env(monkeypatch):
    module = _load_local_signer()
    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"
    monkeypatch.setenv("HACS_SIGNER_PST_REGISTER_FALLBACK", "0")
    monkeypatch.setattr(module, "_risolvi_ufficio_da_snapshot", lambda value: None)

    varianti = module._pst_base_varianti_ricerca_esatta("0800570094", base)

    assert varianti == ["https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"]


def test_pst_varianti_ricerca_esatta_deriva_siecic_dalla_url_se_snapshot_manca(monkeypatch):
    module = _load_local_signer()
    base = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"

    monkeypatch.setattr(module, "_risolvi_ufficio_da_snapshot", lambda value: None)

    varianti = module._pst_base_varianti_ricerca_esatta("0800570094", base)

    assert varianti == [
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIL",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIVG",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_MIN",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIMIN",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIECIC",
    ]


def test_estrai_codice_fiscale_dal_certificato_windows():
    module = _load_local_signer()

    module._ultimo_certificato_windows = {
        "thumbprint": "AABBCC11",
        "soggetto": "MNTRRT64L01L063H/7430010029148677.255hHgKCPtfSkIn6w4MBTjOX0QQ=",
    }

    assert module._estrai_codice_fiscale_testo("MNTRRT64L01L063H/123") == "MNTRRT64L01L063H"
    assert module._cf_avvocato_pst("", "AABBCC11") == "MNTRRT64L01L063H"


def test_cf_avvocato_pst_usa_subject_completo_quando_il_cf_non_e_nel_display_name():
    module = _load_local_signer()

    module._ultimo_certificato_windows = {
        "thumbprint": "FFEEDD22",
        "soggetto": "ROBERTO MONTAGNESE",
        "soggetto_completo": "CN=ROBERTO MONTAGNESE,SERIALNUMBER=CF:MNTRRT64L01L063H",
        "emittente": "ArubaPEC EU Authentica Certificates CA G1",
    }

    assert module._cf_avvocato_pst("", "FFEEDD22") == "MNTRRT64L01L063H"


def test_cf_avvocato_pst_preferisce_certificato_a_cf_studio_diverso():
    module = _load_local_signer()

    module._ultimo_certificato_windows = {
        "thumbprint": "AABBCC11",
        "codice_fiscale": "MNTRRT64L01L063H",
        "soggetto": "CN=Avv. Studio Due",
    }

    assert module._cf_avvocato_pst("RSSMRA80A01H501Z", "AABBCC11") == "MNTRRT64L01L063H"
    assert module._cf_avvocato_pst("RSSMRA80A01H501Z", "FFEEDD22") == "RSSMRA80A01H501Z"


def test_pick_preferred_windows_cert_filtra_per_codice_fiscale_e_prefere_authentica():
    module = _load_local_signer()

    certs = [
        {
            "thumbprint": "QUAL-OTHER",
            "soggetto": "ROBERTO MONTAGNESE",
            "soggetto_completo": "CN=ROBERTO MONTAGNESE,SERIALNUMBER=CF:AAAAAA00A00A000A",
            "codice_fiscale": "AAAAAA00A00A000A",
            "emittente": "ArubaPEC EU Qualified Certificates CA G1",
        },
        {
            "thumbprint": "AUTH-ROBERTO",
            "soggetto": "ROBERTO MONTAGNESE",
            "soggetto_completo": "CN=ROBERTO MONTAGNESE,SERIALNUMBER=CF:MNTRRT64L01L063H",
            "codice_fiscale": "MNTRRT64L01L063H",
            "emittente": "ArubaPEC EU Authentica Certificates CA G1",
        },
        {
            "thumbprint": "QUAL-ROBERTO",
            "soggetto": "ROBERTO MONTAGNESE",
            "soggetto_completo": "CN=ROBERTO MONTAGNESE,SERIALNUMBER=CF:MNTRRT64L01L063H",
            "codice_fiscale": "MNTRRT64L01L063H",
            "emittente": "ArubaPEC EU Qualified Certificates CA G1",
        },
    ]

    picked = module._pick_preferred_windows_cert(
        certs,
        prefer_issuer="ArubaPEC EU Authentica Certificates CA G1|ArubaPEC EU Qualified Certificates CA G1",
        prefer_subject="auth|autentica|client",
        prefer_cf="MNTRRT64L01L063H",
        auto=True,
    )

    assert picked is not None
    assert picked["thumbprint"] == "AUTH-ROBERTO"


def test_pick_preferred_windows_cert_usa_certificato_unico_filtrato_per_cf():
    module = _load_local_signer()

    certs = [
        {
            "thumbprint": "QUAL-ROBERTO",
            "soggetto": "ROBERTO MONTAGNESE",
            "soggetto_completo": "CN=ROBERTO MONTAGNESE,SERIALNUMBER=CF:MNTRRT64L01L063H",
            "codice_fiscale": "MNTRRT64L01L063H",
            "emittente": "ArubaPEC EU Qualified Certificates CA G1",
        },
        {
            "thumbprint": "QUAL-OTHER",
            "soggetto": "ALTRO PROFESSIONISTA",
            "soggetto_completo": "CN=ALTRO PROFESSIONISTA,SERIALNUMBER=CF:AAAAAA00A00A000A",
            "codice_fiscale": "AAAAAA00A00A000A",
            "emittente": "ArubaPEC EU Qualified Certificates CA G1",
        },
    ]

    picked = module._pick_preferred_windows_cert(
        certs,
        prefer_cf="MNTRRT64L01L063H",
        auto=True,
    )

    assert picked is not None
    assert picked["thumbprint"] == "QUAL-ROBERTO"


def test_costruisce_body_qbuilder_ricerca_per_tipo():
    module = _load_local_signer()

    xml = module._soap_ricerca_fascicoli_body(
        base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
        codice_ufficio="0800570094",
        numero_rg="1025",
        anno_rg=2024,
        nome_parte="Parte non corrispondente",
        cf_parte="RSSMRA80A01H501Z",
        cf_avvocato="MNTRRT64L01L063H",
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
    assert "Parte non corrispondente" not in xml
    assert "RSSMRA80A01H501Z" not in xml
    assert '<entry property="ANNORUOLO, NUMERORUOLO" mode="asc"/>' in xml


def test_qbuilder_sicid_family_usa_tipo_registro_ministeriale_corretto():
    module = _load_local_signer()

    attesi = {
        "JPW_SICID": ("urn:CONS-SICC-BE", "RGN"),
        "JPW_SIL": ("urn:CONS-SIL-BE-DISTR", "LAV"),
        "JPW_SIVG": ("urn:CONS-SIVG-BE", "VG"),
        "JPW_MIN": ("urn:CONS-MIN-BE", "MIN"),
        "JPW_SIMIN": ("urn:CONS-MIN-BE", "MIN"),
    }

    for servizio, (namespace, tipo) in attesi.items():
        xml = module._soap_ricerca_fascicoli_body(
            base_url=f"https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/{servizio}",
            codice_ufficio="0800570094",
            numero_rg="3441",
            anno_rg=2025,
            cf_avvocato="MNTGPP94L01G791A",
        )

        assert f'<execute xmlns="{namespace}">' in xml
        assert "<name>RicercaInformazioniFascicoloPerTipo</name>" in xml
        assert f'<value name="tipo" type="string">{tipo}</value>' in xml
        assert '<value name="numero" type="integer">3441</value>' in xml
        assert '<value name="anno" type="string">2025</value>' in xml


def test_qbuilder_ricerca_per_parte_copre_registri_ministeriali_senza_rg():
    module = _load_local_signer()

    attesi = {
        "JPW_SICID": "urn:CONS-SICC-BE",
        "JPW_SIL": "urn:CONS-SIL-BE-DISTR",
        "JPW_SIVG": "urn:CONS-SIVG-BE",
        "JPW_MIN": "urn:CONS-MIN-BE",
        "JPW_SIMIN": "urn:CONS-MIN-BE",
        "JPW_SIGP": "urn:CONS-SIGP-BE",
    }

    for servizio, namespace in attesi.items():
        xml = module._soap_ricerca_fascicoli_body(
            base_url=f"https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/{servizio}",
            codice_ufficio="0800570094",
            nome_parte="Montagnese",
            cf_parte="MNTGPP94L01G791A",
            cf_avvocato="MNTGPP94L01G791A",
        )

        assert f'<execute xmlns="{namespace}">' in xml
        assert "<name>RicercaInformazioniFascicoloPerPartiGiudiceDate</name>" in xml
        assert '<value name="cognomeNome" type="string">MONTAGNESE</value>' in xml
        assert '<value name="codiceFiscale" type="string">MNTGPP94L01G791A</value>' in xml
        assert 'name="numero"' not in xml
        assert 'name="anno"' not in xml


def test_qbuilder_siecic_usa_servizi_catalogo_ministeriale():
    module = _load_local_signer()
    base_url = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIECIC"

    ricerca_xml = module._soap_ricerca_fascicoli_body(
        base_url=base_url,
        codice_ufficio="0800570094",
        numero_rg="3441",
        anno_rg=2025,
        cf_avvocato="MNTRRT64L01L063H",
    )
    profilo_xml = module._soap_profilo_fascicolo_body(
        base_url=base_url,
        codice_ufficio="0800570094",
        numero_rg="3441",
        anno_rg=2025,
    )
    documenti_xml = module._soap_documenti_body(
        base_url=base_url,
        codice_ufficio="0800570094",
        numero_rg="3441",
        anno_rg=2025,
    )

    assert '<execute xmlns="urn:CONS-SIECIC-BE">' in ricerca_xml
    assert "<name>InfoFascicolo</name>" in ricerca_xml
    assert "<name>ProfiloFascicolo</name>" in profilo_xml
    assert "<name>ElencoDocumenti</name>" in documenti_xml
    for xml in (ricerca_xml, profilo_xml, documenti_xml):
        assert '<value name="idUfficio" type="string">0800570094</value>' in xml
        assert '<value name="numeroRuolo" type="string">3441</value>' in xml
        assert '<value name="annoRuolo" type="integer">2025</value>' in xml
        assert "<name>RicercaInformazioniFascicoloPerTipo</name>" not in xml
        assert "<name>DocumentiFascicolo</name>" not in xml


def test_costruisce_body_legacy_ricerca_esatta_senza_filtri_parte():
    module = _load_local_signer()

    xml = module._soap_ricerca_fascicoli_body(
        base_url="https://pst.giustizia.it/PST/services/PSTService",
        codice_ufficio="0800570094",
        numero_rg="1025",
        anno_rg=2024,
        nome_parte="Parte non corrispondente",
        cf_parte="RSSMRA80A01H501Z",
        cf_avvocato="MNTRRT64L01L063H",
    )

    assert "<numeroRG>1025</numeroRG>" in xml
    assert "<annoRG>2024</annoRG>" in xml
    assert "<cfAvvocato>MNTRRT64L01L063H</cfAvvocato>" in xml
    assert "<codiceUfficio>0800570094</codiceUfficio>" in xml
    assert "<nomeParte>" not in xml
    assert "<codiceFiscaleParte>" not in xml


def test_costruisce_body_legacy_ricerca_per_parte_mantiene_filtri():
    module = _load_local_signer()

    xml = module._soap_ricerca_fascicoli_body(
        base_url="https://pst.giustizia.it/PST/services/PSTService",
        codice_ufficio="0800570094",
        nome_parte="Mario Rossi",
        cf_parte="RSSMRA80A01H501Z",
        cf_avvocato="MNTRRT64L01L063H",
    )

    assert "<nomeParte>Mario Rossi</nomeParte>" in xml
    assert "<codiceFiscaleParte>RSSMRA80A01H501Z</codiceFiscaleParte>" in xml


def test_qbuilder_documenti_e_profilo_usano_parametri_pst_live():
    module = _load_local_signer()
    base_url = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"

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

    for xml in (documenti_xml, profilo_xml):
        assert '<value name="anno" type="string">2024</value>' in xml
        assert '<value name="numero" type="string">1025</value>' in xml
        assert 'name="subProc"' not in xml
        assert 'name="annoRuolo"' not in xml
        assert 'name="numeroRuolo"' not in xml
        assert 'name="subpro"' not in xml
    assert '<value name="subProc" type="string">1</value>' in documenti_subproc_xml
    assert 'name="subpro"' not in documenti_subproc_xml


def test_qbuilder_sigp_usa_registro_gdp_senza_subpro_implicito():
    module = _load_local_signer()
    base_url = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP"

    ricerca_xml = module._soap_ricerca_fascicoli_body(
        base_url=base_url,
        codice_ufficio="0800570152",
        numero_rg="466",
        anno_rg=2023,
        cf_avvocato="MNTRRT64L01L063H",
    )
    documenti_xml = module._soap_documenti_body(
        base_url=base_url,
        codice_ufficio="0800570152",
        numero_rg="466",
        anno_rg=2023,
        sub_procedimento="",
    )

    assert '<value name="tipo" type="string">GDP</value>' in ricerca_xml
    assert 'name="subpro"' not in ricerca_xml
    assert 'name="subpro"' not in documenti_xml
    assert 'name="subProc"' not in ricerca_xml
    assert 'name="subProc"' not in documenti_xml


def test_qbuilder_sigp_usa_subpro_solo_se_esplicito():
    module = _load_local_signer()
    base_url = "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP"

    ricerca_xml = module._soap_ricerca_fascicoli_body(
        base_url=base_url,
        codice_ufficio="0800570152",
        numero_rg="466",
        anno_rg=2023,
        cf_avvocato="MNTRRT64L01L063H",
        sub_procedimento="1",
    )
    documenti_xml = module._soap_documenti_body(
        base_url=base_url,
        codice_ufficio="0800570152",
        numero_rg="466",
        anno_rg=2023,
        sub_procedimento="1",
    )

    assert '<value name="subpro" type="string">1</value>' in ricerca_xml
    assert '<value name="subpro" type="integer">1</value>' in documenti_xml
    assert 'name="subProc"' not in ricerca_xml
    assert 'name="subProc"' not in documenti_xml


def test_sigp_ricerca_atti_body_e_parser_ids():
    module = _load_local_signer()

    body = module._soap_sigp_ricerca_atti_body("0800570152", "466", 2023)

    assert 'InvocationDomain name="JPW" role="AVV" group="0800570152"' in body
    assert '<y:ricercaAtti xmlns:y="urn:sigp-consultazioneDocumenti">' in body
    assert "<numRuolo>466</numRuolo>" in body
    assert "<annoRuolo>2023</annoRuolo>" in body

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
<SOAP-ENV:Body>
<ns1:ricercaAttiResponse xmlns:ns1="urn:sigp-consultazioneDocumenti">
  <return><item>3080731</item><item>3080731</item><item>3073476</item></return>
</ns1:ricercaAttiResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    assert module._parse_sigp_ricerca_atti_ids(xml) == ["3080731", "3073476"]


def test_sigp_download_atto_body_include_dominio_invocazione():
    module = _load_local_signer()

    body = module._soap_sigp_download_body("ATTO-SIGP-001", "0800570152")

    assert 'InvocationDomain name="JPW" role="AVV" group="0800570152"' in body
    assert '<y:downloadAtto xmlns:y="urn:sigp-consultazioneDocumenti">' in body
    assert "<idrepeatto>ATTO-SIGP-001</idrepeatto>" in body


def test_sigp_fallback_collega_scheda_ufficiale_gdp():
    module = _load_local_signer()

    fascicolo = module._sigp_fascicolo_fallback(
        codice_ufficio="0800570152",
        numero_rg="466",
        anno_rg=2023,
        cf_avvocato="MNTRRT64L01L063H",
        motivo="SUBPRO",
    )

    assert fascicolo["numero_rg"] == "466"
    assert fascicolo["anno_rg"] == 2023
    assert fascicolo["registro_portale"] == "GDP"
    assert fascicolo["verifica_browser_ufficiale"] is True
    assert fascicolo["sincronizzazione_autorizzata"] == "richiede_servizio_pst_pda_o_model_office"
    assert fascicolo["download_autonomo"] is False
    assert "scraping HTML" in fascicolo["messaggio_operativo"]
    assert "sigp_infofascicolo.wp" in fascicolo["portale_url"]
    assert "ufficioRicerca=0800570152" in fascicolo["portale_url"]
    assert "registroRicerca=GDP" in fascicolo["portale_url"]
    assert "pa=%5BMNTRRT64L01L063H%5D" in fascicolo["portale_url"]


def test_sigp_fallback_non_contiene_scraping_html():
    module = _load_local_signer()
    source = Path(module.__file__).read_text(encoding="utf-8")

    assert "_parse_sigp_info_fascicolo_html" not in source
    assert "_http_get_pst_session" not in source
    assert "_http_get_curl_raw" not in source
    assert "_arricchisci_sigp_fallback_con_scheda" not in source


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


def test_parse_qbuilder_siecic_supporta_nomi_catalogo_camel_case():
    module = _load_local_signer()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SIECIC-BE"><return available="1" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType"><ns2:row class="InfoFascicolo"><ns2:property name="idFascicolo" type="string">FASC-3441</ns2:property><ns2:property name="idUfficio" type="string">0800570094</ns2:property><ns2:property name="annoRuolo" type="integer">2025</ns2:property><ns2:property name="numeroRuolo" type="string">3441</ns2:property><ns2:property name="descrRito" type="string">Esecuzioni immobiliari</ns2:property><ns2:property name="dataUdienza" type="date">12/06/2026</ns2:property><ns2:property name="giudice" type="string">GIUDICE TEST</ns2:property><ns2:property name="creditori" type="string">Creditore Test</ns2:property><ns2:property name="debitori" type="string">Debitore Test</ns2:property></ns2:row></return></ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    fascicoli = module._parse_fascicoli_xml(xml)

    assert len(fascicoli) == 1
    assert fascicoli[0]["id_fascicolo"] == "FASC-3441"
    assert fascicoli[0]["numero_rg"] == "3441"
    assert fascicoli[0]["anno_rg"] == 2025
    assert fascicoli[0]["codice_ufficio"] == "0800570094"
    assert fascicoli[0]["ruolo"] == "Esecuzioni immobiliari"
    assert fascicoli[0]["data_udienza"] == "2026-06-12"


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


def test_parse_qbuilder_siecic_documenti_elenco_documenti():
    module = _load_local_signer()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
<SOAP-ENV:Body>
<ns1:executeResponse xmlns:ns1="urn:CONS-SIECIC-BE"><return available="1" xmlns:ns2="urn:qbuilder-types" xsi:type="ns2:rowListType"><ns2:row class="ElencoDocumenti"><ns2:property name="idDoc" type="string">DOC-3441</ns2:property><ns2:property name="tipoDocumento" type="string">Istanza</ns2:property><ns2:property name="dataDeposito" type="date">15/05/2026</ns2:property><ns2:property name="provenienza" type="string">Cancelleria</ns2:property><ns2:property name="decodeAttivo" type="string">Si</ns2:property></ns2:row></return></ns1:executeResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    documenti = module._parse_documenti_xml(xml)

    assert len(documenti) == 1
    assert documenti[0]["id_documento"] == "DOC-3441"
    assert documenti[0]["tipo"] == "Istanza"
    assert documenti[0]["data_deposito"] == "2026-05-15"
    assert documenti[0]["mittente"] == "Cancelleria"
    assert documenti[0]["disponibile"] is True


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
            <idRepeatTo>ATTO-SIGP-002</idRepeatTo>
            <msgId>PEC-MSG-002</msgId>
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
    assert documenti[1]["id_repeatto"] == "ATTO-SIGP-002"
    assert documenti[1]["msg_id"] == "PEC-MSG-002"


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


def test_parse_profilo_documento_sigp_preserva_nome_originale_e_metadati():
    module = _load_local_signer()

    xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
<SOAP-ENV:Body>
<ns1:estraiProfiloDocumentoResponse xmlns:ns1="urn:BEAFascicoloInformatico-distr">
  <return>
    <codFiscMittente>CRSGPP63P29I725M</codFiscMittente>
    <codiceUfficio>0800570152</codiceUfficio>
    <dataDeposito>2026-03-10T12:11:05Z</dataDeposito>
    <idDocumento>3080731</idDocumento>
    <idBusta>3080730</idBusta>
    <idCat>3080731</idCat>
    <nomeFileOriginale>depositoMinutaSentenzaSemplificata.pdf</nomeFileOriginale>
    <dimensioneFile>179738</dimensioneFile>
    <tipoMIME>application/pdf</tipoMIME>
    <tipoOggetto><descrizione>Documento</descrizione></tipoOggetto>
  </return>
</ns1:estraiProfiloDocumentoResponse>
</SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""

    profilo = module._parse_profilo_documento_xml(xml)
    documento = module._documento_da_profilo_sigp(profilo, "3080731")

    assert profilo["nome_file_originale"] == "depositoMinutaSentenzaSemplificata.pdf"
    assert profilo["data_documento"] == "2026-03-10"
    assert profilo["dimensione_bytes"] == 179738
    assert documento["nome"] == "depositoMinutaSentenzaSemplificata.pdf"
    assert documento["id_deposito"] == "3080730"
    assert documento["id_cat"] == "3080731"


def test_sigp_merge_profili_arricchisce_lista_qbuilder_senza_duplicare():
    module = _load_local_signer()

    base = [{
        "id_documento": "3080731",
        "id_cat": "3080731",
        "nome": "Sentenza_3080731.pdf",
        "id_documento_candidates": ["3080731"],
    }, {
        "id_documento": "3080731",
        "id_cat": "3080731",
        "nome": "Sentenza_3080731_DUPLICATO.pdf",
        "id_documento_candidates": ["3080731"],
    }]
    profili = [{
        "id_documento": "3080731",
        "id_cat": "3080731",
        "nome": "depositoMinutaSentenzaSemplificata.pdf",
        "dimensione_bytes": 179738,
        "id_deposito": "3080730",
    }, {
        "id_documento": "3073476",
        "id_cat": "3073476",
        "nome": "MEMORIA_CONCLUSIVA_ZURICH.pdf.p7m",
        "id_documento_candidates": ["3073476"],
    }]

    merged = module._sigp_merge_documenti_con_profili(base, profili)

    assert len(merged) == 2
    assert merged[0]["nome"] == "depositoMinutaSentenzaSemplificata.pdf"
    assert merged[0]["dimensione_bytes"] == 179738
    assert merged[1]["id_documento"] == "3073476"


def test_map_qbuilder_documento_preserva_candidati_identificativo():
    module = _load_local_signer()

    doc = module._map_qbuilder_documento(
        {
            "IDDOCUMENTO": "",
            "NUMERODOCUMENTO": "32473463",
            "IDDOCMITTENTE": "CAT-ALT-001",
            "IDREPEATTO": "ATTO-SIGP-001",
            "MSGID": "PEC-MSG-001",
            "TIPO": "Ordinanza",
            "DATADEPOSITO": "30/09/2025 16:46:40.000",
        }
    )

    assert doc["id_documento"] == "32473463"
    assert doc["numero_documento"] == "32473463"
    assert doc["id_doc_mittente"] == "CAT-ALT-001"
    assert doc["id_repeatto"] == "ATTO-SIGP-001"
    assert doc["msg_id"] == "PEC-MSG-001"
    assert doc["id_documento_candidates"] == ["32473463", "CAT-ALT-001"]


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

    assert calls["profile"] == 0
    assert calls["download"] == 1
    assert payload["id_documento_portale"] == "33581101"
    assert payload["id_cat"] == "33581101"
    assert payload["nome"] == "SentenzaDefinitiva_33581101.pdf"
    assert payload["data_documento"] == ""
    assert payload["content_type"] == "application/pdf"
    assert payload["servizio_portale"] == "DocumentiFascicolo"
    assert payload["contenuto_b64"].startswith("JVBERi0xLjcK")


def test_pst_download_documento_payload_preserva_nome_p7m_quando_il_payload_e_firmato():
    module = _load_local_signer()

    profile_xml = """<?xml version='1.0' encoding='UTF-8'?>
<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">
  <SOAP-ENV:Body>
    <ns1:estraiProfiloDocumentoResponse xmlns:ns1="urn:BEAFascicoloInformatico-distr">
      <return>
        <idDocumento>33581102</idDocumento>
        <idCat>33581102</idCat>
        <nomeFileOriginale>verbale.pdf</nomeFileOriginale>
        <dataDeposito>2026-01-21T13:47:02Z</dataDeposito>
      </return>
    </ns1:estraiProfiloDocumentoResponse>
  </SOAP-ENV:Body>
</SOAP-ENV:Envelope>"""
    raw_body = (
        b"--signed\r\n"
        b"Content-Type: text/xml\r\n"
        b"Content-Transfer-Encoding: 7bit\r\n\r\n"
        b"<?xml version='1.0' encoding='UTF-8'?><SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>"
        b"<SOAP-ENV:Body><ns1:downloadDocumentoResponse xmlns:ns1='urn:BEAFascicoloInformatico-distr'>"
        b"<return href ='cid:test-doc-2'/></ns1:downloadDocumentoResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>\r\n"
        b"--signed\r\n"
        b"Content-Type: application/pkcs7-mime\r\n"
        b"Content-Disposition: attachment; filename=\"VerbaleUdienza_29740536.pdf.p7m\"\r\n"
        b"Content-Transfer-Encoding: base64\r\n"
        b"Content-ID: <test-doc-2>\r\n\r\n"
        b"ZmFrZS1wN20=\r\n"
        b"--signed--\r\n"
    )

    orig_call = module._soap_call_curl
    orig_raw = module._soap_call_curl_raw
    try:
        module._soap_call_curl = lambda *args, **kwargs: profile_xml
        module._soap_call_curl_raw = lambda *args, **kwargs: (
            raw_body,
            'Content-Type: multipart/related; boundary="signed"',
        )

        payload = module._pst_download_documento_payload(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
            id_documento="33581102",
            nome_documento="VerbaleUdienza_29740536.pdf",
            cert_thumbprint="AABBCC11",
            cf_avvocato="MNTRRT64L01L063H",
        )
    finally:
        module._soap_call_curl = orig_call
        module._soap_call_curl_raw = orig_raw

    assert payload["nome"] == "VerbaleUdienza_29740536.pdf.p7m"
    assert payload["content_type"] == "application/pkcs7-mime"


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
    studio_cfg = str(base / "config" / "studio.json")
    return {
        "TESTING": True,
        "SECRET_KEY": "test",
        "MULTI_TENANT": False,
        "BOOTSTRAP_ADMIN_PASSWORD": "Admin1234!",
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
        "STUDIO_CONFIG": studio_cfg,
        "CONFIG_STUDIO_DB": studio_cfg,
        "TENANTS_REGISTRY": str(base / "tenants.json"),
    }


def test_installer_local_signer_windows_legacy_restituisce_exe_senza_login(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/installa-windows")

    assert r.status_code == 200
    disposition = r.headers.get("Content-Disposition", "")
    assert f"SetupLocalSigner-{version}.exe" in disposition
    assert ".ps1" not in disposition
    assert ".cmd" not in disposition


def test_api_portale_acquisizione_preview_pst_espone_id_documento_come_idcat(tmp_path):
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
                "documenti": [
                    {
                        "id_documento": "32473463",
                        "nome": "Ordinanza_32473463.pdf",
                        "tipo": "ORDINANZA",
                        "tipo_atto": "Ordinanza",
                        "data_deposito": "2025-09-30",
                        "mittente": "GIOVANNELLA MARIA ELENA",
                        "id_deposito": "BUSTA-PST-001",
                        "numero_documento": "32473463",
                        "id_doc_mittente": "CAT-ALT-001",
                        "id_cat": "",
                    }
                ],
            },
            follow_redirects=True,
        )

    data = response.get_json()
    assert response.status_code == 200
    assert data["ok"] is True
    preview_doc = data["preview"]["documenti"][0]
    assert preview_doc["id_documento"] == "32473463"
    assert preview_doc["id_cat"] == "32473463"
    assert preview_doc["id_documento_candidates"][0] == "32473463"


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
    assert "IUSENTRA Local Signer" in body
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


def test_download_visible_signature_local_signer_e_pubblico(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/download/visible-signature")

    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert f"visible_signature-{version}.py" in r.headers.get("Content-Disposition", "")
    body = r.data.decode("utf-8")
    assert "def apply_visible_signature_stamp" in body
    assert "Firmato digitalmente da" in body


def test_download_moduli_local_signer_e_pubblico(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/download/local-signer-mod/ai_handlers.py")
        pec = c.get("/polisWeb/local-signer/download/local-signer-mod/pec_bridge.py")
        forbidden = c.get("/polisWeb/local-signer/download/local-signer-mod/../local_signer.py")

    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert "ai_handlers.py" in r.headers.get("Content-Disposition", "")
    assert "class LocalAiHandlerFacade" in r.data.decode("utf-8")
    assert pec.status_code == 200
    assert "pec_bridge.py" in pec.headers.get("Content-Disposition", "")
    assert "send_pec_local" in pec.data.decode("utf-8")
    assert forbidden.status_code == 404


def test_download_requirements_local_signer_e_pubblico(tmp_path):
    from web.app import create_app

    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/download/requirements")

    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    assert "requirements_local_signer.txt" in r.headers.get("Content-Disposition", "")
    assert "cryptography" in r.data.decode("utf-8")


def test_installer_local_signer_windows_ps1_legacy_restituisce_exe(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/windows-ps1")

    assert r.status_code == 200
    assert "attachment" in r.headers.get("Content-Disposition", "")
    disposition = r.headers.get("Content-Disposition", "")
    assert f"SetupLocalSigner-{version}.exe" in disposition
    assert ".ps1" not in disposition


def test_installer_local_signer_windows_setup_route_e_pubblica(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/windows")

    assert r.status_code == 200
    disposition = r.headers.get("Content-Disposition", "")
    assert "attachment;" in disposition
    assert f"SetupLocalSigner-{version}.exe" in disposition
    assert ".cmd" not in disposition
    assert ".ps1" not in disposition


def test_installer_local_signer_windows_exe_route_se_bundle_presente(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        r = c.get("/polisWeb/local-signer/setup/windows-exe")

    assert r.status_code == 200
    disp = r.headers.get("Content-Disposition", "")
    assert f"SetupLocalSigner-{version}.exe" in disp
    assert ".cmd" not in disp
    assert ".ps1" not in disp


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
    assert "/polisWeb/local-signer/download/visible-signature" in body
    assert "/polisWeb/local-signer/download/local-signer-mod/ai_handlers.py" in body
    assert "zeep" in body


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
    assert "/polisWeb/local-signer/download/visible-signature" in body
    assert "/polisWeb/local-signer/download/local-signer-mod/ai_handlers.py" in body
    assert "zeep" in body


def test_tab_firma_mostra_download_local_signer_per_tutte_le_piattaforme(tmp_path):
    from web.app import create_app

    version = _local_signer_version()
    app = create_app(_cfg_web(tmp_path))
    with app.test_client() as c:
        login = c.post(
            "/login",
        data={"username": "admin", "password": "Admin1234!"},
            follow_redirects=False,
        )
        assert login.status_code in (302, 303)

        r = c.get("/impostazioni?tab=firma&_legacy=1")

    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "Scarica Local Signer" in body
    assert "/polisWeb/local-signer/setup/windows" in body
    assert "/polisWeb/local-signer/setup/macos" in body
    assert "/polisWeb/local-signer/setup/linux" in body
    assert f"Versione corrente pubblicata: v{version}" in body
    assert "Script Python" not in body
    assert "Registro uffici PST" not in body
    assert "Pacchetti disponibili:" not in body
    assert "bit4xpki.dll" not in body


def test_impostazioni_firma_carica_p12_nel_volume_configurato(tmp_path):
    from pct.config_studio import GestioneConfigStudio
    from web.app import create_app

    studio_cfg = tmp_path / "config" / "studio.json"
    app = create_app({**_cfg_web(tmp_path), "STUDIO_CONFIG": str(studio_cfg)})

    with app.test_client() as c:
        login = c.post(
            "/login",
        data={"username": "admin", "password": "Admin1234!"},
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
        data={"username": "admin", "password": "Admin1234!"},
            follow_redirects=False,
        )
        assert login.status_code in (302, 303)
        r = c.get("/polisWeb?_legacy=1")

    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert 'name="demo_mode" value="0"' in body
    assert 'name="server_demo_mode" value="1"' in body
    assert 'id="badge-demo-mode"' not in body
    assert 'id="banner-demo"' not in body


def test_polisweb_passa_il_cf_configurato_alle_preferenze_certificato(tmp_path):
    from pct.config_studio import GestioneConfigStudio
    from web.app import create_app

    studio_cfg = tmp_path / "config" / "studio.json"
    dll_path = tmp_path / "bit4xpki.dll"
    dll_path.write_bytes(b"fake-dll")

    gs = GestioneConfigStudio(str(studio_cfg))
    cfg = gs.config
    cfg.firma.pkcs11_library = str(dll_path)
    cfg.firma.backend_preferito = "pkcs11"
    cfg.firma.cf_avvocato = "MNTRRT64L01L063H"
    gs.aggiorna(cfg)

    app = create_app({**_cfg_web(tmp_path), "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as c:
        login = c.post(
            "/login",
        data={"username": "admin", "password": "Admin1234!"},
            follow_redirects=False,
        )
        assert login.status_code in (302, 303)
        r = c.get("/polisWeb?_legacy=1")

    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert 'preferCf: "MNTRRT64L01L063H"' in body
    assert "Filtro automatico attivo sul codice fiscale" in body


def test_portali_acquisizione_status_mantiene_pkcs11_anche_fuori_da_pst(tmp_path):
    from pct.auth import GestioneUtenti, RuoloUtente
    from pct.config_studio import GestioneConfigStudio
    from web.app import create_app

    studio_cfg = tmp_path / "config" / "studio.json"
    dll_path = tmp_path / "bit4xpki.dll"
    dll_path.write_bytes(b"fake-dll")

    gs = GestioneConfigStudio(str(studio_cfg))
    cfg = gs.config
    cfg.firma.pkcs11_library = str(dll_path)
    cfg.firma.backend_preferito = "pkcs11"
    cfg.firma.cf_avvocato = "MNTRRT64L01L063H"
    gs.aggiorna(cfg)

    web_cfg = _cfg_web(tmp_path)
    gu = GestioneUtenti(
        db_path=web_cfg["AUTH_DB"],
        audit_path=web_cfg["AUDIT_DB"],
        secret_key="test",
    )
    gu.crea(
        username="avvocato",
        password="Avv12345!",
        ruolo=RuoloUtente.AVVOCATO,
        email="avvocato@example.com",
    )

    app = create_app({**web_cfg, "STUDIO_CONFIG": str(studio_cfg)})
    with app.test_client() as c:
        login = c.post(
            "/login",
            data={"username": "avvocato", "password": "Avv12345!"},
            follow_redirects=False,
        )
        assert login.status_code in (302, 303)
        for portale in ("pdp", "pat", "ptt"):
            response = c.get(f"/api/portali/{portale}/acquisizione/status")
            data = response.get_json()
            assert response.status_code == 200
            assert data["ok"] is True
            assert data["status"]["auth_mode"] == "pkcs11"
            assert data["status"]["pkcs11_mode"] is True
            assert data["status"]["demo_mode"] is False
            assert data["status"]["cert_preferences"]["prefer_cf"] == "MNTRRT64L01L063H"


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
        data={"username": "admin", "password": "Admin1234!"},
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

    assert "iusentra-local-signer" in script
    assert "hacs-local-signer" not in script
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
            self.visible_signature_modes = []

        def firma_cades(
            self,
            documento,
            detached=False,
            visible_signature_mode="laterale",
            visible_signature_place="",
        ):
            self.calls += 1
            self.visible_signature_modes.append(visible_signature_mode)
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

    assert firmato1 == b"doc-1.p7m"
    assert firmato2 == b"doc-2.p7m"
    assert info1["pin_session_id"] == "sess-1"
    assert info2["pin_session_id"] == "sess-1"
    assert signer.calls == 2
    assert signer.visible_signature_modes == ["laterale", "laterale"]


def test_build_cades_bes_inline_restituisce_busta_pkcs7_valida_con_contenuto_embedded():
    from datetime import UTC, datetime, timedelta

    from asn1crypto import cms
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.x509.oid import NameOID

    module = _load_local_signer()

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IT"),
        x509.NameAttribute(NameOID.COMMON_NAME, "Avv. Test Inline"),
    ])
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(days=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=30))
        .sign(key, hashes.SHA256())
    )
    documento = b"%PDF-1.4\n% firma inline\n%%EOF"
    signed_attrs_der = module._build_signed_attrs_der_inline(documento)
    firma = key.sign(signed_attrs_der, padding.PKCS1v15(), hashes.SHA256())
    envelope = module._build_cades_bes_inline(
        documento=documento,
        firma=firma,
        cert_der=cert.public_bytes(serialization.Encoding.DER),
        signed_attrs_der=signed_attrs_der,
    )

    content_info = cms.ContentInfo.load(envelope)
    assert content_info["content_type"].native == "signed_data"
    signed_data = content_info["content"]
    assert len(signed_data["signer_infos"]) == 1
    assert signed_data["certificates"] is not None
    assert len(signed_data["certificates"]) == 1
    assert signed_data["encap_content_info"]["content"].native == documento


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

        def _fake_firma_documento(
            lib_path,
            documento,
            pin,
            slot_id,
            pin_session_id=None,
            visible_signature_mode="laterale",
            visible_signature_place="",
            visible_signature_datetime_mode="data_ora",
        ):
            calls.append({
                "lib_path": lib_path,
                "documento": documento,
                "pin": pin,
                "slot_id": slot_id,
                "pin_session_id": pin_session_id,
                "visible_signature_mode": visible_signature_mode,
                "visible_signature_place": visible_signature_place,
                "visible_signature_datetime_mode": visible_signature_datetime_mode,
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
                "visible_signature_mode": "basso_destra",
                "visible_signature_place": "Taurianova",
                "visible_signature_datetime_mode": "solo_data",
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
    assert calls[0]["visible_signature_mode"] == "basso_destra"
    assert calls[0]["visible_signature_place"] == "Taurianova"
    assert calls[0]["visible_signature_datetime_mode"] == "solo_data"
    assert calls[1]["pin"] == ""
    assert calls[1]["pin_session_id"] == "sess-1"
    assert calls[1]["visible_signature_mode"] == "basso_destra"
    assert calls[1]["visible_signature_place"] == "Taurianova"
    assert calls[1]["visible_signature_datetime_mode"] == "solo_data"


def test_firma_singola_propaga_modalita_visibile_al_signer():
    module = _load_local_signer()

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

        def _fake_firma_documento(
            lib_path,
            documento,
            pin,
            slot_id,
            pin_session_id=None,
            visible_signature_mode="laterale",
            visible_signature_place="",
            visible_signature_datetime_mode="data_ora",
        ):
            captured["call"] = {
                "lib_path": lib_path,
                "documento": documento,
                "pin": pin,
                "slot_id": slot_id,
                "pin_session_id": pin_session_id,
                "visible_signature_mode": visible_signature_mode,
                "visible_signature_place": visible_signature_place,
                "visible_signature_datetime_mode": visible_signature_datetime_mode,
            }
            return documento + b".p7m", {
                "pin_session_id": "sess-1",
                "pin_session_cached": False,
                "intestatario": "Avv. Test",
                "scadenza": "2029-02-23",
            }

        module._firma_documento = _fake_firma_documento

        handler = _FakeHandler(
            {
                "documento": base64.b64encode(b"doc-1").decode(),
                "pin": "123456",
                "slot_id": 0,
                "visible_signature_mode": "basso_destra",
                "visible_signature_place": "Taurianova",
                "visible_signature_datetime_mode": "nessuna",
            }
        )

        module._Handler._firma(handler)
    finally:
        module._trova_libreria = orig_trova
        module._firma_documento = orig_firma

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is True
    assert captured["call"]["visible_signature_mode"] == "basso_destra"
    assert captured["call"]["visible_signature_place"] == "Taurianova"
    assert captured["call"]["visible_signature_datetime_mode"] == "nessuna"


def test_download_documenti_batch_esegue_preflight_una_sola_volta():
    module = _load_local_signer()

    orig_preflight = module._pst_preflight_auth_curl
    orig_batch = module._soap_call_curl_batch_raw
    orig_download = module._pst_download_documento_payload
    calls = {"preflight": 0, "download": []}

    try:
        def _fake_preflight(url, cert_thumbprint=None, pkcs11_uri=None, cookie_file=None):
            calls["preflight"] += 1
            return {"ok": True, "nota": "warmup ok"}

        def _fake_batch(requests, cert_thumbprint=None, pkcs11_uri=None):
            return [
                (
                    b"%PDF-1.7\nfake",
                    "HTTP/1.1 200 OK\r\nContent-Type: application/pdf\r\n",
                )
            ] * len(requests)

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
        module._soap_call_curl_batch_raw = _fake_batch
        module._pst_download_documento_payload = _fake_download

        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
                cert_thumbprint="AABBCC11",
                cf_avvocato="RSSMRA80A01H501Z",
                documenti=[
                    {"id_documento": "33581101", "nome_documento": "Sentenza.pdf", "id_cat": "CAT-1"},
                    {"id_documento": "33393309", "nome_documento": "Verbale.pdf", "id_cat": "CAT-2"},
                ],
                do_preflight=True,
                )
    finally:
        module._pst_preflight_auth_curl = orig_preflight
        module._soap_call_curl_batch_raw = orig_batch
        module._pst_download_documento_payload = orig_download

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 2
    assert esito["failures"] == []
    assert calls["preflight"] == 1
    assert calls["download"] == []


def test_download_documenti_batch_singolo_usa_id_documento_come_idcat_sicid():
    module = _load_local_signer()

    orig_best_effort = module._soap_call_pst_session_batch_raw_best_effort
    orig_batch = module._soap_call_pst_session_batch_raw
    calls = {"best_effort": 0, "batch": []}

    try:
        def _fake_best_effort(requests, **kwargs):
            calls["best_effort"] += 1
            return []

        def _fake_batch(requests, **kwargs):
            calls["batch"] = list(requests)
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
            return [(body, 'Content-Type: multipart/related; boundary="abc123"')]

        module._soap_call_pst_session_batch_raw_best_effort = _fake_best_effort
        module._soap_call_pst_session_batch_raw = _fake_batch

        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
            documenti=[{"id_documento": "33581101", "nome_documento": "Sentenza.pdf"}],
            do_preflight=False,
            cookie_file="C:\\temp\\pst.cookies",
        )
    finally:
        module._soap_call_pst_session_batch_raw_best_effort = orig_best_effort
        module._soap_call_pst_session_batch_raw = orig_batch

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 1
    assert esito["failures"] == []
    assert calls["best_effort"] == 0
    assert len(calls["batch"]) == 1
    assert "<idCat>33581101</idCat>" in calls["batch"][0]["soap_body"]
    assert calls["batch"][0]["cookie_file"] == ""


def test_download_documenti_batch_multi_documento_usa_id_documento_come_idcat_sicid():
    module = _load_local_signer()

    orig_best_effort = module._soap_call_pst_session_batch_raw_best_effort
    orig_batch = module._soap_call_pst_session_batch_raw
    calls = {"best_effort": 0, "batch": []}

    try:
        def _fake_best_effort(requests, **kwargs):
            calls["best_effort"] += 1
            return []

        def _fake_batch(requests, **kwargs):
            calls["batch"] = list(requests)
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
            return [(b"<hash/>", "HTTP/1.1 200 OK\r\nContent-Type: text/xml\r\n")] + [
                (body, 'Content-Type: multipart/related; boundary="abc123"')
            ] * (len(requests) - 1)

        module._soap_call_pst_session_batch_raw_best_effort = _fake_best_effort
        module._soap_call_pst_session_batch_raw = _fake_batch

        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
            documenti=[
                {"id_documento": "33581101", "nome_documento": "Sentenza.pdf"},
                {"id_documento": "33393309", "nome_documento": "Verbale.pdf"},
            ],
            do_preflight=False,
            cookie_file="C:\\temp\\pst.cookies",
        )
    finally:
        module._soap_call_pst_session_batch_raw_best_effort = orig_best_effort
        module._soap_call_pst_session_batch_raw = orig_batch

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 2
    assert esito["failures"] == []
    assert calls["best_effort"] == 0
    assert len(calls["batch"]) == 3
    assert "<impl:calcolaHash" in calls["batch"][0]["soap_body"]
    assert "<idDoc>33581101</idDoc>" in calls["batch"][0]["soap_body"]
    assert "<idCat>33581101</idCat>" in calls["batch"][1]["soap_body"]
    assert "<idCat>33393309</idCat>" in calls["batch"][2]["soap_body"]


def test_download_documenti_batch_sicid_accetta_documento_con_solo_id_cat():
    module = _load_local_signer()

    orig_best_effort = module._soap_call_pst_session_batch_raw_best_effort
    orig_batch = module._soap_call_pst_session_batch_raw
    calls = {"best_effort": 0, "batch": []}

    try:
        def _fake_best_effort(requests, **kwargs):
            calls["best_effort"] += 1
            return []

        def _fake_batch(requests, **kwargs):
            calls["batch"] = list(requests)
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
            return [(body, 'Content-Type: multipart/related; boundary="abc123"')]

        module._soap_call_pst_session_batch_raw_best_effort = _fake_best_effort
        module._soap_call_pst_session_batch_raw = _fake_batch

        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
            documenti=[{"id_documento": "", "id_cat": "CAT-ONLY-001", "nome_documento": "Atto.pdf"}],
            do_preflight=False,
            cookie_file="C:\\temp\\pst.cookies",
        )
    finally:
        module._soap_call_pst_session_batch_raw_best_effort = orig_best_effort
        module._soap_call_pst_session_batch_raw = orig_batch

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 1
    assert esito["failures"] == []
    assert calls["best_effort"] == 0
    assert len(calls["batch"]) == 1
    assert "<idCat>CAT-ONLY-001</idCat>" in calls["batch"][0]["soap_body"]
    assert esito["files"][0]["id_documento_portale"] == "CAT-ONLY-001"
    assert esito["files"][0]["id_cat"] == "CAT-ONLY-001"


def test_download_documenti_batch_rispetta_original_false_sicid():
    module = _load_local_signer()

    orig_best_effort = module._soap_call_pst_session_batch_raw_best_effort
    orig_batch = module._soap_call_pst_session_batch_raw
    calls = {"best_effort": 0, "batch": []}

    try:
        def _fake_best_effort(requests, **kwargs):
            calls["best_effort"] += 1
            return []

        def _fake_batch(requests, **kwargs):
            calls["batch"] = list(requests)
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
            return [(body, 'Content-Type: multipart/related; boundary="abc123"')]

        module._soap_call_pst_session_batch_raw_best_effort = _fake_best_effort
        module._soap_call_pst_session_batch_raw = _fake_batch

        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
            documenti=[
                {
                    "id_documento": "33581101",
                    "nome_documento": "SentenzaDefinitiva_33581101.pdf",
                    "id_cat": "",
                }
            ],
            do_preflight=False,
            cookie_file="C:\\temp\\pst.cookies",
            original=False,
        )
    finally:
        module._soap_call_pst_session_batch_raw_best_effort = orig_best_effort
        module._soap_call_pst_session_batch_raw = orig_batch

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 1
    assert esito["failures"] == []
    assert calls["best_effort"] == 0
    assert len(calls["batch"]) == 1
    assert "<idCat>33581101</idCat>" in calls["batch"][0]["soap_body"]
    assert "<original>false</original>" in calls["batch"][0]["soap_body"]
    assert calls["batch"][0]["max_time"] == module.PST_DOWNLOAD_MAX_TIME
    assert calls["batch"][0]["connect_timeout"] == module.PST_DOWNLOAD_CONNECT_TIMEOUT
    assert esito["files"][0]["original_documento_portale"] is False
    assert esito["files"][0]["modalita_documento_portale"] == "copia"


def test_download_documento_sigp_usa_timeout_lungo_e_copia_di_default():
    module = _load_local_signer()

    orig_warmup = module._soap_call_pst_session
    orig_raw = module._soap_call_pst_session_raw
    calls = {"warmup": []}

    try:
        def _fake_warmup(**kwargs):
            calls["warmup"].append(kwargs)
            return "<calcolaHashResponse><return>HASH</return></calcolaHashResponse>"

        def _fake_raw(**kwargs):
            calls.update(kwargs)
            body = (
                b"--abc123\r\n"
                b"Content-Type: text/xml\r\n"
                b"Content-Transfer-Encoding: 7bit\r\n\r\n"
                b"<?xml version='1.0' encoding='UTF-8'?><SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>"
                b"<SOAP-ENV:Body><downloadAttoResponse><return href='cid:test-doc-1'/></downloadAttoResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>\r\n"
                b"--abc123\r\n"
                b"Content-Type: application/pdf\r\n"
                b"Content-Transfer-Encoding: base64\r\n"
                b"Content-ID: <test-doc-1>\r\n\r\n"
                b"JVBERi0xLjcK\r\n"
                b"--abc123--\r\n"
            )
            return body, 'Content-Type: multipart/related; boundary="abc123"'

        module._soap_call_pst_session = _fake_warmup
        module._soap_call_pst_session_raw = _fake_raw
        esito = module._pst_download_documento_payload(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP",
            codice_ufficio="0800570152",
            id_documento="3080760",
            nome_documento="decretoLiquidazioneCTU.pdf",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
        )
    finally:
        module._soap_call_pst_session = orig_warmup
        module._soap_call_pst_session_raw = orig_raw

    assert len(calls["warmup"]) == 1
    assert "<impl:calcolaHash" in calls["warmup"][0]["soap_body"]
    assert "<idDoc>3080760</idDoc>" in calls["warmup"][0]["soap_body"]
    assert calls["soap_action"] == "downloadAtto"
    assert 'InvocationDomain name="JPW" role="AVV" group="0800570152"' in calls["soap_body"]
    assert "<idrepeatto>3080760</idrepeatto>" in calls["soap_body"]
    assert calls["max_time"] == module.PST_DOWNLOAD_MAX_TIME
    assert calls["connect_timeout"] == module.PST_DOWNLOAD_CONNECT_TIMEOUT
    assert esito["original_documento_portale"] is False
    assert esito["modalita_documento_portale"] == "copia"


def test_download_documenti_batch_sigp_include_dominio_invocazione():
    module = _load_local_signer()

    orig_batch = module._soap_call_pst_session_batch_raw
    calls = {"requests": []}
    try:
        def _fake_batch(requests, **kwargs):
            calls["requests"].extend(requests)
            body = (
                b"--abc123\r\n"
                b"Content-Type: text/xml\r\n"
                b"Content-Transfer-Encoding: 7bit\r\n\r\n"
                b"<?xml version='1.0' encoding='UTF-8'?><SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>"
                b"<SOAP-ENV:Body><downloadAttoResponse><return href='cid:test-doc-1'/></downloadAttoResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>\r\n"
                b"--abc123\r\n"
                b"Content-Type: application/pdf\r\n"
                b"Content-Transfer-Encoding: base64\r\n"
                b"Content-ID: <test-doc-1>\r\n\r\n"
                b"JVBERi0xLjcK\r\n"
                b"--abc123--\r\n"
            )
            return [(b"<hash/>", "HTTP/1.1 200 OK\r\nContent-Type: text/xml\r\n")] + [
                (body, 'Content-Type: multipart/related; boundary="abc123"')
            ]

        module._soap_call_pst_session_batch_raw = _fake_batch
        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP",
            codice_ufficio="0800570152",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
            documenti=[
                {
                    "id_documento": "3080760",
                    "nome_documento": "decretoGenerico.pdf",
                    "id_repeatto": "3080760",
                }
            ],
            do_preflight=False,
            cookie_file="C:\\temp\\pst.cookies",
            original=False,
        )
    finally:
        module._soap_call_pst_session_batch_raw = orig_batch

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 1
    assert len(calls["requests"]) == 2
    assert "<impl:calcolaHash" in calls["requests"][0]["soap_body"]
    assert "<idDoc>3080760</idDoc>" in calls["requests"][0]["soap_body"]
    assert calls["requests"][0]["extra_headers"] == ["X-WASP-User: RSSMRA80A01H501Z"]
    soap_body = calls["requests"][1]["soap_body"]
    assert 'InvocationDomain name="JPW" role="AVV" group="0800570152"' in soap_body
    assert "<idrepeatto>3080760</idrepeatto>" in soap_body
    assert calls["requests"][1]["soap_action"] == "downloadAtto"


def test_download_documenti_batch_best_effort_non_azzera_lotto_se_un_profilo_fallisce():
    module = _load_local_signer()

    orig_best_effort = module._soap_call_pst_session_batch_raw_best_effort
    orig_batch = module._soap_call_pst_session_batch_raw
    calls = {"downloads": []}
    try:
        def _fake_best_effort(requests, **kwargs):
            assert len(requests) == 2
            return [
                {
                    "body_bytes": b"",
                    "headers_text": "HTTP/1.1 500 Internal Server Error\r\n",
                    "status_code": 500,
                    "error": "Il PST ha restituito una SOAP Fault: Documento primario non trovato",
                },
                {
                    "body_bytes": (
                        b"<?xml version='1.0' encoding='UTF-8'?>"
                        b"<Envelope><return><idDocumento>DOC-OK</idDocumento><idCat>CAT-OK</idCat>"
                        b"<nomeFileOriginale>Documento_OK.pdf</nomeFileOriginale>"
                        b"<dataDeposito>2026-01-08T18:55:28Z</dataDeposito>"
                        b"</return></Envelope>"
                    ),
                    "headers_text": "HTTP/1.1 200 OK\r\n",
                    "status_code": 200,
                    "error": "",
                },
            ]

        def _fake_download_batch(requests, **kwargs):
            calls["downloads"].append(requests)
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
            return [
                (body, 'Content-Type: multipart/related; boundary="abc123"'),
                (body, 'Content-Type: multipart/related; boundary="abc123"'),
            ]

        module._soap_call_pst_session_batch_raw_best_effort = _fake_best_effort
        module._soap_call_pst_session_batch_raw = _fake_download_batch

        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIECIC",
            codice_ufficio="0800570094",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
            documenti=[
                {"id_documento": "DOC-KO", "nome_documento": ""},
                {"id_documento": "DOC-OK", "nome_documento": ""},
            ],
            do_preflight=False,
            cookie_file="C:\\temp\\pst.cookies",
        )
    finally:
        module._soap_call_pst_session_batch_raw_best_effort = orig_best_effort
        module._soap_call_pst_session_batch_raw = orig_batch

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 2
    assert esito["failures"] == []
    assert calls["downloads"]
    assert calls["downloads"][0][0]["soap_body"].find("<idDoc>DOC-KO</idDoc>") != -1
    assert calls["downloads"][0][1]["soap_body"].find("<idDoc>DOC-OK</idDoc>") != -1


def test_soap_call_curl_batch_raw_windows_preserva_cert_store_spec():
    module = _load_local_signer()

    orig_platform = module.sys.platform
    orig_run = module.subprocess.run
    captured = {}

    try:
        def _fake_run(cmd, capture_output, timeout, **kwargs):
            cfg_path = Path(cmd[-1])
            cfg_text = cfg_path.read_text(encoding="utf-8")
            captured["cfg"] = cfg_text
            for line in cfg_text.splitlines():
                if line.startswith('output = "'):
                    Path(line.split('"')[1]).write_bytes(b"<ok/>")
                elif line.startswith('dump-header = "'):
                    Path(line.split('"')[1]).write_text("HTTP/1.1 200 OK\r\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stderr=b"")

        module.sys.platform = "win32"
        module.subprocess.run = _fake_run

        result = module._soap_call_curl_batch_raw(
            [
                {
                    "url": "https://pst.example.test/one",
                    "soap_body": "<xml/>",
                    "soap_action": "",
                },
                {
                    "url": "https://pst.example.test/two",
                    "soap_body": "<xml/>",
                    "soap_action": "",
                },
            ],
            cert_thumbprint="AABBCC11",
        )
    finally:
        module.sys.platform = orig_platform
        module.subprocess.run = orig_run

    assert len(result) == 2
    assert 'cert = "CurrentUser\\\\MY\\\\AABBCC11"' in captured["cfg"]
    assert 'cert = "CurrentUser/MY/AABBCC11"' not in captured["cfg"]
    assert "ssl-no-revoke" in captured["cfg"]


def test_soap_call_curl_raw_windows_applica_ssl_no_revoke():
    module = _load_local_signer()

    orig_platform = module.sys.platform
    orig_run = module.subprocess.run
    captured = {}

    try:
        def _fake_run(cmd, capture_output, timeout, **kwargs):
            captured["cmd"] = cmd
            header_path = Path(cmd[cmd.index("--dump-header") + 1])
            header_path.write_text("HTTP/1.1 200 OK\r\nContent-Type: text/xml\r\n\r\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout=b"<ok/>", stderr=b"")

        module.sys.platform = "win32"
        module.subprocess.run = _fake_run

        body, _headers = module._soap_call_curl_raw(
            url="https://pst.example.test/service",
            soap_body="<xml/>",
            cert_thumbprint="AABBCC11",
        )
    finally:
        module.sys.platform = orig_platform
        module.subprocess.run = orig_run

    assert body == b"<ok/>"
    assert "--ssl-no-revoke" in captured["cmd"]
    assert ["--cert", "CurrentUser\\MY\\AABBCC11"] == captured["cmd"][
        captured["cmd"].index("--cert"):captured["cmd"].index("--cert") + 2
    ]


def test_pst_preflight_windows_applica_ssl_no_revoke():
    module = _load_local_signer()

    orig_platform = module.sys.platform
    orig_run = module.subprocess.run
    captured = {}

    try:
        def _fake_run(cmd, capture_output, text, timeout, encoding, errors, **kwargs):
            captured["cmd"] = cmd
            header_path = Path(cmd[cmd.index("--dump-header") + 1])
            body_path = Path(cmd[cmd.index("-o") + 1])
            header_path.write_text("HTTP/1.1 405 Method Not Allowed\r\nContent-Type: text/plain\r\n\r\n", encoding="utf-8")
            body_path.write_text("ok", encoding="utf-8")
            return SimpleNamespace(returncode=0, stderr="")

        module.sys.platform = "win32"
        module.subprocess.run = _fake_run

        result = module._pst_preflight_auth_curl(
            "https://pst.example.test/service",
            cert_thumbprint="AABBCC11",
        )
    finally:
        module.sys.platform = orig_platform
        module.subprocess.run = orig_run

    assert result["ok"] is True
    assert "--ssl-no-revoke" in captured["cmd"]


def test_errore_certificato_server_pst_non_chiede_di_aggiungere_ssl_no_revoke():
    module = _load_local_signer()

    message = module._curl_errore_leggibile(
        60,
        "SSL certificate problem: unable to get local issuer certificate",
        "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
        timeout_sec=30,
    )

    assert "connessione sicura al PST" in message
    assert "Aggiungere --ssl-no-revoke" not in message


def test_curl_command_windows_preferisce_curl_di_sistema(monkeypatch):
    module = _load_local_signer()

    class _FakePath:
        def __init__(self, *parts):
            self.value = "\\".join(str(part).strip("\\/") for part in parts if str(part))

        def __truediv__(self, other):
            return _FakePath(self.value, other)

        def exists(self):
            return self.value.endswith("System32\\curl.exe")

        def __str__(self):
            return self.value

    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setenv("SystemRoot", r"C:\Windows")
    monkeypatch.setattr(module, "Path", _FakePath)

    assert module._curl_command().endswith(r"System32\curl.exe")


def test_soap_call_pst_session_riprova_con_certificato_dopo_cookie_only():
    module = _load_local_signer()

    orig_call = module._soap_call_curl
    calls = []
    try:
        def _fake_call(*args, **kwargs):
            calls.append(kwargs.get("cert_thumbprint"))
            if kwargs.get("cert_thumbprint") is None:
                raise RuntimeError("Sessione accesso PST scaduta o non disponibile. Esegui di nuovo il test connessione per riaprire il canale autenticato.")
            return "<ok/>"

        module._soap_call_curl = _fake_call

        result = module._soap_call_pst_session(
            url="https://pst.example.test",
            soap_body="<xml/>",
            cert_thumbprint="AABBCC11",
            cookie_file="C:\\temp\\pst.cookies",
            prefer_cookie_only=True,
        )
    finally:
        module._soap_call_curl = orig_call

    assert result == "<ok/>"
    assert calls == [None, "AABBCC11"]


def test_soap_call_pst_session_batch_raw_riprova_con_certificato_dopo_cookie_only():
    module = _load_local_signer()

    orig_call = module._soap_call_curl_batch_raw
    calls = []
    try:
        def _fake_call(requests, cert_thumbprint=None, pkcs11_uri=None):
            calls.append({
                "cert_thumbprint": cert_thumbprint,
                "cookie_files": [req.get("cookie_file") for req in requests],
            })
            if cert_thumbprint is None:
                raise RuntimeError("Il PST ha risposto HTTP 401 Unauthorized da ext.processotelematico.giustizia.it.")
            return [(b"<ok/>", "HTTP/1.1 200 OK\r\n")] * len(requests)

        module._soap_call_curl_batch_raw = _fake_call

        result = module._soap_call_pst_session_batch_raw(
            [
                {
                    "url": "https://pst.example.test",
                    "soap_body": "<xml/>",
                    "cookie_file": "",
                }
            ],
            cert_thumbprint="AABBCC11",
            cookie_file="C:\\temp\\pst.cookies",
            prefer_cookie_only=True,
        )
    finally:
        module._soap_call_curl_batch_raw = orig_call

    assert result == [(b"<ok/>", "HTTP/1.1 200 OK\r\n")]
    assert calls == [
        {"cert_thumbprint": None, "cookie_files": ["C:\\temp\\pst.cookies"]},
        {"cert_thumbprint": "AABBCC11", "cookie_files": ["C:\\temp\\pst.cookies"]},
    ]


def test_soap_call_pst_session_salta_cookie_se_host_mtls_gia_noto():
    module = _load_local_signer()

    orig_call = module._soap_call_curl
    module._mTLS_required_hosts.add("pst.example.test")
    calls = []
    try:
        def _fake_call(*args, **kwargs):
            calls.append(kwargs.get("cert_thumbprint"))
            return "<ok/>"

        module._soap_call_curl = _fake_call

        result = module._soap_call_pst_session(
            url="https://pst.example.test/soap",
            soap_body="<xml/>",
            cert_thumbprint="AABBCC11",
            cookie_file="C:\\temp\\pst.cookies",
            prefer_cookie_only=True,
        )
    finally:
        module._soap_call_curl = orig_call
        module._mTLS_required_hosts.discard("pst.example.test")

    assert result == "<ok/>"
    assert calls == ["AABBCC11"]


def test_soap_call_pst_session_batch_salta_cookie_se_host_mtls_gia_noto():
    module = _load_local_signer()

    orig_call = module._soap_call_curl_batch_raw
    module._mTLS_required_hosts.add("pst.example.test")
    calls = []
    try:
        def _fake_call(requests, cert_thumbprint=None, pkcs11_uri=None):
            calls.append({
                "cert_thumbprint": cert_thumbprint,
                "cookie_files": [req.get("cookie_file") for req in requests],
            })
            return [(b"<ok/>", "HTTP/1.1 200 OK\r\n")]

        module._soap_call_curl_batch_raw = _fake_call

        result = module._soap_call_pst_session_batch_raw(
            [{"url": "https://pst.example.test/soap", "soap_body": "<xml/>"}],
            cert_thumbprint="AABBCC11",
            cookie_file="C:\\temp\\pst.cookies",
            prefer_cookie_only=True,
        )
    finally:
        module._soap_call_curl_batch_raw = orig_call
        module._mTLS_required_hosts.discard("pst.example.test")

    assert result == [(b"<ok/>", "HTTP/1.1 200 OK\r\n")]
    assert calls == [
        {"cert_thumbprint": "AABBCC11", "cookie_files": ["C:\\temp\\pst.cookies"]},
    ]


def test_pst_best_effort_batch_401_non_diventa_ricerca_vuota():
    module = _load_local_signer()

    message = module._pst_best_effort_batch_blocking_error(
        [
            {
                "body_bytes": b"<html><title>401 Unauthorized</title></html>",
                "headers_text": "HTTP/1.1 401 Unauthorized\r\n",
                "status_code": 401,
                "error": "Il PST ha risposto HTTP 401 Unauthorized da ext.processotelematico.giustizia.it.",
            },
            {
                "body_bytes": b"<html><title>401 Unauthorized</title></html>",
                "headers_text": "HTTP/1.1 401 Unauthorized\r\n",
                "status_code": 401,
                "error": "Il PST ha risposto HTTP 401 Unauthorized da ext.processotelematico.giustizia.it.",
            },
        ]
    )

    assert "Autenticazione PST non riuscita" in message
    assert "401 Unauthorized" in message


def test_pst_best_effort_batch_soap_fault_non_diventa_ricerca_vuota():
    module = _load_local_signer()

    fault_body = (
        b'<SOAP-ENV:Envelope xmlns:SOAP-ENV="http://schemas.xmlsoap.org/soap/envelope/">'
        b"<SOAP-ENV:Body><SOAP-ENV:Fault><faultcode>SOAP-ENV:Client</faultcode>"
        b"<faultstring>L'utente 'B3A95785DA8A2E69E040A8C001C863D0' non puo' eseguire "
        b"l'operazione '{urn:CONS-SICC-BE}execute'</faultstring>"
        b"</SOAP-ENV:Fault></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    )

    message = module._pst_best_effort_batch_blocking_error(
        [
            {"body_bytes": fault_body, "headers_text": "HTTP/1.1 500 Internal Server Error\r\n", "error": ""},
            {"body_bytes": b"", "headers_text": "HTTP/1.1 200 OK\r\n", "error": ""},
        ]
    )

    assert "SOAP Fault" in message
    assert "non puo' eseguire" in message


def test_pst_best_effort_batch_fault_non_blocca_se_esiste_risposta_valida():
    module = _load_local_signer()

    message = module._pst_best_effort_batch_blocking_error(
        [
            {"body_bytes": b"<Envelope><Body><ricercaResponse/></Body></Envelope>", "headers_text": "HTTP/1.1 200 OK\r\n", "error": ""},
            {
                "body_bytes": b"<Envelope><Body><Fault><faultstring>Service non trovato</faultstring></Fault></Body></Envelope>",
                "headers_text": "HTTP/1.1 500 Internal Server Error\r\n",
                "error": "",
            },
        ]
    )

    assert message == ""


def test_soap_call_pst_session_non_richiede_secondo_certificato_su_timeout():
    module = _load_local_signer()

    orig_call = module._soap_call_curl
    calls = []
    try:
        def _fake_call(*args, **kwargs):
            calls.append(kwargs.get("cert_thumbprint"))
            raise RuntimeError(
                "Timeout connessione a ext.processotelematico.giustizia.it (90s).\n"
                "Il servizio PST potrebbe essere sovraccarico. Riprovare tra qualche minuto."
            )

        module._soap_call_curl = _fake_call

        try:
            module._soap_call_pst_session(
                url="https://pst.example.test",
                soap_body="<xml/>",
                cert_thumbprint="AABBCC11",
                cookie_file="C:\\temp\\pst.cookies",
                prefer_cookie_only=True,
            )
            raise AssertionError("Atteso RuntimeError")
        except RuntimeError as err:
            assert "Timeout connessione" in str(err)
    finally:
        module._soap_call_curl = orig_call

    assert calls == [None]


def test_soap_call_pst_session_batch_raw_non_richiede_secondo_certificato_su_timeout():
    module = _load_local_signer()

    orig_call = module._soap_call_curl_batch_raw
    calls = []
    try:
        def _fake_call(requests, cert_thumbprint=None, pkcs11_uri=None):
            calls.append(cert_thumbprint)
            raise RuntimeError(
                "Timeout connessione a ext.processotelematico.giustizia.it (90s).\n"
                "Il servizio PST potrebbe essere sovraccarico. Riprovare tra qualche minuto."
            )

        module._soap_call_curl_batch_raw = _fake_call

        try:
            module._soap_call_pst_session_batch_raw(
                [{"url": "https://pst.example.test", "soap_body": "<xml/>"}],
                cert_thumbprint="AABBCC11",
                cookie_file="C:\\temp\\pst.cookies",
                prefer_cookie_only=True,
            )
            raise AssertionError("Atteso RuntimeError")
        except RuntimeError as err:
            assert "Timeout connessione" in str(err)
    finally:
        module._soap_call_curl_batch_raw = orig_call

    assert calls == [None]


def test_download_documenti_batch_con_sessione_attiva_usa_certificato_in_lotto_unico():
    module = _load_local_signer()

    orig_batch = module._soap_call_curl_batch_raw
    orig_download = module._pst_download_documento_payload
    calls = {"batch": [], "cert_thumbprint": None}
    try:
        def _fake_batch(requests, cert_thumbprint=None, pkcs11_uri=None):
            calls["batch"] = list(requests)
            calls["cert_thumbprint"] = cert_thumbprint
            return [(b"<Envelope><return/></Envelope>", "HTTP/1.1 200 OK\r\n")] * len(requests)

        def _fake_download(**kwargs):
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

        module._soap_call_curl_batch_raw = _fake_batch
        module._pst_download_documento_payload = _fake_download

        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
            documenti=[{"id_documento": "33581101", "nome_documento": "Sentenza.pdf"}],
            do_preflight=False,
            cookie_file="C:\\temp\\pst.cookies",
        )
    finally:
        module._soap_call_curl_batch_raw = orig_batch
        module._pst_download_documento_payload = orig_download

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 1
    assert len(calls["batch"]) == 1
    assert calls["cert_thumbprint"] == "AABBCC11"
    assert "<idCat>33581101</idCat>" in calls["batch"][0]["soap_body"]
    assert calls["batch"][0]["cookie_file"] == ""


def test_download_documenti_batch_timeout_non_torna_al_download_singolo():
    module = _load_local_signer()

    orig_batch = module._soap_call_pst_session_batch_raw
    orig_single = module._soap_call_curl_raw
    calls = {"batch": 0, "single": 0}
    try:
        def _fake_batch(*args, **kwargs):
            calls["batch"] += 1
            raise RuntimeError(
                "Timeout connessione a ext.processotelematico.giustizia.it (300s). "
                "Il servizio PST potrebbe essere sovraccarico."
            )

        def _fake_single(*args, **kwargs):
            calls["single"] += 1
            raise AssertionError("non deve tornare al download singolo")

        module._soap_call_pst_session_batch_raw = _fake_batch
        module._soap_call_curl_raw = _fake_single

        esito = module._pst_download_documenti_batch_payloads(
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
            codice_ufficio="0800570094",
            cert_thumbprint="AABBCC11",
            cf_avvocato="RSSMRA80A01H501Z",
            documenti=[{"id_documento": "33581101", "nome_documento": "Sentenza.pdf"}],
            do_preflight=False,
            cookie_file="C:\\temp\\pst.cookies",
        )
    finally:
        module._soap_call_pst_session_batch_raw = orig_batch
        module._soap_call_curl_raw = orig_single

    assert esito["ok"] is True
    assert esito["documenti_scaricati"] == 0
    assert calls == {"batch": 1, "single": 0}
    assert "non ricade sul download singolo" in esito["failures"][0]["errore"]


def test_pst_prepare_authenticated_session_esegue_preflight_una_sola_volta():
    module = _load_local_signer()

    orig_preflight = module._pst_preflight_auth_curl
    calls = []
    try:
        def _fake_preflight(url, cert_thumbprint=None, pkcs11_uri=None, cookie_file=None):
            calls.append(
                {
                    "url": url,
                    "cert_thumbprint": cert_thumbprint,
                    "cookie_file": cookie_file,
                }
            )
            return {
                "ok": True,
                "http_code": 405,
                "content_type": "text/html",
            }

        module._pst_preflight_auth_curl = _fake_preflight
        session_entry = module._create_pst_session(
            cert_thumbprint="AABBCC11",
            tribunale="0580010",
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
            cf_avvocato="RSSMRA80A01H501Z",
        )

        refreshed, prefer_cookie_only = module._pst_prepare_authenticated_session(
            session_entry,
            tribunale="0580010",
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
            cf_avvocato="RSSMRA80A01H501Z",
            cert_thumbprint="AABBCC11",
        )
        refreshed_again, prefer_cookie_only_again = module._pst_prepare_authenticated_session(
            refreshed,
            tribunale="0580010",
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
            cf_avvocato="RSSMRA80A01H501Z",
            cert_thumbprint="AABBCC11",
        )
    finally:
        module._pst_preflight_auth_curl = orig_preflight

    assert prefer_cookie_only is True
    assert prefer_cookie_only_again is True
    assert refreshed_again["auth_ready"] is True
    assert len(calls) == 1
    assert calls[0]["cert_thumbprint"] == "AABBCC11"
    assert calls[0]["cookie_file"]


def test_pst_prepare_authenticated_session_non_disattiva_cookie_se_host_mtls_gia_noto():
    module = _load_local_signer()

    orig_preflight = module._pst_preflight_auth_curl
    host = "ext.processotelematico.giustizia.it"
    module._mTLS_required_hosts.add(host)
    calls = []
    try:
        def _fake_preflight(url, cert_thumbprint=None, pkcs11_uri=None, cookie_file=None):
            calls.append({"url": url, "cert_thumbprint": cert_thumbprint, "cookie_file": cookie_file})
            return {
                "ok": True,
                "http_code": 405,
                "content_type": "text/html",
            }

        module._pst_preflight_auth_curl = _fake_preflight
        session_entry = module._create_pst_session(
            cert_thumbprint="AABBCC11",
            tribunale="0580010",
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
            cf_avvocato="RSSMRA80A01H501Z",
        )

        refreshed, prefer_cookie_only = module._pst_prepare_authenticated_session(
            session_entry,
            tribunale="0580010",
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
            cf_avvocato="RSSMRA80A01H501Z",
            cert_thumbprint="AABBCC11",
        )
    finally:
        module._pst_preflight_auth_curl = orig_preflight
        module._mTLS_required_hosts.discard(host)

    assert prefer_cookie_only is True
    assert refreshed["auth_ready"] is True
    assert len(calls) == 1


def test_pst_prepare_authenticated_session_non_marca_cookie_pronto_su_preflight_timeout():
    module = _load_local_signer()

    orig_preflight = module._pst_preflight_auth_curl
    calls = []
    try:
        def _fake_preflight(url, cert_thumbprint=None, pkcs11_uri=None, cookie_file=None):
            calls.append({"url": url, "cert_thumbprint": cert_thumbprint, "cookie_file": cookie_file})
            return {
                "ok": True,
                "http_code": None,
                "content_type": None,
                "warning": "Preflight PST in timeout non bloccante.",
            }

        module._pst_preflight_auth_curl = _fake_preflight
        session_entry = module._create_pst_session(
            cert_thumbprint="AABBCC11",
            tribunale="0580010",
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
            cf_avvocato="RSSMRA80A01H501Z",
        )

        refreshed, prefer_cookie_only = module._pst_prepare_authenticated_session(
            session_entry,
            tribunale="0580010",
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
            cf_avvocato="RSSMRA80A01H501Z",
            cert_thumbprint="AABBCC11",
        )
        refreshed_again, prefer_cookie_only_again = module._pst_prepare_authenticated_session(
            refreshed,
            tribunale="0580010",
            base_url="https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID",
            cf_avvocato="RSSMRA80A01H501Z",
            cert_thumbprint="AABBCC11",
        )
    finally:
        module._pst_preflight_auth_curl = orig_preflight

    assert prefer_cookie_only is False
    assert prefer_cookie_only_again is False
    assert refreshed_again["auth_ready"] is False
    assert refreshed_again["preflight_attempted"] is True
    assert len(calls) == 1


def test_pst_ricerca_snapshot_usa_batch_certificato_senza_preflight_separato():
    module = _load_local_signer()

    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_risolvi_base_pst_runtime": module._risolvi_base_pst_runtime,
        "_pst_url_ricerca": module._pst_url_ricerca,
        "_pst_url_documenti": module._pst_url_documenti,
        "_risolvi_codice_ufficio_pst": module._risolvi_codice_ufficio_pst,
        "_require_certificato_pst": module._require_certificato_pst,
        "_cf_avvocato_pst": module._cf_avvocato_pst,
        "_pst_namespace_qbuilder": module._pst_namespace_qbuilder,
        "_pst_servizio_sigp": module._pst_servizio_sigp,
        "_ensure_pst_session_entry": module._ensure_pst_session_entry,
        "_pst_preflight_auth_curl": module._pst_preflight_auth_curl,
        "_resolve_pst_session_entry": module._resolve_pst_session_entry,
        "_soap_call_pst_session_batch_raw": module._soap_call_pst_session_batch_raw,
        "_soap_call_pst_session_batch_raw_best_effort": module._soap_call_pst_session_batch_raw_best_effort,
        "_estrai_fault_soap": module._estrai_fault_soap,
        "_parse_fascicoli_xml": module._parse_fascicoli_xml,
        "_parse_documenti_xml": module._parse_documenti_xml,
        "_risolvi_ufficio_da_snapshot": module._risolvi_ufficio_da_snapshot,
        "_update_pst_session": module._update_pst_session,
        "_get_pst_session": module._get_pst_session,
    }
    captured = {"batch": None, "preflight": 0, "session_ids": []}

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0910011",
                "numero_rg": "274",
                "anno_rg": "2026",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "RSSMRA80A01H501Z",
                "pst_session_id": "SID-STALENESS-FROM-BROWSER",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._curl_disponibile = lambda: True
        module._risolvi_base_pst_runtime = lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID"
        module._pst_url_ricerca = lambda base_url: base_url.rstrip("/")
        module._pst_url_documenti = lambda base_url: base_url.rstrip("/")
        module._risolvi_codice_ufficio_pst = lambda tribunale: "0800570094"
        module._require_certificato_pst = lambda thumbprint: "AABBCC11"
        module._cf_avvocato_pst = lambda cf, thumbprint: "RSSMRA80A01H501Z"
        module._pst_namespace_qbuilder = lambda base_url: "urn:test-qbuilder"
        module._pst_servizio_sigp = lambda base_url: False
        def _fake_ensure_pst_session_entry(requested_session_id, **kwargs):
            captured["session_ids"].append(requested_session_id)
            if requested_session_id:
                raise RuntimeError(
                    "session_expired: Sessione accesso PST scaduta o non disponibile."
                )
            return (
                {
                    "session_id": "SID-SNAPSHOT",
                    "cookie_file": "C:\\temp\\pst.cookies",
                    "auth_ready": False,
                    "cf_avvocato": "RSSMRA80A01H501Z",
                },
                True,
            )

        module._ensure_pst_session_entry = _fake_ensure_pst_session_entry

        def _fake_preflight(*args, **kwargs):
            captured["preflight"] += 1
            captured["preflight_kwargs"] = kwargs
            return {
                "ok": True,
                "http_code": 405,
                "content_type": "text/html",
                "nota": "Certificato selezionato e richiesta PIN gestita dal sistema.",
            }

        def _fake_batch(requests, **kwargs):
            captured["batch"] = {"requests": list(requests), "kwargs": kwargs}
            return [
                (b"<search/>", "HTTP/1.1 200 OK\r\n"),
                (b"<profile/>", "HTTP/1.1 200 OK\r\n"),
                (b"<documents/>", "HTTP/1.1 200 OK\r\n"),
            ]

        def _fake_best_effort(requests, **kwargs):
            return [
                {"body_bytes": body, "headers_text": headers, "status_code": 200, "error": ""}
                for body, headers in _fake_batch(requests, **kwargs)
            ]

        module._pst_preflight_auth_curl = _fake_preflight
        module._resolve_pst_session_entry = lambda session_id: None
        module._soap_call_pst_session_batch_raw_best_effort = _fake_best_effort
        module._estrai_fault_soap = lambda xml: None
        def _fake_parse_fascicoli(xml):
            if "profile" not in str(xml):
                return []
            return [
                {
                    "numero_rg": "274",
                    "anno_rg": 2026,
                    "codice_ufficio": "0800570094",
                    "nome_ufficio": "Tribunale di Palmi",
                    "ruolo": "Civile",
                    "stato": "Pendente",
                    "oggetto": "Usucapione",
                    "data_iscrizione": "2026-03-05",
                    "data_udienza": "2026-07-09",
                    "parti": ["Assistito"],
                }
            ]

        module._parse_fascicoli_xml = _fake_parse_fascicoli
        module._parse_documenti_xml = lambda xml: [
            {"id_documento": "DOC-1", "nome": "Atto.pdf", "id_cat": "DOC-1"}
        ]
        module._risolvi_ufficio_da_snapshot = lambda codice: {"nome": "Tribunale di Palmi"}
        module._update_pst_session = lambda *args, **kwargs: None
        module._get_pst_session = lambda *args, **kwargs: None

        module._Handler._pst_ricerca_snapshot(_FakeHandler())
    finally:
        for name, value in originals.items():
            setattr(module, name, value)

    assert captured["status"] == 200
    assert captured["preflight"] == 0
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["fascicoli"][0]["numero_rg"] == "274"
    assert captured["payload"]["fascicoli"][0]["nome_ufficio"] == "Tribunale di Palmi"
    assert captured["payload"]["fascicoli"][0]["oggetto"] == "Usucapione"
    assert captured["payload"]["snapshot"]["fascicolo"]["data_iscrizione"] == "2026-03-05"
    assert captured["payload"]["documenti"][0]["id_documento"] == "DOC-1"
    assert captured["payload"]["snapshot"]["fascicolo"]["numero"] == "274"
    assert captured["session_ids"] == ["SID-STALENESS-FROM-BROWSER", ""]
    assert len(captured["batch"]["requests"]) == 21
    assert any("/JPW_SIL" in request["url"] for request in captured["batch"]["requests"])
    assert any("/JPW_SIVG" in request["url"] for request in captured["batch"]["requests"])
    assert any("/JPW_MIN" in request["url"] for request in captured["batch"]["requests"])
    assert any("/JPW_SIMIN" in request["url"] for request in captured["batch"]["requests"])
    assert captured["batch"]["kwargs"]["cert_thumbprint"] == "AABBCC11"
    assert captured["batch"]["kwargs"]["prefer_cookie_only"] is False


def test_pst_ricerca_snapshot_fault_client_su_sicid_passa_a_siecic(monkeypatch):
    module = _load_local_signer()
    captured = {}
    monkeypatch.setenv("HACS_SIGNER_PST_REGISTER_FALLBACK", "1")

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0800570094",
                "numero_rg": "274",
                "anno_rg": "2026",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "RSSMRA80A01H501Z",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    monkeypatch.setattr(module, "_curl_disponibile", lambda: True)
    monkeypatch.setattr(
        module,
        "_risolvi_base_pst_runtime",
        lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
    )
    monkeypatch.setattr(module, "_risolvi_codice_ufficio_pst", lambda tribunale: "0800570094")
    monkeypatch.setattr(module, "_require_certificato_pst", lambda thumbprint: "AABBCC11")
    monkeypatch.setattr(module, "_cf_avvocato_pst", lambda cf, thumbprint: "RSSMRA80A01H501Z")
    monkeypatch.setattr(
        module,
        "_risolvi_ufficio_da_snapshot",
        lambda codice: {
            "nome": "Tribunale di Palmi",
            "servizi_ministero": ["JPW_SICID", "JPW_SIECIC"],
        },
    )
    monkeypatch.setattr(
        module,
        "_ensure_pst_session_entry",
        lambda *args, **kwargs: (
            {
                "session_id": "SID-PALMI",
                "cookie_file": "C:\\temp\\pst.cookies",
                "auth_ready": False,
                "cf_avvocato": "RSSMRA80A01H501Z",
            },
            True,
        ),
    )
    captured["preflight"] = 0

    def _fake_preflight(*args, **kwargs):
        captured["preflight"] += 1
        captured["preflight_kwargs"] = kwargs
        return {
            "ok": True,
            "http_code": 405,
            "content_type": "text/html",
            "nota": "Certificato selezionato e richiesta PIN gestita dal sistema.",
        }

    monkeypatch.setattr(module, "_pst_preflight_auth_curl", _fake_preflight)
    monkeypatch.setattr(module, "_resolve_pst_session_entry", lambda session_id: None)

    def _fake_batch(requests, **kwargs):
        captured["requests"] = list(requests)
        results = []
        for request in requests:
            servizio = module._pst_servizio_proxy(request.get("url", ""))
            body = str(request.get("soap_body") or "")
            if servizio == "JPW_SICID" and "RicercaInformazioniFascicoloPerTipo" in body:
                results.append((b"<fault-primary/>", "HTTP/1.1 200 OK\r\n"))
            elif servizio == "JPW_SIECIC" and "<name>InfoFascicolo</name>" in body:
                results.append((b"<fallback-search/>", "HTTP/1.1 200 OK\r\n"))
            elif servizio == "JPW_SIECIC" and "<name>ElencoDocumenti</name>" in body:
                results.append((b"<fallback-docs/>", "HTTP/1.1 200 OK\r\n"))
            elif servizio == "JPW_SIECIC":
                results.append((b"<fallback-profile/>", "HTTP/1.1 200 OK\r\n"))
            elif servizio == "JPW_SICID" and "<name>DocumentiFascicolo</name>" in body:
                results.append((b"<primary-docs/>", "HTTP/1.1 200 OK\r\n"))
            elif servizio == "JPW_SICID":
                results.append((b"<primary-profile/>", "HTTP/1.1 200 OK\r\n"))
            else:
                results.append((b"<empty/>", "HTTP/1.1 200 OK\r\n"))
        return results

    def _fake_best_effort(requests, **kwargs):
        return [
            {"body_bytes": body, "headers_text": headers, "status_code": 200, "error": ""}
            for body, headers in _fake_batch(requests, **kwargs)
        ]

    monkeypatch.setattr(module, "_soap_call_pst_session_batch_raw_best_effort", _fake_best_effort)
    monkeypatch.setattr(
        module,
        "_estrai_fault_soap",
        lambda xml: "SOAP-ENV:Client RicercaInformazioniFascicoloPerTipo" if "fault-primary" in str(xml) else None,
    )
    monkeypatch.setattr(
        module,
        "_parse_fascicoli_xml",
        lambda xml: [
            {
                "numero_rg": "274",
                "anno_rg": 2026,
                "codice_ufficio": "0800570094",
                "nome_ufficio": "Tribunale di Palmi",
                "oggetto": "Usucapione",
            }
        ]
        if "fallback-search" in str(xml)
        else [],
    )
    monkeypatch.setattr(
        module,
        "_parse_documenti_xml",
        lambda xml: [{"id_documento": "DOC-SIECIC", "nome": "Atto.pdf"}] if "fallback-docs" in str(xml) else [],
    )
    monkeypatch.setattr(module, "_update_pst_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_get_pst_session", lambda *args, **kwargs: None)

    module._Handler._pst_ricerca_snapshot(_FakeHandler())

    assert captured["status"] == 200
    assert captured["preflight"] == 0
    assert len(captured["requests"]) == 18
    assert any("/JPW_SIL" in request["url"] for request in captured["requests"])
    assert any("/JPW_SIVG" in request["url"] for request in captured["requests"])
    assert any("/JPW_MIN" in request["url"] for request in captured["requests"])
    assert any("/JPW_SIMIN" in request["url"] for request in captured["requests"])
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["fascicoli"][0]["numero_rg"] == "274"
    assert captured["payload"]["documenti"][0]["id_documento"] == "DOC-SIECIC"


def test_pst_ricerca_snapshot_fault_fallback_non_diventa_ricerca_vuota(monkeypatch):
    module = _load_local_signer()
    captured = {}
    monkeypatch.setenv("HACS_SIGNER_PST_REGISTER_FALLBACK", "1")

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0910011",
                "numero_rg": "3441",
                "anno_rg": "2025",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "MNTGPP94L01G791A",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    monkeypatch.setattr(module, "_curl_disponibile", lambda: True)
    monkeypatch.setattr(
        module,
        "_risolvi_base_pst_runtime",
        lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
    )
    monkeypatch.setattr(module, "_risolvi_codice_ufficio_pst", lambda tribunale: "0800570094")
    monkeypatch.setattr(module, "_require_certificato_pst", lambda thumbprint: "AABBCC11")
    monkeypatch.setattr(module, "_cf_avvocato_pst", lambda cf, thumbprint: "MNTGPP94L01G791A")
    monkeypatch.setattr(
        module,
        "_risolvi_ufficio_da_snapshot",
        lambda codice: {
            "nome": "Tribunale di Palmi",
            "servizi_ministero": ["JPW_SICID", "JPW_SIECIC"],
        },
    )
    monkeypatch.setattr(
        module,
        "_ensure_pst_session_entry",
        lambda *args, **kwargs: (
            {
                "session_id": "SID-GIUSEPPE",
                "cookie_file": "C:\\temp\\pst.cookies",
                "auth_ready": False,
                "cf_avvocato": "MNTGPP94L01G791A",
            },
            True,
        ),
    )
    monkeypatch.setattr(module, "_resolve_pst_session_entry", lambda session_id: None)
    monkeypatch.setattr(module, "_update_pst_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_get_pst_session", lambda *args, **kwargs: None)

    user_fault = (
        b"<SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>"
        b"<SOAP-ENV:Body><SOAP-ENV:Fault><faultcode>SOAP-ENV:Client</faultcode>"
        b"<faultstring>L'utente 'B3A95785DA8A2E69E040A8C001C863D0' non puo' eseguire "
        b"l'operazione '{urn:CONS-SICC-BE}execute'</faultstring>"
        b"</SOAP-ENV:Fault></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    )
    service_fault = (
        b"<SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>"
        b"<SOAP-ENV:Body><SOAP-ENV:Fault><faultcode>SOAP-ENV:Client</faultcode>"
        b"<faultstring>Service 'InfoFascicolo' non trovato</faultstring>"
        b"</SOAP-ENV:Fault></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    )

    def _fake_best_effort(requests, **kwargs):
        captured["requests"] = list(requests)
        bodies = []
        for request in requests:
            servizio = module._pst_servizio_proxy(request.get("url", ""))
            body = str(request.get("soap_body") or "")
            if servizio == "JPW_SICID" and "RicercaInformazioniFascicoloPerTipo" in body:
                bodies.append(b"")
            elif servizio == "JPW_SICID" and "<name>DocumentiFascicolo</name>" in body:
                bodies.append(b"<documents/>")
            elif servizio == "JPW_SICID":
                bodies.append(b"<profile/>")
            elif servizio in {"JPW_SIL", "JPW_SIVG"}:
                bodies.append(user_fault)
            else:
                bodies.append(service_fault)
        return [
            {"body_bytes": bodies[index], "headers_text": "HTTP/1.1 200 OK\r\n", "status_code": 200, "error": ""}
            for index, _request in enumerate(requests)
        ]

    monkeypatch.setattr(module, "_soap_call_pst_session_batch_raw_best_effort", _fake_best_effort)

    module._Handler._pst_ricerca_snapshot(_FakeHandler())

    assert captured["status"] == 500
    assert len(captured["requests"]) == 21
    assert captured["payload"]["ok"] is False
    assert "SOAP Fault" in captured["payload"]["errore"]
    assert "non puo' eseguire" in captured["payload"]["errore"]


def test_pst_ricerca_snapshot_risposta_valida_vuota_non_bloccata_da_fault_fallback(monkeypatch):
    module = _load_local_signer()
    captured = {}
    monkeypatch.setenv("HACS_SIGNER_PST_REGISTER_FALLBACK", "1")

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0910011",
                "numero_rg": "9999",
                "anno_rg": "2025",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "MNTGPP94L01G791A",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    monkeypatch.setattr(module, "_curl_disponibile", lambda: True)
    monkeypatch.setattr(
        module,
        "_risolvi_base_pst_runtime",
        lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
    )
    monkeypatch.setattr(module, "_risolvi_codice_ufficio_pst", lambda tribunale: "0800570094")
    monkeypatch.setattr(module, "_require_certificato_pst", lambda thumbprint: "AABBCC11")
    monkeypatch.setattr(module, "_cf_avvocato_pst", lambda cf, thumbprint: "MNTGPP94L01G791A")
    monkeypatch.setattr(
        module,
        "_risolvi_ufficio_da_snapshot",
        lambda codice: {
            "nome": "Tribunale di Palmi",
            "servizi_ministero": ["JPW_SICID", "JPW_SIECIC"],
        },
    )
    monkeypatch.setattr(
        module,
        "_ensure_pst_session_entry",
        lambda *args, **kwargs: (
            {
                "session_id": "SID-EMPTY",
                "cookie_file": "C:\\temp\\pst.cookies",
                "auth_ready": False,
                "cf_avvocato": "MNTGPP94L01G791A",
            },
            True,
        ),
    )
    monkeypatch.setattr(module, "_resolve_pst_session_entry", lambda session_id: None)
    monkeypatch.setattr(module, "_update_pst_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_get_pst_session", lambda *args, **kwargs: None)

    empty_rowlist = (
        b"<?xml version='1.0' encoding='UTF-8'?>"
        b"<SOAP-ENV:Envelope xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' "
        b"xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>"
        b"<SOAP-ENV:Body><ns1:executeResponse xmlns:ns1='urn:CONS-SICC-BE'>"
        b"<return available='0' xmlns:ns2='urn:qbuilder-types' xsi:type='ns2:rowListType'/>"
        b"</ns1:executeResponse></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    )
    service_fault = (
        b"<SOAP-ENV:Envelope xmlns:SOAP-ENV='http://schemas.xmlsoap.org/soap/envelope/'>"
        b"<SOAP-ENV:Body><SOAP-ENV:Fault><faultcode>SOAP-ENV:Client</faultcode>"
        b"<faultstring>Service 'InfoFascicolo' non trovato</faultstring>"
        b"</SOAP-ENV:Fault></SOAP-ENV:Body></SOAP-ENV:Envelope>"
    )

    def _fake_best_effort(requests, **kwargs):
        captured["requests"] = list(requests)
        bodies = []
        for request in requests:
            servizio = module._pst_servizio_proxy(request.get("url", ""))
            body = str(request.get("soap_body") or "")
            if servizio == "JPW_SICID" and "RicercaInformazioniFascicoloPerTipo" in body:
                bodies.append(empty_rowlist)
            elif servizio == "JPW_SICID" and "<name>DocumentiFascicolo</name>" in body:
                bodies.append(b"<documents/>")
            elif servizio == "JPW_SICID":
                bodies.append(b"<profile/>")
            else:
                bodies.append(service_fault)
        return [
            {"body_bytes": bodies[index], "headers_text": "HTTP/1.1 200 OK\r\n", "status_code": 200, "error": ""}
            for index, _request in enumerate(requests)
        ]

    monkeypatch.setattr(module, "_soap_call_pst_session_batch_raw_best_effort", _fake_best_effort)

    module._Handler._pst_ricerca_snapshot(_FakeHandler())

    assert captured["status"] == 200
    assert len(captured["requests"]) == 21
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["fascicoli"] == []
    assert captured["payload"]["documenti"] == []


def test_pst_ricerca_snapshot_prova_codice_ufficio_ufficiale_se_diverso(monkeypatch):
    module = _load_local_signer()
    captured = {}
    monkeypatch.setenv("HACS_SIGNER_PST_REGISTER_FALLBACK", "0")

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0910011",
                "numero_rg": "3441",
                "anno_rg": "2025",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "RSSMRA80A01H501Z",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    monkeypatch.setattr(module, "_curl_disponibile", lambda: True)
    monkeypatch.setattr(
        module,
        "_risolvi_base_pst_runtime",
        lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SICID",
    )
    monkeypatch.setattr(module, "_risolvi_codice_ufficio_pst", lambda tribunale: "0800570094")
    monkeypatch.setattr(module, "_require_certificato_pst", lambda thumbprint: "AABBCC11")
    monkeypatch.setattr(module, "_cf_avvocato_pst", lambda cf, thumbprint: "RSSMRA80A01H501Z")
    monkeypatch.setattr(module, "_risolvi_ufficio_da_snapshot", lambda codice: {"nome": "Tribunale di Palmi"})
    monkeypatch.setattr(
        module,
        "_ensure_pst_session_entry",
        lambda *args, **kwargs: (
            {
                "session_id": "SID-PALMI",
                "cookie_file": "C:\\temp\\pst.cookies",
                "auth_ready": False,
                "cf_avvocato": "RSSMRA80A01H501Z",
            },
            True,
        ),
    )
    captured["preflight"] = 0

    def _fake_preflight(*args, **kwargs):
        captured["preflight"] += 1
        captured["preflight_kwargs"] = kwargs
        return {
            "ok": True,
            "http_code": 405,
            "content_type": "text/html",
            "nota": "Certificato selezionato e richiesta PIN gestita dal sistema.",
        }

    monkeypatch.setattr(module, "_pst_preflight_auth_curl", _fake_preflight)
    monkeypatch.setattr(module, "_resolve_pst_session_entry", lambda session_id: None)

    def _fake_best_effort(requests, **kwargs):
        captured["requests"] = list(requests)
        bodies = [
            b"<primary-search/>",
            b"<primary-profile/>",
            b"<primary-docs/>",
            b"<official-search/>",
            b"<official-profile/>",
            b"<official-docs/>",
        ]
        return [
            {"body_bytes": body, "headers_text": "HTTP/1.1 200 OK\r\n", "status_code": 200, "error": ""}
            for body in bodies
        ]

    monkeypatch.setattr(module, "_soap_call_pst_session_batch_raw_best_effort", _fake_best_effort)
    monkeypatch.setattr(module, "_estrai_fault_soap", lambda xml: None)
    monkeypatch.setattr(
        module,
        "_parse_fascicoli_xml",
        lambda xml: [
            {
                "numero_rg": "3441",
                "anno_rg": 2025,
                "codice_ufficio": "0910011",
                "nome_ufficio": "Tribunale di Palmi",
                "oggetto": "Fascicolo reale",
            }
        ]
        if "official-search" in str(xml)
        else [],
    )
    monkeypatch.setattr(
        module,
        "_parse_documenti_xml",
        lambda xml: [{"id_documento": "DOC-PALMI", "nome": "Atto.pdf"}] if "official-docs" in str(xml) else [],
    )
    monkeypatch.setattr(module, "_update_pst_session", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "_get_pst_session", lambda *args, **kwargs: None)

    module._Handler._pst_ricerca_snapshot(_FakeHandler())

    assert captured["status"] == 200
    assert captured["preflight"] == 0
    assert len(captured["requests"]) == 6
    assert any('group="0910011"' in request["soap_body"] for request in captured["requests"])
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["fascicoli"][0]["numero_rg"] == "3441"
    assert captured["payload"]["snapshot"]["fascicolo"]["ufficio_codice"] == "0910011"
    assert captured["payload"]["documenti"][0]["id_documento"] == "DOC-PALMI"


def test_pst_ricerca_snapshot_sigp_include_ricerca_atti_nel_batch_visualizzazione():
    module = _load_local_signer()

    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_risolvi_base_pst_runtime": module._risolvi_base_pst_runtime,
        "_pst_url_ricerca": module._pst_url_ricerca,
        "_pst_url_documenti": module._pst_url_documenti,
        "_risolvi_codice_ufficio_pst": module._risolvi_codice_ufficio_pst,
        "_require_certificato_pst": module._require_certificato_pst,
        "_cf_avvocato_pst": module._cf_avvocato_pst,
        "_pst_namespace_qbuilder": module._pst_namespace_qbuilder,
        "_pst_servizio_sigp": module._pst_servizio_sigp,
        "_ensure_pst_session_entry": module._ensure_pst_session_entry,
        "_pst_preflight_auth_curl": module._pst_preflight_auth_curl,
        "_resolve_pst_session_entry": module._resolve_pst_session_entry,
        "_soap_call_pst_session_batch_raw": module._soap_call_pst_session_batch_raw,
        "_soap_call_pst_session_batch_raw_best_effort": module._soap_call_pst_session_batch_raw_best_effort,
        "_sigp_documenti_da_ricerca_atti": module._sigp_documenti_da_ricerca_atti,
        "_estrai_fault_soap": module._estrai_fault_soap,
        "_parse_fascicoli_xml": module._parse_fascicoli_xml,
        "_parse_documenti_xml": module._parse_documenti_xml,
        "_sigp_fascicolo_fallback": module._sigp_fascicolo_fallback,
        "_risolvi_ufficio_da_snapshot": module._risolvi_ufficio_da_snapshot,
        "_update_pst_session": module._update_pst_session,
        "_get_pst_session": module._get_pst_session,
    }
    captured = {"batch": None, "preflight": 0}

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0800570152",
                "numero_rg": "466",
                "anno_rg": "2023",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "RSSMRA80A01H501Z",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    ricerca_atti_xml = """<?xml version='1.0' encoding='UTF-8'?>
<Envelope><Body><ricercaAttiResponse><return><item>3080731</item><item>3073476</item></return></ricercaAttiResponse></Body></Envelope>"""

    try:
        module._curl_disponibile = lambda: True
        module._risolvi_base_pst_runtime = lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP"
        module._pst_url_ricerca = lambda base_url: base_url.rstrip("/")
        module._pst_url_documenti = lambda base_url: base_url.rstrip("/") + "/doc"
        module._risolvi_codice_ufficio_pst = lambda tribunale: "0800570152"
        module._require_certificato_pst = lambda thumbprint: "AABBCC11"
        module._cf_avvocato_pst = lambda cf, thumbprint: "RSSMRA80A01H501Z"
        module._pst_namespace_qbuilder = lambda base_url: "urn:CONS-SIGP-BE"
        module._pst_servizio_sigp = lambda base_url: True
        module._ensure_pst_session_entry = lambda *args, **kwargs: (
            {
                "session_id": "SID-SIGP-VIEW",
                "cookie_file": "C:\\temp\\pst.cookies",
                "auth_ready": False,
                "cf_avvocato": "RSSMRA80A01H501Z",
            },
            True,
        )
        module._pst_preflight_auth_curl = lambda *args, **kwargs: (
            captured.__setitem__("preflight", captured["preflight"] + 1)
            or {
                "ok": True,
                "http_code": 405,
                "content_type": "text/html",
                "nota": "Certificato selezionato e richiesta PIN gestita dal sistema.",
            }
        )
        module._resolve_pst_session_entry = lambda session_id: None

        def _fake_batch(requests, **kwargs):
            captured["batch"] = {"requests": list(requests), "kwargs": kwargs}
            return [
                (b"<search/>", "HTTP/1.1 200 OK\r\n"),
                (b"<profile/>", "HTTP/1.1 200 OK\r\n"),
                (b"<documents/>", "HTTP/1.1 200 OK\r\n"),
                (ricerca_atti_xml.encode("utf-8"), "HTTP/1.1 200 OK\r\n"),
            ]

        def _fake_best_effort(requests, **kwargs):
            return [
                {"body_bytes": body, "headers_text": headers, "status_code": 200, "error": ""}
                for body, headers in _fake_batch(requests, **kwargs)
            ]

        def _unexpected_sigp_profile_roundtrip(*args, **kwargs):
            raise AssertionError("La visualizzazione SIGP non deve aprire chiamate profilo fuori batch")

        module._soap_call_pst_session_batch_raw_best_effort = _fake_best_effort
        module._sigp_documenti_da_ricerca_atti = _unexpected_sigp_profile_roundtrip
        module._estrai_fault_soap = lambda xml: None
        module._parse_fascicoli_xml = lambda xml: []
        module._parse_documenti_xml = lambda xml: []
        module._sigp_fascicolo_fallback = lambda **kwargs: {
            "numero_rg": "466",
            "anno_rg": 2023,
            "codice_ufficio": "0800570152",
            "nome_ufficio": "Giudice di Pace di Palmi",
            "parti": [],
        }
        module._risolvi_ufficio_da_snapshot = lambda codice: {"nome": "Giudice di Pace di Palmi"}
        module._update_pst_session = lambda *args, **kwargs: None
        module._get_pst_session = lambda *args, **kwargs: None

        module._Handler._pst_ricerca_snapshot(_FakeHandler())
    finally:
        for name, value in originals.items():
            setattr(module, name, value)

    assert captured["status"] == 200
    assert captured["preflight"] == 0
    assert captured["payload"]["ok"] is True
    assert [doc["id_repeatto"] for doc in captured["payload"]["documenti"]] == ["3080731", "3073476"]
    assert len(captured["batch"]["requests"]) == 4
    assert captured["batch"]["requests"][3]["soap_action"] == "ricercaAtti"
    assert "ricercaAtti" in captured["batch"]["requests"][3]["soap_body"]
    assert not any("estraiProfiloDocumento" in req["soap_body"] for req in captured["batch"]["requests"])


def test_pst_documenti_sigp_batcha_documenti_e_ricerca_atti_senza_chiamate_extra():
    module = _load_local_signer()

    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_risolvi_base_pst_runtime": module._risolvi_base_pst_runtime,
        "_pst_url_documenti": module._pst_url_documenti,
        "_risolvi_codice_ufficio_pst": module._risolvi_codice_ufficio_pst,
        "_require_certificato_pst": module._require_certificato_pst,
        "_cf_avvocato_pst": module._cf_avvocato_pst,
        "_pst_namespace_qbuilder": module._pst_namespace_qbuilder,
        "_pst_servizio_sigp": module._pst_servizio_sigp,
        "_ensure_pst_session_entry": module._ensure_pst_session_entry,
        "_pst_preflight_auth_curl": module._pst_preflight_auth_curl,
        "_resolve_pst_session_entry": module._resolve_pst_session_entry,
        "_soap_call_pst_session": module._soap_call_pst_session,
        "_soap_call_pst_session_batch_raw": module._soap_call_pst_session_batch_raw,
        "_sigp_documenti_da_ricerca_atti": module._sigp_documenti_da_ricerca_atti,
        "_estrai_fault_soap": module._estrai_fault_soap,
        "_parse_documenti_xml": module._parse_documenti_xml,
        "_update_pst_session": module._update_pst_session,
    }
    captured = {"batch": None, "preflight": 0}

    class _FakeHandler:
        def _read_json(self):
            return {
                "codice_ufficio": "0800570152",
                "numero_rg": "466",
                "anno_rg": "2023",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "RSSMRA80A01H501Z",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    ricerca_atti_xml = """<?xml version='1.0' encoding='UTF-8'?>
<Envelope><Body><ricercaAttiResponse><return><item>3080731</item></return></ricercaAttiResponse></Body></Envelope>"""

    try:
        module._curl_disponibile = lambda: True
        module._risolvi_base_pst_runtime = lambda codice: "https://ext.processotelematico.giustizia.it/pda/pycons/GLRC/JPW_SIGP"
        module._pst_url_documenti = lambda base_url: base_url.rstrip("/") + "/doc"
        module._risolvi_codice_ufficio_pst = lambda codice: "0800570152"
        module._require_certificato_pst = lambda thumbprint: "AABBCC11"
        module._cf_avvocato_pst = lambda cf, thumbprint: "RSSMRA80A01H501Z"
        module._pst_namespace_qbuilder = lambda base_url: "urn:CONS-SIGP-BE"
        module._pst_servizio_sigp = lambda base_url: True
        module._ensure_pst_session_entry = lambda *args, **kwargs: (
            {
                "session_id": "SID-SIGP-VIEW",
                "cookie_file": "C:\\temp\\pst.cookies",
                "auth_ready": False,
                "cf_avvocato": "RSSMRA80A01H501Z",
            },
            True,
        )
        module._pst_preflight_auth_curl = lambda *args, **kwargs: (
            captured.__setitem__("preflight", captured["preflight"] + 1)
            or {
                "ok": True,
                "http_code": 405,
                "content_type": "text/html",
                "nota": "Certificato selezionato e richiesta PIN gestita dal sistema.",
            }
        )
        module._resolve_pst_session_entry = lambda session_id: None
        module._soap_call_pst_session = lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("Il catalogo SIGP deve usare il batch unico di visualizzazione")
        )

        def _fake_batch(requests, **kwargs):
            captured["batch"] = {"requests": list(requests), "kwargs": kwargs}
            return [
                (b"<documents/>", "HTTP/1.1 200 OK\r\n"),
                (ricerca_atti_xml.encode("utf-8"), "HTTP/1.1 200 OK\r\n"),
            ]

        def _unexpected_sigp_profile_roundtrip(*args, **kwargs):
            raise AssertionError("Il catalogo SIGP non deve aprire profili documento separati")

        module._soap_call_pst_session_batch_raw = _fake_batch
        module._sigp_documenti_da_ricerca_atti = _unexpected_sigp_profile_roundtrip
        module._estrai_fault_soap = lambda xml: None
        module._parse_documenti_xml = lambda xml: []
        module._update_pst_session = lambda *args, **kwargs: None

        module._Handler._pst_documenti(_FakeHandler())
    finally:
        for name, value in originals.items():
            setattr(module, name, value)

    assert captured["status"] == 200
    assert captured["preflight"] == 1
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["documenti"][0]["id_repeatto"] == "3080731"
    assert len(captured["batch"]["requests"]) == 2
    assert captured["batch"]["requests"][1]["soap_action"] == "ricercaAtti"
    assert "ricercaAtti" in captured["batch"]["requests"][1]["soap_body"]
    assert not any("estraiProfiloDocumento" in req["soap_body"] for req in captured["batch"]["requests"])


def test_pst_ricerca_esatta_arricchisce_profilo_se_mancano_campi_identita():
    module = _load_local_signer()

    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_risolvi_base_pst_runtime": module._risolvi_base_pst_runtime,
        "_pst_url_ricerca": module._pst_url_ricerca,
        "_risolvi_codice_ufficio_pst": module._risolvi_codice_ufficio_pst,
        "_require_certificato_pst": module._require_certificato_pst,
        "_cf_avvocato_pst": module._cf_avvocato_pst,
        "_pst_namespace_qbuilder": module._pst_namespace_qbuilder,
        "_ensure_pst_session_entry": module._ensure_pst_session_entry,
        "_pst_prepare_authenticated_session": module._pst_prepare_authenticated_session,
        "_soap_ricerca_fascicoli_body": module._soap_ricerca_fascicoli_body,
        "_soap_call_pst_session": module._soap_call_pst_session,
        "_estrai_fault_soap": module._estrai_fault_soap,
        "_parse_fascicoli_xml": module._parse_fascicoli_xml,
        "_arricchisci_fascicoli_con_profilo": module._arricchisci_fascicoli_con_profilo,
        "_update_pst_session": module._update_pst_session,
    }
    captured = {}
    calls = {"arricchisci": 0}

    class _FakeHandler:
        def _read_json(self):
            return {
                "tribunale": "0580010",
                "numero_rg": "1025",
                "anno_rg": "2024",
                "cert_thumbprint": "AABBCC11",
                "cf_avvocato": "RSSMRA80A01H501Z",
                "pst_session_id": "SID-EXACT",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._curl_disponibile = lambda: True
        module._risolvi_base_pst_runtime = lambda tribunale: "https://ext.processotelematico.giustizia.it/pda/pycons/GLMI/JPW_SICID"
        module._pst_url_ricerca = lambda base_url: base_url
        module._risolvi_codice_ufficio_pst = lambda tribunale: "0151460094"
        module._require_certificato_pst = lambda thumbprint: "AABBCC11"
        module._cf_avvocato_pst = lambda cf, thumbprint: "RSSMRA80A01H501Z"
        module._pst_namespace_qbuilder = lambda base_url: True
        module._ensure_pst_session_entry = lambda *args, **kwargs: (
            {
                "session_id": "SID-EXACT",
                "cookie_file": "C:\\temp\\pst.cookies",
                "auth_ready": True,
                "cf_avvocato": "RSSMRA80A01H501Z",
            },
            False,
        )
        def _fake_prepare(session_entry, **kwargs):
            captured["prepare_kwargs"] = kwargs
            return session_entry, True

        module._pst_prepare_authenticated_session = _fake_prepare
        module._soap_ricerca_fascicoli_body = lambda **kwargs: "<xml/>"
        def _fake_call_pst_session(**kwargs):
            captured["soap_kwargs"] = kwargs
            return "<Envelope/>"

        module._soap_call_pst_session = _fake_call_pst_session
        module._estrai_fault_soap = lambda xml: None
        module._parse_fascicoli_xml = lambda xml: [
            {
                "numero_rg": "1025",
                "anno_rg": 2024,
                "codice_ufficio": "0580010",
                "nome_ufficio": "Tribunale di Milano",
            }
        ]

        def _fake_arricchisci(*args, **kwargs):
            calls["arricchisci"] += 1
            return args[0]

        module._arricchisci_fascicoli_con_profilo = _fake_arricchisci
        module._update_pst_session = lambda *args, **kwargs: None

        module._Handler._pst_ricerca(_FakeHandler())
    finally:
        for name, value in originals.items():
            setattr(module, name, value)

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is True
    assert len(captured["payload"]["fascicoli"]) == 1
    assert captured["prepare_kwargs"]["cert_thumbprint"] == "AABBCC11"
    assert captured["prepare_kwargs"]["force"] is False
    assert captured["soap_kwargs"]["prefer_cookie_only"] is True
    assert calls["arricchisci"] == 1


def test_pdp_ricerca_local_signer_restituisce_fascicoli_parsati():
    module = _load_local_signer()

    captured = {}
    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_portale_wsdl_diretto_abilitato": module._portale_wsdl_diretto_abilitato,
        "_require_certificato_pst": module._require_certificato_pst,
        "_require_cf_avvocato_locale": module._require_cf_avvocato_locale,
        "_soap_call_zeep_operation_via_curl": module._soap_call_zeep_operation_via_curl,
        "_parse_pdp_fascicoli_response": module._parse_pdp_fascicoli_response,
        "_risolvi_codice_ufficio_pdp_runtime": module._risolvi_codice_ufficio_pdp_runtime,
    }

    class _FakeHandler:
        def _read_json(self):
            return {
                "ufficio": "Procura di Reggio Calabria",
                "numero_rg": "4521",
                "anno_rg": "2026",
                "nome_imputato": "Mario Rossi",
                "tipo_registro": "RGNR",
                "cert_thumbprint": "AABBCC11",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._curl_disponibile = lambda: True
        module._portale_wsdl_diretto_abilitato = lambda portale: True
        module._require_certificato_pst = lambda thumb: "AABBCC11"
        module._require_cf_avvocato_locale = lambda cf, thumb: "RSSMRA80A01H501Z"
        module._soap_call_zeep_operation_via_curl = lambda **kwargs: captured.setdefault("bridge", kwargs) or SimpleNamespace()
        module._risolvi_codice_ufficio_pdp_runtime = lambda ufficio: "0580010"
        module._parse_pdp_fascicoli_response = lambda risposta: [
            {
                "numero_rg": "4521",
                "anno_rg": 2026,
                "tipo_registro": "RGNR",
                "fase": "INDAGINI",
                "stato": "PENDENTE",
                "reato": "Truffa",
                "codice_ufficio": "0580010",
                "nome_ufficio": "Procura di Reggio Calabria",
                "imputati": ["Mario Rossi"],
                "parti_offese": ["Parte Offesa"],
            }
        ]

        module._Handler._pdp_ricerca(_FakeHandler())
    finally:
        module._curl_disponibile = originals["_curl_disponibile"]
        module._portale_wsdl_diretto_abilitato = originals["_portale_wsdl_diretto_abilitato"]
        module._require_certificato_pst = originals["_require_certificato_pst"]
        module._require_cf_avvocato_locale = originals["_require_cf_avvocato_locale"]
        module._soap_call_zeep_operation_via_curl = originals["_soap_call_zeep_operation_via_curl"]
        module._parse_pdp_fascicoli_response = originals["_parse_pdp_fascicoli_response"]
        module._risolvi_codice_ufficio_pdp_runtime = originals["_risolvi_codice_ufficio_pdp_runtime"]

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["fascicoli"][0]["numero_rg"] == "4521"
    assert captured["bridge"]["operation_name"] == "ricercaFascicoliPenale"
    assert captured["bridge"]["payload"]["codiceUfficio"] == "0580010"
    assert captured["bridge"]["cert_thumbprint"] == "AABBCC11"


def test_portale_wsdl_diretto_abilitato_default_attivo():
    module = _load_local_signer()
    env_names = [
        "HACS_SIGNER_FORCE_BROWSER_ASSIST",
        "PCT_FORCE_BROWSER_ASSIST",
        "HACS_SIGNER_DISABLE_PORTALI_WSDL",
        "PCT_DISABLE_PORTALI_WSDL",
        "HACS_SIGNER_DISABLE_PDP_WSDL",
        "PCT_DISABLE_PDP_WSDL",
        "HACS_SIGNER_DISABLE_PAT_WSDL",
        "PCT_DISABLE_PAT_WSDL",
        "HACS_SIGNER_DISABLE_PTT_WSDL",
        "PCT_DISABLE_PTT_WSDL",
    ]
    saved = {name: os.environ.get(name) for name in env_names}
    try:
        for name in env_names:
            os.environ.pop(name, None)
        assert module._portale_wsdl_diretto_abilitato("pdp") is True
        assert module._portale_wsdl_diretto_abilitato("pat") is True
        assert module._portale_wsdl_diretto_abilitato("ptt") is True
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def test_pdp_ricerca_local_signer_dns_restituisce_manual_required():
    module = _load_local_signer()

    captured = {}
    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_portale_wsdl_diretto_abilitato": module._portale_wsdl_diretto_abilitato,
        "_require_certificato_pst": module._require_certificato_pst,
        "_require_cf_avvocato_locale": module._require_cf_avvocato_locale,
        "_soap_call_zeep_operation_via_curl": module._soap_call_zeep_operation_via_curl,
        "_risolvi_codice_ufficio_pdp_runtime": module._risolvi_codice_ufficio_pdp_runtime,
    }

    class _FakeHandler:
        def _read_json(self):
            return {
                "ufficio": "Procura di Reggio Calabria",
                "numero_rg": "4521",
                "anno_rg": "2026",
                "cert_thumbprint": "AABBCC11",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._curl_disponibile = lambda: True
        module._portale_wsdl_diretto_abilitato = lambda portale: True
        module._require_certificato_pst = lambda thumb: "AABBCC11"
        module._require_cf_avvocato_locale = lambda cf, thumb: "RSSMRA80A01H501Z"
        module._risolvi_codice_ufficio_pdp_runtime = lambda ufficio: "0580010"

        def _boom(**kwargs):
            raise RuntimeError(
                "HTTPSConnectionPool(host='appweb.giustizia.it', port=443): "
                "Max retries exceeded with url: /snt/RicercaFascicoliPenaleService?wsdl "
                "(Caused by NameResolutionError(\"getaddrinfo failed\"))"
            )

        module._soap_call_zeep_operation_via_curl = _boom
        module._Handler._pdp_ricerca(_FakeHandler())
    finally:
        module._curl_disponibile = originals["_curl_disponibile"]
        module._portale_wsdl_diretto_abilitato = originals["_portale_wsdl_diretto_abilitato"]
        module._require_certificato_pst = originals["_require_certificato_pst"]
        module._require_cf_avvocato_locale = originals["_require_cf_avvocato_locale"]
        module._soap_call_zeep_operation_via_curl = originals["_soap_call_zeep_operation_via_curl"]
        module._risolvi_codice_ufficio_pdp_runtime = originals["_risolvi_codice_ufficio_pdp_runtime"]

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is False
    assert captured["payload"]["manual_required"] is True
    assert captured["payload"]["manual_phase"] == "ricerca"
    assert captured["payload"]["manual_title"] == "Consultazione via browser ufficiale"
    assert captured["payload"]["portale_url"] == "https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp"


def test_pdp_ricerca_local_signer_browser_assistito_se_wsdl_disabilitato():
    module = _load_local_signer()

    captured = {}
    originals = {
        "_portale_wsdl_diretto_abilitato": module._portale_wsdl_diretto_abilitato,
        "_require_certificato_pst": module._require_certificato_pst,
    }

    class _FakeHandler:
        def _read_json(self):
            return {
                "ufficio": "Procura di Reggio Calabria",
                "numero_rg": "4521",
                "anno_rg": "2026",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._portale_wsdl_diretto_abilitato = lambda portale: False
        module._require_certificato_pst = lambda thumb: (_ for _ in ()).throw(AssertionError("Certificato non atteso in modalita browser-assistita"))
        module._Handler._pdp_ricerca(_FakeHandler())
    finally:
        module._portale_wsdl_diretto_abilitato = originals["_portale_wsdl_diretto_abilitato"]
        module._require_certificato_pst = originals["_require_certificato_pst"]

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is False
    assert captured["payload"]["manual_required"] is True
    assert captured["payload"]["manual_title"] == "Consultazione via browser ufficiale"
    assert "Consultazione via browser ufficiale" in captured["payload"]["errore"]
    assert captured["payload"]["portale_url"] == "https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp"


def test_pat_documenti_local_signer_restituisce_documenti_parsati():
    module = _load_local_signer()

    captured = {}
    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_portale_wsdl_diretto_abilitato": module._portale_wsdl_diretto_abilitato,
        "_require_certificato_pst": module._require_certificato_pst,
        "_require_cf_avvocato_locale": module._require_cf_avvocato_locale,
        "_soap_call_zeep_operation_via_curl": module._soap_call_zeep_operation_via_curl,
        "_parse_pat_documenti_response": module._parse_pat_documenti_response,
    }

    class _FakeHandler:
        def _read_json(self):
            return {
                "codice_ufficio": "TARLZ",
                "numero_ricorso": "1876",
                "anno": "2026",
                "cert_thumbprint": "AABBCC11",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._curl_disponibile = lambda: True
        module._portale_wsdl_diretto_abilitato = lambda portale: True
        module._require_certificato_pst = lambda thumb: "AABBCC11"
        module._require_cf_avvocato_locale = lambda cf, thumb: "RSSMRA80A01H501Z"
        module._soap_call_zeep_operation_via_curl = lambda **kwargs: captured.setdefault("bridge", kwargs) or SimpleNamespace()
        module._parse_pat_documenti_response = lambda risposta: [
            {
                "id_documento": "PAT-001",
                "nome": "Ricorso.pdf",
                "tipo": "RICORSO",
                "data_deposito": "2026-03-11",
                "mittente": "Studio Rossi",
                "id_deposito": "BUSTA-PAT-001",
                "tipo_atto": "Ricorso",
            }
        ]

        module._Handler._pat_documenti(_FakeHandler())
    finally:
        module._curl_disponibile = originals["_curl_disponibile"]
        module._portale_wsdl_diretto_abilitato = originals["_portale_wsdl_diretto_abilitato"]
        module._require_certificato_pst = originals["_require_certificato_pst"]
        module._require_cf_avvocato_locale = originals["_require_cf_avvocato_locale"]
        module._soap_call_zeep_operation_via_curl = originals["_soap_call_zeep_operation_via_curl"]
        module._parse_pat_documenti_response = originals["_parse_pat_documenti_response"]

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["documenti"][0]["id_documento"] == "PAT-001"
    assert captured["bridge"]["operation_name"] == "consultazioneDocumenti"
    assert captured["bridge"]["payload"]["codiceUfficio"] == "TARLZ"


def test_pat_documenti_local_signer_browser_assistito_se_wsdl_disabilitato():
    module = _load_local_signer()

    captured = {}
    originals = {
        "_portale_wsdl_diretto_abilitato": module._portale_wsdl_diretto_abilitato,
        "_require_certificato_pst": module._require_certificato_pst,
    }

    class _FakeHandler:
        def _read_json(self):
            return {
                "codice_ufficio": "TARLZ",
                "numero_ricorso": "1876",
                "anno": "2026",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._portale_wsdl_diretto_abilitato = lambda portale: False
        module._require_certificato_pst = lambda thumb: (_ for _ in ()).throw(AssertionError("Certificato non atteso in modalita browser-assistita"))
        module._Handler._pat_documenti(_FakeHandler())
    finally:
        module._portale_wsdl_diretto_abilitato = originals["_portale_wsdl_diretto_abilitato"]
        module._require_certificato_pst = originals["_require_certificato_pst"]

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is False
    assert captured["payload"]["manual_required"] is True
    assert captured["payload"]["manual_title"] == "Consultazione via browser ufficiale"
    assert "Consultazione via browser ufficiale" in captured["payload"]["errore"]
    assert captured["payload"]["portale_url"] == "https://www.giustizia-amministrativa.it/portale-avvocato"


def test_ptt_ricerca_local_signer_restituisce_fascicoli_parsati():
    module = _load_local_signer()

    captured = {}
    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_portale_wsdl_diretto_abilitato": module._portale_wsdl_diretto_abilitato,
        "_require_certificato_pst": module._require_certificato_pst,
        "_require_cf_avvocato_locale": module._require_cf_avvocato_locale,
        "_soap_call_zeep_operation_via_curl": module._soap_call_zeep_operation_via_curl,
        "_parse_ptt_fascicoli_response": module._parse_ptt_fascicoli_response,
        "_risolvi_codice_commissione_ptt_runtime": module._risolvi_codice_commissione_ptt_runtime,
    }

    class _FakeHandler:
        def _read_json(self):
            return {
                "commissione": "CPT Milano",
                "numero_rgt": "1234",
                "anno_rgt": "2026",
                "nome_ricorrente": "Mario Rossi",
                "tipo": "RICORSO",
                "cert_thumbprint": "AABBCC11",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._curl_disponibile = lambda: True
        module._portale_wsdl_diretto_abilitato = lambda portale: True
        module._require_certificato_pst = lambda thumb: "AABBCC11"
        module._require_cf_avvocato_locale = lambda cf, thumb: "RSSMRA80A01H501Z"
        module._soap_call_zeep_operation_via_curl = lambda **kwargs: captured.setdefault("bridge", kwargs) or SimpleNamespace()
        module._risolvi_codice_commissione_ptt_runtime = lambda commissione: "CPT030000"
        module._parse_ptt_fascicoli_response = lambda risposta: [
            {
                "numero_rgt": "1234",
                "anno_rgt": 2026,
                "tipo": "RICORSO",
                "stato": "PENDENTE",
                "materia": "IVA",
                "ricorrenti": ["Mario Rossi"],
                "resistenti": ["Agenzia Entrate"],
                "codice_commissione": "CPT030000",
                "nome_commissione": "CPT Milano",
            }
        ]

        module._Handler._ptt_ricerca(_FakeHandler())
    finally:
        module._curl_disponibile = originals["_curl_disponibile"]
        module._portale_wsdl_diretto_abilitato = originals["_portale_wsdl_diretto_abilitato"]
        module._require_certificato_pst = originals["_require_certificato_pst"]
        module._require_cf_avvocato_locale = originals["_require_cf_avvocato_locale"]
        module._soap_call_zeep_operation_via_curl = originals["_soap_call_zeep_operation_via_curl"]
        module._parse_ptt_fascicoli_response = originals["_parse_ptt_fascicoli_response"]
        module._risolvi_codice_commissione_ptt_runtime = originals["_risolvi_codice_commissione_ptt_runtime"]

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is True
    assert captured["payload"]["fascicoli"][0]["codice_commissione"] == "CPT030000"
    assert captured["bridge"]["operation_name"] == "ricercaFascicoliTributari"
    assert captured["bridge"]["payload"]["codiceCommissione"] == "CPT030000"


def test_ptt_ricerca_local_signer_403_restituisce_manual_required():
    module = _load_local_signer()

    captured = {}
    originals = {
        "_curl_disponibile": module._curl_disponibile,
        "_portale_wsdl_diretto_abilitato": module._portale_wsdl_diretto_abilitato,
        "_require_certificato_pst": module._require_certificato_pst,
        "_require_cf_avvocato_locale": module._require_cf_avvocato_locale,
        "_soap_call_zeep_operation_via_curl": module._soap_call_zeep_operation_via_curl,
        "_risolvi_codice_commissione_ptt_runtime": module._risolvi_codice_commissione_ptt_runtime,
    }

    class _FakeHandler:
        def _read_json(self):
            return {
                "commissione": "CPT Milano",
                "numero_rgt": "1234",
                "anno_rgt": "2026",
                "cert_thumbprint": "AABBCC11",
            }

        def _send_json(self, payload, status=200):
            captured["payload"] = payload
            captured["status"] = status

    try:
        module._curl_disponibile = lambda: True
        module._portale_wsdl_diretto_abilitato = lambda portale: True
        module._require_certificato_pst = lambda thumb: "AABBCC11"
        module._require_cf_avvocato_locale = lambda cf, thumb: "RSSMRA80A01H501Z"
        module._risolvi_codice_commissione_ptt_runtime = lambda commissione: "CPT030000"

        def _boom(**kwargs):
            raise RuntimeError(
                "403 Client Error: Forbidden for url: "
                "https://sigit.finanze.it/ptt/RicercaFascicoliTributarioService?wsdl"
            )

        module._soap_call_zeep_operation_via_curl = _boom
        module._Handler._ptt_ricerca(_FakeHandler())
    finally:
        module._curl_disponibile = originals["_curl_disponibile"]
        module._portale_wsdl_diretto_abilitato = originals["_portale_wsdl_diretto_abilitato"]
        module._require_certificato_pst = originals["_require_certificato_pst"]
        module._require_cf_avvocato_locale = originals["_require_cf_avvocato_locale"]
        module._soap_call_zeep_operation_via_curl = originals["_soap_call_zeep_operation_via_curl"]
        module._risolvi_codice_commissione_ptt_runtime = originals["_risolvi_codice_commissione_ptt_runtime"]

    assert captured["status"] == 200
    assert captured["payload"]["ok"] is False
    assert captured["payload"]["manual_required"] is True
    assert captured["payload"]["manual_phase"] == "ricerca"
    assert captured["payload"]["manual_title"] == "Consultazione via browser ufficiale"
    assert captured["payload"]["portale_url"] == "https://sigit.giustiziatributaria.gov.it/Sigit/index.do"


def test_parse_pdp_documenti_response_popola_campi_busta():
    module = _load_local_signer()

    risposta = SimpleNamespace(
        documenti=[
            SimpleNamespace(
                idDocumento="PDP-001",
                nomeFile="Memoria.pdf",
                tipoDocumento="MEMORIA",
                dataDeposito="2026-04-11T09:30:00",
                mittente="Studio Rossi",
                dimensione=2048,
                disponibile=True,
                idDeposito="BUSTA-PDP-001",
                tipoAtto="Memoria",
            )
        ]
    )

    parsed = module._parse_pdp_documenti_response(risposta)

    assert parsed[0]["id_documento"] == "PDP-001"
    assert parsed[0]["id_deposito"] == "BUSTA-PDP-001"
    assert parsed[0]["tipo_atto"] == "Memoria"


def test_parse_pat_documenti_response_popola_campi_busta():
    module = _load_local_signer()

    risposta = SimpleNamespace(
        documenti=[
            SimpleNamespace(
                idDocumento="PAT-001",
                nomeFile="Ricorso.pdf",
                tipoDocumento="RICORSO",
                dataDeposito="2026-04-11T09:30:00",
                mittente="Studio Rossi",
                dimensione=4096,
                disponibile=True,
                idDeposito="BUSTA-PAT-001",
                tipoAtto="Ricorso",
            )
        ]
    )

    parsed = module._parse_pat_documenti_response(risposta)

    assert parsed[0]["id_documento"] == "PAT-001"
    assert parsed[0]["id_deposito"] == "BUSTA-PAT-001"
    assert parsed[0]["tipo_atto"] == "Ricorso"
