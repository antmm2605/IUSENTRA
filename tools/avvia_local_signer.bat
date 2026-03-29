@echo off
:: HACS Local Signer — Avvio manuale tecnico (fallback)
:: Usare solo se il servizio automatico non è già installato sul PC.

title HACS Local Signer

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  ERRORE: Python non trovato nel PATH.
    echo  Installare Python da https://python.org e aggiungere al PATH.
    echo.
    pause
    exit /b 1
)

:: Installa dipendenze se mancanti
echo Verifica dipendenze Local Signer...
pip show python-pkcs11 >nul 2>&1
if errorlevel 1 (
    echo Installazione dipendenze...
    pip install -r "%~dp0requirements_local_signer.txt"
)

:: Avvia il signer
echo.
echo Avvio manuale HACS Local Signer...
echo.
python "%~dp0local_signer.py" %*

pause
