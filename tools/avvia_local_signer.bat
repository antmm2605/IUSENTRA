@echo off
setlocal
:: IUSENTRA Local Signer - bootstrap locale intelligente
:: - Se il servizio automatico e' gia' installato, lo riavvia.
:: - Se manca, lancia l'installer locale Windows.

title IUSENTRA Local Signer

set "TASK_NAME=IUSENTRA Local Signer"
set "INSTALLER_PS1=%~dp0installa_local_signer_locale.ps1"
set "APPDATA_STARTER=%APPDATA%\IUSENTRA\LocalSigner\start_local_signer.cmd"
set "BACKGROUND_MODE=0"
set "SILENT_MODE=0"
set "FORCE_RESTART=0"

if /I "%~1"=="--background" set "BACKGROUND_MODE=1"
if /I "%~1"=="--silent" set "SILENT_MODE=1"
if /I "%~1"=="--force" set "FORCE_RESTART=1"

echo.
echo IUSENTRA Local Signer - bootstrap locale
echo.

schtasks /Query /TN "%TASK_NAME%" >nul 2>&1
if not errorlevel 1 (
    echo Servizio gia' installato. Controllo stato locale...
    if "%FORCE_RESTART%"=="0" (
        powershell -NoProfile -WindowStyle Hidden -Command "try { $r = Invoke-RestMethod 'http://127.0.0.1:27272/ping?light=1' -UseBasicParsing -TimeoutSec 2; if ($r.ok) { exit 0 } } catch {}; exit 1" >nul 2>&1
        if not errorlevel 1 (
            if "%BACKGROUND_MODE%"=="1" exit /b 0
            if "%SILENT_MODE%"=="1" exit /b 0
            start "" "http://127.0.0.1:27272/diagnosi"
            exit /b 0
        )
    )
    echo Avvio in background...
    if "%FORCE_RESTART%"=="1" (
        powershell -NoProfile -WindowStyle Hidden -Command "Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -and $_.CommandLine -match 'local_signer.py' } | ForEach-Object { try { Stop-Process -Id $_.ProcessId -Force -ErrorAction Stop } catch {} }; Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 27272 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { try { Stop-Process -Id $_ -Force -ErrorAction Stop } catch {} }" >nul 2>&1
    )
    schtasks /Run /TN "%TASK_NAME%" >nul 2>&1
    if "%BACKGROUND_MODE%"=="1" exit /b 0
    if "%SILENT_MODE%"=="1" exit /b 0
    timeout /t 2 >nul
    start "" "http://127.0.0.1:27272/diagnosi"
    exit /b 0
)

if exist "%APPDATA_STARTER%" (
    echo Installazione locale trovata. Avvio Local Signer...
    call "%APPDATA_STARTER%" --background
    if "%BACKGROUND_MODE%"=="1" exit /b 0
    if "%SILENT_MODE%"=="1" exit /b 0
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
if "%SILENT_MODE%"=="1" exit /b 0
timeout /t 2 >nul
start "" "http://127.0.0.1:27272/diagnosi"
