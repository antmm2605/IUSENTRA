# IUSENTRA Local Signer Setup v1.6.64
# Pacchetto generato il 2026-05-29 16:02:17
# Punto ufficiale download: https://app.iusentra.it/impostazioni?tab=firma

# IUSENTRA Local Signer - Installazione locale Windows
# Usa i file gia' presenti nella cartella tools e configura l'avvio automatico.
# Se Python non e' installato, scarica automaticamente Python portatile.

param(
    [switch]$Quiet
)

$ErrorActionPreference = "Stop"

$taskName = "IUSENTRA Local Signer"
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $toolsDir
$targetDir = Join-Path $env:APPDATA "IUSENTRA\LocalSigner"
$venvDir = Join-Path $targetDir ".venv"
$embeddedPythonDir = Join-Path $targetDir "python"
$pythonScript = Join-Path $targetDir "local_signer.py"
$aiBridgeScript = Join-Path $targetDir "local_ai_host_bridge.py"
$lexContextScript = Join-Path $targetDir "lex_document_context.py"
$visibleSignatureScript = Join-Path $targetDir "visible_signature.py"
$moduleDir = Join-Path $targetDir "local_signer_mod"
$dataDir = Join-Path $targetDir "data"
$ufficiTarget = Join-Path $dataDir "uffici_ministero.json"
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

New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

function Write-InstallerLog([string]$Message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $installerLog -Value "[$timestamp] $Message" -Encoding UTF8
}

