#!/usr/bin/env bash
# Plain ZIP (no 7z password) — GitHub-safe template pack only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAG="saqr-v6.2.3-bridge"
REPO="hassanayar3-afk/goldenshield-ai"

"$ROOT/scripts/build_saqr_windows_complete.sh"

ZIP="/tmp/Saqr-Windows-Complete-v6.2.3-bridge.zip"
README="/tmp/SAQR-INSTALL-AR.txt"

gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1 || \
  gh release create "$TAG" --repo "$REPO" \
    --title "SAQR v6.2.3-bridge — حزمة Windows (ZIP عادي)" \
    --notes "See SAQR-INSTALL-AR.txt"

gh release upload "$TAG" "$ZIP" "$README" --repo "$REPO" --clobber
echo "DOWNLOAD https://github.com/$REPO/releases/download/$TAG/Saqr-Windows-Complete-v6.2.3-bridge.zip"
