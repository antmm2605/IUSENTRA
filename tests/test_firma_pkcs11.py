from __future__ import annotations

import pct.firma_pkcs11 as firma_pkcs11


def test_libreria_disponibile_prefers_best_scored_candidate(monkeypatch):
    monkeypatch.delenv(firma_pkcs11._ENV_LIBRARY, raising=False)
    monkeypatch.setattr(
        firma_pkcs11,
        "_candidate_libraries",
        lambda: ["C:\\fake\\legacy.dll", "C:\\fake\\bit4xpki.dll"],
    )
    monkeypatch.setattr(
        firma_pkcs11,
        "_score_library",
        lambda path: 1 if path.endswith("legacy.dll") else 3,
    )

    assert firma_pkcs11.libreria_disponibile() == "C:\\fake\\bit4xpki.dll"


def test_libreria_disponibile_accetta_override_env_esistente(monkeypatch, tmp_path):
    override = tmp_path / "bit4xpki.dll"
    override.write_text("stub", encoding="utf-8")
    monkeypatch.setenv(firma_pkcs11._ENV_LIBRARY, str(override))

    assert firma_pkcs11.libreria_disponibile() == str(override)


def test_windows_candidates_include_bit4xpki():
    assert any("bit4xpki.dll" in lib.lower() for lib in firma_pkcs11._LIBRERIE_DEFAULT)
