# IUSENTRA - Builder pacchetto Windows per import Studio Telematico
# Genera web/static/tools/PreparaPacchettoStudioTelematico.exe partendo dallo
# script locale che raccoglie QuickOrganizer.mdb, ATTI ed EMAILS.

$ErrorActionPreference = "Stop"

$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoDir = Split-Path -Parent $toolsDir
$staticToolsDir = Join-Path $repoDir "web\static\tools"
$sourcePs1 = Join-Path $staticToolsDir "prepara_import_studio_telematico.ps1"
$outputExe = Join-Path $staticToolsDir "PreparaPacchettoStudioTelematico.exe"
$buildDir = Join-Path $toolsDir ".studio-telematico-iexpress-build"
$iexpressExe = Join-Path $env:SystemRoot "System32\iexpress.exe"
$sedFile = Join-Path $buildDir "prepara_import_studio_telematico.sed"

if (-not (Test-Path $sourcePs1)) {
    throw "Script preparazione Studio Telematico non trovato: $sourcePs1"
}
if (-not (Test-Path $iexpressExe)) {
    throw "IExpress non trovato. Verificare l'installazione di Windows."
}

if (Test-Path $buildDir) {
    Remove-Item -Recurse -Force $buildDir
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
New-Item -ItemType Directory -Force -Path $staticToolsDir | Out-Null

Copy-Item $sourcePs1 (Join-Path $buildDir "prepara_import_studio_telematico.ps1") -Force

$escapedSource = $buildDir.Replace("\", "\\")
$escapedTarget = $outputExe.Replace("\", "\\")
$friendlyName = "IUSENTRA Prepara Pacchetto Studio Telematico"
$finishMessage = "Pacchetto Studio Telematico preparato. Carica lo ZIP in IUSENTRA."

$sed = @"
[Version]
Class=IEXPRESS
SEDVersion=3
[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=1
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
AppLaunched=powershell.exe -NoProfile -ExecutionPolicy Bypass -File prepara_import_studio_telematico.ps1
PostInstallCmd=<None>
AdminQuietInstCmd=powershell.exe -NoProfile -ExecutionPolicy Bypass -File prepara_import_studio_telematico.ps1
UserQuietInstCmd=powershell.exe -NoProfile -ExecutionPolicy Bypass -File prepara_import_studio_telematico.ps1
SourceFiles=SourceFiles
[SourceFiles]
SourceFiles0=$escapedSource
[SourceFiles0]
%FILE0%=
[Strings]
FILE0=prepara_import_studio_telematico.ps1
"@

Set-Content -Path $sedFile -Value $sed -Encoding ASCII

Write-Host "Genero pacchetto Windows: PreparaPacchettoStudioTelematico.exe" -ForegroundColor Cyan
& $iexpressExe /N $sedFile | Out-Null

if (-not (Test-Path $outputExe)) {
    throw "Build completata senza generare $outputExe"
}

$signature = [System.IO.File]::ReadAllBytes($outputExe)[0..1]
if ($signature[0] -ne 0x4d -or $signature[1] -ne 0x5a) {
    throw "Il file generato non e' un eseguibile Windows valido."
}

Write-Host "OK: $outputExe" -ForegroundColor Green
