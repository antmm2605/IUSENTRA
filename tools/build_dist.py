#!/usr/bin/env python3
"""
HACS Local Signer — Build cross-platform da Linux/macOS/Windows.

Genera in tools/dist/:
  - SetupLocalSigner-<versione>.ps1        Windows offline (file embedded come base64)
  - InstallaLocalSigner-<versione>.command macOS  online  (download dal server)
  - InstallaLocalSigner-<versione>.run     Linux  online  (download dal server)
  - LocalSigner-<versione>.txt             release note

Uso:
  python3 tools/build_dist.py
  python3 tools/build_dist.py --base-url https://mio-server.example.com

Il PS1 Windows e' un installer offline self-contained: contiene local_signer.py,
requirements_local_signer.txt e uffici_ministero.json come stringhe base64.
Non richiede IExpress ne' connessione internet per l'installazione.
"""

from __future__ import annotations

import argparse
import base64
import re
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

# ── Percorsi ───────────────────────────────────────────────────────────────────
TOOLS_DIR   = Path(__file__).resolve().parent
REPO_DIR    = TOOLS_DIR.parent
DIST_DIR    = TOOLS_DIR / "dist"
LS_PY       = TOOLS_DIR / "local_signer.py"
REQS_TXT    = TOOLS_DIR / "requirements_local_signer.txt"
INSTALL_PS1 = TOOLS_DIR / "installa_local_signer_locale.ps1"
UFFICI_JSON = REPO_DIR / "pct" / "data" / "uffici_ministero.json"

BASE_URL_DEFAULT  = "https://studio-legale-pct-production.up.railway.app"
DOWNLOAD_PAGE     = f"{BASE_URL_DEFAULT}/impostazioni?tab=firma"

# ── Helpers ────────────────────────────────────────────────────────────────────

def _version() -> str:
    src = LS_PY.read_text(encoding="utf-8")
    m = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', src)
    if not m:
        raise ValueError("VERSION non trovata in local_signer.py")
    return m.group(1)


def _b64(path: Path) -> str:
    """Ritorna il contenuto del file come stringa base64 con newline ogni 76 char."""
    raw = path.read_bytes()
    return base64.b64encode(raw).decode("ascii")


def _ps1_escape(text: str) -> str:
    """Escaping minimo per here-string PowerShell (@' ... '@)."""
    # In un here-string @' ... '@ non serve escaping, ma la stringa non può
    # contenere la sequenza di chiusura "'@" a inizio riga.
    return text.replace("\r\n", "\n").replace("\r", "\n")


# ── Generatori ─────────────────────────────────────────────────────────────────

