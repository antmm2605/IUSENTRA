#!/usr/bin/env bash
# IUSENTRA Local Signer - builder DMG nativo macOS.
# Richiede hdiutil; la firma/notarizzazione vengono applicate solo quando
# l'ambiente di rilascio fornisce le credenziali Apple previste.
set -euo pipefail

VERSION="${1:?versione mancante}"
COMMAND_SOURCE="${2:?installer .command mancante}"
OUTPUT_DMG="${3:?percorso DMG mancante}"

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Il DMG IUSENTRA puo' essere creato solo su macOS." >&2
  exit 2
fi
if ! command -v hdiutil >/dev/null 2>&1; then
  echo "hdiutil non disponibile: usare una macchina macOS per il rilascio." >&2
  exit 3
fi
if [[ ! -f "$COMMAND_SOURCE" ]]; then
  echo "Installer macOS non trovato: $COMMAND_SOURCE" >&2
  exit 4
fi

BUILD_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/iusentra-local-signer-dmg.XXXXXX")"
cleanup() { rm -rf "$BUILD_ROOT"; }
trap cleanup EXIT

PAYLOAD_DIR="$BUILD_ROOT/IUSENTRA Local Signer"
mkdir -p "$PAYLOAD_DIR"
COMMAND_NAME="$(basename "$COMMAND_SOURCE")"
install -m 0755 "$COMMAND_SOURCE" "$PAYLOAD_DIR/$COMMAND_NAME"
cat > "$PAYLOAD_DIR/LEGGIMI.txt" <<EOF
IUSENTRA Local Signer $VERSION

1. Apri "$COMMAND_NAME" con doppio clic.
2. Se macOS chiede conferma, scegli Apri e completa l'installazione.
3. Torna in IUSENTRA e usa "Riverifica".

Il PIN del dispositivo resta gestito dal provider di firma sul Mac e non viene
salvato da IUSENTRA.
EOF

mkdir -p "$(dirname "$OUTPUT_DMG")"
rm -f "$OUTPUT_DMG"
hdiutil create \
  -volname "IUSENTRA Local Signer" \
  -srcfolder "$PAYLOAD_DIR" \
  -format UDZO \
  -ov \
  "$OUTPUT_DMG" >/dev/null

# I segreti Apple non sono mai scritti nel repository. In un runner di release
# configurato, l'identita' e il profilo di notarizzazione completano il DMG.
if [[ -n "${IUSENTRA_MACOS_CODESIGN_IDENTITY:-}" ]]; then
  codesign --force --sign "$IUSENTRA_MACOS_CODESIGN_IDENTITY" --timestamp "$OUTPUT_DMG"
fi
if [[ -n "${IUSENTRA_MACOS_NOTARY_PROFILE:-}" ]]; then
  xcrun notarytool submit "$OUTPUT_DMG" --keychain-profile "$IUSENTRA_MACOS_NOTARY_PROFILE" --wait
  xcrun stapler staple "$OUTPUT_DMG"
fi

echo "DMG macOS creato: $OUTPUT_DMG"
