# HACS Local Signer - Installazione locale Windows
# Usa i file gia' presenti nella cartella tools e configura l'avvio automatico.

param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$taskName = "HACS Local Signer"
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$targetDir = Join-Path $env:APPDATA "HACS\LocalSigner"
$venvDir = Join-Path $targetDir ".venv"
$pythonScript = Join-Path $targetDir "local_signer.py"
$dataDir = Join-Path $targetDir "data"
$ufficiTarget = Join-Path $dataDir "uffici_ministero.json"
$starterCmd = Join-Path $targetDir "start_local_signer.cmd"
$starterVbs = Join-Path $targetDir "start_local_signer.vbs"
$requirementsFile = Join-Path $targetDir "requirements_local_signer.txt"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$pythonwExe = Join-Path $venvDir "Scripts\pythonw.exe"

function Write-Step([string]$Message) {
    Write-Host "  $Message" -ForegroundColor Cyan
}

function Find-PythonCommand {
    foreach ($candidate in @("py -3", "python")) {
        try {
            & cmd /c "$candidate --version" *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
        }
    }
    return $null
}

function Wait-LocalSigner([int]$Attempts = 15) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping" -UseBasicParsing -TimeoutSec 2
            if ($resp.ok) {
                return $true
            }
        } catch {
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Write-LocalSignerLaunchers {
    $cmd = @'
@echo off
setlocal
set "TASK_NAME=HACS Local Signer"
set "DIR=%~dp0"
set "PYW=%DIR%.venv\Scripts\pythonw.exe"
set "PY=%DIR%local_signer.py"

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    schtasks /Run /TN "%TASK_NAME%" >nul 2>&1
) else (
    if exist "%PYW%" if exist "%PY%" (
        start "" "%PYW%" "%PY%"
    ) else (
        exit /b 1
    )
)

if /I "%~1"=="--background" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
exit /b 0
'@
    Set-Content -Path $starterCmd -Value $cmd -Encoding ASCII

    $vbs = @"
Set shell = CreateObject("WScript.Shell")
shell.Run Chr(34) & "$starterCmd" & Chr(34) & " --background", 0, False
"@
    Set-Content -Path $starterVbs -Value $vbs -Encoding ASCII
}

function Register-LocalSignerProtocol {
    $protocolRoot = "HKCU:\Software\Classes\hacs-local-signer"
    $commandKey = Join-Path $protocolRoot "shell\open\command"
    $wscriptExe = Join-Path $env:SystemRoot "System32\wscript.exe"
    $command = "`"$wscriptExe`" `"$starterVbs`" `"%1`""

    New-Item -Path $commandKey -Force | Out-Null
    Set-Item -Path $protocolRoot -Value "URL:HACS Local Signer Protocol"
    New-ItemProperty -Path $protocolRoot -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
    Set-Item -Path $commandKey -Value $command
}

Write-Host ""
Write-Host "HACS Local Signer - Installazione Windows" -ForegroundColor Green
Write-Host ""

$pythonCmd = Find-PythonCommand
if (-not $pythonCmd) {
    Write-Host "Python 3 non trovato nel PATH." -ForegroundColor Red
    Write-Host "Installare Python da https://python.org e riprovare." -ForegroundColor Yellow
    if (-not $Quiet) {
        Read-Host "Premere Invio per chiudere"
    }
    exit 1
}

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null

if (Test-Path $pythonScript) {
    Write-Step "Aggiorno l'installazione locale gia' presente..."
}

Write-Step "Copio i file del Local Signer..."
Copy-Item (Join-Path $toolsDir "local_signer.py") $pythonScript -Force
Copy-Item (Join-Path $toolsDir "requirements_local_signer.txt") $requirementsFile -Force
$ufficiSource = Join-Path $toolsDir "uffici_ministero.json"
if (-not (Test-Path $ufficiSource)) {
    $ufficiSource = Join-Path (Split-Path -Parent $toolsDir) "pct\data\uffici_ministero.json"
}
if (Test-Path $ufficiSource) {
    Copy-Item $ufficiSource $ufficiTarget -Force
    Write-Step "Registro uffici PST locale copiato."
} else {
    Write-Host "  AVVISO: registro uffici PST locale non trovato; il signer usera' solo la configurazione esplicita." -ForegroundColor Yellow
}

Write-Step "Preparo l'ambiente Python..."
if (-not (Test-Path $pythonExe)) {
    & cmd /c "$pythonCmd -m venv `"$venvDir`""
}

Write-Step "Aggiorno pip e installo le dipendenze..."
& $pythonExe -m pip install --quiet --upgrade pip
& $pythonExe -m pip install --quiet -r $requirementsFile

Write-Step "Preparo l'avvio contestuale da HACS..."
Write-LocalSignerLaunchers

Write-Step "Registro il protocollo locale hacs-local-signer://..."
Register-LocalSignerProtocol

Write-Step "Registro l'avvio automatico al login..."
$action = New-ScheduledTaskAction -Execute $pythonwExe -Argument "`"$pythonScript`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "HACS Local Signer - avvio automatico al login" `
    -Force | Out-Null

Write-Step "Avvio subito il servizio in background..."
Get-Process pythonw -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $pythonwExe } |
    Stop-Process -Force -ErrorAction SilentlyContinue
Start-Process -WindowStyle Hidden -FilePath $pythonwExe -ArgumentList @($pythonScript)

Write-Step "Attendo che il servizio risponda su 127.0.0.1:27272..."
$online = Wait-LocalSigner
$exitCode = 0
if (-not $online) {
    $exitCode = 1
}

Write-Host ""
if ($online) {
    Write-Host "Installazione completata." -ForegroundColor Green
    Write-Host "Il Local Signer e' attivo e raggiungibile." -ForegroundColor Green
    Write-Host "Da ora in poi HACS puo' avviarlo automaticamente quando clicchi Cerca." -ForegroundColor Cyan
    Write-Host "Diagnostica locale: http://127.0.0.1:27272/diagnosi" -ForegroundColor Cyan
} else {
    Write-Host "Installazione completata con avviso." -ForegroundColor Yellow
    Write-Host "Il servizio non ha ancora risposto su http://127.0.0.1:27272." -ForegroundColor Yellow
    Write-Host "Apri HACS e usa 'Avvia Local Signer', oppure esegui di nuovo questo installer." -ForegroundColor Yellow
}

if (-not $Quiet) {
    Read-Host "Premere Invio per chiudere"
}

exit $exitCode
