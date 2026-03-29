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

Start-Sleep -Seconds 2

Write-Host ""
Write-Host "Installazione completata." -ForegroundColor Green
Write-Host "Diagnostica locale: http://127.0.0.1:27272/diagnosi" -ForegroundColor Cyan

try {
    Start-Process "http://127.0.0.1:27272/diagnosi" | Out-Null
} catch {
}

if (-not $Quiet) {
    Read-Host "Premere Invio per chiudere"
}
