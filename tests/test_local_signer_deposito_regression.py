"""Regressioni del pacchetto installabile e del formato sul percorso Windows."""
from pathlib import Path

import pytest

from tools import local_signer as signer


@pytest.mark.parametrize("standalone", [False, True])
@pytest.mark.parametrize("formato", ["pades", "cades"])
def test_no_token_preserva_formato_richiesto(monkeypatch, standalone, formato):
    monkeypatch.setattr(signer.sys, "platform", "win32")
    def open_session(*args):
        raise ImportError() if standalone else RuntimeError("Token not present")
    monkeypatch.setattr(signer, "_create_pin_session", open_session)
    monkeypatch.setattr(signer, "_errore_pkcs11_senza_token", lambda exc: True)
    def inline(*args, **kwargs):
        raise RuntimeError("Token not present")
    monkeypatch.setattr(signer, "_firma_inline", inline)
    monkeypatch.setattr(signer, "_firma_documento_windows_store_pades", lambda *args, **kwargs: (b"%PDF-signed", {"formato": "pades"}))
    monkeypatch.setattr(signer, "_firma_documento_windows_store", lambda *args, **kwargs: (b"CMS-signed", {"formato": "cades"}))
    content, info = signer._firma_documento("provider.dll", b"document", "test-only", formato=formato)
    assert info["formato"] == formato
    assert content.startswith(b"%PDF") == (formato == "pades")


def test_pkcs11_distribuito_identico_alla_implementazione_accettata():
    root = Path(__file__).resolve().parents[1]
    assert (root / "local_signer_mod/firma_pkcs11.py").read_bytes() == (root / "pct/firma_pkcs11.py").read_bytes()
    from local_signer_mod.firma_pkcs11 import FirmaPKCS11
    assert callable(FirmaPKCS11.firma_pades)
    assert callable(FirmaPKCS11.firma_cades)


def test_moduli_sessione_presenti_in_tutti_i_canali_installazione():
    root = Path(__file__).resolve().parents[1]
    for name in ("firma_pkcs11.py", "windows_signing_session.py"):
        assert name in signer._LOCAL_SIGNER_SOURCE_MOD_FILES
        for file in ("tools/build_local_signer_windows_exe.ps1", "tools/installa_local_signer_locale.ps1", "web/bootstrap/telematico_local_signer_routes.py", "web/services/telematico_runtime.py"):
            assert name in (root / file).read_text(encoding="utf-8")


def test_firma_windows_ripristina_sessione_unica_e_monitor_pin(monkeypatch):
    from local_signer_mod import windows_signing_session

    calls = []
    monkeypatch.setattr(windows_signing_session, "sign_raw", lambda thumb, payload: calls.append((thumb, payload)) or b"signed")
    monkeypatch.setattr(signer, "_windows_visible_top_level_window_handles", lambda: set())
    monkeypatch.setattr(signer, "_windows_prepare_foreground_for_process_start", lambda: calls.append("foreground"))
    def monitor(stop, timeout, excluded, owned):
        calls.append(("monitor", timeout))
        stop.wait(1)
    monkeypatch.setattr(signer, "_windows_pin_prompt_foreground_pump", monitor)
    assert signer._windows_store_sign_raw("A" * 40, b"one", "sha256") == b"signed"
    assert signer._windows_store_sign_raw("A" * 40, b"two", "sha256") == b"signed"
    assert calls.count("foreground") == 2
    assert calls.count(("monitor", 240)) == 2
    assert ("A" * 40, b"one") in calls and ("A" * 40, b"two") in calls


def test_sessione_windows_riusa_la_chiave_per_documenti_successivi(monkeypatch):
    from local_signer_mod import windows_signing_session as session
    created = []
    class FakeSession:
        def __init__(self, thumbprint):
            self.process = type("Process", (), {"poll": lambda self: None})()
            self.payloads = []
            created.append(self)
        def sign(self, payload):
            self.payloads.append(payload)
            return b"signed:" + payload
        def close(self):
            pass
    monkeypatch.setattr(session, "WindowsSigningSession", FakeSession)
    monkeypatch.setattr(session, "_sessions", {})
    assert session.sign_raw("A" * 40, b"one") == b"signed:one"
    assert session.sign_raw("A" * 40, b"two") == b"signed:two"
    assert len(created) == 1 and created[0].payloads == [b"one", b"two"]


def test_installer_correnti_sono_presenti_e_includono_catalogo_dispositivi():
    root = Path(__file__).resolve().parents[1]
    version = signer.VERSION
    dist = root / "tools/dist"
    assert (dist / f"SetupLocalSigner-{version}.exe").read_bytes() == (dist / "SetupLocalSigner.exe").read_bytes()
    for extension in ("command", "run"):
        source = (dist / f"InstallaLocalSigner-{version}.{extension}").read_text(encoding="utf-8")
        assert f'VERSION="{version}"' in source and "dispositivi_firma.py" in source
    assert (root / "local_signer_mod/dispositivi_firma.py").read_bytes() == (dist / "local_signer_mod/dispositivi_firma.py").read_bytes()


def test_luogo_vuoto_scelto_non_viene_sostituito_dallo_studio(monkeypatch):
    import visible_signature
    received = {}
    monkeypatch.setenv("PCT_STUDIO_CITY", "Comune non scelto")
    monkeypatch.setenv("PCT_STUDIO_INDIRIZZO", "Via Test, Comune non scelto")
    monkeypatch.setattr(visible_signature, "prepare_document_for_signature", lambda document, **kwargs: received.update(kwargs) or document)
    assert signer._prepare_documento_firma_visibile(b"%PDF-test", "Test", "Test", "01", visible_signature_place="", visible_signature_datetime_mode="nessuna") == b"%PDF-test"
    assert received["luogo"] == "" and received["datetime_mode"] == "nessuna"

