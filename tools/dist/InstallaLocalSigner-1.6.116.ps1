# IUSENTRA Local Signer Setup v1.6.116
# Pacchetto generato il 2026-08-26 21:05:48
# Punto ufficiale download: https://app.iusentra.it/impostazioni?tab=firma
# IUSENTRA Local Signer - Installazione locale Windows
# Usa i file gia' presenti nella cartella tools e configura l'avvio automatico.
# Se Python non e' installato, scarica automaticamente Python portatile.

param(
    [switch]$Quiet,
    # Usato esclusivamente dai test comportamentali: carica le funzioni senza
    # eseguire alcuna installazione o accedere all'AppData reale dell'utente.
    [switch]$LibraryOnly
)

$ErrorActionPreference = "Stop"

$taskName = "IUSENTRA Local Signer"
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $toolsDir
$targetDir = Join-Path $env:APPDATA "IUSENTRA\LocalSigner"
$targetParentDir = Split-Path -Parent $targetDir
$venvDir = Join-Path $targetDir ".venv"
$embeddedPythonDir = Join-Path $targetDir "python"
$pythonScript = Join-Path $targetDir "local_signer.py"
$windowsHttpScript = Join-Path $targetDir "local_signer_windows_http.ps1"
$aiBridgeScript = Join-Path $targetDir "local_ai_host_bridge.py"
$lexContextScript = Join-Path $targetDir "lex_document_context.py"
$visibleSignatureScript = Join-Path $targetDir "visible_signature.py"
$moduleDir = Join-Path $targetDir "local_signer_mod"
$dataDir = Join-Path $targetDir "data"
$ufficiTarget = Join-Path $dataDir "uffici_ministero.json"
$ufficiPstPubbliciTarget = Join-Path $dataDir "uffici_pst_pubblici.json"
$starterCmd = Join-Path $targetDir "start_local_signer.cmd"
$starterVbs = Join-Path $targetDir "start_local_signer.vbs"
$requirementsFile = Join-Path $targetDir "requirements_local_signer.txt"
$pythonExe = Join-Path $venvDir "Scripts\python.exe"
$pythonwExe = Join-Path $venvDir "Scripts\pythonw.exe"
$defaultBaseUrl = "https://app.iusentra.it"
$defaultAllowedOrigins = "$defaultBaseUrl,https://studio-legale-pct-production.up.railway.app,http://127.0.0.1:8080,http://localhost:8080"
$installerLog = Join-Path $targetDir "installer.log"
$runtimeStdoutLog = Join-Path $targetDir "local_signer.out.log"
$runtimeStderrLog = Join-Path $targetDir "local_signer.err.log"
$env:PIP_NO_CACHE_DIR = "1"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

# Python portatile: versione e URL di download
$embeddedPythonVersion = "3.12.8"
$embeddedPythonUrl = "https://www.python.org/ftp/python/$embeddedPythonVersion/python-$embeddedPythonVersion-embed-amd64.zip"
$embeddedPythonUrlFallback = "$defaultBaseUrl/polisWeb/local-signer/download/python-embedded"
$getPipUrl = "https://bootstrap.pypa.io/get-pip.py"

# Il lock vive fuori dalla directory sostituita durante il cutover atomico.
# Un file rimasto dopo un arresto anomalo non blocca la reinstallazione: conta
# soltanto l'handle esclusivo, che Windows rilascia alla chiusura del processo.
$installLockPath = Join-Path $targetParentDir "LocalSigner.installer.lock"
$installLockStream = $null

function Write-InstallerLog([string]$Message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $installerLog -Value "[$timestamp] $Message" -Encoding UTF8
}

function Acquire-InstallerLock {
    New-Item -ItemType Directory -Force -Path $targetParentDir | Out-Null
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        try {
            $script:installLockStream = [System.IO.File]::Open(
                $installLockPath,
                [System.IO.FileMode]::OpenOrCreate,
                [System.IO.FileAccess]::ReadWrite,
                [System.IO.FileShare]::None
            )
        } catch {
            Start-Sleep -Seconds 2
            continue
        }
        try {
            $bytes = [System.Text.Encoding]::UTF8.GetBytes("pid=$PID started=$(Get-Date -Format o)")
            $script:installLockStream.SetLength(0)
            $script:installLockStream.Write($bytes, 0, $bytes.Length)
            $script:installLockStream.Flush()
            break
        } catch {
            Release-InstallerLock
            throw
        }
    }
    if (-not $script:installLockStream) {
        throw "Un'altra installazione Local Signer è ancora in corso. Attendere la chiusura e riprovare."
    }

    try {
        # La directory live si puo' creare soltanto dopo avere ottenuto il lock
        # esterno: una seconda installazione non deve ricrearla nella breve
        # finestra tra i due rename del cutover atomico.
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        Write-InstallerLog "Lock installazione acquisito."
    } catch {
        Release-InstallerLock
        throw
    }
}

function Release-InstallerLock {
    if ($script:installLockStream) {
        try {
            $script:installLockStream.Close()
            $script:installLockStream.Dispose()
        } catch {
        }
        $script:installLockStream = $null
    }
    Remove-Item -LiteralPath $installLockPath -Force -ErrorAction SilentlyContinue
}

function Wait-InstallerDebugExit {
    if ($env:IUSENTRA_LOCAL_SIGNER_KEEP_INSTALLER_OPEN -eq "1") {
        Read-Host "Premere Invio per chiudere"
    }
}

function Write-Step([string]$Message) {
    Write-Host "  $Message" -ForegroundColor Cyan
    Write-InstallerLog $Message
}

function Invoke-Pip {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [Parameter(Mandatory = $true)]
        [string]$FailureMessage,
        [Parameter(Mandatory = $true)]
        [string]$PythonPath
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & $PythonPath -m pip @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousPreference

    foreach ($line in $output) {
        if ($line) {
            Write-InstallerLog "pip: $line"
        }
    }

    if ($exitCode -ne 0) {
        Write-Host "  ERRORE: $FailureMessage" -ForegroundColor Red
        return $false
    }
    return $true
}

