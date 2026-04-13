import os
import subprocess
from pathlib import Path

import tools.build_dist as build_dist


def test_build_windows_exe_native_usa_builder_powershell_e_legge_l_exe(monkeypatch, tmp_path):
    versione = "1.5.12"
    script = tmp_path / "build_local_signer_windows_exe.ps1"
    script.write_text("# fake builder", encoding="utf-8")
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    exe_path = dist_dir / f"SetupLocalSigner-{versione}.exe"
    contenuto = b"MZfake-exe"

    def _fake_run(cmd, cwd, check):
        assert "powershell" in cmd[0].lower()
        assert str(script) in cmd
        assert check is True
        exe_path.write_bytes(contenuto)

    monkeypatch.setattr(build_dist.os, "name", "nt")
    monkeypatch.setattr(build_dist, "WINDOWS_NATIVE_BUILDER", script)
    monkeypatch.setattr(build_dist, "DIST_DIR", dist_dir)
    monkeypatch.setattr(build_dist, "REPO_DIR", tmp_path)
    monkeypatch.setattr(build_dist.subprocess, "run", _fake_run)

    risultato = build_dist.build_windows_exe_native(versione)

    assert risultato == contenuto
    assert exe_path.read_bytes() == contenuto


def test_build_windows_ps1_include_versione_e_script_originale():
    versione = "1.5.12"

    contenuto = build_dist.build_windows_ps1(versione)

    assert f"HACS Local Signer Setup v{versione}" in contenuto
    assert "param(" in contenuto
    assert "Find-PythonCommand" in contenuto
    assert "FORCE_RESTART" in contenuto
    assert "hacs-local-signer://restart" in contenuto
    assert "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272" in contenuto


def test_write_windows_support_files_copia_i_file_necessari(monkeypatch, tmp_path):
    ls_py = tmp_path / "local_signer.py"
    ai_bridge = tmp_path / "local_ai_host_bridge.py"
    lex_context = tmp_path / "lex_document_context.py"
    visible_signature = tmp_path / "visible_signature.py"
    reqs = tmp_path / "requirements_local_signer.txt"
    uffici = tmp_path / "uffici_ministero.json"
    dist = tmp_path / "dist"
    dist.mkdir()
    ls_py.write_text("VERSION = '1.5.16'\n", encoding="utf-8")
    ai_bridge.write_text("def bridge():\n    return 'ok'\n", encoding="utf-8")
    lex_context.write_text("def parse_document():\n    return []\n", encoding="utf-8")
    visible_signature.write_text("def apply_visible_signature_stamp(data):\n    return data\n", encoding="utf-8")
    reqs.write_text("cryptography\n", encoding="utf-8")
    uffici.write_text('{"uffici":[]}', encoding="utf-8")

    monkeypatch.setattr(build_dist, "LS_PY", ls_py)
    monkeypatch.setattr(build_dist, "AI_BRIDGE_PY", ai_bridge)
    monkeypatch.setattr(build_dist, "LEX_CONTEXT_PY", lex_context)
    monkeypatch.setattr(build_dist, "VISIBLE_SIGNATURE_PY", visible_signature)
    monkeypatch.setattr(build_dist, "REQS_TXT", reqs)
    monkeypatch.setattr(build_dist, "UFFICI_JSON", uffici)

    copied = build_dist.write_windows_support_files(dist)

    assert [path.name for path in copied] == [
        "local_signer.py",
        "local_ai_host_bridge.py",
        "lex_document_context.py",
        "visible_signature.py",
        "requirements_local_signer.txt",
        "uffici_ministero.json",
    ]
    assert (dist / "local_signer.py").read_text(encoding="utf-8") == "VERSION = '1.5.16'\n"
    assert (dist / "local_ai_host_bridge.py").read_text(encoding="utf-8") == "def bridge():\n    return 'ok'\n"
    assert (dist / "lex_document_context.py").read_text(encoding="utf-8") == "def parse_document():\n    return []\n"
    assert (dist / "visible_signature.py").read_text(encoding="utf-8") == "def apply_visible_signature_stamp(data):\n    return data\n"
    assert (dist / "requirements_local_signer.txt").read_text(encoding="utf-8") == "cryptography\n"
    assert (dist / "uffici_ministero.json").read_text(encoding="utf-8") == '{"uffici":[]}'


def test_installer_powershell_non_ha_errori_di_parse():
    if os.name != "nt":
        return

    comando = [
        "powershell",
        "-NoProfile",
        "-Command",
        "$errors=$null; $tokens=$null; "
        "[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path 'tools\\installa_local_signer_locale.ps1'), [ref]$tokens, [ref]$errors) > $null; "
        "if ($errors) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }",
    ]

    subprocess.run(comando, cwd=Path(__file__).resolve().parents[1], check=True)
