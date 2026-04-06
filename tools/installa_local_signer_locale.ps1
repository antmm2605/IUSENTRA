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
$defaultAllowedOrigins = "https://studio-legale-pct-production.up.railway.app"

function Write-Step([string]$Message) {
    Write-Host "  $Message" -ForegroundColor Cyan
}

function Find-PythonCommand {
    # 1. Prova il Python Launcher (py) e i comandi standard
    foreach ($candidate in @("py -3", "py", "python3", "python")) {
        try {
            $out = & cmd /c "$candidate --version 2>&1"
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        } catch {
        }
    }

    # 2. Cerca nei percorsi comuni di installazione Windows
    $commonPaths = @(
        # Installazione per tutti gli utenti (default installer)
        "C:\Python314\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Python39\python.exe",
        # Installazione per utente corrente (opzione installer)
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe",
        # Microsoft Store
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\python3.exe",
        "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe",
    )
    foreach ($path in $commonPaths) {
        $expanded = [System.Environment]::ExpandEnvironmentVariables($path)
        if (Test-Path $expanded) {
            return "`"$expanded`""
        }
    }

    # 3. Cerca python.exe nella directory del PATH tramite where.exe
    try {
        $found = & where.exe python 2>$null | Select-Object -First 1
        if ($found -and (Test-Path $found)) {
            return "`"$found`""
        }
    } catch {
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

function Test-LocalSignerOnline {
    try {
        $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping" -UseBasicParsing -TimeoutSec 2
        return [bool]$resp.ok
    } catch {
        return $false
    }
}

function Stop-LocalSignerProcesses {
    $needle = $pythonScript.Replace('\', '\\')
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -in @("python.exe", "pythonw.exe") -and
            $_.CommandLine -and
            $_.CommandLine -like "*$pythonScript*"
        } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
            } catch {
            }
        }
}

function Write-LocalSignerLaunchers {
    $allowedOrigins = $defaultAllowedOrigins
    $cmd = @'
@echo off
setlocal
set "DIR=%~dp0"
set "PYW=%DIR%.venv\Scripts\pythonw.exe"
set "PY=%DIR%local_signer.py"
set "TARGET=%DIR%local_signer.py"
set "PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=__ALLOWED_ORIGINS__"

powershell -NoProfile -Command "try { $r = Invoke-RestMethod 'http://127.0.0.1:27272/ping' -UseBasicParsing -TimeoutSec 2; if ($r.ok) { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 goto :online

powershell -NoProfile -Command "$target = [regex]::Escape($env:TARGET); Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -match $target } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }" >nul 2>&1

if exist "%PYW%" if exist "%PY%" (
    start "" "%PYW%" "%PY%"
) else (
    exit /b 1
)

:online
if /I "%~1"=="--background" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
exit /b 0
'@
    $cmd = $cmd.Replace('__ALLOWED_ORIGINS__', $allowedOrigins)
    Set-Content -Path $starterCmd -Value $cmd -Encoding ASCII

    $vbs = @'
Set shell = CreateObject("WScript.Shell")
shell.Run Chr(34) & "__STARTER_CMD__" & Chr(34) & " --background", 0, False
'@
    $vbs = $vbs.Replace('__STARTER_CMD__', $starterCmd)
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
    Write-Host "Python 3 non trovato nel PATH e nei percorsi comuni." -ForegroundColor Red
    Write-Host ""
    Write-Host "Soluzioni:" -ForegroundColor Yellow
    Write-Host "  1. Installare Python da https://python.org" -ForegroundColor Yellow
    Write-Host "     Durante l'installazione spuntare 'Add Python to PATH'" -ForegroundColor Yellow
    Write-Host "  2. Oppure riavviare PowerShell dopo aver installato Python" -ForegroundColor Yellow
    Write-Host ""
    if (-not $Quiet) {
        Read-Host "Premere Invio per chiudere"
    }
    exit 1
}

Write-Step "Python trovato: $pythonCmd"

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
    if (-not (Test-Path $pythonExe)) {
        Write-Host "  ERRORE: impossibile creare il virtual environment Python." -ForegroundColor Red
        Write-Host "  Verificare che Python sia installato correttamente." -ForegroundColor Yellow
        if (-not $Quiet) { Read-Host "Premere Invio per chiudere" }
        exit 1
    }
}

Write-Step "Aggiorno pip..."
& $pythonExe -m pip install --quiet --upgrade pip

Write-Step "Installo dipendenze base (asn1crypto, cryptography)..."
& $pythonExe -m pip install --quiet "asn1crypto>=1.5.0" "cryptography>=41.0.0"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERRORE: impossibile installare le dipendenze base." -ForegroundColor Red
    Write-Host "  Verificare la connessione internet e riprovare." -ForegroundColor Yellow
    if (-not $Quiet) { Read-Host "Premere Invio per chiudere" }
    exit 1
}

Write-Step "Installo python-pkcs11 (per firma con smart card/token CNS)..."
& $pythonExe -m pip install --quiet "python-pkcs11>=0.7.0" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Step "python-pkcs11 installato correttamente."
} else {
    Write-Host "  AVVISO: python-pkcs11 non installato (potrebbe non avere wheel per questa versione di Python)." -ForegroundColor Yellow
    Write-Host "  Il Local Signer funzionera' ma la firma con smart card richiede python-pkcs11." -ForegroundColor Yellow
    Write-Host "  Per installarlo manualmente: $pythonExe -m pip install python-pkcs11" -ForegroundColor Yellow
}

Write-Step "Preparo l'avvio contestuale da HACS..."
Write-LocalSignerLaunchers

Write-Step "Registro il protocollo locale hacs-local-signer://..."
Register-LocalSignerProtocol

Write-Step "Registro l'avvio automatico al login..."
$cmdExe = Join-Path $env:SystemRoot "System32\cmd.exe"
$action = New-ScheduledTaskAction -Execute $cmdExe -Argument "/c `"$starterCmd`" --background"
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
Stop-LocalSignerProcesses
Start-Sleep -Milliseconds 500
Start-Process -WindowStyle Hidden -FilePath $starterCmd -ArgumentList @("--background")

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
