#!/usr/bin/env bash
# تثبيت Android command-line SDK (Linux) لبناء APK debug
set -euo pipefail
SDK_ROOT="${ANDROID_SDK_ROOT:-/opt/android-sdk}"
CMDLINE_ZIP="/tmp/android-cmdline-tools.zip"
GRADLE_ZIP="/tmp/gradle-8.7-bin.zip"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [[ ! -d "$SDK_ROOT/cmdline-tools/latest" ]]; then
  sudo mkdir -p "$SDK_ROOT/cmdline-tools"
  curl -fsSL -o "$CMDLINE_ZIP" \
    "https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip"
  rm -rf /tmp/cmdline-unpack
  mkdir -p /tmp/cmdline-unpack
  unzip -q "$CMDLINE_ZIP" -d /tmp/cmdline-unpack
  sudo mv /tmp/cmdline-unpack/cmdline-tools "$SDK_ROOT/cmdline-tools/latest"
fi

export ANDROID_HOME="$SDK_ROOT"
export PATH="$SDK_ROOT/cmdline-tools/latest/bin:$SDK_ROOT/platform-tools:$PATH"

mkdir -p "$SDK_ROOT/licenses"
if [[ ! -f "$SDK_ROOT/licenses/android-sdk-license" ]]; then
  printf '%s\n' "24333f8a63b6825ea9c5514f83c2829b004d1fee" >"$SDK_ROOT/licenses/android-sdk-license"
fi
sdkmanager "platform-tools" "platforms;android-34" "build-tools;34.0.0"

if [[ ! -x "$ROOT/mobile_android/gradlew" ]]; then
  if [[ ! -d /opt/gradle-8.7 ]]; then
    curl -fsSL -o "$GRADLE_ZIP" "https://services.gradle.org/distributions/gradle-8.7-bin.zip"
    sudo unzip -q "$GRADLE_ZIP" -d /opt
  fi
  /opt/gradle-8.7/bin/gradle -p "$ROOT/mobile_android" wrapper --gradle-version 8.7
fi

echo "ANDROID_SDK_OK $SDK_ROOT"
