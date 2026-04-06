#!/usr/bin/env python3
"""
HACS Local Signer — Build cross-platform da Linux/macOS/Windows.

Genera in tools/dist/:
  - SetupLocalSigner-<versione>.cmd        Windows offline (CMD auto-estraente, doppio clic)
  - InstallaLocalSigner-<versione>.command macOS  online  (download dal server)
  - InstallaLocalSigner-<versione>.run     Linux  online  (download dal server)
  - LocalSigner-<versione>.txt             release note

Uso:
  python3 tools/build_dist.py
  python3 tools/build_dist.py --base-url https://mio-server.example.com

Il CMD Windows e' un batch auto-estraente offline self-contained:
contiene tutti i file necessari come base64 e li decodifica con certutil.
Non richiede internet, non richiede Execution Policy, funziona con doppio clic.
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
TOOLS_DIR    = Path(__file__).resolve().parent
REPO_DIR     = TOOLS_DIR.parent
DIST_DIR     = TOOLS_DIR / "dist"
LS_PY        = TOOLS_DIR / "local_signer.py"
REQS_TXT     = TOOLS_DIR / "requirements_local_signer.txt"
INSTALL_PS1  = TOOLS_DIR / "installa_local_signer_locale.ps1"
UFFICI_JSON  = REPO_DIR / "pct" / "data" / "uffici_ministero.json"

BASE_URL_DEFAULT  = "https://studio-legale-pct-production.up.railway.app"
DOWNLOAD_PAGE     = f"{BASE_URL_DEFAULT}/impostazioni?tab=firma"

# ── Helpers ────────────────────────────────────────────────────────────────────

def _version() -> str:
    src = LS_PY.read_text(encoding="utf-8")
    m = re.search(r'(?m)^VERSION\s*=\s*"([^"]+)"', src)
    if not m:
        raise ValueError("VERSION non trovata in local_signer.py")
    return m.group(1)


def _b64_lines(data: bytes, line_len: int = 76) -> str:
    """Codifica in base64 con righe di lunghezza fissa (formato certutil)."""
    encoded = base64.b64encode(data).decode("ascii")
    return "\r\n".join(
        encoded[i : i + line_len] for i in range(0, len(encoded), line_len)
    )


# ── Generatori ─────────────────────────────────────────────────────────────────

def build_windows_cmd(version: str) -> str:
    """
    Genera un installer Windows CMD offline self-contained.
    I file sono embedded come base64 e decodificati con certutil -decode.
    Poi lancia il PS1 con -ExecutionPolicy Bypass (aggira il blocco script).
    Funziona con doppio clic, non richiede internet ne' permessi speciali.
    """
    # Converti PS1 in CRLF per Windows
    ps1_crlf = INSTALL_PS1.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")

    files_to_embed = [
        ("installa_local_signer_locale.ps1", ps1_crlf),
        ("local_signer.py",                  LS_PY.read_bytes()),
        ("requirements_local_signer.txt",    REQS_TXT.read_bytes()),
        ("uffici_ministero.json",            UFFICI_JSON.read_bytes()),
    ]

    # Genera i blocchi di estrazione per ogni file
    extract_blocks = []
    for fname, content in files_to_embed:
        b64 = _b64_lines(content)
        safe_name = fname.replace(".", "_").replace("-", "_")
        extract_blocks.append(
            f'echo Estraggo {fname}...\r\n'
            f'(\r\n'
            f'echo -----BEGIN CERTIFICATE-----\r\n'
            f'{b64}\r\n'
            f'echo -----END CERTIFICATE-----\r\n'
            f') > "%TMPDIR%\\{safe_name}.b64"\r\n'
            f'certutil -decode "%TMPDIR%\\{safe_name}.b64" "%TMPDIR%\\{fname}" >nul 2>&1\r\n'
            f'del "%TMPDIR%\\{safe_name}.b64" >nul 2>&1'
        )

    extract_section = "\r\n".join(extract_blocks)

    cmd = (
        '@echo off\r\n'
        'chcp 65001 >nul 2>&1\r\n'
        f'title HACS Local Signer v{version} - Installazione\r\n'
        'echo.\r\n'
        f'echo HACS Local Signer v{version} - Installer Windows offline\r\n'
        'echo.\r\n'
        'echo Estrazione file in corso...\r\n'
        'set "TMPDIR=%TEMP%\\hacs_local_signer_install"\r\n'
        'if exist "%TMPDIR%" rmdir /s /q "%TMPDIR%" >nul 2>&1\r\n'
        'mkdir "%TMPDIR%" >nul 2>&1\r\n'
        '\r\n'
        f'{extract_section}\r\n'
        '\r\n'
        'echo.\r\n'
        'echo Avvio installazione...\r\n'
        'echo.\r\n'
        'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%TMPDIR%\\installa_local_signer_locale.ps1"\r\n'
        'set "EXITCODE=%ERRORLEVEL%"\r\n'
        '\r\n'
        'echo.\r\n'
        'echo Pulizia file temporanei...\r\n'
        'rmdir /s /q "%TMPDIR%" >nul 2>&1\r\n'
        'exit /b %EXITCODE%\r\n'
    )

    return cmd


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
        f"Piattaforme: Windows (CMD offline), macOS (.command), Linux (.run)\n"
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
        help="Salta la generazione del pacchetto Windows (CMD offline)",
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

    # Windows CMD (batch auto-estraente offline)
    if not args.no_windows:
        win_path = DIST_DIR / f"SetupLocalSigner-{version}.cmd"
        print(f"  Genero Windows CMD offline (base64 + certutil, {LS_PY.stat().st_size//1024}KB + {UFFICI_JSON.stat().st_size//1024}KB)...")
        cmd_data = build_windows_cmd(version)
        win_path.write_text(cmd_data, encoding="utf-8", newline="")
        # Aggiorna alias legacy
        alias_path = DIST_DIR / "SetupLocalSigner.cmd"
        alias_path.write_text(cmd_data, encoding="utf-8", newline="")
        print(f"  [OK] Windows : {win_path.name}  ({win_path.stat().st_size//1024}KB)")
        print(f"  [OK] Alias   : SetupLocalSigner.cmd aggiornato")

    # Release note
    note_path = DIST_DIR / f"LocalSigner-{version}.txt"
    note_path.write_text(build_release_note(version), encoding="utf-8")
    print(f"  [OK] Note    : {note_path.name}")

    print()
    print(f"Build completata. {3 if not args.no_windows else 2} pacchetti generati in {DIST_DIR}")


if __name__ == "__main__":
    main()