function Test-PythonWorks([string]$Cmd) {
    # Verifica che il candidato Python esegua davvero codice (non sia un alias Store)
    try {
        $out = & cmd /c "$Cmd -c `"print('ok')`" 2>&1"
        if ($LASTEXITCODE -eq 0 -and $out -match "ok") {
            return $true
        }
    } catch {
    }
    return $false
}

function Test-IsWindowsStoreAlias([string]$Path) {
    $resolved = [System.Environment]::ExpandEnvironmentVariables($Path)
    return ($resolved -like "*\Microsoft\WindowsApps\*" -or
            $resolved -like "*\WindowsApps\*")
}

function Find-PythonCommand {
    # 1. Prova il Python Launcher (py) e i comandi standard
    foreach ($candidate in @("py -3", "py", "python3", "python")) {
        try {
            $out = & cmd /c "$candidate --version 2>&1"
            if ($LASTEXITCODE -eq 0) {
                if (Test-PythonWorks $candidate) {
                    return $candidate
                }
            }
        } catch {
        }
    }

    # 2. Cerca nei percorsi comuni di installazione Windows
    $commonPaths = @(
        "C:\Python314\python.exe",
        "C:\Python313\python.exe",
        "C:\Python312\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Python39\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe"
    )
    foreach ($path in $commonPaths) {
        $expanded = [System.Environment]::ExpandEnvironmentVariables($path)
        if (Test-Path $expanded) {
            if (Test-PythonWorks "`"$expanded`"") {
                return "`"$expanded`""
            }
        }
    }

    # 3. Cerca python.exe nel PATH (esclusi alias Microsoft Store)
    try {
        $allFound = & where.exe python 2>$null
        foreach ($found in $allFound) {
            if ($found -and (Test-Path $found) -and -not (Test-IsWindowsStoreAlias $found)) {
                if (Test-PythonWorks "`"$found`"") {
                    return "`"$found`""
                }
            }
        }
    } catch {
    }

    return $null
}

function Install-EmbeddedPython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DestinationDir
    )
    <#
    .SYNOPSIS
    Scarica e configura Python portatile (embeddable) nella cartella IUSENTRA.
    Non modifica il sistema, non richiede permessi admin, non richiede
    installazione manuale da parte dell'utente.
    #>

    $embedZip = Join-Path (Split-Path -Parent $DestinationDir) "python-embed.zip"

    Write-Step "Python non presente sul PC."
    Write-Step "Scarico Python $embeddedPythonVersion portatile (circa 10 MB)..."
    Write-InstallerLog "Download Python embeddable $embeddedPythonVersion"

    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

    $downloaded = $false
    foreach ($url in @($embeddedPythonUrl, $embeddedPythonUrlFallback)) {
        try {
            Write-Host "    Scarico da: $url" -ForegroundColor DarkGray
            Invoke-WebRequest -Uri $url -OutFile $embedZip -UseBasicParsing
            if ((Get-Item $embedZip).Length -gt 1000000) {
                $downloaded = $true
                break
            }
            Remove-Item $embedZip -Force -ErrorAction SilentlyContinue
        } catch {
            Write-InstallerLog "Download fallito da $url : $_"
        }
    }

    if (-not $downloaded) {
        Write-Host ""
        Write-Host "  ERRORE: impossibile scaricare Python." -ForegroundColor Red
        Write-Host "  Verificare la connessione internet e riprovare." -ForegroundColor Yellow
        Write-Host "  In alternativa, installare Python da https://python.org/downloads" -ForegroundColor Yellow
        return $false
    }

    Write-Step "Estraggo Python portatile..."
    if (Test-Path $DestinationDir) {
        Remove-Item $DestinationDir -Recurse -Force
    }
    Expand-Archive -Path $embedZip -DestinationPath $DestinationDir -Force
    Remove-Item $embedZip -Force

    # Abilita "import site" nel file ._pth (necessario per pip e site-packages)
    $pthFile = Get-ChildItem $DestinationDir -Filter "python*._pth" | Select-Object -First 1
    if ($pthFile) {
        $content = Get-Content $pthFile.FullName -Raw
        $content = $content -replace "#\s*import site", "import site"
        Set-Content $pthFile.FullName $content -NoNewline
        Write-InstallerLog "Abilitato import site in $($pthFile.Name)"
    }

    # Scarica e installa pip
    Write-Step "Configuro pip (gestore pacchetti Python)..."
    $getPipFile = Join-Path $DestinationDir "get-pip.py"
    $embedPython = Join-Path $DestinationDir "python.exe"

    try {
        Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipFile -UseBasicParsing
    } catch {
        Write-Host "  ERRORE: impossibile scaricare pip." -ForegroundColor Red
        return $false
    }

    & $embedPython $getPipFile --quiet --no-warn-script-location 2>$null
    $getPipExitCode = $LASTEXITCODE
    Remove-Item $getPipFile -Force -ErrorAction SilentlyContinue
    if ($getPipExitCode -ne 0) {
        Write-Host "  ERRORE: configurazione pip fallita." -ForegroundColor Red
        return $false
    }

    # Verifica che pip sia installato
    $pipExe = Join-Path $DestinationDir "Scripts\pip.exe"
    if (-not (Test-Path $pipExe)) {
        Write-Host "  ERRORE: configurazione pip fallita." -ForegroundColor Red
        return $false
    }

    Write-Step "Python $embeddedPythonVersion portatile pronto."
    Write-InstallerLog "Python embeddable installato in $DestinationDir"
    return $true
}

function Wait-LocalSigner([int]$Attempts = 45) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping?light=1" -UseBasicParsing -TimeoutSec 2
            if ($resp.ok) {
                $version = ""
                if ($resp.versione) {
                    $version = " versione $($resp.versione)"
                } elseif ($resp.version) {
                    $version = " versione $($resp.version)"
                }
                Write-InstallerLog "Ping leggero Local Signer riuscito$version."
                return $true
            }
            Write-InstallerLog "Ping leggero Local Signer ricevuto senza conferma ok."
        } catch {
            Write-InstallerLog "Ping leggero Local Signer non ancora riuscito: $($_.Exception.Message)"
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Test-LocalSignerOnline {
    try {
        $resp = Invoke-RestMethod "http://127.0.0.1:27272/ping?light=1" -UseBasicParsing -TimeoutSec 2
        return [bool]$resp.ok
    } catch {
        return $false
    }
}

function Write-LocalSignerStartupDiagnostics {
    param([string]$ServicePythonExe = "")

    Write-InstallerLog "Diagnostica avvio Local Signer:"
    Write-InstallerLog "  cartella installazione: $targetDir"
    if ($ServicePythonExe) {
        Write-InstallerLog "  python selezionato: $ServicePythonExe; presente=$(Test-Path -LiteralPath $ServicePythonExe)"
    }
    foreach ($path in @($pythonScript, $starterCmd, $starterVbs, (Join-Path $moduleDir "security.py"), $runtimeStdoutLog, $runtimeStderrLog)) {
        $item = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
        if ($item) {
            Write-InstallerLog "  file: $path; presente=true; byte=$($item.Length); aggiornato=$($item.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
        } else {
            Write-InstallerLog "  file: $path; presente=false"
        }
    }
    try {
        $owners = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        if ($owners) {
            foreach ($owner in $owners) {
                $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$owner" -ErrorAction SilentlyContinue
                Write-InstallerLog "  porta 27272 occupata da PID ${owner}: $($proc.CommandLine)"
            }
        } else {
            Write-InstallerLog "  porta 27272: nessun processo in ascolto"
        }
    } catch {
        Write-InstallerLog "  controllo porta 27272 non riuscito: $($_.Exception.Message)"
    }
    foreach ($logFile in @($runtimeStderrLog, $runtimeStdoutLog)) {
        if (Test-Path -LiteralPath $logFile) {
            Write-InstallerLog "  ultime righe ${logFile}:"
            Get-Content -LiteralPath $logFile -Tail 30 -ErrorAction SilentlyContinue |
                ForEach-Object { Write-InstallerLog "    $_" }
        }
    }
}

function Stop-LocalSignerProcesses {
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -in @("python.exe", "pythonw.exe") -and
            $_.CommandLine -and
            $_.CommandLine -like "*local_signer*"
        } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
            } catch {
            }
        }
    for ($i = 0; $i -lt 6; $i++) {
        $conn = Get-NetTCPConnection -LocalPort 27272 -ErrorAction SilentlyContinue
        if (-not $conn) { break }
        Start-Sleep -Milliseconds 500
    }
}

function Stop-LocalSignerDuplicateProcesses {
    $owner = $null
    try {
        $owner = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -First 1 -ExpandProperty OwningProcess
    } catch {
        $owner = $null
    }
    if (-not $owner) {
        return
    }
    $processes = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $processes |
        Where-Object {
            $_.Name -in @("python.exe", "pythonw.exe") -and
            [int]$_.ProcessId -ne [int]$owner -and
            $_.CommandLine -and
            $_.CommandLine -like "*local_signer*"
        } |
        ForEach-Object {
            try {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop
                Write-InstallerLog "Istanza Local Signer duplicata chiusa: PID $($_.ProcessId)"
            } catch {
            }
        }
}

function Test-LocalSignerSingleInstance {
    $owners = @(
        Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272 -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    )
    $processes = @(
        Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
            Where-Object {
                $_.Name -in @("python.exe", "pythonw.exe") -and
                $_.CommandLine -and
                $_.CommandLine -like "*local_signer*"
            }
    )
    if ($owners.Count -ne 1 -or $processes.Count -ne 1) {
        Write-InstallerLog "Verifica istanza unica fallita: listener=$($owners.Count), processi=$($processes.Count)."
        return $false
    }
    if ([int]$owners[0] -ne [int]$processes[0].ProcessId) {
        Write-InstallerLog "Verifica istanza unica fallita: listener PID $($owners[0]), processo PID $($processes[0].ProcessId)."
        return $false
    }
    Write-InstallerLog "Istanza unica verificata: PID $($owners[0])."
    return $true
}

function Get-LocalSignerServicePython {
    param([string]$RootDir = $targetDir)

    $rootEmbeddedPythonDir = Join-Path $RootDir "python"
    $rootVenvDir = Join-Path $RootDir ".venv"
    $rootPythonExe = Join-Path $rootVenvDir "Scripts\python.exe"
    $rootPythonwExe = Join-Path $rootVenvDir "Scripts\pythonw.exe"
    $embeddedPython = Join-Path $rootEmbeddedPythonDir "python.exe"
    if (Test-Path $embeddedPython) {
        return $embeddedPython
    }
    $venvConfig = Join-Path $rootVenvDir "pyvenv.cfg"
    if (Test-Path $venvConfig) {
        try {
            $line = Get-Content -LiteralPath $venvConfig -ErrorAction Stop |
                Where-Object { $_ -match "^\s*executable\s*=" } |
                Select-Object -First 1
            if ($line) {
                $resolved = ($line -replace "^\s*executable\s*=\s*", "").Trim()
                if ($resolved -and (Test-Path $resolved)) {
                    return $resolved
                }
            }
        } catch {
            Write-InstallerLog "Python reale da pyvenv.cfg non risolto: $($_.Exception.Message)"
        }
    }
    if (Test-Path $rootPythonExe) {
        return $rootPythonExe
    }
    if (Test-Path $rootPythonwExe) {
        return $rootPythonwExe
    }
    return $null
}

function Set-LocalSignerRuntimeEnvironment {
    param([string]$RootDir = $targetDir)

    $paths = @()
    $rootVenvDir = Join-Path $RootDir ".venv"
    $venvSitePackages = Join-Path $rootVenvDir "Lib\site-packages"
    if (Test-Path $venvSitePackages) {
        $paths += $venvSitePackages
    }
    $paths += $RootDir
    if ($env:PYTHONPATH) {
        $paths += $env:PYTHONPATH
    }
    $env:PYTHONPATH = ($paths -join ";")
    $env:VIRTUAL_ENV = $rootVenvDir
}

function Copy-LocalSignerModule {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DestinationModuleDir
    )

    $moduleSourceDir = Join-Path $toolsDir "local_signer_mod"
    New-Item -ItemType Directory -Force -Path $DestinationModuleDir | Out-Null

    foreach ($moduleFile in @("__init__.py", "ai_cache.py", "ai_handlers.py", "pec_bridge.py", "security.py", "server_bootstrap.py", "support_agent.py")) {
        $source = Join-Path $moduleSourceDir $moduleFile
        if (-not (Test-Path $source)) {
            $source = Join-Path $toolsDir ("local_signer_mod__" + $moduleFile)
        }
        if (-not (Test-Path $source)) {
            $downloadUrl = "$defaultBaseUrl/polisWeb/local-signer/download/local-signer-mod/$moduleFile"
            $target = Join-Path $DestinationModuleDir $moduleFile
            try {
                Invoke-WebRequest -Uri $downloadUrl -OutFile $target -UseBasicParsing
                continue
            } catch {
                throw "Modulo Local Signer mancante nel pacchetto e download non riuscito: local_signer_mod\$moduleFile"
            }
        }
        Copy-Item $source (Join-Path $DestinationModuleDir $moduleFile) -Force
    }
}

function Write-LocalSignerLaunchers {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DestinationRoot
    )

    $destinationStarterCmd = Join-Path $DestinationRoot "start_local_signer.cmd"
    $destinationStarterVbs = Join-Path $DestinationRoot "start_local_signer.vbs"
    $allowedOrigins = $defaultAllowedOrigins
    $updateInstallerUrl = "$defaultBaseUrl/polisWeb/local-signer/setup/windows"
    # Il launcher usa python.exe nascosto per scrivere log diagnostici; pythonw.exe resta fallback.
    $cmd = @'
@echo off
setlocal
set "DIR=%~dp0"
set "PY=%DIR%local_signer.py"
set "TARGET=%DIR%local_signer.py"
set "PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=__ALLOWED_ORIGINS__"
set "IUSENTRA_LOCAL_SIGNER_UPDATE_URL=__UPDATE_INSTALLER_URL__"
set "FORCE_RESTART=0"
set "SILENT_MODE=0"
set "UPDATE_MODE=0"
set "ARGS=%*"

if /I "%~1"=="--force" set "FORCE_RESTART=1"
if /I "%~1"=="--silent" set "SILENT_MODE=1"
if /I "%~1"=="--update" set "UPDATE_MODE=1"
echo %ARGS% | find /I "--force" >nul 2>&1 && set "FORCE_RESTART=1"
echo %ARGS% | find /I "iusentra-local-signer://restart" >nul 2>&1 && set "FORCE_RESTART=1"
echo %ARGS% | find /I "iusentra-local-signer://update" >nul 2>&1 && set "UPDATE_MODE=1"

if "%UPDATE_MODE%"=="1" goto :update

rem Cerca Python: prima python.exe per log diagnostici, poi pythonw.exe come fallback
set "PYE=%DIR%python\python.exe"
if not exist "%PYE%" for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$cfg=Join-Path $env:DIR '.venv\pyvenv.cfg'; if (Test-Path $cfg) { $line=Get-Content -LiteralPath $cfg | Where-Object { $_ -match '^\s*executable\s*=' } | Select-Object -First 1; if ($line) { ($line -replace '^\s*executable\s*=\s*','').Trim() } }"`) do set "PYE=%%P"
if not exist "%PYE%" set "PYE=%DIR%.venv\Scripts\python.exe"
set "PYW=%DIR%python\pythonw.exe"
if not exist "%PYW%" set "PYW=%DIR%.venv\Scripts\pythonw.exe"
set "VENVSITE=%DIR%.venv\Lib\site-packages"
if exist "%VENVSITE%" set "PYTHONPATH=%VENVSITE%;%DIR%;%PYTHONPATH%"
set "OUTLOG=%DIR%local_signer.out.log"
set "ERRLOG=%DIR%local_signer.err.log"

if "%FORCE_RESTART%"=="0" (
powershell -NoProfile -WindowStyle Hidden -Command "try { $r = Invoke-RestMethod 'http://127.0.0.1:27272/ping?light=1' -UseBasicParsing -TimeoutSec 2; if ($r.ok) { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 goto :online
)

powershell -NoProfile -WindowStyle Hidden -Command "$target = [regex]::Escape($env:TARGET); Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -match $target } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }" >nul 2>&1
powershell -NoProfile -WindowStyle Hidden -Command "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {} }" >nul 2>&1

if not exist "%PY%" exit /b 1
if exist "%PYE%" (
    powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -WorkingDirectory $env:DIR -FilePath $env:PYE -ArgumentList @($env:PY) -RedirectStandardOutput $env:OUTLOG -RedirectStandardError $env:ERRLOG"
) else if exist "%PYW%" (
    powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -WorkingDirectory $env:DIR -FilePath $env:PYW -ArgumentList @($env:PY)"
) else (
    exit /b 1
)
powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; try { $r = Invoke-RestMethod 'http://127.0.0.1:27272/ping?light=1' -UseBasicParsing -TimeoutSec 2; if (-not $r.ok) { exit 1 } } catch { exit 1 }"

:online
if /I "%~1"=="--background" exit /b 0
if "%SILENT_MODE%"=="1" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
exit /b 0

:update
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$ErrorActionPreference='Stop'; $url=$env:IUSENTRA_LOCAL_SIGNER_UPDATE_URL; if (-not $url.StartsWith('https://app.iusentra.it/')) { exit 2 }; $target=Join-Path $env:TEMP ('SetupLocalSigner-' + [Guid]::NewGuid().ToString('N') + '.exe'); try { Invoke-WebRequest -Uri $url -UseBasicParsing -OutFile $target; $installer=Start-Process -WindowStyle Hidden -FilePath $target -ArgumentList @('/Q') -PassThru -Wait; if ($installer.ExitCode -ne 0) { exit $installer.ExitCode }; $ready=$false; for ($i=0; $i -lt 180; $i++) { try { $ping=Invoke-RestMethod 'http://127.0.0.1:27272/ping?light=1' -UseBasicParsing -TimeoutSec 2; if ($ping.ok) { $ready=$true; break } } catch {}; Start-Sleep -Seconds 1 }; if (-not $ready) { exit 3 } } finally { Remove-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue }"
exit /b %ERRORLEVEL%
'@
    $cmd = $cmd.Replace('__ALLOWED_ORIGINS__', $allowedOrigins)
    $cmd = $cmd.Replace('__UPDATE_INSTALLER_URL__', $updateInstallerUrl)
    Set-Content -Path $destinationStarterCmd -Value $cmd -Encoding ASCII

    $vbs = @'
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Dim extra
Dim here
Dim starter
here = fso.GetParentFolderName(WScript.ScriptFullName)
starter = fso.BuildPath(here, "start_local_signer.cmd")
extra = " --background"
If WScript.Arguments.Count > 0 Then
  If InStr(LCase(WScript.Arguments(0)), "iusentra-local-signer://update") > 0 Then
    extra = " --update"
  ElseIf InStr(LCase(WScript.Arguments(0)), "iusentra-local-signer://restart") > 0 Then
    extra = extra & " --force"
  End If
End If
shell.Run Chr(34) & starter & Chr(34) & extra, 0, False
'@
    Set-Content -Path $destinationStarterVbs -Value $vbs -Encoding ASCII
}