def build_windows_ps1(version: str, base_url: str) -> str:
    """
    Genera un installer Windows PowerShell offline self-contained.
    Tutti i file sorgente sono embedded come base64.
    """
    allowed_origins = ",".join(sorted({
        base_url.rstrip("/"),
        BASE_URL_DEFAULT,
    }))
    ls_b64     = _b64(LS_PY)
    reqs_b64   = _b64(REQS_TXT)
    uffici_b64 = _b64(UFFICI_JSON)
    now        = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    install_body = INSTALL_PS1.read_text(encoding="utf-8")

    # Rimuovi l'intestazione 'param(...)' e gli import perché li iniettamo noi
    # (il corpo dello script locale usa $toolsDir che ridefiniremo)
    # Usiamo l'intero script modificando solo $toolsDir
    install_lines = install_body.splitlines()

    return textwrap.dedent(f"""\
        # HACS Local Signer Setup v{version} — Installer offline Windows
        # Generato il: {now}
        # Punto ufficiale: {DOWNLOAD_PAGE}
        #
        # USO: Tasto destro sul file → "Esegui con PowerShell"
        #   OPPURE: powershell -NoProfile -ExecutionPolicy Bypass -File SetupLocalSigner-{version}.ps1
        #
        # Questo script NON richiede connessione internet.
        # Tutti i file necessari sono embedded nel pacchetto.

        param([switch]$Quiet)
        $ErrorActionPreference = 'Stop'

        $version          = "{version}"
        $defaultAllowedOrigins = "{allowed_origins}"

        # ── Estrazione file embedded ────────────────────────────────────────────
        $tmpDir = Join-Path $env:TEMP "HacsLocalSignerSetup-$version"
        New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

        function Expand-B64File([string]$B64, [string]$Dest) {{
            $bytes = [System.Convert]::FromBase64String($B64 -replace "\\s","")
            [System.IO.File]::WriteAllBytes($Dest, $bytes)
        }}

        Write-Host ""
        Write-Host "HACS Local Signer v$version — Setup" -ForegroundColor Cyan
        Write-Host "Estrazione file embedded in corso..." -ForegroundColor Gray

        $lsB64 = @'
{ls_b64}
'@
        $reqsB64 = @'
{reqs_b64}
'@
        $ufficiB64 = @'
{uffici_b64}
'@

        Expand-B64File $lsB64     (Join-Path $tmpDir "local_signer.py")
        Expand-B64File $reqsB64   (Join-Path $tmpDir "requirements_local_signer.txt")
        Expand-B64File $ufficiB64 (Join-Path $tmpDir "uffici_ministero.json")

        # ── Copio install script nella temp dir e lo eseguo ────────────────────
        $installScript = Join-Path $tmpDir "installa_local_signer_locale.ps1"
        $installBody = @'
        INSTALL_BODY_PLACEHOLDER
'@
        # Scrivi lo script di installazione su disco (encoding UTF-8 senza BOM)
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($installScript, $installBody, $utf8NoBom)

        # Sostituisci $toolsDir con $tmpDir nello script prima di eseguirlo
        $scriptContent = [System.IO.File]::ReadAllText($installScript)
        $scriptContent = $scriptContent -replace [regex]::Escape('$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path'), ('$toolsDir = "' + $tmpDir + '"')
        [System.IO.File]::WriteAllText($installScript, $scriptContent, $utf8NoBom)

        Write-Host "Avvio installazione..." -ForegroundColor Cyan
        & powershell -NoProfile -ExecutionPolicy Bypass -File $installScript $(if ($Quiet) {{ '-Quiet' }})
        $exitCode = $LASTEXITCODE

        # Pulizia temp
        try {{ Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue }} catch {{}}

        exit $exitCode
    """).replace("        INSTALL_BODY_PLACEHOLDER", _ps1_escape(install_body))


def build_macos_command(version: str, base_url: str) -> str:
    allowed_origins = ",".join(sorted({
        base_url.rstrip("/"),
        BASE_URL_DEFAULT,
    }))
    return textwrap.dedent(f"""\
        #!/bin/bash
        # HACS Local Signer v{version} - Installer macOS
        # Punto ufficiale: {DOWNLOAD_PAGE}
        set -euo pipefail

        BASE_URL="{base_url}"
        ALLOWED_ORIGINS="{allowed_origins}"
        VERSION="{version}"
        DIR="$HOME/Library/Application Support/HACS/LocalSigner"
        DATA_DIR="$DIR/data"
        VENV="$DIR/.venv"
        PY="$VENV/bin/python3"
        PLIST="$HOME/Library/LaunchAgents/it.hacs.local-signer.plist"

        echo "HACS Local Signer v$VERSION - Installazione macOS"
        echo "Scarico da: $BASE_URL"

        mkdir -p "$DIR" "$DATA_DIR" "$(dirname "$PLIST")"

        if ! command -v python3 >/dev/null 2>&1; then
          echo "Python 3 non trovato. Scaricarlo da https://python.org"
          read -r -p "Premi Invio per uscire..." _; exit 1
        fi

        curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
        curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
        python3 -m venv "$VENV"
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography

        cat > "$PLIST" <<PLISTEOF
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
          <key>Label</key><string>it.hacs.local-signer</string>
          <key>ProgramArguments</key>
          <array><string>$PY</string><string>$DIR/local_signer.py</string></array>
          <key>EnvironmentVariables</key>
          <dict>
            <key>PCT_LOCAL_SIGNER_ALLOWED_ORIGINS</key><string>$ALLOWED_ORIGINS</string>
          </dict>
          <key>RunAtLoad</key><true/>
          <key>KeepAlive</key><true/>
          <key>WorkingDirectory</key><string>$DIR</string>
        </dict>
        </plist>
        PLISTEOF

        launchctl bootout "gui/$(id -u)" "$PLIST" >/dev/null 2>&1 || true
        launchctl bootstrap "gui/$(id -u)" "$PLIST"
        launchctl kickstart -k "gui/$(id -u)/it.hacs.local-signer"

        echo
        echo "Installazione completata. Local Signer v$VERSION pronto su http://127.0.0.1:27272"
        echo "Tornare su HACS e cliccare Riverifica."
        read -r -p "Premi Invio per chiudere..." _
    """)


