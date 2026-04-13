# HACS Local Signer - Build pacchetti multipiattaforma versionati
# Genera contestualmente:
#   - Windows  : SetupLocalSigner-<versione>.exe
#   - macOS    : InstallaLocalSigner-<versione>.command
#   - Linux    : InstallaLocalSigner-<versione>.run
# e aggiorna l'alias legacy SetupLocalSigner.exe per retrocompatibilita'.

$ErrorActionPreference = "Stop"

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Split-Path -Parent $toolsDir
$distDir = Join-Path $toolsDir "dist"
$buildDir = Join-Path $toolsDir ".iexpress-build"
$iexpressExe = Join-Path $env:SystemRoot "System32\iexpress.exe"
$localSignerPy = Join-Path $toolsDir "local_signer.py"
$ufficiJson = Join-Path $repoDir "pct\data\uffici_ministero.json"
$baseUrl = "https://studio-legale-pct-production.up.railway.app"
$downloadPage = "$baseUrl/impostazioni?tab=firma"
$allowedOrigins = $baseUrl
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Utf8TextFile {
    param(
        [string]$Path,
        [string]$Content
    )
    $normalized = $Content -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText($Path, $normalized, $utf8NoBom)
}

if (-not (Test-Path $localSignerPy)) {
    throw "File Local Signer non trovato: $localSignerPy"
}

$sourceText = [System.IO.File]::ReadAllText($localSignerPy)
$match = [regex]::Match($sourceText, '^\s*VERSION\s*=\s*"([^"]+)"', [System.Text.RegularExpressions.RegexOptions]::Multiline)
if (-not $match.Success) {
    throw "Impossibile determinare la versione da $localSignerPy"
}
$version = $match.Groups[1].Value

$outputExeVersioned = Join-Path $distDir ("SetupLocalSigner-$version.exe")
$outputExeAlias = Join-Path $distDir "SetupLocalSigner.exe"
$outputPs1Versioned = Join-Path $distDir ("InstallaLocalSigner-$version.ps1")
$outputMac = Join-Path $distDir ("InstallaLocalSigner-$version.command")
$outputLinux = Join-Path $distDir ("InstallaLocalSigner-$version.run")
$releaseNote = Join-Path $distDir ("LocalSigner-$version.txt")
$buildInstallPs1 = Join-Path $buildDir "installa_local_signer_locale.ps1"
$buildReleaseTxt = Join-Path $buildDir "local_signer_release.txt"
$sedFile = Join-Path $buildDir "local_signer.sed"