function Register-LocalSignerProtocol {
    $legacyProtocolName = ("ha" + "cs-local-signer")
    Remove-Item -Path "HKCU:\Software\Classes\$legacyProtocolName" -Recurse -Force -ErrorAction SilentlyContinue

    $protocolRoot = "HKCU:\Software\Classes\iusentra-local-signer"
    $commandKey = Join-Path $protocolRoot "shell\open\command"
    $wscriptExe = Join-Path $env:SystemRoot "System32\wscript.exe"
    $command = "`"$wscriptExe`" `"$starterVbs`" `"%1`""

    New-Item -Path $commandKey -Force | Out-Null
    Set-Item -Path $protocolRoot -Value "URL:IUSENTRA Local Signer Protocol"
    New-ItemProperty -Path $protocolRoot -Name "URL Protocol" -Value "" -PropertyType String -Force | Out-Null
    Set-Item -Path $commandKey -Value $command
}

function Register-LocalSignerStartupShortcut {
    $startupDir = [Environment]::GetFolderPath("Startup")
    if (-not $startupDir) {
        Write-InstallerLog "Startup folder non disponibile; uso solo attivita' pianificata."
        return $false
    }

    New-Item -ItemType Directory -Force -Path $startupDir | Out-Null
    $shortcutPath = Join-Path $startupDir "IUSENTRA Local Signer.lnk"
    $wscriptExe = Join-Path $env:SystemRoot "System32\wscript.exe"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $wscriptExe
    $shortcut.Arguments = "`"$starterVbs`""
    $shortcut.WorkingDirectory = $targetDir
    $shortcut.WindowStyle = 7
    $shortcut.Description = "IUSENTRA Local Signer - avvio automatico al login"
    $shortcut.Save()
    Write-InstallerLog "Collegamento Startup registrato: $shortcutPath"
    return $true
}

function Remove-LocalSignerStartupShortcut {
    $startupDir = [Environment]::GetFolderPath("Startup")
    if (-not $startupDir) {
        return
    }
    $shortcutPath = Join-Path $startupDir "IUSENTRA Local Signer.lnk"
    if (Test-Path -LiteralPath $shortcutPath) {
        Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction Stop
        Write-InstallerLog "Collegamento Startup duplicato rimosso: $shortcutPath"
    }
}

function Test-LocalSignerScheduledTaskAction {
    param(
        [string]$Execute,
        [string]$Arguments
    )

    if (-not $Execute -or -not $Arguments) {
        return $false
    }
    $expandedExecute = [Environment]::ExpandEnvironmentVariables($Execute.Trim().Trim('"'))
    $expandedArguments = [Environment]::ExpandEnvironmentVariables($Arguments)
    if ([System.IO.Path]::GetFileName($expandedExecute) -ine "wscript.exe") {
        return $false
    }
    $expectedLauncher = [System.IO.Path]::GetFullPath($starterVbs)
    return $expandedArguments.IndexOf($expectedLauncher, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Get-LocalSignerScheduledTaskStatus {
    $known = $false
    $exists = $false
    $valid = $false
    $detail = ""

    $getTaskCommand = Get-Command Get-ScheduledTask -ErrorAction SilentlyContinue
    if ($getTaskCommand) {
        try {
            $taskErrors = @()
            $task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue -ErrorVariable taskErrors
            if ($task) {
                $known = $true
                $exists = $true
                foreach ($action in @($task.Actions)) {
                    if (Test-LocalSignerScheduledTaskAction -Execute $action.Execute -Arguments $action.Arguments) {
                        $valid = $true
                        break
                    }
                }
            } elseif ($taskErrors.Count -eq 0) {
                $known = $true
            } else {
                $detail = ($taskErrors | ForEach-Object { $_.Exception.Message }) -join "; "
                if ($detail -notmatch "(?i)accesso negato|access is denied|0x80070005") {
                    $known = $true
                }
            }
        } catch {
            $detail = $_.Exception.Message
        }
    }

    if (-not $known) {
        try {
            $xmlOutput = & schtasks.exe /Query /TN $taskName /XML 2>&1
            $queryExitCode = $LASTEXITCODE
            $xmlText = ($xmlOutput | ForEach-Object { [string]$_ }) -join "`n"
            if ($queryExitCode -eq 0 -and $xmlText) {
                $known = $true
                $exists = $true
                [xml]$taskXml = $xmlText
                foreach ($execNode in @($taskXml.SelectNodes("//*[local-name()='Exec']"))) {
                    if (Test-LocalSignerScheduledTaskAction -Execute ([string]$execNode.Command) -Arguments ([string]$execNode.Arguments)) {
                        $valid = $true
                        break
                    }
                }
            } elseif ($xmlText -notmatch "(?i)accesso negato|access is denied|0x80070005") {
                $known = $true
                $exists = $false
            }
            if ($xmlText) {
                $detail = $xmlText
            }
        } catch {
            $detail = $_.Exception.Message
        }
    }

    return [PSCustomObject]@{
        Known  = [bool]$known
        Exists = [bool]$exists
        Valid  = [bool]$valid
        Detail = [string]$detail
    }
}