def build_linux_run(version: str, base_url: str) -> str:
    allowed_origins = ",".join(sorted({
        base_url.rstrip("/"),
        BASE_URL_DEFAULT,
    }))
    return textwrap.dedent(f"""\
        #!/usr/bin/env bash
        # HACS Local Signer v{version} - Installer Linux
        # Punto ufficiale: {DOWNLOAD_PAGE}
        set -euo pipefail

        BASE_URL="{base_url}"
        ALLOWED_ORIGINS="{allowed_origins}"
        VERSION="{version}"
        DIR="${{XDG_DATA_HOME:-$HOME/.local/share}}/hacs/local-signer"
        DATA_DIR="$DIR/data"
        VENV="$DIR/.venv"
        PY="$VENV/bin/python"
        SERVICE_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/systemd/user"
        SERVICE="$SERVICE_DIR/hacs-local-signer.service"

        echo "HACS Local Signer v$VERSION - Installazione Linux"
        echo "Scarico da: $BASE_URL"

        mkdir -p "$DIR" "$DATA_DIR" "$SERVICE_DIR"

        if ! command -v python3 >/dev/null 2>&1; then
          echo "Python 3 non trovato. Installarlo con il gestore pacchetti della distribuzione."
          read -r -p "Premi Invio per uscire..." _; exit 1
        fi

        curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
        curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
        python3 -m venv "$VENV"
        "$PY" -m pip install --quiet --upgrade pip
        "$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography

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
        echo "Installazione completata. Local Signer v$VERSION pronto su http://127.0.0.1:27272"
        echo "Tornare su HACS e cliccare Riverifica."
        read -r -p "Premi Invio per chiudere..." _
    """)


def build_release_note(version: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"HACS Local Signer\n"
        f"Versione: {version}\n"
        f"Generato: {now}\n"
        f"Piattaforme: Windows (PS1 offline), macOS (.command), Linux (.run)\n"
        f"Punto ufficiale download: {DOWNLOAD_PAGE}\n"
    )


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Build Local Signer dist packages")
    parser.add_argument(
        "--base-url",
        default=BASE_URL_DEFAULT,
        help=f"URL base del server HACS (default: {BASE_URL_DEFAULT})",
    )
    parser.add_argument(
        "--no-windows",
        action="store_true",
        help="Salta la generazione del pacchetto Windows (PS1 offline è grande ~800KB)",
    )
    args = parser.parse_args()

    for path in [LS_PY, REQS_TXT, INSTALL_PS1, UFFICI_JSON]:
        if not path.exists():
            print(f"ERRORE: file sorgente non trovato: {path}", file=sys.stderr)
            sys.exit(1)

    version = _version()
    base_url = args.base_url.rstrip("/")
    DIST_DIR.mkdir(exist_ok=True)

    print(f"Build HACS Local Signer v{version}")
    print(f"  Base URL: {base_url}")
    print(f"  Output:   {DIST_DIR}")
    print()

    # macOS
    mac_path = DIST_DIR / f"InstallaLocalSigner-{version}.command"
    mac_path.write_text(build_macos_command(version, base_url), encoding="utf-8")
    mac_path.chmod(0o755)
    print(f"  [OK] macOS   : {mac_path.name}")

    # Linux
    linux_path = DIST_DIR / f"InstallaLocalSigner-{version}.run"
    linux_path.write_text(build_linux_run(version, base_url), encoding="utf-8")
    linux_path.chmod(0o755)
    print(f"  [OK] Linux   : {linux_path.name}")

    # Windows PS1 offline
    if not args.no_windows:
        win_path = DIST_DIR / f"SetupLocalSigner-{version}.ps1"
        print(f"  Genero Windows PS1 offline (embedding {LS_PY.stat().st_size//1024}KB + {UFFICI_JSON.stat().st_size//1024}KB)...")
        win_path.write_text(build_windows_ps1(version, base_url), encoding="utf-8")
        print(f"  [OK] Windows : {win_path.name}  ({win_path.stat().st_size//1024}KB)")

    # Release note
    note_path = DIST_DIR / f"LocalSigner-{version}.txt"
    note_path.write_text(build_release_note(version), encoding="utf-8")
    print(f"  [OK] Note    : {note_path.name}")

    print()
    print(f"Build completata. {3 if not args.no_windows else 2} pacchetti generati in {DIST_DIR}")


if __name__ == "__main__":
    main()
