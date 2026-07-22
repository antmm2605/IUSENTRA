import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools" / "installa_local_signer_locale.ps1"


def _powershell_executable() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        pytest.skip("PowerShell non disponibile per i test comportamentali dell'installer Windows")
    return executable


def _run_harness(tmp_path: Path, source: str) -> dict:
    harness = tmp_path / "installer-harness.ps1"
    harness.write_text(source, encoding="utf-8")
    env = os.environ.copy()
    env["APPDATA"] = str(tmp_path / "appdata")
    if os.name != "nt":
        env.setdefault("SystemRoot", str(tmp_path / "Windows"))
    completed = subprocess.run(
        [
            _powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(harness),
            "-InstallerPath",
            str(INSTALLER),
            "-SandboxRoot",
            str(tmp_path / "appdata"),
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    assert lines, completed.stderr
    return json.loads(lines[-1])


def test_errore_pre_cutover_rilascia_lock_e_lascia_versione_attiva(tmp_path):
    result = _run_harness(
        tmp_path,
        r'''
param([string]$InstallerPath, [string]$SandboxRoot)
$ErrorActionPreference = "Stop"
$env:APPDATA = $SandboxRoot
. $InstallerPath -LibraryOnly

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Set-Content -LiteralPath (Join-Path $targetDir "local_signer.py") -Value "VERSIONE_PRECEDENTE" -Encoding UTF8
Set-Content -LiteralPath $installLockPath -Value "lock-stale" -Encoding UTF8
$stage = Join-Path $targetParentDir "LocalSigner.install-test"
$rollback = Join-Path $targetParentDir "LocalSigner.rollback-test"
$script:stopCalls = 0

function Test-LocalSignerOnline { return $true }
function Stop-LocalSignerProcesses { $script:stopCalls += 1 }
function New-LocalSignerPreparedStage {
    param([string]$StageRoot)
    New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null
    Set-Content -LiteralPath (Join-Path $StageRoot "parziale.txt") -Value "parziale"
    throw "DNS non disponibile durante pip"
}

$exitCode = Invoke-LocalSignerInstallerMain -StageRoot $stage -RollbackRoot $rollback

$payload = [ordered]@{
    exit_code = $exitCode
    stop_calls = $script:stopCalls
    old_content = (Get-Content -LiteralPath (Join-Path $targetDir "local_signer.py") -Raw).Trim()
    lock_exists = Test-Path -LiteralPath $installLockPath
    stage_exists = Test-Path -LiteralPath $stage
    rollback_exists = Test-Path -LiteralPath $rollback
}
$payload | ConvertTo-Json -Compress
''',
    )

    assert result == {
        "exit_code": 1,
        "stop_calls": 0,
        "old_content": "VERSIONE_PRECEDENTE",
        "lock_exists": False,
        "stage_exists": False,
        "rollback_exists": False,
    }


def test_errore_post_cutover_ripristina_file_e_riavvia_versione_precedente(tmp_path):
    result = _run_harness(
        tmp_path,
        r'''
param([string]$InstallerPath, [string]$SandboxRoot)
$ErrorActionPreference = "Stop"
$env:APPDATA = $SandboxRoot
. $InstallerPath -LibraryOnly

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
Set-Content -LiteralPath (Join-Path $targetDir "local_signer.py") -Value "VERSIONE_PRECEDENTE" -Encoding UTF8
$stage = Join-Path $targetParentDir "LocalSigner.install-test"
$rollback = Join-Path $targetParentDir "LocalSigner.rollback-test"
$script:stopCalls = 0
$script:startCalls = 0

function Test-LocalSignerOnline { return $true }
function Stop-LocalSignerProcesses { $script:stopCalls += 1 }
function New-LocalSignerPreparedStage {
    param([string]$StageRoot)
    New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null
    Set-Content -LiteralPath (Join-Path $StageRoot "local_signer.py") -Value "VERSIONE_NUOVA" -Encoding UTF8
    Set-Content -LiteralPath (Join-Path $StageRoot "start_local_signer.cmd") -Value "@echo off" -Encoding ASCII
    return [PSCustomObject]@{ Root = $StageRoot; PythonExe = "fake-python" }
}
function Sync-LocalSignerPreservedStateToStage { param([string]$StageRoot) }
function Register-LocalSignerProtocol { throw "Accesso negato dopo il cutover" }
function Start-InstalledLocalSigner { param([switch]$PreserveRuntimeLogs); $script:startCalls += 1; return "fake-python" }
function Wait-LocalSigner { param([int]$Attempts = 45); return $true }

$exitCode = Invoke-LocalSignerInstallerMain -StageRoot $stage -RollbackRoot $rollback

$payload = [ordered]@{
    exit_code = $exitCode
    stop_calls = $script:stopCalls
    start_calls = $script:startCalls
    live_content = (Get-Content -LiteralPath (Join-Path $targetDir "local_signer.py") -Raw).Trim()
    lock_exists = Test-Path -LiteralPath $installLockPath
    stage_exists = Test-Path -LiteralPath $stage
    rollback_exists = Test-Path -LiteralPath $rollback
    failed_exists = Test-Path -LiteralPath "$rollback.failed"
}
$payload | ConvertTo-Json -Compress
''',
    )

    assert result["exit_code"] == 1
    assert result["stop_calls"] == 2
    assert result["start_calls"] == 1
    assert result["live_content"] == "VERSIONE_PRECEDENTE"
    assert result["lock_exists"] is False
    assert result["stage_exists"] is False
    assert result["rollback_exists"] is False
    assert result["failed_exists"] is False


def test_task_diventato_valido_dopo_accesso_negato_non_crea_startup(tmp_path):
    result = _run_harness(
        tmp_path,
        r'''
param([string]$InstallerPath, [string]$SandboxRoot)
$ErrorActionPreference = "Stop"
$env:APPDATA = $SandboxRoot
. $InstallerPath -LibraryOnly

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
$script:statusCalls = 0
$script:taskRegisterCalls = 0
$script:startupRegisterCalls = 0
$script:startupRemoveCalls = 0

function Get-LocalSignerScheduledTaskStatus {
    $script:statusCalls += 1
    if ($script:statusCalls -eq 1) {
        return [PSCustomObject]@{ Known = $true; Exists = $false; Valid = $false; Detail = "" }
    }
    return [PSCustomObject]@{ Known = $true; Exists = $true; Valid = $true; Detail = "launcher corretto" }
}
function Register-LocalSignerScheduledTask {
    $script:taskRegisterCalls += 1
    throw "Accesso negato"
}
function Register-LocalSignerStartupShortcut {
    $script:startupRegisterCalls += 1
    return $true
}
function Remove-LocalSignerStartupShortcut { $script:startupRemoveCalls += 1 }
function Test-LocalSignerStartupShortcutValid { return $false }

$ok = Ensure-LocalSignerAutostart
$payload = [ordered]@{
    ok = $ok
    status_calls = $script:statusCalls
    task_register_calls = $script:taskRegisterCalls
    startup_register_calls = $script:startupRegisterCalls
    startup_remove_calls = $script:startupRemoveCalls
}
$payload | ConvertTo-Json -Compress
''',
    )

    assert result == {
        "ok": True,
        "status_calls": 2,
        "task_register_calls": 1,
        "startup_register_calls": 0,
        "startup_remove_calls": 1,
    }


def test_task_gia_valido_non_viene_riscritto_e_non_duplica_startup(tmp_path):
    result = _run_harness(
        tmp_path,
        r'''
param([string]$InstallerPath, [string]$SandboxRoot)
$ErrorActionPreference = "Stop"
$env:APPDATA = $SandboxRoot
. $InstallerPath -LibraryOnly

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
$script:taskRegisterCalls = 0
$script:startupRegisterCalls = 0
$script:startupRemoveCalls = 0
function Get-LocalSignerScheduledTaskStatus {
    return [PSCustomObject]@{ Known = $true; Exists = $true; Valid = $true; Detail = "launcher corretto" }
}
function Register-LocalSignerScheduledTask { $script:taskRegisterCalls += 1; throw "non deve essere chiamato" }
function Register-LocalSignerStartupShortcut { $script:startupRegisterCalls += 1; return $true }
function Remove-LocalSignerStartupShortcut { $script:startupRemoveCalls += 1 }

$ok = Ensure-LocalSignerAutostart
$payload = [ordered]@{
    ok = $ok
    task_register_calls = $script:taskRegisterCalls
    startup_register_calls = $script:startupRegisterCalls
    startup_remove_calls = $script:startupRemoveCalls
}
$payload | ConvertTo-Json -Compress
''',
    )

    assert result == {
        "ok": True,
        "task_register_calls": 0,
        "startup_register_calls": 0,
        "startup_remove_calls": 1,
    }


def test_staging_contiene_launcher_e_moduli_prima_del_cutover(tmp_path):
    result = _run_harness(
        tmp_path,
        r'''
param([string]$InstallerPath, [string]$SandboxRoot)
$ErrorActionPreference = "Stop"
$env:APPDATA = $SandboxRoot
. $InstallerPath -LibraryOnly

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
$stage = Join-Path $targetParentDir "LocalSigner.install-package-test"
Copy-LocalSignerPackageToStage -StageRoot $stage

$payload = [ordered]@{
    cmd = Test-Path -LiteralPath (Join-Path $stage "start_local_signer.cmd")
    vbs = Test-Path -LiteralPath (Join-Path $stage "start_local_signer.vbs")
    signer = Test-Path -LiteralPath (Join-Path $stage "local_signer.py")
    security = Test-Path -LiteralPath (Join-Path $stage "local_signer_mod\security.py")
    correct_task_action = Test-LocalSignerScheduledTaskAction -Execute (Join-Path $env:SystemRoot "System32\wscript.exe") -Arguments "`"$starterVbs`""
    wrong_task_action = Test-LocalSignerScheduledTaskAction -Execute (Join-Path $env:SystemRoot "System32\wscript.exe") -Arguments "`"C:\altro\start_local_signer.vbs`""
}
Remove-Item -LiteralPath $stage -Recurse -Force
$payload | ConvertTo-Json -Compress
''',
    )

    assert result == {
        "cmd": True,
        "vbs": True,
        "signer": True,
        "security": True,
        "correct_task_action": True,
        "wrong_task_action": False,
    }