trap {
    $errText = $_.Exception.Message
    Write-InstallerLog "ERRORE: $errText"
    Write-Host "ERRORE: $errText" -ForegroundColor Red
    Write-Host "Log installazione: $installerLog" -ForegroundColor Yellow
    if (-not $Quiet) {
        Read-Host "Premere Invio per chiudere"
    }
    exit 1
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
        [string]$FailureMessage
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $output = & $pythonExe -m pip @Arguments 2>&1
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
    <#
    .SYNOPSIS
    Scarica e configura Python portatile (embeddable) nella cartella IUSENTRA.
    Non modifica il sistema, non richiede permessi admin, non richiede
    installazione manuale da parte dell'utente.
    #>

    $embedZip = Join-Path $targetDir "python-embed.zip"

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
    if (Test-Path $embeddedPythonDir) {
        Remove-Item $embeddedPythonDir -Recurse -Force
    }
    Expand-Archive -Path $embedZip -DestinationPath $embeddedPythonDir -Force
    Remove-Item $embedZip -Force

    # Abilita "import site" nel file ._pth (necessario per pip e site-packages)
    $pthFile = Get-ChildItem $embeddedPythonDir -Filter "python*._pth" | Select-Object -First 1
    if ($pthFile) {
        $content = Get-Content $pthFile.FullName -Raw
        $content = $content -replace "#\s*import site", "import site"
        Set-Content $pthFile.FullName $content -NoNewline
        Write-InstallerLog "Abilitato import site in $($pthFile.Name)"
    }

    # Scarica e installa pip
    Write-Step "Configuro pip (gestore pacchetti Python)..."
    $getPipFile = Join-Path $embeddedPythonDir "get-pip.py"
    $embedPython = Join-Path $embeddedPythonDir "python.exe"

    try {
        Invoke-WebRequest -Uri $getPipUrl -OutFile $getPipFile -UseBasicParsing
    } catch {
        Write-Host "  ERRORE: impossibile scaricare pip." -ForegroundColor Red
        return $false
    }

    & $embedPython $getPipFile --quiet --no-warn-script-location 2>$null
    Remove-Item $getPipFile -Force -ErrorAction SilentlyContinue

    # Verifica che pip sia installato
    $pipExe = Join-Path $embeddedPythonDir "Scripts\pip.exe"
    if (-not (Test-Path $pipExe)) {
        Write-Host "  ERRORE: configurazione pip fallita." -ForegroundColor Red
        return $false
    }

    Write-Step "Python $embeddedPythonVersion portatile pronto."
    Write-InstallerLog "Python embeddable installato in $embeddedPythonDir"
    return $true
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

function Uninstall-ExistingLocalSigner {
    Write-InstallerLog "Avvio disinstallazione controllata della vecchia installazione"

    Stop-LocalSignerProcesses
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null

    $startupDir = [Environment]::GetFolderPath("Startup")
    if ($startupDir) {
        $shortcutPath = Join-Path $startupDir "IUSENTRA Local Signer.lnk"
        Remove-Item -LiteralPath $shortcutPath -Force -ErrorAction SilentlyContinue
    }

    foreach ($protocolName in @("iusentra-local-signer", ("ha" + "cs-local-signer"))) {
        Remove-Item -Path "HKCU:\Software\Classes\$protocolName" -Recurse -Force -ErrorAction SilentlyContinue
    }

    $resolvedTarget = [System.IO.Path]::GetFullPath($targetDir)
    $resolvedAppData = [System.IO.Path]::GetFullPath((Join-Path $env:APPDATA "IUSENTRA"))
    if (-not $resolvedTarget.StartsWith($resolvedAppData, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Percorso Local Signer non sicuro per la disinstallazione: $resolvedTarget"
    }

    if (-not (Test-Path $targetDir)) {
        return
    }

    $preserve = @("data", "installer.log", "local_signer.out.log", "local_signer.err.log")
    Get-ChildItem -LiteralPath $targetDir -Force -ErrorAction SilentlyContinue |
        Where-Object { $preserve -notcontains $_.Name } |
        ForEach-Object {
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }

    Write-InstallerLog "Vecchia installazione rimossa; dati locali e log preservati"
}

function Copy-LocalSignerModule {
    $moduleSourceDir = Join-Path $toolsDir "local_signer_mod"
    New-Item -ItemType Directory -Force -Path $moduleDir | Out-Null

    foreach ($moduleFile in @("__init__.py", "ai_cache.py", "ai_handlers.py", "pec_bridge.py", "security.py", "server_bootstrap.py")) {
        $source = Join-Path $moduleSourceDir $moduleFile
        if (-not (Test-Path $source)) {
            $source = Join-Path $toolsDir ("local_signer_mod__" + $moduleFile)
        }
        if (-not (Test-Path $source)) {
            $downloadUrl = "$defaultBaseUrl/polisWeb/local-signer/download/local-signer-mod/$moduleFile"
            $target = Join-Path $moduleDir $moduleFile
            try {
                Invoke-WebRequest -Uri $downloadUrl -OutFile $target -UseBasicParsing
                continue
            } catch {
                throw "Modulo Local Signer mancante nel pacchetto e download non riuscito: local_signer_mod\$moduleFile"
            }
        }
        Copy-Item $source (Join-Path $moduleDir $moduleFile) -Force
    }
}

function Write-LocalSignerLaunchers {
    $allowedOrigins = $defaultAllowedOrigins
    $updateInstallerUrl = "$defaultBaseUrl/polisWeb/local-signer/setup/windows"
    # Il launcher cerca pythonw.exe in due posizioni:
    # 1. python\pythonw.exe  (Python portatile scaricato dall'installer)
    # 2. .venv\Scripts\pythonw.exe  (venv creato da Python di sistema)
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

if /I "%~1"=="--force" set "FORCE_RESTART=1"
if /I "%~1"=="--silent" set "SILENT_MODE=1"
if /I "%~1"=="--update" set "UPDATE_MODE=1"
echo %~1 | find /I "iusentra-local-signer://restart" >nul 2>&1 && set "FORCE_RESTART=1"
echo %~1 | find /I "iusentra-local-signer://update" >nul 2>&1 && set "UPDATE_MODE=1"

if "%UPDATE_MODE%"=="1" goto :update

rem Cerca pythonw: prima Python portatile, poi venv
set "PYW=%DIR%python\pythonw.exe"
if not exist "%PYW%" set "PYW=%DIR%.venv\Scripts\pythonw.exe"

if "%FORCE_RESTART%"=="0" (
powershell -NoProfile -WindowStyle Hidden -Command "try { $r = Invoke-RestMethod 'http://127.0.0.1:27272/ping' -UseBasicParsing -TimeoutSec 2; if ($r.ok) { exit 0 } } catch {}; exit 1" >nul 2>&1
if not errorlevel 1 goto :online
)

powershell -NoProfile -WindowStyle Hidden -Command "$target = [regex]::Escape($env:TARGET); Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -match $target } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }" >nul 2>&1
powershell -NoProfile -WindowStyle Hidden -Command "Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {} }" >nul 2>&1

if exist "%PYW%" if exist "%PY%" (
    powershell -NoProfile -WindowStyle Hidden -Command "Start-Process -WindowStyle Hidden -FilePath $env:PYW -ArgumentList @($env:PY)"
) else (
    exit /b 1
)

:online
if /I "%~1"=="--background" exit /b 0
if "%SILENT_MODE%"=="1" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
exit /b 0

:update
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$ErrorActionPreference='Stop'; $url=$env:IUSENTRA_LOCAL_SIGNER_UPDATE_URL; if (-not $url.StartsWith('https://app.iusentra.it/')) { exit 2 }; $target=Join-Path $env:TEMP ('SetupLocalSigner-' + [Guid]::NewGuid().ToString('N') + '.exe'); Invoke-WebRequest -Uri $url -UseBasicParsing -OutFile $target; Start-Process -WindowStyle Hidden -FilePath $target -ArgumentList @('/Q')"
exit /b %ERRORLEVEL%
'@
    $cmd = $cmd.Replace('__ALLOWED_ORIGINS__', $allowedOrigins)
    $cmd = $cmd.Replace('__UPDATE_INSTALLER_URL__', $updateInstallerUrl)
    Set-Content -Path $starterCmd -Value $cmd -Encoding ASCII

    $vbs = @'
Set shell = CreateObject("WScript.Shell")
Dim extra
extra = " --background"
If WScript.Arguments.Count > 0 Then
  If InStr(LCase(WScript.Arguments(0)), "iusentra-local-signer://update") > 0 Then
    extra = " --update"
  ElseIf InStr(LCase(WScript.Arguments(0)), "iusentra-local-signer://restart") > 0 Then
    extra = extra & " --force"
  End If
End If
shell.Run Chr(34) & "__STARTER_CMD__" & Chr(34) & extra, 0, False
'@
    $vbs = $vbs.Replace('__STARTER_CMD__', $starterCmd)
    Set-Content -Path $starterVbs -Value $vbs -Encoding ASCII
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

function Register-LocalSignerScheduledTask {
    $cmdExe = Join-Path $env:SystemRoot "System32\cmd.exe"
    $action = New-ScheduledTaskAction -Execute $cmdExe -Argument "/c `"$starterCmd`" --background"
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERNAME"
    $settings = New-ScheduledTaskSettingsSet `
        -ExecutionTimeLimit 0 `
        -RestartCount 3 `
        -StartWhenAvailable `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries

    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null
    Register-ScheduledTask `
        -TaskName $taskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "IUSENTRA Local Signer - avvio automatico al login" `
        -Force | Out-Null
    Write-InstallerLog "Attivita' pianificata registrata: $taskName"
}


# ═══════════════════════════════════════════════════════════════════
#  INIZIO INSTALLAZIONE
# ═══════════════════════════════════════════════════════════════════

Write-Host ""
Write-Host "IUSENTRA Local Signer - Installazione Windows" -ForegroundColor Green
Write-Host ""
Write-InstallerLog "Avvio installazione Local Signer"

Write-Step "Disinstallo la vecchia versione locale prima di installare quella nuova..."
Uninstall-ExistingLocalSigner

# ── Rilevamento Python ────────────────────────────────────────────
# Priorita': 1) Python di sistema  2) Python portatile gia' installato  3) Download automatico
$useEmbeddedPython = $false
$pythonCmd = Find-PythonCommand

if ($pythonCmd) {
    Write-Step "Python di sistema trovato: $pythonCmd"
} else {
    # Controlla se c'e' gia' il Python portatile da un'installazione precedente
    $embPy = Join-Path $embeddedPythonDir "python.exe"
    if ((Test-Path $embPy) -and (Test-PythonWorks "`"$embPy`"")) {
        Write-Step "Python portatile gia' presente: $embPy"
        $useEmbeddedPython = $true
    } else {
        # Scarica Python portatile automaticamente
        $result = Install-EmbeddedPython
        if (-not $result) {
            Write-Host ""
            Write-Host "  L'installazione automatica di Python non e' riuscita." -ForegroundColor Red
            Write-Host "  Verificare la connessione internet e riprovare." -ForegroundColor Yellow
            Write-Host ""
            if (-not $Quiet) {
                Read-Host "Premere Invio per chiudere"
            }
            exit 1
        }
        $useEmbeddedPython = $true
    }
}

# ── Preparazione directory e file ─────────────────────────────────
New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
New-Item -ItemType Directory -Force -Path $moduleDir | Out-Null

if (Test-Path $pythonScript) {
    Write-Step "Aggiorno l'installazione locale gia' presente..."
}

Write-Step "Arresto eventuali istanze Local Signer prima dell'aggiornamento..."
Stop-LocalSignerProcesses

Write-Step "Copio i file del Local Signer..."
Copy-Item (Join-Path $toolsDir "local_signer.py") $pythonScript -Force
Copy-Item (Join-Path $toolsDir "local_ai_host_bridge.py") $aiBridgeScript -Force
Copy-Item (Join-Path $toolsDir "lex_document_context.py") $lexContextScript -Force
$visibleSignatureSource = Join-Path $toolsDir "visible_signature.py"
if (-not (Test-Path $visibleSignatureSource)) {
    $visibleSignatureSource = Join-Path $repoRoot "visible_signature.py"
}
Copy-Item $visibleSignatureSource $visibleSignatureScript -Force
Copy-Item (Join-Path $toolsDir "requirements_local_signer.txt") $requirementsFile -Force
Copy-LocalSignerModule
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

# ── Configurazione ambiente Python ────────────────────────────────
if ($useEmbeddedPython) {
    # Python portatile: i pacchetti si installano direttamente (nessun venv)
    $pythonExe = Join-Path $embeddedPythonDir "python.exe"
    $pythonwExe = Join-Path $embeddedPythonDir "pythonw.exe"
    Write-Step "Uso Python portatile (nessun virtualenv necessario)."
} else {
    # Python di sistema: crea venv isolato
    Write-Step "Preparo l'ambiente Python (virtualenv)..."
    if (-not (Test-Path $pythonExe)) {
        & cmd /c "$pythonCmd -m venv `"$venvDir`""
        if (-not (Test-Path $pythonExe)) {
            Write-Host "  ERRORE: impossibile creare il virtual environment Python." -ForegroundColor Red
            Write-Host "  Verificare che Python sia installato correttamente." -ForegroundColor Yellow
            if (-not $Quiet) { Read-Host "Premere Invio per chiudere" }
            exit 1
        }
    }
}

Write-Step "Aggiorno pip..."
if (-not (Invoke-Pip -Arguments @("install", "--quiet", "--no-cache-dir", "--upgrade", "pip") -FailureMessage "impossibile aggiornare pip.")) {
    Write-Host "  Verificare la connessione internet e riprovare." -ForegroundColor Yellow
    if (-not $Quiet) { Read-Host "Premere Invio per chiudere" }
    exit 1
}

Write-Step "Installo dipendenze base (asn1crypto, cryptography, zeep, pdfplumber, mammoth, pypdf, reportlab)..."
if (-not (Invoke-Pip -Arguments @("install", "--quiet", "--no-cache-dir", "--no-warn-script-location", "asn1crypto>=1.5.0", "cryptography>=41.0.0", "zeep>=4.2.1", "pdfplumber>=0.10.0", "mammoth>=1.6.0", "pypdf>=6.0.0", "reportlab>=4.0.0") -FailureMessage "impossibile installare le dipendenze base.")) {
    Write-Host "  Verificare la connessione internet e riprovare." -ForegroundColor Yellow
    if (-not $Quiet) { Read-Host "Premere Invio per chiudere" }
    exit 1
}

Write-Step "Installo python-pkcs11 (per firma con smart card/token CNS)..."
if (Invoke-Pip -Arguments @("install", "--quiet", "--no-cache-dir", "--no-warn-script-location", "python-pkcs11>=0.7.0") -FailureMessage "python-pkcs11 non installato.") {
    Write-Step "python-pkcs11 installato correttamente."
} else {
    Write-Host "  AVVISO: python-pkcs11 non installato (potrebbe non avere wheel per questa versione di Python)." -ForegroundColor Yellow
    Write-Host "  Il Local Signer funzionera' ma la firma con smart card richiede python-pkcs11." -ForegroundColor Yellow
}

# ── Launcher, protocollo e avvio automatico ───────────────────────
Write-Step "Preparo l'avvio contestuale da IUSENTRA..."
Write-LocalSignerLaunchers

Write-Step "Registro il protocollo locale iusentra-local-signer://..."
Register-LocalSignerProtocol

Write-Step "Registro l'avvio automatico permanente al login..."
$autostartOk = $false
try {
    Register-LocalSignerScheduledTask
    $autostartOk = $true
} catch {
    Write-InstallerLog "Attivita' pianificata non registrata: $($_.Exception.Message)"
    Write-Host "  AVVISO: attivita' pianificata non registrata, preparo fallback Startup." -ForegroundColor Yellow
}
try {
    if (Register-LocalSignerStartupShortcut) {
        $autostartOk = $true
    }
} catch {
    Write-InstallerLog "Fallback Startup non registrato: $($_.Exception.Message)"
}
if (-not $autostartOk) {
    throw "Impossibile registrare l'avvio automatico permanente del Local Signer."
}

Write-Step "Avvio subito il servizio in background..."
Stop-LocalSignerProcesses
Remove-Item $runtimeStdoutLog, $runtimeStderrLog -Force -ErrorAction SilentlyContinue
if (Test-Path $pythonExe) {
    $env:PCT_LOCAL_SIGNER_ALLOWED_ORIGINS = $defaultAllowedOrigins
    Start-Process `
        -WindowStyle Hidden `
        -WorkingDirectory $targetDir `
        -FilePath $pythonExe `
        -ArgumentList $pythonScript `
        -RedirectStandardOutput $runtimeStdoutLog `
        -RedirectStandardError $runtimeStderrLog
} else {
    Start-Process -WindowStyle Hidden -FilePath $starterCmd -ArgumentList @("--background")
}

Write-Step "Attendo che il servizio risponda su 127.0.0.1:27272..."
$online = Wait-LocalSigner
$exitCode = 0
if (-not $online) {
    $exitCode = 1
}

Write-Host ""
if ($online) {
    Write-InstallerLog "Installazione completata con servizio attivo"
    Write-Host "Installazione completata." -ForegroundColor Green
    Write-Host "Il Local Signer e' attivo e raggiungibile." -ForegroundColor Green
    Write-Host "Da ora in poi IUSENTRA puo' avviarlo automaticamente quando clicchi Cerca." -ForegroundColor Cyan
    Write-Host "Diagnostica locale: http://127.0.0.1:27272/diagnosi" -ForegroundColor Cyan
} else {
    Write-Host "Installazione completata con avviso." -ForegroundColor Yellow
    Write-Host "Il servizio non ha ancora risposto su http://127.0.0.1:27272." -ForegroundColor Yellow
    Write-Host "Apri IUSENTRA e usa 'Avvia Local Signer', oppure esegui di nuovo questo installer." -ForegroundColor Yellow
    if (Test-Path $runtimeStderrLog) {
        Write-Host "Dettagli errore: $runtimeStderrLog" -ForegroundColor Yellow
        Write-InstallerLog "Avvio non riuscito. Consultare $runtimeStderrLog"
    }
}

if (-not $Quiet) {
    Read-Host "Premere Invio per chiudere"
}

exit $exitCode
