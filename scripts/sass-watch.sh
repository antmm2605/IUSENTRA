#!/usr/bin/env bash
# ================================================================
#  IUSENTRA — Compilazione / watch SCSS con dart-sass standalone
#  Uso:
#    ./scripts/sass-watch.sh          # watch (ricompila al salvataggio)
#    ./scripts/sass-watch.sh --once   # compila una volta sola
#    ./scripts/sass-watch.sh --prod   # compila una volta, output compresso
# ================================================================

set -euo pipefail

DART_SASS_VERSION="1.83.0"
SCSS_DIR="web/static/scss"
CSS_DIR="web/static/css"
SASS_CACHE="$HOME/.cache/iusentra-dart-sass"
SASS_BIN="$SASS_CACHE/dart-sass/sass"

# ---- Download dart-sass se non presente ----
if [[ ! -x "$SASS_BIN" ]]; then
    echo "→ Scarico dart-sass v${DART_SASS_VERSION}..."
    mkdir -p "$SASS_CACHE"
    PLATFORM="linux-x64"
    if [[ "$(uname)" == "Darwin" ]]; then
        PLATFORM="macos-x64"
        if [[ "$(uname -m)" == "arm64" ]]; then
            PLATFORM="macos-arm64"
        fi
    fi
    curl -fsSL \
        "https://github.com/sass/dart-sass/releases/download/${DART_SASS_VERSION}/dart-sass-${DART_SASS_VERSION}-${PLATFORM}.tar.gz" \
        | tar -xzC "$SASS_CACHE"
    echo "✓ dart-sass installato in $SASS_BIN"
fi

# ---- Argomenti ----
ONCE=false
STYLE="expanded"
for arg in "$@"; do
    case "$arg" in
        --once) ONCE=true ;;
        --prod) ONCE=true; STYLE="compressed" ;;
    esac
done

# ---- Sorgenti → output ----
SASS_PAIRS=(
    "$SCSS_DIR/app.scss:$CSS_DIR/app.css"
    "$SCSS_DIR/auth.scss:$CSS_DIR/auth.css"
    "$SCSS_DIR/design-system.scss:$CSS_DIR/design-system.css"
    "$SCSS_DIR/editor-word.scss:$CSS_DIR/editor-word.css"
    "$SCSS_DIR/mobile.scss:$CSS_DIR/mobile.css"
    "$SCSS_DIR/portal.scss:$CSS_DIR/portal.css"
    "$SCSS_DIR/theme.scss:$CSS_DIR/theme.css"
)

if $ONCE; then
    echo "→ Compilazione SCSS (style=$STYLE)..."
    "$SASS_BIN" --no-source-map --style="$STYLE" "${SASS_PAIRS[@]}"
    echo "✓ CSS aggiornati in $CSS_DIR/"
else
    echo "→ SCSS watch attivo (Ctrl+C per uscire)..."
    "$SASS_BIN" --no-source-map --style=expanded --watch "${SASS_PAIRS[@]}"
fi
