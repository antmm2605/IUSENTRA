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


def test_main_windows_default_usa_iexpress_storico_e_aggiorna_alias(monkeypatch, tmp_path):
    versione = "1.6.32"
    dist_dir = tmp_path / "dist"
    ls_py = tmp_path / "local_signer.py"
    reqs = tmp_path / "requirements_local_signer.txt"
    install = tmp_path / "installa_local_signer_locale.ps1"
    uffici = tmp_path / "uffici_ministero.json"
    uffici_pst_pubblici = tmp_path / "uffici_pst_pubblici.json"
    visible_signature = tmp_path / "visible_signature.py"
    module_dir = tmp_path / "local_signer_mod"
    module_dir.mkdir()
    for name in [
        "__init__.py",
        "ai_cache.py",
        "ai_handlers.py",
        "pec_bridge.py",
        "security.py",
        "server_bootstrap.py",
        "support_agent.py",
    ]:
        (module_dir / name).write_text("# ok\n", encoding="utf-8")
    ls_py.write_text(f'VERSION = "{versione}"\n', encoding="utf-8")
    reqs.write_text("cryptography\n", encoding="utf-8")
    install.write_text("Write-Host setup\n", encoding="utf-8")
    uffici.write_text('{"uffici":[]}', encoding="utf-8")
    uffici_pst_pubblici.write_text('{"uffici":{"civili":[],"penali":[]}}', encoding="utf-8")
    visible_signature.write_text("def apply_visible_signature_stamp(data): return data\n", encoding="utf-8")

    monkeypatch.setattr(build_dist.os, "name", "nt")
    monkeypatch.setattr(build_dist.sys, "argv", ["build_dist.py"])
    monkeypatch.setattr(build_dist, "DIST_DIR", dist_dir)
    monkeypatch.setattr(build_dist, "LS_PY", ls_py)
    monkeypatch.setattr(build_dist, "REQS_TXT", reqs)
    monkeypatch.setattr(build_dist, "INSTALL_PS1", install)
    monkeypatch.setattr(build_dist, "UFFICI_JSON", uffici)
    monkeypatch.setattr(build_dist, "UFFICI_PST_PUBBLICI_JSON", uffici_pst_pubblici)
    monkeypatch.setattr(build_dist, "VISIBLE_SIGNATURE_PY", visible_signature)
    monkeypatch.setattr(build_dist, "LOCAL_SIGNER_MOD_DIR", module_dir)
    monkeypatch.setattr(
        build_dist,
        "build_windows_exe",
        lambda version, base_url=build_dist.BASE_URL_DEFAULT: b"MZiexpress-storico-piccolo",
    )
    monkeypatch.setattr(
        build_dist,
        "build_windows_exe_native",
        lambda version: (_ for _ in ()).throw(AssertionError("builder nativo non deve partire di default")),
    )
    monkeypatch.setattr(build_dist, "build_macos_command", lambda version, base_url: "# mac\n")
    monkeypatch.setattr(build_dist, "build_linux_run", lambda version, base_url: "# linux\n")
    monkeypatch.setattr(build_dist, "build_windows_ps1", lambda version: "# ps1\n")
    monkeypatch.setattr(build_dist, "write_windows_support_files", lambda dist: [])
    monkeypatch.setattr(build_dist, "build_release_note", lambda version: "note\n")

    build_dist.main()

    assert (dist_dir / f"SetupLocalSigner-{versione}.exe").read_bytes() == b"MZiexpress-storico-piccolo"
    assert (dist_dir / "SetupLocalSigner.exe").read_bytes() == b"MZiexpress-storico-piccolo"