function Test-LocalSignerStartupShortcutValid {
    $startupDir = [Environment]::GetFolderPath("Startup")
    if (-not $startupDir) {
        return $false
    }
    $shortcutPath = Join-Path $startupDir "IUSENTRA Local Signer.lnk"
    if (-not (Test-Path -LiteralPath $shortcutPath)) {
        return $false
    }
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $targetName = [System.IO.Path]::GetFileName([Environment]::ExpandEnvironmentVariables([string]$shortcut.TargetPath))
        $expectedLauncher = [System.IO.Path]::GetFullPath($starterVbs)
        return ($targetName -ieq "wscript.exe" -and
                ([string]$shortcut.Arguments).IndexOf($expectedLauncher, [System.StringComparison]::OrdinalIgnoreCase) -ge 0)
    } catch {
        Write-InstallerLog "Verifica collegamento Startup non riuscita: $($_.Exception.Message)"
        return $false
    }
}

function Register-LocalSignerScheduledTask {
    $wscriptExe = Join-Path $env:SystemRoot "System32\wscript.exe"
    $action = New-ScheduledTaskAction -Execute $wscriptExe -Argument "`"$starterVbs`""
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit 0 `
        -RestartCount 3 `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries

    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "IUSENTRA Local Signer - avvio automatico al login" `
        -Force | Out-Null
    Write-InstallerLog "Attivita' pianificata registrata: $taskName"
}

