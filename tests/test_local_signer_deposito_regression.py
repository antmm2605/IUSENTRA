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