def test_build_windows_ps1_include_versione_e_script_originale():
    versione = "1.5.12"

    contenuto = build_dist.build_windows_ps1(versione)

    assert f"IUSENTRA Local Signer Setup v{versione}" in contenuto
    assert "param(" in contenuto
    assert "Find-PythonCommand" in contenuto
    assert "FORCE_RESTART" in contenuto
    assert "iusentra-local-signer://restart" in contenuto
    assert "iusentra-local-signer://update" in contenuto
    assert 'set "ARGS=%*"' in contenuto
    assert 'echo %ARGS% | find /I "--force"' in contenuto
    assert 'echo %~1 | find /I "iusentra-local-signer://restart"' not in contenuto
    assert "IUSENTRA_LOCAL_SIGNER_UPDATE_URL" in contenuto
    assert "/polisWeb/local-signer/setup/windows" in contenuto
    assert "Copy-OrDownloadFile" not in contenuto
    assert 'Copy-Item (Join-Path $toolsDir "local_signer.py") $pythonScript -Force' in contenuto
    assert 'Copy-Item (Join-Path $toolsDir "local_ai_host_bridge.py") $aiBridgeScript -Force' in contenuto
    assert 'Copy-Item (Join-Path $toolsDir "lex_document_context.py") $lexContextScript -Force' in contenuto
    assert "/polisWeb/local-signer/download/local-signer-mod/" in contenuto
    assert "support_agent.py" in contenuto
    assert "reportlab" in contenuto
    assert "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272" in contenuto
    assert "Uninstall-ExistingLocalSigner" in contenuto
    assert "Disinstallo la vecchia versione locale prima di installare quella nuova" in contenuto
    assert "function Get-LocalSignerServicePython" in contenuto
    assert "function Set-LocalSignerRuntimeEnvironment" in contenuto
    assert "$servicePythonExe = Get-LocalSignerServicePython" in contenuto
    assert "$env:PYTHONPATH" in contenuto
    assert '(Split-Path -Leaf $servicePythonExe).ToLowerInvariant() -eq "pythonw.exe"' in contenuto
    assert "pillow>=10.0.0" in contenuto
    assert "function Wait-LocalSigner([int]$Attempts = 45)" in contenuto
    assert "RedirectStandardOutput $env:OUTLOG" in contenuto
    assert '$env:IUSENTRA_LOCAL_SIGNER_UPDATE_URL' in contenuto
    assert "Unregister-ScheduledTask -TaskName $taskName" in contenuto
    assert '$preserve = @("data", "installer.log", "local_signer.out.log", "local_signer.err.log")' in contenuto
    assert "$installLockPath = Join-Path $targetDir \"installer.lock\"" in contenuto
    assert "Acquire-InstallerLock" in contenuto
    assert "Release-InstallerLock" in contenuto
    assert '$venvConfig = Join-Path $venvDir "pyvenv.cfg"' in contenuto
    assert "Virtualenv incompleta rilevata" in contenuto


def test_build_windows_exe_profile_resta_iexpress_1_6_35():
    builder = (Path(__file__).resolve().parents[1] / "tools" / "build_local_signer_windows_exe.ps1").read_text(
        encoding="utf-8"
    )

    assert '$iexpressExe = Join-Path $env:SystemRoot "System32\\iexpress.exe"' in builder
    assert "Class=IEXPRESS" in builder
    assert "InsideCompressed=0" in builder
    assert "HideExtractAnimation=1" in builder
    assert "AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -File installa_local_signer_locale.ps1" in builder
    assert "FILE0=installa_local_signer_locale.ps1" in builder
    assert "FILE1=local_signer.py" in builder
    assert "FILE6=uffici_ministero.json" in builder
    assert "FILE7=uffici_pst_pubblici.json" in builder
    assert "FILE14=local_signer_mod__server_bootstrap.py" in builder
    assert "FILE15=local_signer_mod__support_agent.py" in builder
    assert "pillow" in builder.lower()


def test_build_studio_telematico_packager_pubblica_exe_senza_ps1_primario():
    root = Path(__file__).resolve().parents[1]
    builder = (root / "tools" / "build_studio_telematico_packager_exe.ps1").read_text(encoding="utf-8")
    packager = (root / "web" / "static" / "tools" / "prepara_import_studio_telematico.ps1").read_text(encoding="utf-8")
    api_source = (root / "web" / "blueprints" / "api_v1_react.py").read_text(encoding="utf-8")
    ts_source = (root / "frontend" / "src" / "quickOrganizerImportData.ts").read_text(encoding="utf-8")
    exe = root / "web" / "static" / "tools" / "PreparaPacchettoStudioTelematico.exe"

    assert '$iexpressExe = Join-Path $env:SystemRoot "System32\\iexpress.exe"' in builder
    assert "Class=IEXPRESS" in builder
    assert "InsideCompressed=0" in builder
    assert "AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -File prepara_import_studio_telematico.ps1" in builder
    assert "FILE0=prepara_import_studio_telematico.ps1" in builder
    assert "[Environment]::Is64BitProcess" in packager
    assert "$requiredTables = @(\"PRATICHE\", \"NOMI\", \"TAVOLA\", \"TESTI\", \"EMAILS\", \"AGENDA\")" in packager
    assert "\"NOMI\" = @(\"NUM_NOM\", \"CONTROLLO\")" in packager
    assert "relation_counts" in packager
    assert "client_party_links" in packager
    assert "Nessun pacchetto parziale e' stato creato" in packager
    assert "System.IO.Compression.ZipArchive" in packager
    assert "CreateEntryFromFile" in packager
    assert "Compress-Archive" not in packager
    assert "/static/tools/PreparaPacchettoStudioTelematico.exe" in api_source
    assert "/static/tools/PreparaPacchettoStudioTelematico.exe" in ts_source
    assert exe.exists()
    assert exe.read_bytes()[:2] == b"MZ"