function Ensure-LocalSignerAutostart {
    $autostartOk = $false
    $taskStatus = Get-LocalSignerScheduledTaskStatus

    if ($taskStatus.Valid) {
        # Il percorso e' stabile: non tentare di rimuovere o riscrivere un task
        # gia' corretto. In questo modo un task protetto da ACL resta valido e
        # non viene affiancato da un secondo trigger nella cartella Startup.
        Remove-LocalSignerStartupShortcut
        Write-InstallerLog "Attivita' pianificata gia' valida; nessuna riscrittura necessaria."
        $autostartOk = $true
    }

    if (-not $autostartOk) {
        try {
            Register-LocalSignerScheduledTask
            $taskStatus = Get-LocalSignerScheduledTaskStatus
            if (-not $taskStatus.Valid) {
                throw "L'attivita' pianificata registrata non punta al launcher Local Signer atteso."
            }
            Remove-LocalSignerStartupShortcut
            $autostartOk = $true
        } catch {
            Write-InstallerLog "Attivita' pianificata non registrata: $($_.Exception.Message)"

            # Una seconda lettura copre il caso in cui Windows abbia applicato
            # il task ma abbia negato la successiva riscrittura/rimozione.
            $taskStatus = Get-LocalSignerScheduledTaskStatus
            if ($taskStatus.Valid) {
                Remove-LocalSignerStartupShortcut
                Write-InstallerLog "Attivita' pianificata valida confermata dopo Accesso negato; fallback Startup non creato."
                $autostartOk = $true
            } elseif ($taskStatus.Exists -or -not $taskStatus.Known) {
                throw "L'avvio pianificato esiste ma non puo' essere verificato o corretto; il fallback Startup non viene creato per evitare due trigger."
            }
        }
    }

    if (-not $autostartOk) {
        if (Test-LocalSignerStartupShortcutValid) {
            Write-InstallerLog "Collegamento Startup gia' valido; nessun secondo trigger creato."
            $autostartOk = $true
        } else {
            Write-Host "  AVVISO: attivita' pianificata non disponibile, preparo il solo fallback Startup." -ForegroundColor Yellow
            if (Register-LocalSignerStartupShortcut) {
                $autostartOk = $true
            }
        }
    }

    if (-not $autostartOk) {
        throw "Impossibile registrare un solo avvio automatico permanente del Local Signer."
    }
    return $true
}

