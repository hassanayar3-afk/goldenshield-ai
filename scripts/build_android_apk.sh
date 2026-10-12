#!/usr/bin/env bash
# بناء GoldenShield-Control.apk (debug) — يتطلب Java 17+ و Android SDK
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ANDROID_DIR="$ROOT/mobile_android"
OUT_APK="$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk"
DEST="$ROOT/downloads/GoldenShield-Control.apk"
ARTIFACT="/opt/cursor/artifacts/GoldenShield-Control.apk"

SDK_ROOT="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-/opt/android-sdk}}"
export ANDROID_HOME="$SDK_ROOT"
export ANDROID_SDK_ROOT="$SDK_ROOT"

if [[ ! -x "$SDK_ROOT/cmdline-tools/latest/bin/sdkmanager" ]] && [[ ! -x "$SDK_ROOT/tools/bin/sdkmanager" ]]; then
  echo "Android SDK not found at $SDK_ROOT — run scripts/install_android_sdk.sh first"
  exit 1
fi

bash "$ROOT/scripts/sync_apk_default_url.sh" 2>/dev/null || true
cd "$ANDROID_DIR"
if [[ ! -f ./gradlew ]]; then
  echo "gradlew missing — run install script or: gradle wrapper"
  exit 1
fi

chmod +x ./gradlew
./gradlew assembleDebug --no-daemon -q

mkdir -p "$ROOT/downloads"
cp -f "$OUT_APK" "$DEST"
mkdir -p /opt/cursor/artifacts
cp -f "$OUT_APK" "$ARTIFACT"
echo "APK_OK $DEST"
sha256sum "$DEST"
