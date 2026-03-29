@echo off
setlocal
:: HACS Local Signer - bootstrap locale intelligente
:: - Se il servizio automatico e' gia' installato, lo riavvia.
:: - Se manca, lancia l'installer locale Windows.

title HACS Local Signer

set "TASK_NAME=HACS Local Signer"
set "INSTALLER_PS1=%~dp0installa_local_signer_locale.ps1"
set "BACKGROUND_MODE=0"

if /I "%~1"=="--background" set "BACKGROUND_MODE=1"

echo.
echo HACS Local Signer - bootstrap locale
echo.

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo Servizio gia' installato. Avvio in background...
    schtasks /Run /TN "%TASK_NAME%" >nul 2>&1
    if "%BACKGROUND_MODE%"=="1" exit /b 0
    timeout /t 2 >nul
    start "" "http://127.0.0.1:27272/diagnosi"
    exit /b 0
)

if not exist "%INSTALLER_PS1%" (
    echo ERRORE: installer locale non trovato.
    echo Percorso atteso: %INSTALLER_PS1%
    echo.
    pause
    exit /b 1
)

echo Installo il servizio locale e l'avvio automatico...
powershell -NoProfile -ExecutionPolicy Bypass -File "%INSTALLER_PS1%"
if errorlevel 1 (
    echo.
    echo Installazione non riuscita.
    echo.
    pause
    exit /b 1
)

if "%BACKGROUND_MODE%"=="1" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