function Copy-LocalSignerCatalogs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DestinationDataDir
    )

    New-Item -ItemType Directory -Force -Path $DestinationDataDir | Out-Null
    $ufficiSource = Join-Path $toolsDir "uffici_ministero.json"
    if (-not (Test-Path $ufficiSource)) {
        $ufficiSource = Join-Path $repoRoot "pct\data\uffici_ministero.json"
    }
    if (Test-Path $ufficiSource) {
        Copy-Item $ufficiSource (Join-Path $DestinationDataDir "uffici_ministero.json") -Force
    } else {
        Write-Host "  AVVISO: registro uffici PST locale non trovato; il signer usera' solo la configurazione esplicita." -ForegroundColor Yellow
    }

    $ufficiPstPubbliciSource = Join-Path $toolsDir "uffici_pst_pubblici.json"
    if (-not (Test-Path $ufficiPstPubbliciSource)) {
        $ufficiPstPubbliciSource = Join-Path $repoRoot "pct\data\uffici_pst_pubblici.json"
    }
    if (Test-Path $ufficiPstPubbliciSource) {
        Copy-Item $ufficiPstPubbliciSource (Join-Path $DestinationDataDir "uffici_pst_pubblici.json") -Force
    } else {
        Write-Host "  AVVISO: catalogo pubblico uffici PST non trovato; il PDP usera' il registro compatibile." -ForegroundColor Yellow
    }
}

function Copy-LocalSignerPackageToStage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StageRoot
    )

    $stageModuleDir = Join-Path $StageRoot "local_signer_mod"
    $stageDataDir = Join-Path $StageRoot "data"
    New-Item -ItemType Directory -Force -Path $StageRoot, $stageModuleDir, $stageDataDir | Out-Null

    $requiredCopies = @(
        @((Join-Path $toolsDir "local_signer.py"), (Join-Path $StageRoot "local_signer.py")),
        @((Join-Path $toolsDir "local_signer_windows_http.ps1"), (Join-Path $StageRoot "local_signer_windows_http.ps1")),
        @((Join-Path $toolsDir "local_ai_host_bridge.py"), (Join-Path $StageRoot "local_ai_host_bridge.py")),
        @((Join-Path $toolsDir "lex_document_context.py"), (Join-Path $StageRoot "lex_document_context.py")),
        @((Join-Path $toolsDir "requirements_local_signer.txt"), (Join-Path $StageRoot "requirements_local_signer.txt"))
    )
    foreach ($copy in $requiredCopies) {
        if (-not (Test-Path -LiteralPath $copy[0])) {
            throw "File obbligatorio mancante nel pacchetto Local Signer: $($copy[0])"
        }
        Copy-Item -LiteralPath $copy[0] -Destination $copy[1] -Force
    }

    $visibleSignatureSource = Join-Path $toolsDir "visible_signature.py"
    if (-not (Test-Path $visibleSignatureSource)) {
        $visibleSignatureSource = Join-Path $repoRoot "visible_signature.py"
    }
    if (-not (Test-Path $visibleSignatureSource)) {
        throw "File obbligatorio mancante nel pacchetto Local Signer: visible_signature.py"
    }
    Copy-Item $visibleSignatureSource (Join-Path $StageRoot "visible_signature.py") -Force
    Copy-LocalSignerModule -DestinationModuleDir $stageModuleDir
    Copy-LocalSignerCatalogs -DestinationDataDir $stageDataDir
    Write-LocalSignerLaunchers -DestinationRoot $StageRoot
}

function Initialize-LocalSignerStageRuntime {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StageRoot
    )

    $stageVenvDir = Join-Path $StageRoot ".venv"
    $stageEmbeddedDir = Join-Path $StageRoot "python"
    $stagePythonExe = Join-Path $stageVenvDir "Scripts\python.exe"
    $liveEmbeddedPython = Join-Path $embeddedPythonDir "python.exe"

    # Un runtime portatile gia' operativo ha priorita': viene clonato nello
    # staging, aggiornato e validato senza dipendere dalla versione Python di
    # sistema eventualmente cambiata dopo la precedente installazione.
    if ((Test-Path -LiteralPath $liveEmbeddedPython) -and (Test-PythonWorks "`"$liveEmbeddedPython`"")) {
        Write-Step "Copio Python portatile esistente nella cartella di staging..."
        Copy-Item -LiteralPath $embeddedPythonDir -Destination $stageEmbeddedDir -Recurse -Force
        $stagePythonExe = Join-Path $stageEmbeddedDir "python.exe"
    } else {
        $pythonCmd = Find-PythonCommand
    }

    if (-not (Test-Path -LiteralPath $stagePythonExe) -and $pythonCmd) {
        Write-Step "Preparo Python di sistema in un ambiente isolato di staging..."
        & cmd /c "$pythonCmd -m venv `"$stageVenvDir`""
        if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $stagePythonExe)) {
            throw "Impossibile preparare il virtual environment Python nella cartella di staging."
        }
    } elseif (-not (Test-Path -LiteralPath $stagePythonExe)) {
        if (-not (Install-EmbeddedPython -DestinationDir $stageEmbeddedDir)) {
            throw "L'installazione automatica di Python nella cartella di staging non e' riuscita."
        }
        $stagePythonExe = Join-Path $stageEmbeddedDir "python.exe"
    }

    if (-not (Test-Path -LiteralPath $stagePythonExe)) {
        throw "Runtime Python di staging mancante dopo la preparazione."
    }

    Write-Step "Aggiorno pip nell'ambiente di staging..."
    if (-not (Invoke-Pip -PythonPath $stagePythonExe -Arguments @("install", "--quiet", "--no-cache-dir", "--upgrade", "pip") -FailureMessage "impossibile aggiornare pip nell'ambiente di staging.")) {
        throw "Preparazione dipendenze interrotta: pip non e' stato aggiornato. La versione Local Signer attiva resta invariata."
    }

    Write-Step "Installo le dipendenze Local Signer nell'ambiente di staging..."
    if (-not (Invoke-Pip -PythonPath $stagePythonExe -Arguments @("install", "--quiet", "--no-cache-dir", "--no-warn-script-location", "asn1crypto>=1.5.0", "cryptography>=41.0.0", "zeep>=4.2.1", "pdfplumber>=0.10.0", "mammoth>=1.6.0", "pypdf>=6.0.0", "reportlab>=4.0.0", "pillow>=10.0.0") -FailureMessage "impossibile installare le dipendenze base nell'ambiente di staging.")) {
        throw "Preparazione dipendenze interrotta. La versione Local Signer attiva resta invariata."
    }

    Write-Step "Installo python-pkcs11 nell'ambiente di staging..."
    if (Invoke-Pip -PythonPath $stagePythonExe -Arguments @("install", "--quiet", "--no-cache-dir", "--no-warn-script-location", "python-pkcs11>=0.7.0") -FailureMessage "python-pkcs11 non installato.") {
        Write-Step "python-pkcs11 installato correttamente."
    } else {
        # Se il runtime portatile copiato contiene gia' pkcs11, un errore di
        # rete durante l'upgrade non elimina la funzionalita'. In ogni altro
        # caso il cutover viene bloccato: non sostituire mai una versione che
        # firma correttamente con una priva del supporto smart card.
        & $stagePythonExe -c "import pkcs11"
        if ($LASTEXITCODE -ne 0) {
            throw "Preparazione python-pkcs11 interrotta. La versione Local Signer attiva resta invariata."
        }
        Write-InstallerLog "Upgrade python-pkcs11 non riuscito; il modulo gia' presente nello staging e' stato validato."
    }

    return $stagePythonExe
}

