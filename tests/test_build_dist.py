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
