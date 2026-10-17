#!/usr/bin/env bash
# Build distributable zips (run from repo root).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${1:-/opt/cursor/artifacts}"
mkdir -p "$OUT"
TS="$(date +%Y%m%d)"

SAQR="$ROOT/saqr"
ZIP_PROJECT="$OUT/saqr-project-${TS}.zip"
ZIP_MOBILE="$OUT/saqr-control-mobile-pwa-${TS}.zip"

(
  cd "$ROOT"
  zip -rq "$ZIP_PROJECT" saqr \
    -x 'saqr/.venv/*' \
    -x 'saqr/logs/*' \
    -x 'saqr/**/__pycache__/*' \
    -x 'saqr/.env' \
    -x 'saqr/**/*.db*'
)

(
  cd "$SAQR"
  zip -rq "$ZIP_MOBILE" \
    terminal_ui/manifest.webmanifest \
    terminal_ui/sw.js \
    terminal_ui/icons \
    mobile_app/INSTALL_AR.md
)

echo "Created:"
echo "  $ZIP_PROJECT"
echo "  $ZIP_MOBILE"