function Test-LocalSignerPreparedStage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StageRoot,
        [Parameter(Mandatory = $true)]
        [string]$StagePythonExe
    )

    $requiredPaths = @(
        (Join-Path $StageRoot "local_signer.py"),
        (Join-Path $StageRoot "local_signer_windows_http.ps1"),
        (Join-Path $StageRoot "local_ai_host_bridge.py"),
        (Join-Path $StageRoot "lex_document_context.py"),
        (Join-Path $StageRoot "visible_signature.py"),
        (Join-Path $StageRoot "local_signer_mod\security.py"),
        (Join-Path $StageRoot "start_local_signer.cmd"),
        (Join-Path $StageRoot "start_local_signer.vbs"),
        $StagePythonExe
    )
    foreach ($requiredPath in $requiredPaths) {
        if (-not (Test-Path -LiteralPath $requiredPath)) {
            throw "Staging Local Signer incompleto: manca $requiredPath"
        }
    }

    $pythonFiles = @(
        (Join-Path $StageRoot "local_signer.py"),
        (Join-Path $StageRoot "local_ai_host_bridge.py"),
        (Join-Path $StageRoot "lex_document_context.py"),
        (Join-Path $StageRoot "visible_signature.py")
    ) + @(Get-ChildItem -LiteralPath (Join-Path $StageRoot "local_signer_mod") -Filter "*.py" | Select-Object -ExpandProperty FullName)

    $oldPythonPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = $StageRoot
        & $StagePythonExe -m py_compile @pythonFiles
        if ($LASTEXITCODE -ne 0) {
            throw "Validazione sintattica del Local Signer di staging non riuscita."
        }
        & $StagePythonExe -c "import asn1crypto, cryptography, zeep, pdfplumber, mammoth, pypdf, reportlab, PIL, pkcs11"
        if ($LASTEXITCODE -ne 0) {
            throw "Validazione delle dipendenze Local Signer di staging non riuscita."
        }
    } finally {
        $env:PYTHONPATH = $oldPythonPath
    }
    return $true
}

function New-LocalSignerPreparedStage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StageRoot
    )

    if (Test-Path -LiteralPath $StageRoot) {
        Remove-Item -LiteralPath $StageRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $StageRoot | Out-Null
    Copy-LocalSignerPackageToStage -StageRoot $StageRoot
    $stagePythonExe = Initialize-LocalSignerStageRuntime -StageRoot $StageRoot
    Test-LocalSignerPreparedStage -StageRoot $StageRoot -StagePythonExe $stagePythonExe | Out-Null
    return [PSCustomObject]@{
        Root      = $StageRoot
        PythonExe = $stagePythonExe
    }
}

function Sync-LocalSignerPreservedStateToStage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StageRoot
    )

    $stageDataDir = Join-Path $StageRoot "data"
    $liveDataDir = Join-Path $targetDir "data"
    if (Test-Path -LiteralPath $liveDataDir) {
        New-Item -ItemType Directory -Force -Path $stageDataDir | Out-Null
        Get-ChildItem -LiteralPath $liveDataDir -Force -ErrorAction Stop |
            ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $stageDataDir -Recurse -Force }
        # I dati operativi vengono preservati, ma i cataloghi distribuiti dal
        # nuovo pacchetto devono restare quelli appena validati.
        Copy-LocalSignerCatalogs -DestinationDataDir $stageDataDir
    }

    foreach ($logName in @("installer.log", "local_signer.out.log", "local_signer.err.log")) {
        $sourceLog = Join-Path $targetDir $logName
        if (Test-Path -LiteralPath $sourceLog) {
            Copy-Item -LiteralPath $sourceLog -Destination (Join-Path $StageRoot $logName) -Force
        }
    }
}

function Switch-LocalSignerStageToLive {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StageRoot,
        [Parameter(Mandatory = $true)]
        [string]$RollbackRoot
    )

    $safeParent = [System.IO.Path]::GetFullPath($targetParentDir).TrimEnd('\') + '\'
    foreach ($candidate in @($targetDir, $StageRoot, $RollbackRoot)) {
        $resolved = [System.IO.Path]::GetFullPath($candidate)
        if (-not $resolved.StartsWith($safeParent, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Percorso non sicuro per il cutover Local Signer: $resolved"
        }
    }
    if (Test-Path -LiteralPath $RollbackRoot) {
        throw "Cartella rollback Local Signer gia' presente: $RollbackRoot"
    }

    # Nessuna scrittura nel log tra i due rename: installer.log si sposta con
    # la directory e il percorso torna valido subito dopo il secondo rename.
    Move-Item -LiteralPath $targetDir -Destination $RollbackRoot -ErrorAction Stop
    try {
        Move-Item -LiteralPath $StageRoot -Destination $targetDir -ErrorAction Stop
    } catch {
        Move-Item -LiteralPath $RollbackRoot -Destination $targetDir -ErrorAction Stop
        throw
    }
}

function Start-InstalledLocalSigner {
    param([switch]$PreserveRuntimeLogs)

    $installedStarterCmd = Join-Path $targetDir "start_local_signer.cmd"
    $servicePythonExe = Get-LocalSignerServicePython -RootDir $targetDir
    if (-not $PreserveRuntimeLogs) {
        Remove-Item $runtimeStdoutLog, $runtimeStderrLog -Force -ErrorAction SilentlyContinue
    }

    if ($servicePythonExe -and (Test-Path -LiteralPath $servicePythonExe)) {
        $env:PCT_LOCAL_SIGNER_ALLOWED_ORIGINS = $defaultAllowedOrigins
        $env:IUSENTRA_LOCAL_SIGNER_UPDATE_URL = "$defaultBaseUrl/polisWeb/local-signer/setup/windows"
        Set-LocalSignerRuntimeEnvironment -RootDir $targetDir
        if ((Split-Path -Leaf $servicePythonExe).ToLowerInvariant() -eq "pythonw.exe") {
            Start-Process -WindowStyle Hidden -WorkingDirectory $targetDir -FilePath $servicePythonExe -ArgumentList @($pythonScript)
        } else {
            Start-Process `
                -WindowStyle Hidden `
                -WorkingDirectory $targetDir `
                -FilePath $servicePythonExe `
                -ArgumentList @($pythonScript) `
                -RedirectStandardOutput $runtimeStdoutLog `
                -RedirectStandardError $runtimeStderrLog
        }
    } elseif (Test-Path -LiteralPath $installedStarterCmd) {
        Start-Process -WindowStyle Hidden -FilePath $installedStarterCmd -ArgumentList @("--background")
    } else {
        throw "Launcher Local Signer mancante dopo il cutover."
    }
    return $servicePythonExe
}

function Restore-PreviousLocalSigner {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RollbackRoot,
        [bool]$PreviousWasOnline
    )

    Stop-LocalSignerProcesses
    if (Test-Path -LiteralPath $RollbackRoot) {
        $failedRoot = "$RollbackRoot.failed"
        Remove-Item -LiteralPath $failedRoot -Recurse -Force -ErrorAction SilentlyContinue
        if (Test-Path -LiteralPath $targetDir) {
            Move-Item -LiteralPath $targetDir -Destination $failedRoot -ErrorAction Stop
        }
        try {
            Move-Item -LiteralPath $RollbackRoot -Destination $targetDir -ErrorAction Stop
        } catch {
            if ((Test-Path -LiteralPath $failedRoot) -and -not (Test-Path -LiteralPath $targetDir)) {
                Move-Item -LiteralPath $failedRoot -Destination $targetDir -ErrorAction SilentlyContinue
            }
            throw
        }
        Remove-Item -LiteralPath $failedRoot -Recurse -Force -ErrorAction SilentlyContinue
    }

    if ($PreviousWasOnline -and (Test-Path -LiteralPath (Join-Path $targetDir "local_signer.py"))) {
        Start-InstalledLocalSigner -PreserveRuntimeLogs | Out-Null
        if (-not (Wait-LocalSigner -Attempts 30)) {
            throw "La versione Local Signer precedente e' stata ripristinata ma non ha risposto al riavvio."
        }
    }
}

