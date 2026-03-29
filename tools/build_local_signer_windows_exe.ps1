# HACS Local Signer - Build installer Windows .exe
# Usa IExpress (integrato in Windows) per creare SetupLocalSigner.exe senza dipendenze esterne.

$ErrorActionPreference = "Stop"

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$distDir = Join-Path $toolsDir "dist"
$buildDir = Join-Path $toolsDir ".iexpress-build"
$iexpressExe = Join-Path $env:SystemRoot "System32\iexpress.exe"
$outputExe = Join-Path $distDir "SetupLocalSigner.exe"
$sedFile = Join-Path $buildDir "local_signer.sed"

if (-not (Test-Path $iexpressExe)) {
    throw "IExpress non trovato. Verificare l'installazione di Windows."
}

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
if (Test-Path $buildDir) {
    Remove-Item -Recurse -Force $buildDir
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

Copy-Item (Join-Path $toolsDir "installa_local_signer_locale.ps1") $buildDir -Force
Copy-Item (Join-Path $toolsDir "local_signer.py") $buildDir -Force
Copy-Item (Join-Path $toolsDir "requirements_local_signer.txt") $buildDir -Force
Copy-Item (Join-Path (Split-Path -Parent $toolsDir) "pct\data\uffici_ministero.json") $buildDir -Force

$escapedSource = $buildDir.Replace("\", "\\")
$escapedTarget = $outputExe.Replace("\", "\\")

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
FinishMessage=Installazione completata.
TargetName=$escapedTarget
FriendlyName=HACS Local Signer Setup
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
[Strings]
FILE0=installa_local_signer_locale.ps1
FILE1=local_signer.py
FILE2=requirements_local_signer.txt
FILE3=uffici_ministero.json
"@

Set-Content -Path $sedFile -Value $sed -Encoding ASCII

Write-Host ""
Write-Host "Genero SetupLocalSigner.exe..." -ForegroundColor Cyan
& $iexpressExe /N $sedFile | Out-Null

if (-not (Test-Path $outputExe)) {
    throw "Build completata senza generare $outputExe"
}

Write-Host "Installer creato: $outputExe" -ForegroundColor Green