if (-not (Test-Path $iexpressExe)) {
    throw "IExpress non trovato. Verificare l'installazione di Windows."
}

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
if (Test-Path $buildDir) {
    Remove-Item -Recurse -Force $buildDir
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

$installScriptSource = [System.IO.File]::ReadAllText((Join-Path $toolsDir "installa_local_signer_locale.ps1"))
$installHeader = @"
# HACS Local Signer Setup v$version
# Pacchetto generato il $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Punto ufficiale download: $downloadPage

"@
Write-Utf8TextFile -Path $buildInstallPs1 -Content ($installHeader + $installScriptSource)
Write-Utf8TextFile -Path $outputPs1Versioned -Content ($installHeader + $installScriptSource)
Copy-Item (Join-Path $toolsDir "local_signer.py") $buildDir -Force
Copy-Item (Join-Path $toolsDir "local_ai_host_bridge.py") $buildDir -Force
Copy-Item (Join-Path $toolsDir "requirements_local_signer.txt") $buildDir -Force
Copy-Item $ufficiJson $buildDir -Force

$releaseText = @"
HACS Local Signer
Versione: $version
Pacchetto generato: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
Piattaforme generate contestualmente: Windows, macOS, Linux
Punto ufficiale download: $downloadPage
"@
Write-Utf8TextFile -Path $buildReleaseTxt -Content $releaseText
Write-Utf8TextFile -Path $releaseNote -Content $releaseText

$escapedSource = $buildDir.Replace("\", "\\")
$escapedTarget = $outputExeVersioned.Replace("\", "\\")
$finishMessage = "Installazione completata. HACS Local Signer v$version pronto."
$friendlyName = "HACS Local Signer Setup v$version"

$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
RebootMode=N
InstallPrompt=
DisplayLicense=
FinishMessage=$finishMessage
TargetName=$escapedTarget
FriendlyName=$friendlyName
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -File installa_local_signer_locale.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=powershell.exe -NoProfile -ExecutionPolicy Bypass -File installa_local_signer_locale.ps1 -Quiet
UserQuietInstCmd=powershell.exe -NoProfile -ExecutionPolicy Bypass -File installa_local_signer_locale.ps1 -Quiet
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$escapedSource
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
%FILE3%=
%FILE4%=
%FILE5%=
[Strings]
FILE0=installa_local_signer_locale.ps1
FILE1=local_signer.py
FILE2=local_ai_host_bridge.py
FILE3=requirements_local_signer.txt
FILE4=uffici_ministero.json
FILE5=local_signer_release.txt
"@

Set-Content -Path $sedFile -Value $sed -Encoding ASCII

Write-Host ""
Write-Host "Genero pacchetto Windows versionato: SetupLocalSigner-$version.exe" -ForegroundColor Cyan
& $iexpressExe /N $sedFile | Out-Null

if (-not (Test-Path $outputExeVersioned)) {
    throw "Build completata senza generare $outputExeVersioned"
}

Copy-Item $outputExeVersioned $outputExeAlias -Force

$macTemplate = @'
#!/bin/bash
# HACS Local Signer Setup v__VERSION__
set -euo pipefail

BASE_URL="__BASE_URL__"
ALLOWED_ORIGINS="__ALLOWED_ORIGINS__"
VERSION="__VERSION__"
DIR="$HOME/Library/Application Support/HACS/LocalSigner"
DATA_DIR="$DIR/data"
VENV="$DIR/.venv"
PY="$VENV/bin/python3"
PLIST="$HOME/Library/LaunchAgents/it.hacs.local-signer.plist"

echo "HACS Local Signer v$VERSION - Installazione macOS"
echo "Punto ufficiale download: __DOWNLOAD_PAGE__"

mkdir -p "$DIR" "$DATA_DIR" "$(dirname "$PLIST")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima da https://python.org"
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep

cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>it.hacs.local-signer</string>
  <key>ProgramArguments</key>
  <array>
    <string>$PY</string>
    <string>$DIR/local_signer.py</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PCT_LOCAL_SIGNER_ALLOWED_ORIGINS</key>
    <string>$ALLOWED_ORIGINS</string>
  </dict>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>WorkingDirectory</key>
  <string>$DIR</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$PLIST"
launchctl kickstart -k "gui/$(id -u)/it.hacs.local-signer"

echo
echo "Installazione completata. Local Signer v$VERSION pronto."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Tornare su HACS e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
'@

$macContent = $macTemplate.
    Replace("__BASE_URL__", $baseUrl).
    Replace("__ALLOWED_ORIGINS__", $allowedOrigins).
    Replace("__VERSION__", $version).
    Replace("__DOWNLOAD_PAGE__", $downloadPage)
Write-Utf8TextFile -Path $outputMac -Content $macContent

$linuxTemplate = @'
#!/usr/bin/env bash
# HACS Local Signer Setup v__VERSION__
set -euo pipefail

BASE_URL="__BASE_URL__"
ALLOWED_ORIGINS="__ALLOWED_ORIGINS__"
VERSION="__VERSION__"
DIR="${XDG_DATA_HOME:-$HOME/.local/share}/hacs/local-signer"
DATA_DIR="$DIR/data"
VENV="$DIR/.venv"
PY="$VENV/bin/python"
SERVICE_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE="$SERVICE_DIR/hacs-local-signer.service"

echo "HACS Local Signer v$VERSION - Installazione Linux"
echo "Punto ufficiale download: __DOWNLOAD_PAGE__"

mkdir -p "$DIR" "$DATA_DIR" "$SERVICE_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima con il gestore pacchetti della distribuzione."
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep

cat > "$SERVICE" <<EOF
[Unit]
Description=HACS Local Signer
After=network.target

[Service]
Type=simple
WorkingDirectory=$DIR
Environment=PCT_LOCAL_SIGNER_ALLOWED_ORIGINS=$ALLOWED_ORIGINS
ExecStart=$PY $DIR/local_signer.py
Restart=on-failure

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now hacs-local-signer.service

echo
echo "Installazione completata. Local Signer v$VERSION pronto."
echo "Local Signer attivo su http://127.0.0.1:27272"
echo "Tornare su HACS e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _
'@

$linuxContent = $linuxTemplate.
    Replace("__BASE_URL__", $baseUrl).
    Replace("__ALLOWED_ORIGINS__", $allowedOrigins).
    Replace("__VERSION__", $version).
    Replace("__DOWNLOAD_PAGE__", $downloadPage)
Write-Utf8TextFile -Path $outputLinux -Content $linuxContent

Write-Host "Pacchetto macOS creato: $outputMac" -ForegroundColor Green
Write-Host "Pacchetto Linux creato: $outputLinux" -ForegroundColor Green
Write-Host "Alias legacy aggiornato: $outputExeAlias" -ForegroundColor Green