function Invoke-LocalSignerInstallWorkflow {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StageRoot,
        [Parameter(Mandatory = $true)]
        [string]$RollbackRoot
    )

    $prepared = $null
    $previousWasOnline = Test-LocalSignerOnline
    $cutoverAttempted = $false
    $cutoverSucceeded = $false
    try {
        Write-Step "Preparo file, runtime e dipendenze senza interrompere il Local Signer attivo..."
        $prepared = New-LocalSignerPreparedStage -StageRoot $StageRoot
        Write-Step "Staging verificato: avvio il passaggio atomico alla nuova versione..."

        $cutoverAttempted = $true
        Stop-LocalSignerProcesses
        Sync-LocalSignerPreservedStateToStage -StageRoot $prepared.Root
        Switch-LocalSignerStageToLive -StageRoot $prepared.Root -RollbackRoot $RollbackRoot

        Write-Step "Registro il protocollo locale iusentra-local-signer://..."
        Register-LocalSignerProtocol
        Write-Step "Verifico un solo avvio automatico permanente al login..."
        Ensure-LocalSignerAutostart | Out-Null

        Write-Step "Avvio il servizio aggiornato in background..."
        $servicePythonExe = Start-InstalledLocalSigner
        Write-Step "Attendo che il servizio risponda su 127.0.0.1:27272..."
        $online = Wait-LocalSigner
        if ($online) {
            Stop-LocalSignerDuplicateProcesses
            Start-Sleep -Milliseconds 500
            $online = (Test-LocalSignerOnline) -and (Test-LocalSignerSingleInstance)
        }
        if (-not $online) {
            Write-LocalSignerStartupDiagnostics -ServicePythonExe $servicePythonExe
            throw "Il nuovo Local Signer non ha superato la verifica di avvio; ripristino la versione precedente."
        }

        $cutoverSucceeded = $true
        try {
            Remove-Item -LiteralPath $RollbackRoot -Recurse -Force -ErrorAction Stop
        } catch {
            # Il nuovo servizio e' gia' stato verificato. Un file temporaneamente
            # bloccato dall'antivirus non deve trasformare un cutover riuscito in
            # un falso fallimento; il finally riprova la pulizia senza interrompere
            # il Local Signer appena validato.
            Write-InstallerLog "Pulizia rollback da ripetere: $($_.Exception.Message)"
        }
        Write-InstallerLog "Installazione completata con staging validato, cutover atomico e servizio attivo."
        return 0
    } catch {
        if ($cutoverAttempted -and -not $cutoverSucceeded) {
            try {
                Restore-PreviousLocalSigner -RollbackRoot $RollbackRoot -PreviousWasOnline $previousWasOnline
                Write-InstallerLog "Versione Local Signer precedente preservata o ripristinata dopo l'errore."
            } catch {
                Write-InstallerLog "ERRORE RIPRISTINO: $($_.Exception.Message)"
                throw
            }
        }
        throw
    } finally {
        if (Test-Path -LiteralPath $StageRoot) {
            Remove-Item -LiteralPath $StageRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
        if ($cutoverSucceeded -and (Test-Path -LiteralPath $RollbackRoot)) {
            Remove-Item -LiteralPath $RollbackRoot -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}


# ═══════════════════════════════════════════════════════════════════
#  INIZIO INSTALLAZIONE
# ═══════════════════════════════════════════════════════════════════

function Invoke-LocalSignerInstallerMain {
    param(
        [string]$StageRoot = "",
        [string]$RollbackRoot = ""
    )

    New-Item -ItemType Directory -Force -Path $targetParentDir | Out-Null
    if (-not $StageRoot -or -not $RollbackRoot) {
        $transactionId = "$PID-$([Guid]::NewGuid().ToString('N'))"
        if (-not $StageRoot) {
            $StageRoot = Join-Path $targetParentDir "LocalSigner.install-$transactionId"
        }
        if (-not $RollbackRoot) {
            $RollbackRoot = Join-Path $targetParentDir "LocalSigner.rollback-$transactionId"
        }
    }

    $exitCode = 0
    $lockAcquired = $false
    try {
        Acquire-InstallerLock
        $lockAcquired = $true
        Write-InstallerLog "Avvio installazione Local Signer con staging transazionale."
        $exitCode = Invoke-LocalSignerInstallWorkflow -StageRoot $StageRoot -RollbackRoot $RollbackRoot
    } catch {
        $exitCode = 1
        $errText = $_.Exception.Message
        try {
            Write-InstallerLog "ERRORE: $errText"
        } catch {
        }
        Write-Host "ERRORE: $errText" -ForegroundColor Red
        Write-Host "La versione Local Signer precedente e' stata preservata o ripristinata." -ForegroundColor Yellow
        Write-Host "Log installazione: $installerLog" -ForegroundColor Yellow
    } finally {
        Remove-Item -LiteralPath $StageRoot -Recurse -Force -ErrorAction SilentlyContinue
        if ($lockAcquired -or $script:installLockStream) {
            Release-InstallerLock
        }
    }
    return $exitCode
}

if ($LibraryOnly) {
    return
}

Write-Host ""
Write-Host "IUSENTRA Local Signer - Installazione Windows" -ForegroundColor Green
Write-Host ""

$exitCode = Invoke-LocalSignerInstallerMain

Write-Host ""
if ($exitCode -eq 0) {
    Write-Host "Installazione completata." -ForegroundColor Green
    Write-Host "Il Local Signer e' attivo, raggiungibile e dispone di un solo avvio automatico." -ForegroundColor Green
    Write-Host "Diagnostica locale: http://127.0.0.1:27272/diagnosi" -ForegroundColor Cyan
}

Wait-InstallerDebugExit
exit $exitCode

# ── Rilevamento Python ────────────────────────────────────────────
# Priorita': 1) Python di sistema  2) Python portatile gia' installato  3) Download automatico

# ── Preparazione directory e file ─────────────────────────────────

# ── Configurazione ambiente Python ────────────────────────────────

# ── Launcher, protocollo e avvio automatico ───────────────────────
