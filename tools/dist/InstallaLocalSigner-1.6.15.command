#!/bin/bash
# IUSENTRA Local Signer Setup v1.6.15
set -euo pipefail

BASE_URL="https://studio-legale-pct-production.up.railway.app"
ALLOWED_ORIGINS="https://studio-legale-pct-production.up.railway.app"
VERSION="1.6.15"
DIR="$HOME/Library/Application Support/HACS/LocalSigner"
DATA_DIR="$DIR/data"
MOD_DIR="$DIR/local_signer_mod"
VENV="$DIR/.venv"
PY="$VENV/bin/python3"
PLIST="$HOME/Library/LaunchAgents/it.hacs.local-signer.plist"

echo "IUSENTRA Local Signer v$VERSION - Installazione macOS"
echo "Punto ufficiale download: https://studio-legale-pct-production.up.railway.app/impostazioni?tab=firma"

mkdir -p "$DIR" "$DATA_DIR" "$MOD_DIR" "$(dirname "$PLIST")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 non trovato. Installarlo prima da https://python.org"
  read -r -p "Premi Invio per uscire..." _
  exit 1
fi

curl -fsSL "$BASE_URL/polisWeb/local-signer/download" -o "$DIR/local_signer.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-ai-bridge" -o "$DIR/local_ai_host_bridge.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/lex-document-context" -o "$DIR/lex_document_context.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/visible-signature" -o "$DIR/visible_signature.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/uffici" -o "$DATA_DIR/uffici_ministero.json"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/__init__.py" -o "$MOD_DIR/__init__.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/ai_cache.py" -o "$MOD_DIR/ai_cache.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/ai_handlers.py" -o "$MOD_DIR/ai_handlers.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/security.py" -o "$MOD_DIR/security.py"
curl -fsSL "$BASE_URL/polisWeb/local-signer/download/local-signer-mod/server_bootstrap.py" -o "$MOD_DIR/server_bootstrap.py"
python3 -m venv "$VENV"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet python-pkcs11 asn1crypto cryptography zeep pdfplumber mammoth pypdf

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
echo "Tornare su IUSENTRA e cliccare Riverifica."
read -r -p "Premi Invio per chiudere..." _