def test_write_windows_support_files_copia_i_file_necessari(monkeypatch, tmp_path):
    ls_py = tmp_path / "local_signer.py"
    ai_bridge = tmp_path / "local_ai_host_bridge.py"
    lex_context = tmp_path / "lex_document_context.py"
    visible_signature = tmp_path / "visible_signature.py"
    reqs = tmp_path / "requirements_local_signer.txt"
    uffici = tmp_path / "uffici_ministero.json"
    uffici_pst_pubblici = tmp_path / "uffici_pst_pubblici.json"
    module_dir = tmp_path / "local_signer_mod"
    dist = tmp_path / "dist"
    dist.mkdir()
    module_dir.mkdir()
    ls_py.write_text("VERSION = '1.5.16'\n", encoding="utf-8")
    ai_bridge.write_text("def bridge():\n    return 'ok'\n", encoding="utf-8")
    lex_context.write_text("def parse_document():\n    return []\n", encoding="utf-8")
    visible_signature.write_text("def apply_visible_signature_stamp(data):\n    return data\n", encoding="utf-8")
    reqs.write_text("cryptography\n", encoding="utf-8")
    uffici.write_text('{"uffici":[]}', encoding="utf-8")
    uffici_pst_pubblici.write_text('{"uffici":{"civili":[],"penali":[]}}', encoding="utf-8")
    for name in [
        "__init__.py",
        "ai_cache.py",
        "ai_handlers.py",
        "pec_bridge.py",
        "security.py",
        "server_bootstrap.py",
        "support_agent.py",
    ]:
        (module_dir / name).write_text(f"# {name}\n", encoding="utf-8")

    monkeypatch.setattr(build_dist, "LS_PY", ls_py)
    monkeypatch.setattr(build_dist, "AI_BRIDGE_PY", ai_bridge)
    monkeypatch.setattr(build_dist, "LEX_CONTEXT_PY", lex_context)
    monkeypatch.setattr(build_dist, "VISIBLE_SIGNATURE_PY", visible_signature)
    monkeypatch.setattr(build_dist, "REQS_TXT", reqs)
    monkeypatch.setattr(build_dist, "UFFICI_JSON", uffici)
    monkeypatch.setattr(build_dist, "UFFICI_PST_PUBBLICI_JSON", uffici_pst_pubblici)
    monkeypatch.setattr(build_dist, "LOCAL_SIGNER_MOD_DIR", module_dir)

    copied = build_dist.write_windows_support_files(dist)

    assert [path.name for path in copied[:7]] == [
        "local_signer.py",
        "local_ai_host_bridge.py",
        "lex_document_context.py",
        "visible_signature.py",
        "requirements_local_signer.txt",
        "uffici_ministero.json",
        "uffici_pst_pubblici.json",
    ]
    assert {path.name for path in copied[7:]} == {
        "__init__.py",
        "ai_cache.py",
        "ai_handlers.py",
        "pec_bridge.py",
        "security.py",
        "server_bootstrap.py",
        "support_agent.py",
    }
    assert (dist / "local_signer.py").read_text(encoding="utf-8") == "VERSION = '1.5.16'\n"
    assert (dist / "local_ai_host_bridge.py").read_text(encoding="utf-8") == "def bridge():\n    return 'ok'\n"
    assert (dist / "lex_document_context.py").read_text(encoding="utf-8") == "def parse_document():\n    return []\n"
    assert (dist / "visible_signature.py").read_text(encoding="utf-8") == "def apply_visible_signature_stamp(data):\n    return data\n"
    assert (dist / "requirements_local_signer.txt").read_text(encoding="utf-8") == "cryptography\n"
    assert (dist / "uffici_ministero.json").read_text(encoding="utf-8") == '{"uffici":[]}'
    assert (dist / "uffici_pst_pubblici.json").read_text(encoding="utf-8") == '{"uffici":{"civili":[],"penali":[]}}'
    assert (dist / "local_signer_mod" / "ai_handlers.py").read_text(encoding="utf-8") == "# ai_handlers.py\n"


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
