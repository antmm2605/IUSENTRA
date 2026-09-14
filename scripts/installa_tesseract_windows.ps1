# Installa Tesseract OCR e il dizionario italiano su un host Windows dello studio.
#
# Uso (PowerShell, come utente):
#   powershell -ExecutionPolicy Bypass -File scripts\installa_tesseract_windows.ps1
#
# 1. Eseguibile: pacchetto ufficiale UB-Mannheim tramite winget.
# 2. Dizionario: ita.traineddata (tessdata_fast 4.1.0) scaricato in
#    %LOCALAPPDATA%\IUSENTRA\tessdata e verificato con SHA-256, la stessa
#    cartella che il motore IUSENTRA controlla all'avvio.
$ErrorActionPreference = "Stop"
$pacchetto = "UB-Mannheim.TesseractOCR"
$cartella = Join-Path $env:LOCALAPPDATA "IUSENTRA\tessdata"
$destinazione = Join-Path $cartella "ita.traineddata"
$impronta = "b8f89e1e785118dac4d51ae042c029a64edb5c3ee42ef73027a6d412748d8827"
$sorgenti = @(
  "https://github.com/tesseract-ocr/tessdata_fast/raw/4.1.0/ita.traineddata",
  "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/ita.traineddata"
)

if (-not (Get-Command tesseract -ErrorAction SilentlyContinue) -and -not (Test-Path "$env:ProgramFiles\Tesseract-OCR\tesseract.exe")) {
  Write-Host "Installo Tesseract OCR ($pacchetto) con winget..."
  winget install -e --id $pacchetto --silent --accept-package-agreements --accept-source-agreements
} else {
  Write-Host "Tesseract OCR gia' presente."
}

New-Item -ItemType Directory -Force -Path $cartella | Out-Null
$valido = $false
if (Test-Path $destinazione) {
  $valido = ((Get-FileHash -Algorithm SHA256 $destinazione).Hash.ToLower() -eq $impronta)
}
if (-not $valido) {
  foreach ($url in $sorgenti) {
    try {
      Write-Host "Scarico il dizionario italiano da $url ..."
      Invoke-WebRequest -Uri $url -OutFile "$destinazione.parziale" -UseBasicParsing
      $hash = (Get-FileHash -Algorithm SHA256 "$destinazione.parziale").Hash.ToLower()
      if ($hash -eq $impronta) {
        Move-Item -Force "$destinazione.parziale" $destinazione
        $valido = $true
        break
      }
      Write-Warning "Impronta non corrispondente ($hash): file scartato."
      Remove-Item -Force "$destinazione.parziale"
    } catch {
      Write-Warning "Download non riuscito da ${url}: $($_.Exception.Message)"
    }
  }
}
if ($valido) {
  Write-Host "Dizionario italiano pronto in $cartella (SHA-256 verificato)."
  Write-Host "Riavvia IUSENTRA: il motore trova il dizionario da solo."
} else {
  Write-Error "Dizionario italiano non installato: controlla la connessione e riprova."
}
